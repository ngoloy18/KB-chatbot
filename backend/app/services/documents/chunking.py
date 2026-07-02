from dataclasses import dataclass
import re

from app.constants.documents import (
    DEFAULT_CHUNK_MAX_CHARACTERS,
    DEFAULT_CHUNK_OVERLAP_CHARACTERS,
)


MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class TextChunk:
    """Small text piece ready to save into kb.document_chunks."""

    chunk_index: int
    content: str
    token_count: int


class DocumentChunkingService:
    """Split document text into chunks for search and future AI retrieval."""

    def split_text(
        self,
        content: str,
        max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
        overlap_characters: int = DEFAULT_CHUNK_OVERLAP_CHARACTERS,
    ) -> list[TextChunk]:
        """Return ordered chunks while preserving paragraph boundaries when possible."""

        cleaned_content = content.strip()
        if not cleaned_content:
            return []

        chunks: list[str] = []
        current_parts: list[str] = []
        current_length = 0

        paragraphs = self._attach_markdown_heading_context(
            self._split_paragraphs(cleaned_content)
        )

        for paragraph in paragraphs:
            if len(paragraph) > max_characters:
                self._flush_current_chunk(chunks, current_parts)
                current_parts = []
                current_length = 0
                chunks.extend(
                    self._split_long_text(
                        paragraph,
                        max_characters,
                        overlap_characters,
                    )
                )
                continue

            separator_length = 2 if current_parts else 0
            next_length = current_length + separator_length + len(paragraph)
            if current_parts and next_length > max_characters:
                previous_chunk = "\n\n".join(current_parts).strip()
                chunks.append(previous_chunk)

                allowed_overlap = max(max_characters - len(paragraph) - 2, 0)
                overlap_text = self._get_overlap_text(
                    previous_chunk,
                    min(overlap_characters, allowed_overlap),
                )
                current_parts = [overlap_text, paragraph] if overlap_text else [paragraph]
                current_length = len("\n\n".join(current_parts))
            else:
                current_parts.append(paragraph)
                current_length = next_length

        self._flush_current_chunk(chunks, current_parts)
        return [
            TextChunk(
                chunk_index=index,
                content=chunk,
                token_count=self._estimate_token_count(chunk),
            )
            for index, chunk in enumerate(chunks)
            if chunk
        ]

    @staticmethod
    def _split_paragraphs(content: str) -> list[str]:
        """Normalize blank-line separated paragraphs."""

        return [
            paragraph.strip()
            for paragraph in content.split("\n\n")
            if paragraph.strip()
        ]

    @staticmethod
    def _attach_markdown_heading_context(paragraphs: list[str]) -> list[str]:
        """Copy active Markdown headings into body paragraphs for better retrieval."""

        contextual_paragraphs: list[str] = []
        heading_stack: list[tuple[int, str]] = []
        for paragraph in paragraphs:
            heading = DocumentChunkingService._extract_first_markdown_heading(paragraph)
            if heading is not None:
                level, heading_line = heading
                heading_stack = [
                    existing_heading
                    for existing_heading in heading_stack
                    if existing_heading[0] < level
                ]
                heading_stack.append((level, heading_line))
                contextual_paragraphs.append(paragraph)
                continue

            if heading_stack:
                heading_context = "\n".join(
                    heading_line for _, heading_line in heading_stack
                )
                contextual_paragraphs.append(f"{heading_context}\n\n{paragraph}")
            else:
                contextual_paragraphs.append(paragraph)

        return contextual_paragraphs

    @staticmethod
    def _extract_first_markdown_heading(paragraph: str) -> tuple[int, str] | None:
        """Return the first Markdown heading line in a paragraph, if present."""

        first_line = paragraph.splitlines()[0].strip()
        heading_match = MARKDOWN_HEADING_PATTERN.match(first_line)
        if heading_match is None:
            return None
        return len(heading_match.group(1)), first_line

    @staticmethod
    def _flush_current_chunk(chunks: list[str], current_parts: list[str]) -> None:
        """Append the current paragraph group as one chunk."""

        if current_parts:
            chunks.append("\n\n".join(current_parts).strip())

    @staticmethod
    def _split_long_text(
        text: str,
        max_characters: int,
        overlap_characters: int,
    ) -> list[str]:
        """Split a very long paragraph when it cannot fit as one chunk."""

        chunks = []
        start = 0
        safe_overlap = min(overlap_characters, max_characters // 2)
        while start < len(text):
            end = min(start + max_characters, len(text))
            chunks.append(text[start:end].strip())
            if end == len(text):
                break
            start = max(0, end - safe_overlap)
        return chunks

    @staticmethod
    def _estimate_token_count(text: str) -> int:
        """Approximate token count until a model tokenizer is introduced."""

        return len(text.split())

    @staticmethod
    def _get_overlap_text(previous_chunk: str, overlap_characters: int) -> str:
        """Get the last part of the previous chunk to use as overlap for the next chunk."""

        if overlap_characters <= 0:
            return ""
        overlap_text = previous_chunk[-overlap_characters:].strip()
        first_space_index = overlap_text.find(" ")
        if first_space_index > 0:
            return overlap_text[first_space_index + 1 :].strip()
        return overlap_text


document_chunking_service = DocumentChunkingService()
