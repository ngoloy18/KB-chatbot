from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Question submitted to the long-context Q&A endpoint."""

    question: str = Field(..., min_length=1, max_length=1000)


class AskResponse(BaseModel):
    """Answer returned by the configured AI provider."""

    answer: str
    sources: list[str]
    model_used: str
