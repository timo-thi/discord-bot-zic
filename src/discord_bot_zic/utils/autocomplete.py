"""Formatting helpers for Discord autocomplete choices."""

from discord import app_commands

from discord_bot_zic.models.entities import MusicTrack


def track_choice(track: MusicTrack) -> app_commands.Choice[str]:
    """Return an autocomplete choice displaying track name and tags."""
    tag_suffix = f" - {' | '.join(track.tags)}" if track.tags else ""
    display_name = f"{track.name}{tag_suffix}"
    return app_commands.Choice(name=display_name[:100], value=track.name)
