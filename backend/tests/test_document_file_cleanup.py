import asyncio
from datetime import UTC, datetime
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.constants.auth import USER_ROLE_ADMIN
from app.core.config import DocumentCategory
from app.routes.documents import documents as document_routes
from app.schemas.documents.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
)


def _document_response(name: str, content: str, file_name: str) -> DocumentResponse:
    """Build the committed service response used by direct route checks."""

    return DocumentResponse(
        id=uuid4(),
        name=name,
        category=DocumentCategory.API_STANDARD,
        file_name=file_name,
        file_type="text/markdown",
        content_checksum="a" * 64,
        content=content,
        created_at=datetime.now(UTC),
    )


async def check_create_keeps_persisted_file_on_post_commit_failure() -> None:
    """A failure after create returns must not remove its persisted upload."""

    upload_path = document_routes.UPLOAD_DIR / f"route-create-{uuid4().hex}.md"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_text("# Created", encoding="utf-8")
    payload = DocumentCreate(
        name="Post-commit create",
        category=DocumentCategory.API_STANDARD,
        content="# Created",
        file_name=upload_path.name,
        file_path=upload_path.as_posix(),
        file_type="text/markdown",
    )
    response = _document_response(payload.name, payload.content, upload_path.name)

    original_builder = document_routes.build_document_payload_from_upload
    original_create = document_routes.document_service.create_document
    original_audit = document_routes.audit_service.safe_record

    async def fake_builder(*args: object, **kwargs: object) -> DocumentCreate:
        return payload

    async def fake_create(*args: object, **kwargs: object) -> DocumentResponse:
        return response

    async def fail_audit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected post-commit audit failure")

    document_routes.build_document_payload_from_upload = fake_builder
    document_routes.document_service.create_document = fake_create
    document_routes.audit_service.safe_record = fail_audit
    try:
        try:
            await document_routes.upload_document(
                request=object(),
                file=object(),
                db=object(),
                current_user=SimpleNamespace(id=uuid4(), role=USER_ROLE_ADMIN),
            )
        except RuntimeError as exc:
            if str(exc) != "injected post-commit audit failure":
                raise
        else:
            raise AssertionError("Injected post-commit failure should propagate.")
        if not upload_path.exists():
            raise AssertionError("Committed create upload must not be cleaned up.")
    finally:
        document_routes.build_document_payload_from_upload = original_builder
        document_routes.document_service.create_document = original_create
        document_routes.audit_service.safe_record = original_audit
        upload_path.unlink(missing_ok=True)


async def check_update_keeps_new_file_on_post_commit_failure() -> None:
    """A failure after update returns may remove only the superseded file."""

    suffix = uuid4().hex
    old_path = document_routes.UPLOAD_DIR / f"route-update-{suffix}-old.md"
    new_path = document_routes.UPLOAD_DIR / f"route-update-{suffix}-new.md"
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_text("# Old", encoding="utf-8")
    new_path.write_text("# New", encoding="utf-8")
    create_payload = DocumentCreate(
        name="Post-commit update",
        category=DocumentCategory.API_STANDARD,
        content="# New",
        file_name=new_path.name,
        file_path=new_path.as_posix(),
        file_type="text/markdown",
    )
    response = _document_response(
        create_payload.name,
        create_payload.content,
        new_path.name,
    )

    original_builder = document_routes.build_document_payload_from_upload
    original_get_path = (
        document_routes.document_service.get_document_file_path_for_replacement
    )
    original_update = document_routes.document_service.update_document
    original_audit = document_routes.audit_service.safe_record

    async def fake_builder(*args: object, **kwargs: object) -> DocumentCreate:
        return create_payload

    async def fake_get_path(*args: object, **kwargs: object) -> str:
        return old_path.as_posix()

    async def fake_update(*args: object, **kwargs: object) -> DocumentResponse:
        if not isinstance(kwargs.get("payload"), DocumentUpdate):
            raise AssertionError("Update route should build a DocumentUpdate payload.")
        return response

    async def fail_audit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected post-commit audit failure")

    document_routes.build_document_payload_from_upload = fake_builder
    document_routes.document_service.get_document_file_path_for_replacement = (
        fake_get_path
    )
    document_routes.document_service.update_document = fake_update
    document_routes.audit_service.safe_record = fail_audit
    try:
        try:
            await document_routes.update_document(
                document_id=uuid4(),
                request=object(),
                file=object(),
                db=object(),
                current_user=SimpleNamespace(id=uuid4(), role=USER_ROLE_ADMIN),
            )
        except RuntimeError as exc:
            if str(exc) != "injected post-commit audit failure":
                raise
        else:
            raise AssertionError("Injected post-commit failure should propagate.")
        if not new_path.exists():
            raise AssertionError("Committed replacement upload must not be cleaned up.")
        if old_path.exists():
            raise AssertionError("Committed replacement should clean up the old upload.")
    finally:
        document_routes.build_document_payload_from_upload = original_builder
        document_routes.document_service.get_document_file_path_for_replacement = (
            original_get_path
        )
        document_routes.document_service.update_document = original_update
        document_routes.audit_service.safe_record = original_audit
        old_path.unlink(missing_ok=True)
        new_path.unlink(missing_ok=True)


def check_cleanup_is_non_throwing() -> None:
    """Invalid paths and logging errors must not escape best-effort cleanup."""

    original_log_exception = document_routes.logger.exception

    def fail_logging(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected logging failure")

    document_routes.logger.exception = fail_logging
    try:
        document_routes.cleanup_saved_upload("\0")
    finally:
        document_routes.logger.exception = original_log_exception


async def main() -> None:
    """Run upload cleanup consistency checks."""

    check_cleanup_is_non_throwing()
    await check_create_keeps_persisted_file_on_post_commit_failure()
    await check_update_keeps_new_file_on_post_commit_failure()
    print("Document file cleanup OK.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print("Document file cleanup test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
