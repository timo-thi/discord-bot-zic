"""SQLite connection and schema validation utilities.

The bot owns a small SQLite schema. Startup calls `initialize_database`, which
creates a missing database and then verifies the expected table/column layout.
If a future incompatible schema is detected, startup fails loudly instead of
silently corrupting catalog or queue data.
"""

from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

SCHEMA_VERSION = 1

EXPECTED_COLUMNS: dict[str, tuple[str, ...]] = {
    "music_tracks": ("id", "name", "file_path", "tags", "created_at", "updated_at"),
    "guild_queues": ("guild_id", "position", "track_id", "created_at"),
}

CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS music_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    file_path TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS guild_queues (
    guild_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    track_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, position),
    FOREIGN KEY (track_id) REFERENCES music_tracks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_music_tracks_name ON music_tracks(name);
CREATE INDEX IF NOT EXISTS idx_music_tracks_tags ON music_tracks(tags);
CREATE INDEX IF NOT EXISTS idx_guild_queues_guild_position ON guild_queues(guild_id, position);
PRAGMA user_version = 1;
"""


class Database:
    """Factory for SQLite connections configured for this application."""

    def __init__(self, path: Path) -> None:
        """Create a database factory for `path`."""
        self.path = path

    async def connect(self) -> aiosqlite.Connection:
        """Open a SQLite connection with row dictionaries and foreign keys."""
        connection = await aiosqlite.connect(self.path)
        connection.row_factory = aiosqlite.Row
        await connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @asynccontextmanager
    async def session(self) -> AsyncIterator[aiosqlite.Connection]:
        """Yield a configured SQLite connection and close it afterward."""
        connection = await self.connect()
        try:
            yield connection
        finally:
            await connection.close()


async def initialize_database(path: Path) -> Database:
    """Create and validate the SQLite database, then return a connection factory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    database = Database(path)
    async with database.session() as connection:
        await connection.executescript(CREATE_SCHEMA_SQL)
        await connection.commit()
        await verify_schema(connection)
    return database


async def verify_schema(connection: aiosqlite.Connection) -> None:
    """Validate the SQLite schema version and required columns.

    This check intentionally validates only the public contract the bot relies
    on: version and column names. SQLite type affinity is permissive, so the
    service layer handles value validation where behavior depends on it.
    """
    version = await _get_user_version(connection)
    if version != SCHEMA_VERSION:
        raise RuntimeError(f"Unsupported SQLite schema version {version}; expected {SCHEMA_VERSION}.")

    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        actual_columns = await _get_columns(connection, table_name)
        missing = tuple(column for column in expected_columns if column not in actual_columns)
        if missing:
            missing_list = ", ".join(missing)
            raise RuntimeError(f"SQLite table `{table_name}` is missing required columns: {missing_list}.")


async def _get_user_version(connection: aiosqlite.Connection) -> int:
    """Read SQLite `PRAGMA user_version`."""
    async with connection.execute("PRAGMA user_version") as cursor:
        row = await cursor.fetchone()
    return int(row[0])


async def _get_columns(connection: aiosqlite.Connection, table_name: str) -> Iterable[str]:
    """Return column names for a SQLite table."""
    async with connection.execute(f"PRAGMA table_info({table_name})") as cursor:
        rows = await cursor.fetchall()
    return tuple(str(row["name"]) for row in rows)
