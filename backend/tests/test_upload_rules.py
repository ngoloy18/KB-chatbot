import json
import sys
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


BASE_URL = "http://127.0.0.1:8000"


def build_text_pdf(text: str) -> bytes:
    """Build a small PDF fixture with a real extractable text layer."""

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


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
    other_user_email = f"upload_other_{suffix}@example.com"
    password = "Password123!"
    created_user_ids: list[str] = []
    created_documents: list[tuple[str, str]] = []
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
        created_user_ids.append(registered_user["user"]["id"])
        api_request(
            "POST",
            "/api/auth/verify-email",
            json_body={"token": registered_user["verification_token"]},
        )
        user_token = login(user_email, password)

        registered_other_user = api_request(
            "POST",
            "/api/auth/register",
            json_body={
                "email": other_user_email,
                "password": password,
                "full_name": "Other Upload Rule User",
            },
            expected_status={201},
        )
        created_user_ids.append(registered_other_user["user"]["id"])
        api_request(
            "POST",
            "/api/auth/verify-email",
            json_body={"token": registered_other_user["verification_token"]},
        )
        other_user_token = login(other_user_email, password)

        user_document_name = f"Normal User Upload {suffix}"
        unique_phrase = f"normal-upload-private-{suffix}"
        uploaded_by_user = api_request(
            "POST",
            "/api/documents/upload",
            token=user_token,
            multipart={
                "name": user_document_name,
                "category": "api-standard",
                "file": (
                    "normal-user.md",
                    f"# User upload\n\nPrivate marker {unique_phrase}.".encode("utf-8"),
                    "text/markdown",
                ),
            },
            expected_status={201},
        )
        created_documents.append((uploaded_by_user["id"], user_token))

        api_request(
            "GET",
            f"/api/documents/{uploaded_by_user['id']}",
            token=user_token,
        )
        api_request(
            "GET",
            f"/api/documents/{uploaded_by_user['id']}",
            token=admin_token,
        )
        api_request(
            "GET",
            f"/api/documents/{uploaded_by_user['id']}",
            token=other_user_token,
            expected_status={403},
        )
        other_user_list = api_request(
            "GET",
            "/api/documents?" + urlencode({"name": user_document_name}),
            token=other_user_token,
        )
        if other_user_list["total"] != 0:
            raise AssertionError("Other users should not list private uploads.")
        other_user_search = api_request(
            "GET",
            "/api/documents/search?" + urlencode({"q": unique_phrase}),
            token=other_user_token,
        )
        if other_user_search["total"] != 0:
            raise AssertionError("Other users should not search private upload chunks.")

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
        created_documents.append((uploaded["id"], admin_token))
        if "Valid markdown upload" not in uploaded["content"]:
            raise AssertionError("Markdown upload should store extracted content.")

        text_upload = api_request(
            "POST",
            "/api/documents/upload",
            token=admin_token,
            multipart={
                "name": f"Text Upload {suffix}",
                "category": "logging",
                "file": (
                    "logging.txt",
                    b"Log failures with useful context.",
                    "text/plain",
                ),
            },
            expected_status={201},
        )
        created_documents.append((text_upload["id"], admin_token))
        if text_upload["content"] != "Log failures with useful context.":
            raise AssertionError("TXT upload should store extracted content.")

        pdf_marker = f"PDF extraction marker {suffix}"
        pdf_upload = api_request(
            "POST",
            "/api/documents/upload",
            token=admin_token,
            multipart={
                "name": f"PDF Upload {suffix}",
                "category": "database",
                "file": (
                    "database.pdf",
                    build_text_pdf(pdf_marker),
                    "application/pdf",
                ),
            },
            expected_status={201},
        )
        created_documents.append((pdf_upload["id"], admin_token))
        if pdf_marker not in pdf_upload["content"]:
            raise AssertionError("PDF upload should store extracted content.")

        api_request(
            "POST",
            "/api/documents/upload",
            token=admin_token,
            multipart={
                "name": f"Wrong Extension {suffix}",
                "category": "api-standard",
                "file": (
                    "unsupported.docx",
                    b"not supported",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
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
        for document_id, owner_token in created_documents:
            api_request(
                "DELETE",
                f"/api/documents/{document_id}",
                token=owner_token,
                expected_status={204, 404},
            )
        for user_id in created_user_ids:
            api_request(
                "DELETE",
                f"/api/users/{user_id}",
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
