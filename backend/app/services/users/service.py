from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.auth import USER_ROLE_ADMIN
from app.core.security import hash_password
from app.repositories.auth.email_verification_tokens import (
    email_verification_token_repository,
)
from app.repositories.auth.password_reset_tokens import password_reset_token_repository
from app.repositories.auth.refresh_tokens import refresh_token_repository
from app.repositories.users.users import user_repository
from app.schemas.users.schemas import (
    UserAdminResponse,
    UserListResponse,
    UserUpdateRequest,
)
from app.services.auth.exceptions import DuplicateEmailError
from app.services.users.exceptions import (
    CannotDeleteSelfError,
    CannotRemoveLastAdminError,
    UserNotFoundError,
)


class UserService:
    """Business logic for admin user management."""

    async def list_users(
        self,
        db: AsyncSession,
        page: int,
        page_size: int,
    ) -> UserListResponse:
        """Return a paginated list of users for admins."""

        users, total = await user_repository.list_users(db, page, page_size)
        return UserListResponse(
            items=[UserAdminResponse.model_validate(user) for user in users],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_user(self, db: AsyncSession, user_id: UUID) -> UserAdminResponse:
        """Return one user or raise not-found."""

        user = await user_repository.get_by_id(db, user_id)
        if user is None:
            raise UserNotFoundError("User not found.")
        return UserAdminResponse.model_validate(user)

    async def update_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        payload: UserUpdateRequest,
    ) -> UserAdminResponse:
        """Update editable user information as admin."""

        user = await user_repository.get_by_id(db, user_id)
        if user is None:
            raise UserNotFoundError("User not found.")

        if (
            user.role == USER_ROLE_ADMIN
            and (
                (payload.role is not None and payload.role != USER_ROLE_ADMIN)
                or payload.is_active is False
            )
        ):
            await self._raise_if_last_active_admin(db, user.id)

        if payload.email is not None and payload.email != user.email:
            # Email is a unique login identifier, so updates must also reject duplicates.
            existing_user = await user_repository.get_by_email(db, payload.email)
            if existing_user is not None:
                raise DuplicateEmailError("A user with this email already exists.")
            user.email = payload.email
            # Changing email means the new address should be verified again.
            user.is_email_verified = False
            await email_verification_token_repository.revoke_active_for_user(db, user.id)

        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.role is not None:
            # Role is validated by the request schema before it reaches the service.
            user.role = payload.role
        if payload.is_active is not None:
            user.is_active = payload.is_active
            if not payload.is_active:
                # Disabled users should lose active sessions immediately.
                await refresh_token_repository.revoke_all_for_user(db, user.id)
        if payload.is_email_verified is not None:
            user.is_email_verified = payload.is_email_verified
            if payload.is_email_verified:
                await email_verification_token_repository.revoke_active_for_user(
                    db,
                    user.id,
                )
        if payload.password is not None:
            user.hashed_password = hash_password(payload.password)
            await refresh_token_repository.revoke_all_for_user(db, user.id)

        await db.commit()
        await db.refresh(user)
        return UserAdminResponse.model_validate(user)

    async def delete_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        current_admin_id: UUID,
    ) -> None:
        """Delete one user, but do not allow admins to delete themselves."""

        if user_id == current_admin_id:
            raise CannotDeleteSelfError("Admins cannot delete their own account.")

        user = await user_repository.get_by_id(db, user_id)
        if user is None:
            raise UserNotFoundError("User not found.")
        if user.role == USER_ROLE_ADMIN and user.is_active:
            await self._raise_if_last_active_admin(db, user.id)
        await user_repository.delete_user(db, user)

    async def soft_delete_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        current_admin_id: UUID,
    ) -> UserAdminResponse:
        """Deactivate a user while keeping the row for history and auditing."""

        if user_id == current_admin_id:
            raise CannotDeleteSelfError("Admins cannot soft-delete their own account.")

        user = await user_repository.get_by_id(db, user_id)
        if user is None:
            raise UserNotFoundError("User not found.")
        if user.role == USER_ROLE_ADMIN and user.is_active:
            await self._raise_if_last_active_admin(db, user.id)

        # Soft delete means the account remains in the database but cannot login.
        user.is_active = False
        await refresh_token_repository.revoke_all_for_user(db, user.id)
        await email_verification_token_repository.revoke_active_for_user(db, user.id)
        await password_reset_token_repository.revoke_active_for_user(db, user.id)
        await db.commit()
        await db.refresh(user)
        return UserAdminResponse.model_validate(user)

    async def _raise_if_last_active_admin(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> None:
        """Block actions that would leave the system with no active admins."""

        remaining_admins = await user_repository.count_active_admins(
            db,
            exclude_user_id=user_id,
        )
        if remaining_admins == 0:
            raise CannotRemoveLastAdminError(
                "Cannot remove the final active admin account."
            )

    async def restore_user(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> UserAdminResponse:
        """Reactivate a soft-deleted user account."""

        user = await user_repository.get_by_id(db, user_id)
        if user is None:
            raise UserNotFoundError("User not found.")

        # Restore only reverses the soft-delete flag; email verification stays unchanged.
        user.is_active = True
        await db.commit()
        await db.refresh(user)
        return UserAdminResponse.model_validate(user)


user_service = UserService()
