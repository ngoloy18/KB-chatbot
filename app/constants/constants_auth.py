"""Authentication and authorization constants."""


USER_ROLE_ADMIN = "admin"
USER_ROLE_USER = "user"
USER_ROLES = [USER_ROLE_ADMIN, USER_ROLE_USER]

TOKEN_TYPE_BEARER = "bearer"
AUTH_SCHEME_BEARER = "Bearer"

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_REQUIREMENTS_DESCRIPTION = (
    "Password must be 8-128 characters and include uppercase, lowercase, "
    "number, and special character."
)

JWT_SUBJECT_CLAIM = "sub"
JWT_ROLE_CLAIM = "role"
JWT_EXPIRES_AT_CLAIM = "exp"
JWT_TOKEN_TYPE_CLAIM = "token_type"
JWT_ID_CLAIM = "jti"

JWT_ACCESS_TOKEN_TYPE = "access"
JWT_REFRESH_TOKEN_TYPE = "refresh"
