from dataclasses import dataclass

from app.constants.documents import (
    DEFAULT_CHUNK_MAX_CHARACTERS,
    DEFAULT_CHUNK_OVERLAP_CHARACTERS,
)


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

        for paragraph in self._split_paragraphs(cleaned_content):
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
                self._flush_current_chunk(chunks, current_parts)
                current_parts = [paragraph]
                current_length = len(paragraph)
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


document_chunking_service = DocumentChunkingService()
