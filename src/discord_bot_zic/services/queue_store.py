"""Persistent per-guild queue storage."""

from discord_bot_zic.models.database import Database
from discord_bot_zic.models.entities import MusicTrack


class QueueStore:
    """Persist pending music queues for each Discord guild."""

    def __init__(self, database: Database) -> None:
        """Create a queue store backed by `database`."""
        self.database = database

    async def load_queue(self, guild_id: int) -> list[MusicTrack]:
        """Load a guild queue ordered by position."""
        async with self.database.session() as connection:
            async with connection.execute(
                """
                SELECT m.id, m.name, m.file_path, m.tags
                FROM guild_queues q
                JOIN music_tracks m ON m.id = q.track_id
                WHERE q.guild_id = ?
                ORDER BY q.position ASC
                """,
                (guild_id,),
            ) as cursor:
                rows = await cursor.fetchall()
        from discord_bot_zic.services.catalog import _row_to_track

        return [_row_to_track(row) for row in rows]

    async def save_queue(self, guild_id: int, tracks: list[MusicTrack]) -> None:
        """Replace a guild's persisted queue with `tracks`."""
        async with self.database.session() as connection:
            await connection.execute("DELETE FROM guild_queues WHERE guild_id = ?", (guild_id,))
            await connection.executemany(
                """
                INSERT INTO guild_queues (guild_id, position, track_id)
                VALUES (?, ?, ?)
                """,
                [(guild_id, position, track.id) for position, track in enumerate(tracks)],
            )
            await connection.commit()

    async def clear_queue(self, guild_id: int) -> None:
        """Delete a guild's persisted queue."""
        async with self.database.session() as connection:
            await connection.execute("DELETE FROM guild_queues WHERE guild_id = ?", (guild_id,))
            await connection.commit()
