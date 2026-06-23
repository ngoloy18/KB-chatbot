"""Authentication and authorization constants."""


USER_ROLE_ADMIN = "admin"
USER_ROLE_USER = "user"
USER_ROLES = [USER_ROLE_ADMIN, USER_ROLE_USER]

TOKEN_TYPE_BEARER = "bearer"
AUTH_SCHEME_BEARER = "Bearer"

JWT_SUBJECT_CLAIM = "sub"
JWT_ROLE_CLAIM = "role"
JWT_EXPIRES_AT_CLAIM = "exp"
JWT_TOKEN_TYPE_CLAIM = "token_type"

JWT_ACCESS_TOKEN_TYPE = "access"
JWT_REFRESH_TOKEN_TYPE = "refresh"
