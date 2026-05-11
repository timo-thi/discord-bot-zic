"""Catalog service for known local music files."""

from pathlib import Path

from discord_bot_zic.models.database import Database
from discord_bot_zic.models.entities import MusicTrack
from discord_bot_zic.utils.audio_files import default_track_name, parse_tags, resolve_audio_path, validate_audio_file


class CatalogService:
    """Manage music metadata stored in SQLite."""

    def __init__(self, database: Database, music_root: Path | None) -> None:
        """Create a catalog service backed by `database`."""
        self.database = database
        self.music_root = music_root

    async def add_track(self, raw_path: str, name: str | None, raw_tags: str) -> MusicTrack:
        """Validate and add a local music file to the catalog."""
        file_path = resolve_audio_path(raw_path, self.music_root)
        validate_audio_file(file_path)
        track_name = (name or default_track_name(file_path)).strip()
        if not track_name:
            raise ValueError("Le nom de la musique ne peut pas être vide.")
        tags = parse_tags(raw_tags)
        async with self.database.session() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO music_tracks (name, file_path, tags)
                VALUES (?, ?, ?)
                """,
                (track_name, str(file_path), " ".join(tags)),
            )
            await connection.commit()
            track_id = int(cursor.lastrowid)
        return MusicTrack(id=track_id, name=track_name, file_path=file_path, tags=tags)

    async def update_track(self, current_name: str, raw_path: str, new_name: str | None, raw_tags: str) -> MusicTrack:
        """Replace a catalog entry's path, display name and tags."""
        existing = await self.get_track_by_name(current_name)
        if existing is None:
            raise ValueError(f"Musique introuvable: {current_name}")

        file_path = resolve_audio_path(raw_path, self.music_root)
        validate_audio_file(file_path)
        track_name = (new_name or default_track_name(file_path)).strip()
        if not track_name:
            raise ValueError("Le nom de la musique ne peut pas être vide.")
        tags = parse_tags(raw_tags)
        async with self.database.session() as connection:
            await connection.execute(
                """
                UPDATE music_tracks
                SET name = ?, file_path = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (track_name, str(file_path), " ".join(tags), existing.id),
            )
            await connection.commit()
        return MusicTrack(id=existing.id, name=track_name, file_path=file_path, tags=tags)

    async def remove_track(self, name: str) -> MusicTrack:
        """Remove a catalog entry by name and cascade queued references."""
        track = await self.get_track_by_name(name)
        if track is None:
            raise ValueError(f"Musique introuvable: {name}")
        async with self.database.session() as connection:
            await connection.execute("DELETE FROM music_tracks WHERE id = ?", (track.id,))
            await connection.commit()
        return track

    async def get_track_by_name(self, name: str) -> MusicTrack | None:
        """Return one track by exact case-insensitive name."""
        async with self.database.session() as connection:
            async with connection.execute(
                """
                SELECT id, name, file_path, tags
                FROM music_tracks
                WHERE name = ? COLLATE NOCASE
                """,
                (name,),
            ) as cursor:
                row = await cursor.fetchone()
        return _row_to_track(row) if row is not None else None

    async def search_tracks(self, query: str, limit: int) -> list[MusicTrack]:
        """Search tracks by name or tag for autocomplete."""
        like_query = f"%{query.strip()}%"
        async with self.database.session() as connection:
            async with connection.execute(
                """
                SELECT id, name, file_path, tags
                FROM music_tracks
                WHERE ? = '' OR name LIKE ? COLLATE NOCASE OR tags LIKE ? COLLATE NOCASE
                ORDER BY name COLLATE NOCASE
                LIMIT ?
                """,
                (query.strip(), like_query, like_query, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_track(row) for row in rows]

    async def count_tracks(self) -> int:
        """Return the number of tracks known by the catalog."""
        async with self.database.session() as connection:
            async with connection.execute("SELECT COUNT(*) AS total FROM music_tracks") as cursor:
                row = await cursor.fetchone()
        return int(row["total"])

    async def list_tracks(self, limit: int, offset: int) -> list[MusicTrack]:
        """Return one page of catalog tracks ordered by display name."""
        async with self.database.session() as connection:
            async with connection.execute(
                """
                SELECT id, name, file_path, tags
                FROM music_tracks
                ORDER BY name COLLATE NOCASE
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_track(row) for row in rows]


def _row_to_track(row) -> MusicTrack:
    """Convert a SQLite row into a `MusicTrack` entity."""
    tags = tuple(tag for tag in str(row["tags"]).split() if tag)
    return MusicTrack(id=int(row["id"]), name=str(row["name"]), file_path=Path(str(row["file_path"])), tags=tags)
