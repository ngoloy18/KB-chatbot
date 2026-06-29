import asyncio
import json
import mimetypes
import sys
from pathlib import Path
from uuid import uuid4
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import delete, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import AsyncSessionLocal
from app.models.database import Document


BASE_URL = "http://127.0.0.1:8000"
UPLOAD_ROOT = PROJECT_ROOT / "uploads"


def load_env() -> dict[str, str]:
    """Read local .env values without printing secrets."""

    env_path = PROJECT_ROOT / ".env"
    values: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def api_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    json_body: dict | None = None,
    multipart: dict[str, object] | None = None,
    expected_status: set[int] | None = None,
) -> object | None:
    """Call the live FastAPI server and validate the response status."""

    expected_status = expected_status or {200}
    headers = {}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(json_body).encode("utf-8")
    if multipart is not None:
        body, content_type = encode_multipart(multipart)
        headers["Content-Type"] = content_type

    request = Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            status = response.status
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        status = exc.code
        response_body = exc.read().decode("utf-8")

    if status not in expected_status:
        raise AssertionError(
            f"{method} {path} returned {status}, expected {sorted(expected_status)}. "
            f"Body: {response_body[:300]}"
        )
    if not response_body:
        return None
    return json.loads(response_body)


def encode_multipart(fields: dict[str, object]) -> tuple[bytes, str]:
    """Build multipart/form-data without third-party dependencies."""

    boundary = f"----kb-chatbot-{uuid4().hex}"
    lines: list[bytes] = []
    for name, value in fields.items():
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        if isinstance(value, tuple):
            filename, file_bytes, content_type = value
            content_type = (
                content_type
                or mimetypes.guess_type(filename)[0]
                or "application/octet-stream"
            )
            lines.append(
                (
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{filename}"\r\n'
                    f"Content-Type: {content_type}\r\n\r\n"
                ).encode("utf-8")
            )
            lines.append(file_bytes)
            lines.append(b"\r\n")
        else:
            lines.append(
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode(
                    "utf-8"
                )
            )
    lines.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(lines), f"multipart/form-data; boundary={boundary}"


def login(email: str, password: str) -> str:
    """Return an access token for an existing verified user."""

    response = api_request(
        "POST",
        "/api/auth/login",
        json_body={"email": email, "password": password},
    )
    return response["access_token"]


def assert_no_public_file_path(payload: dict) -> None:
    """Document endpoint responses must not expose local server storage paths."""

    if "file_path" in payload:
        raise AssertionError("Public document responses must not expose file_path.")


async def cleanup_documents(name_prefix: str) -> None:
    """Hard-delete lifecycle API test documents and their uploaded files."""

    async with AsyncSessionLocal() as db:
        rows = await db.scalars(
            select(Document).where(Document.title.ilike(f"{name_prefix}%"))
        )
        documents = list(rows.all())
        file_paths = [document.file_path for document in documents if document.file_path]
        await db.execute(delete(Document).where(Document.title.ilike(f"{name_prefix}%")))
        await db.commit()

    upload_root = UPLOAD_ROOT.resolve()
    for file_path in file_paths:
        saved_path = Path(file_path)
        resolved_path = saved_path.resolve()
        if resolved_path.is_relative_to(upload_root) and resolved_path.exists():
            resolved_path.unlink()


async def cleanup_document_prefixes(name_prefixes: list[str]) -> None:
    """Hard-delete generated test documents for several title prefixes."""

    for name_prefix in name_prefixes:
        await cleanup_documents(name_prefix)


def run_document_lifecycle_api_test() -> None:
    """Exercise lifecycle document endpoints against the live server."""

    env = load_env()
    suffix = uuid4().hex[:8]
    document_name = f"lifecycle-http-{suffix}"
    original_content = f"# Lifecycle API {suffix}\n\nOriginal content {suffix}."
    updated_content = f"# Lifecycle API {suffix}\n\nUpdated content {suffix}."
    admin_token = login(env["INITIAL_ADMIN_EMAIL"], env["INITIAL_ADMIN_PASSWORD"])
    document_id = None

    try:
        uploaded = api_request(
            "POST",
            "/api/documents/upload",
            token=admin_token,
            multipart={
                "name": document_name,
                "category": "api-standard",
                "file": (
                    f"{document_name}.md",
                    original_content.encode("utf-8"),
                    "text/markdown",
                ),
            },
            expected_status={201},
        )
        document_id = uploaded["id"]
        original_checksum = uploaded["content_checksum"]
        assert_no_public_file_path(uploaded)
        if not original_checksum or len(original_checksum) != 64:
            raise AssertionError("Upload should return a SHA-256 checksum.")

        api_request(
            "POST",
            "/api/documents/upload",
            token=admin_token,
            multipart={
                "name": f"{document_name}-duplicate",
                "category": "api-standard",
                "file": (
                    f"{document_name}-duplicate.md",
                    original_content.encode("utf-8"),
                    "text/markdown",
                ),
            },
            expected_status={409},
        )

        versions = api_request(
            "GET",
            f"/api/documents/{document_id}/versions",
            token=admin_token,
        )
        if versions["total"] != 1:
            raise AssertionError("Upload should create version 1.")
        assert_no_public_file_path(versions["items"][0])

        updated = api_request(
            "PUT",
            f"/api/documents/{document_id}",
            token=admin_token,
            multipart={
                "name": document_name,
                "category": "database",
                "file": (
                    f"{document_name}-updated.md",
                    updated_content.encode("utf-8"),
                    "text/markdown",
                ),
            },
        )
        if updated["content_checksum"] == original_checksum:
            raise AssertionError("Update should change the checksum.")
        assert_no_public_file_path(updated)

        versions = api_request(
            "GET",
            f"/api/documents/{document_id}/versions",
            token=admin_token,
        )
        if versions["total"] != 2:
            raise AssertionError("Update should append a second version.")

        api_request(
            "DELETE",
            f"/api/documents/{document_id}",
            token=admin_token,
            expected_status={204},
        )
        api_request(
            "GET",
            f"/api/documents/{document_id}",
            token=admin_token,
            expected_status={404},
        )
        listed = api_request(
            "GET",
            "/api/documents?" + urlencode({"name": document_name}),
            token=admin_token,
        )
        if listed["total"] != 0:
            raise AssertionError("Soft-deleted documents should be hidden from lists.")

        restored = api_request(
            "PATCH",
            f"/api/documents/{document_id}/restore",
            token=admin_token,
        )
        if restored["is_deleted"] or restored["deleted_at"] is not None:
            raise AssertionError("Restore should clear soft-delete fields.")
        assert_no_public_file_path(restored)
    finally:
        asyncio.run(cleanup_documents(document_name))

    print("Live document lifecycle API test OK.")


if __name__ == "__main__":
    try:
        run_document_lifecycle_api_test()
    except Exception as exc:
        print("Live document lifecycle API test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
