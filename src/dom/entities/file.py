# src/dom/entities/file.py

from dataclasses import dataclass
from datetime import datetime


@dataclass
class File:
    """Metadata của một file/thư mục thuộc workspace của conversation."""

    id: int
    conversation_id: int
    parent_id: int | None

    name: str
    path: str

    is_directory: bool

    file_type: str | None
    mime_type: str | None

    size: int
    source: str

    created_at: datetime
    updated_at: datetime