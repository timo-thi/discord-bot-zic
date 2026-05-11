"""Environment-based settings for the Discord music bot."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    discord_token: str = Field(alias="DISCORD_TOKEN")
    discord_guild_id: int | None = Field(default=None, alias="DISCORD_GUILD_ID")
    discord_log_channel_id: int = Field(alias="DISCORD_LOG_CHANNEL_ID")
    sqlite_path: Path = Field(
        default=Path("./data/discord-bot-zic.sqlite3"), alias="SQLITE_PATH"
    )
    music_root: Path | None = Field(default=Path("./music"), alias="MUSIC_ROOT")
    idle_timeout_seconds: int = Field(default=600, alias="IDLE_TIMEOUT_SECONDS", ge=1)
    ffmpeg_executable: str = Field(default="ffmpeg", alias="FFMPEG_EXECUTABLE")
    default_volume_percent: int = Field(
        default=100, alias="DEFAULT_VOLUME_PERCENT", ge=0, le=100
    )
    autocomplete_limit: int = Field(default=25, alias="AUTOCOMPLETE_LIMIT", ge=1, le=25)
    store_list_page_size: int = Field(
        default=10, alias="STORE_LIST_PAGE_SIZE", ge=1, le=25
    )

    @field_validator("discord_guild_id", mode="before")
    @classmethod
    def empty_guild_id_to_none(cls, value: object) -> object:
        """Treat an empty `DISCORD_GUILD_ID` as global command sync."""
        return None if value == "" else value

    @field_validator("music_root", mode="before")
    @classmethod
    def empty_music_root_to_none(cls, value: object) -> object:
        """Allow disabling relative music paths with an empty `MUSIC_ROOT`."""
        return None if value == "" else value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings for the current process."""
    return Settings()  # pyright: ignore[reportCallIssue]
