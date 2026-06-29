import json
import sys
from pathlib import Path
from uuid import uuid4
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


BASE_URL = "http://127.0.0.1:8000"


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
    """Call the running API server and assert the expected HTTP status."""

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
    """Build a multipart/form-data body using only Python standard library."""

    boundary = f"----kb-chatbot-{uuid4().hex}"
    lines: list[bytes] = []
    for name, value in fields.items():
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        if isinstance(value, tuple):
            filename, file_bytes, content_type = value
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


def run_upload_rule_test() -> None:
    """Verify Week 3 upload access and validation rules."""

    env = load_env()
    suffix = uuid4().hex[:8]
    user_email = f"upload_user_{suffix}@example.com"
    password = "Password123!"
    created_user_id = None
    created_document_ids: list[str] = []
    admin_token = login(env["INITIAL_ADMIN_EMAIL"], env["INITIAL_ADMIN_PASSWORD"])

    try:
        registered_user = api_request(
            "POST",
            "/api/auth/register",
            json_body={
                "email": user_email,
                "password": password,
                "full_name": "Upload Rule User",
            },
            expected_status={201},
        )
        created_user_id = registered_user["user"]["id"]
        api_request(
            "POST",
            "/api/auth/verify-email",
            json_body={"token": registered_user["verification_token"]},
        )
        user_token = login(user_email, password)

        api_request(
            "POST",
            "/api/documents/upload",
            token=user_token,
            multipart={
                "name": f"Normal User Upload {suffix}",
                "category": "api-standard",
                "file": ("normal-user.md", b"# Should fail", "text/markdown"),
            },
            expected_status={403},
        )

        uploaded = api_request(
            "POST",
            "/api/documents/upload",
            token=admin_token,
            multipart={
                "name": f"Admin Upload {suffix}",
                "category": "api-standard",
                "file": ("admin-upload.md", b"# Valid markdown upload", "text/markdown"),
            },
            expected_status={201},
        )
        created_document_ids.append(uploaded["id"])

        api_request(
            "POST",
            "/api/documents/upload",
            token=admin_token,
            multipart={
                "name": f"Wrong Extension {suffix}",
                "category": "api-standard",
                "file": ("not-markdown.txt", b"not markdown", "text/plain"),
            },
            expected_status={400},
        )

        oversized_file = b"x" * (10 * 1024 * 1024 + 1)
        api_request(
            "POST",
            "/api/documents/upload",
            token=admin_token,
            multipart={
                "name": f"Too Large {suffix}",
                "category": "api-standard",
                "file": ("too-large.md", oversized_file, "text/markdown"),
            },
            expected_status={413},
        )
    finally:
        for document_id in created_document_ids:
            api_request(
                "DELETE",
                f"/api/documents/{document_id}",
                token=admin_token,
                expected_status={204, 404},
            )
        if created_user_id is not None:
            api_request(
                "DELETE",
                f"/api/users/{created_user_id}",
                token=admin_token,
                expected_status={204, 404},
            )

    print("Upload rules OK.")


if __name__ == "__main__":
    try:
        run_upload_rule_test()
    except Exception as exc:
        print("Upload rules test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
