"""
rat.crawler.chunker — Hierarchical semantic text chunking.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


class DocumentChunk:
    """Represents a single semantic chunk of a larger document."""

    def __init__(
        self,
        chunk_index: int,
        text: str,
        start_char: int,
        end_char: int,
        section_title: str = "",
    ) -> None:
        self.chunk_index = chunk_index
        self.text = text
        self.start_char = start_char
        self.end_char = end_char
        self.section_title = section_title

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_index": self.chunk_index,
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "section_title": self.section_title,
        }


class SemanticChunker:
    """
    Chunks document text into overlapping semantic blocks while respecting
    paragraphs, headings, slide boundaries, and page markers.
    """

    def __init__(
        self,
        chunk_size: int = 350,  # Approximate words per chunk
        chunk_overlap: int = 50,  # Word overlap between adjacent chunks
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, full_text: str) -> List[DocumentChunk]:
        """Split text into overlapping semantic chunks."""
        if not full_text or not full_text.strip():
            return []

        # If text is small, return as single chunk
        words = full_text.split()
        if len(words) <= self.chunk_size:
            return [
                DocumentChunk(
                    chunk_index=0,
                    text=full_text.strip(),
                    start_char=0,
                    end_char=len(full_text),
                )
            ]

        # Break text by semantic boundaries (pages, slides, paragraphs)
        boundary_pattern = r"(?:\n--- (?:Page|Slide|Sheet)[^\n]*---\n|\n\n+)"
        splits = re.split(boundary_pattern, full_text)

        chunks: List[DocumentChunk] = []
        current_chunk_words: List[str] = []
        current_start_idx = 0
        chunk_idx = 0

        for block in splits:
            block_words = block.split()
            if not block_words:
                continue

            if len(current_chunk_words) + len(block_words) <= self.chunk_size:
                current_chunk_words.extend(block_words)
            else:
                # If current chunk has enough words, save it
                if current_chunk_words:
                    chunk_str = " ".join(current_chunk_words)
                    chunks.append(
                        DocumentChunk(
                            chunk_index=chunk_idx,
                            text=chunk_str,
                            start_char=current_start_idx,
                            end_char=current_start_idx + len(chunk_str),
                        )
                    )
                    chunk_idx += 1
                    # Keep overlap
                    current_chunk_words = current_chunk_words[-self.chunk_overlap:] if len(current_chunk_words) > self.chunk_overlap else []

                # Handle block if it's very large
                while len(block_words) > self.chunk_size:
                    sub_words = block_words[:self.chunk_size]
                    chunk_str = " ".join(sub_words)
                    chunks.append(
                        DocumentChunk(
                            chunk_index=chunk_idx,
                            text=chunk_str,
                            start_char=current_start_idx,
                            end_char=current_start_idx + len(chunk_str),
                        )
                    )
                    chunk_idx += 1
                    block_words = block_words[self.chunk_size - self.chunk_overlap:]

                current_chunk_words.extend(block_words)

        if current_chunk_words:
            chunk_str = " ".join(current_chunk_words)
            chunks.append(
                DocumentChunk(
                    chunk_index=chunk_idx,
                    text=chunk_str,
                    start_char=current_start_idx,
                    end_char=current_start_idx + len(chunk_str),
                )
            )

        return chunks


# Global chunker instance
chunker = SemanticChunker()
