from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def register_exception_handlers(app: FastAPI) -> None:
    """Register consistent JSON error responses for API failures."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        # Keep FastAPI-raised errors in the same response shape as custom errors.
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": exc.detail}},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # Validation details help the client see exactly which field was wrong.
        return JSONResponse(
            status_code=422,
            content={"error": {"message": "Validation failed.", "details": exc.errors()}},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        # Do not leak internal exception text to API users.
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "Internal server error."}},
        )
