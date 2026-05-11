"""Discord bot bootstrap and lifecycle management."""

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot_zic.cogs.music import MusicCog
from discord_bot_zic.cogs.store import StoreCog
from discord_bot_zic.config.settings import Settings, get_settings
from discord_bot_zic.models.database import initialize_database
from discord_bot_zic.services.bot_logger import BotLogger
from discord_bot_zic.services.catalog import CatalogService
from discord_bot_zic.services.music import MusicService
from discord_bot_zic.services.queue_store import QueueStore


class LocalMusicBot(commands.Bot):
    """Discord bot configured for local music playback."""

    def __init__(self, settings: Settings) -> None:
        """Create the bot with the Discord intents required for slash commands and voice."""
        intents = discord.Intents.default()
        intents.guilds = True
        intents.voice_states = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.settings = settings
        self.bot_logger: BotLogger | None = None
        self.music_service: MusicService | None = None
        self._idle_task: asyncio.Task[None] | None = None

    async def setup_hook(self) -> None:
        """Initialize database, services, cogs, slash-command sync and idle loop."""
        database = await initialize_database(self.settings.sqlite_path)
        self.bot_logger = BotLogger(self, self.settings.discord_log_channel_id)
        catalog = CatalogService(database, self.settings.music_root)
        queue_store = QueueStore(database)
        self.music_service = MusicService(
            bot=self,
            queue_store=queue_store,
            logger=self.bot_logger,
            ffmpeg_executable=self.settings.ffmpeg_executable,
            idle_timeout_seconds=self.settings.idle_timeout_seconds,
            default_volume_percent=self.settings.default_volume_percent,
        )

        await self.add_cog(MusicCog(catalog, self.music_service, self.settings.autocomplete_limit))
        await self.add_cog(
            StoreCog(
                catalog,
                self.bot_logger,
                self.settings.autocomplete_limit,
                self.settings.store_list_page_size,
            )
        )
        self.tree.on_error = self.on_app_command_error
        await self._sync_application_commands()
        self._idle_task = asyncio.create_task(self._idle_loop(), name="discord-bot-zic-idle-loop")

    async def on_ready(self) -> None:
        """Log the successful Discord connection."""
        if self.bot_logger is not None and self.user is not None:
            await self.bot_logger.info(f"Bot connecté comme `{self.user}`.")

    async def close(self) -> None:
        """Cancel background tasks before closing Discord connections."""
        if self._idle_task is not None:
            self._idle_task.cancel()
        await super().close()

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """Report unexpected slash-command errors to Discord and the log channel."""
        command_name = interaction.command.qualified_name if interaction.command is not None else "inconnue"
        message = f"Erreur pendant la commande `/{command_name}`: {error}"
        if self.bot_logger is not None:
            await self.bot_logger.error(message)
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def _sync_application_commands(self) -> None:
        """Sync slash commands to one configured guild or globally."""
        if self.settings.discord_guild_id is not None:
            guild = discord.Object(id=self.settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logging.getLogger("discord_bot_zic").info("Slash commands synced to guild %s.", guild.id)
            return
        await self.tree.sync()
        logging.getLogger("discord_bot_zic").info("Slash commands synced globally.")

    async def _idle_loop(self) -> None:
        """Periodically disconnect guilds that have exceeded the idle timeout."""
        await self.wait_until_ready()
        while not self.is_closed():
            if self.music_service is not None:
                await self.music_service.disconnect_idle_guilds()
            await asyncio.sleep(60)


def run() -> None:
    """Load settings and run the Discord bot."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    bot = LocalMusicBot(settings)
    bot.run(settings.discord_token)
