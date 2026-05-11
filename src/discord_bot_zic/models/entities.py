"""Typed entities persisted in SQLite."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MusicTrack:
    """A known local music file from the catalog."""

    id: int
    name: str
    file_path: Path
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QueueEntry:
    """A queued track for one Discord guild."""

    guild_id: int
    position: int
    track: MusicTrack
