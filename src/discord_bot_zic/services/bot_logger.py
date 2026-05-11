"""Logging helpers for Discord text-channel bot logs."""

import logging

import discord


class BotLogger:
    """Send important bot events to Python logging and one Discord channel."""

    def __init__(self, bot: discord.Client, channel_id: int) -> None:
        """Create a logger that posts to `channel_id` when available."""
        self.bot = bot
        self.channel_id = channel_id
        self.logger = logging.getLogger("discord_bot_zic")

    async def info(self, message: str) -> None:
        """Log an informational message."""
        self.logger.info(message)
        await self._send(message)

    async def error(self, message: str) -> None:
        """Log an error message."""
        self.logger.error(message)
        await self._send(f"Erreur: {message}")

    async def _send(self, message: str) -> None:
        """Post a short message to the configured Discord log channel."""
        channel = self.bot.get_channel(self.channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            return
        try:
            await channel.send(message[:1900])
        except discord.DiscordException:
            self.logger.exception("Failed to send bot log to Discord channel.")
