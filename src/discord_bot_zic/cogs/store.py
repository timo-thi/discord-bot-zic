"""Slash commands for catalog management."""

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot_zic.services.bot_logger import BotLogger
from discord_bot_zic.services.catalog import CatalogService
from discord_bot_zic.ui.modals import AddTrackModal, EditTrackModal
from discord_bot_zic.ui.views import StoreListView
from discord_bot_zic.utils.autocomplete import track_choice


class StoreCog(commands.GroupCog, name="store"):
    """Slash-command group managing the music catalog."""

    def __init__(
        self,
        catalog: CatalogService,
        logger: BotLogger,
        autocomplete_limit: int,
        list_page_size: int,
    ) -> None:
        """Create the store command group."""
        self.catalog = catalog
        self.logger = logger
        self.autocomplete_limit = autocomplete_limit
        self.list_page_size = list_page_size
        super().__init__()

    async def track_autocomplete(self, _: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Return known tracks matching the current autocomplete query."""
        tracks = await self.catalog.search_tracks(current, self.autocomplete_limit)
        return [track_choice(track) for track in tracks]

    @app_commands.command(name="add", description="Ajoute une musique au catalogue.")
    async def add(self, interaction: discord.Interaction) -> None:
        """Open a modal to add a catalog track."""
        await interaction.response.send_modal(AddTrackModal(self.catalog, self.logger))

    @app_commands.command(name="list", description="Liste les musiques connues du catalogue.")
    async def list(self, interaction: discord.Interaction) -> None:
        """Display known catalog tracks in a paginated embed."""
        try:
            total_tracks = await self.catalog.count_tracks()
            view = StoreListView(self.catalog, self.list_page_size, total_tracks)
            embed = await view.build_embed()
            if view.total_pages > 1:
                await interaction.response.send_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed)
        except Exception as exc:
            await self.logger.error(f"Impossible de lister le catalogue: {exc}")
            message = f"Impossible de lister le catalogue: {exc}"
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="remove", description="Retire une musique du catalogue.")
    @app_commands.describe(music_name="Musique à retirer")
    @app_commands.autocomplete(music_name=track_autocomplete)
    async def remove(self, interaction: discord.Interaction, music_name: str) -> None:
        """Remove one catalog track by name."""
        try:
            track = await self.catalog.remove_track(music_name)
        except Exception as exc:
            await interaction.response.send_message(f"Impossible de retirer la musique: {exc}", ephemeral=True)
            return
        await self.logger.info(f"Catalogue: suppression `{track.name}` par {interaction.user}.")
        await interaction.response.send_message(f"Musique retirée: `{track.name}`.", ephemeral=True)

    @app_commands.command(name="edit", description="Modifie une musique du catalogue.")
    @app_commands.describe(music_name="Musique à modifier")
    @app_commands.autocomplete(music_name=track_autocomplete)
    async def edit(self, interaction: discord.Interaction, music_name: str) -> None:
        """Open a modal to edit an existing catalog track."""
        track = await self.catalog.get_track_by_name(music_name)
        if track is None:
            await interaction.response.send_message(f"Musique introuvable: `{music_name}`.", ephemeral=True)
            return
        await interaction.response.send_modal(EditTrackModal(self.catalog, self.logger, track))
