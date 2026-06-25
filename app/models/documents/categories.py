from uuid import UUID, uuid4

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.constants.constants_database import SCHEMA_NAME
from app.models.common.mixins import TimestampMixin


class DocumentCategoryModel(TimestampMixin, Base):
    """One of the six knowledge-base categories that documents can belong to."""

    __tablename__ = "document_categories"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    # This stores values such as "database" or "coding-convention".
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    documents: Mapped[list["Document"]] = relationship(back_populates="category")
