import json
import mimetypes
import sys
from pathlib import Path
from uuid import uuid4
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


BASE_URL = "http://127.0.0.1:8000"


def load_env() -> dict[str, str]:
    """Read .env without printing secrets."""

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
) -> tuple[int, object | None]:
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
        with urlopen(request, timeout=20) as response:
            status = response.status
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        status = exc.code
        response_body = exc.read().decode("utf-8")

    parsed_body = None
    if response_body:
        try:
            parsed_body = json.loads(response_body)
        except json.JSONDecodeError:
            parsed_body = response_body
    if status not in expected_status:
        raise AssertionError(
            f"{method} {path} returned {status}, expected {sorted(expected_status)}. "
            f"Body: {response_body[:300]}"
        )
    return status, parsed_body


def encode_multipart(fields: dict[str, object]) -> tuple[bytes, str]:
    """Build a multipart/form-data body without third-party dependencies."""

    boundary = f"----kb-chatbot-{uuid4().hex}"
    lines: list[bytes] = []
    for name, value in fields.items():
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        if isinstance(value, tuple):
            filename, file_bytes, content_type = value
            content_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
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


def run_api_smoke_test() -> None:
    """Exercise every current Swagger operation against the live server."""

    env = load_env()
    suffix = uuid4().hex[:8]
    normal_email = f"swagger_normal_{suffix}@example.com"
    soft_delete_email = f"swagger_soft_delete_{suffix}@example.com"
    password = "Password123!"
    new_password = "NewPassword123!"
    created_users: list[str] = []
    created_documents: list[str] = []
    admin_token = ""

    try:
        api_request("GET", "/api/health")
        api_request("GET", "/openapi.json")

        _, admin_login = api_request(
            "POST",
            "/api/auth/login",
            json_body={
                "email": env["INITIAL_ADMIN_EMAIL"],
                "password": env["INITIAL_ADMIN_PASSWORD"],
            },
        )
        admin_token = admin_login["access_token"]

        _, registered = api_request(
            "POST",
            "/api/auth/register",
            json_body={
                "email": normal_email,
                "password": password,
                "full_name": "Swagger Normal User",
            },
            expected_status={201},
        )
        normal_user_id = registered["user"]["id"]
        created_users.append(normal_user_id)

        _, resent = api_request(
            "POST",
            "/api/auth/resend-verification",
            json_body={"email": normal_email},
        )
        api_request(
            "POST",
            "/api/auth/verify-email",
            json_body={"token": resent["verification_token"]},
        )
        _, normal_login = api_request(
            "POST",
            "/api/auth/login",
            json_body={"email": normal_email, "password": password},
        )
        normal_token = normal_login["access_token"]
        refresh_token = normal_login["refresh_token"]

        api_request("GET", "/api/auth/me", token=normal_token)
        _, refreshed = api_request(
            "POST",
            "/api/auth/refresh",
            json_body={"refresh_token": refresh_token},
        )
        refresh_token = refreshed["refresh_token"]

        _, reset_response = api_request(
            "POST",
            "/api/auth/forgot-password",
            json_body={"email": normal_email},
        )
        api_request(
            "POST",
            "/api/auth/reset-password",
            json_body={
                "token": reset_response["reset_token"],
                "new_password": new_password,
            },
        )
        _, relogin = api_request(
            "POST",
            "/api/auth/login",
            json_body={"email": normal_email, "password": new_password},
        )
        normal_token = relogin["access_token"]
        refresh_token = relogin["refresh_token"]
        api_request(
            "POST",
            "/api/auth/logout",
            json_body={"refresh_token": refresh_token},
        )

        api_request("GET", "/api/users", token=admin_token)
        api_request("GET", f"/api/users/{normal_user_id}", token=admin_token)
        api_request(
            "PATCH",
            f"/api/users/{normal_user_id}",
            token=admin_token,
            json_body={"full_name": "Swagger Updated User"},
        )

        _, second_user = api_request(
            "POST",
            "/api/auth/register",
            json_body={
                "email": soft_delete_email,
                "password": password,
                "full_name": "Swagger Soft Delete User",
            },
            expected_status={201},
        )
        second_user_id = second_user["user"]["id"]
        created_users.append(second_user_id)
        api_request(
            "PATCH",
            f"/api/users/{second_user_id}/soft-delete",
            token=admin_token,
        )

        _, uploaded = api_request(
            "POST",
            "/api/documents/upload",
            token=admin_token,
            multipart={
                "name": f"Swagger Doc {suffix}",
                "category": "api-standard",
                "file": (
                    f"swagger-{suffix}.md",
                    (
                        "# Swagger Test\n\n"
                        "This document validates upload, chunking, permissions, "
                        "update, and delete."
                    ).encode("utf-8"),
                    "text/markdown",
                ),
            },
            expected_status={201},
        )
        document_id = uploaded["id"]
        created_documents.append(document_id)

        api_request("GET", "/api/documents?page=1&page_size=10", token=admin_token)
        api_request(
            "GET",
            "/api/documents/search?" + urlencode({"q": "validates"}),
            token=admin_token,
        )
        api_request("GET", f"/api/documents/{document_id}", token=admin_token)
        api_request(
            "GET",
            f"/api/documents/{document_id}/permissions",
            token=admin_token,
        )
        api_request(
            "PUT",
            f"/api/documents/{document_id}/permissions",
            token=admin_token,
            json_body={"user_id": normal_user_id, "permission": "read"},
        )
        api_request("GET", "/api/documents?page=1&page_size=10", token=normal_token)
        api_request(
            "GET",
            "/api/documents/search?" + urlencode({"q": "validates"}),
            token=normal_token,
        )
        api_request("GET", f"/api/documents/{document_id}", token=normal_token)
        api_request(
            "DELETE",
            f"/api/documents/{document_id}/permissions/{normal_user_id}",
            token=admin_token,
            expected_status={204},
        )
        api_request(
            "PUT",
            f"/api/documents/{document_id}",
            token=admin_token,
            multipart={
                "name": f"Swagger Doc Updated {suffix}",
                "category": "database",
                "file": (
                    f"swagger-updated-{suffix}.md",
                    "# Updated Swagger Test\n\nUpdated content for chunk replacement.".encode(
                        "utf-8"
                    ),
                    "text/markdown",
                ),
            },
        )
        api_request(
            "DELETE",
            f"/api/documents/{document_id}",
            token=admin_token,
            expected_status={204},
        )
        created_documents.remove(document_id)

        api_request(
            "DELETE",
            f"/api/users/{second_user_id}",
            token=admin_token,
            expected_status={204},
        )
        created_users.remove(second_user_id)
    finally:
        for document_id in list(created_documents):
            if admin_token:
                try:
                    api_request(
                        "DELETE",
                        f"/api/documents/{document_id}",
                        token=admin_token,
                        expected_status={204, 404},
                    )
                except Exception:
                    pass
        for user_id in list(created_users):
            if admin_token:
                try:
                    api_request(
                        "DELETE",
                        f"/api/users/{user_id}",
                        token=admin_token,
                        expected_status={204, 404},
                    )
                except Exception:
                    pass

    print("Live Swagger/API smoke test OK.")


if __name__ == "__main__":
    try:
        run_api_smoke_test()
    except Exception as exc:
        print("Live Swagger/API smoke test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
