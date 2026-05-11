"""Discord modals used by catalog commands."""

import discord

from discord_bot_zic.models.entities import MusicTrack
from discord_bot_zic.services.bot_logger import BotLogger
from discord_bot_zic.services.catalog import CatalogService


class AddTrackModal(discord.ui.Modal, title="Ajouter une musique"):
    """Modal collecting metadata for a new catalog track."""

    file_path = discord.ui.TextInput(label="Chemin du fichier", required=True, max_length=1000)
    name = discord.ui.TextInput(label="Nom de la musique", required=False, max_length=200)
    tags = discord.ui.TextInput(label="Tags séparés par des espaces", required=False, max_length=500)

    def __init__(self, catalog: CatalogService, logger: BotLogger) -> None:
        """Create an add-track modal using catalog and logging services."""
        super().__init__()
        self.catalog = catalog
        self.logger = logger

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Validate modal data and insert the track in the catalog."""
        try:
            track = await self.catalog.add_track(self.file_path.value, self.name.value or None, self.tags.value)
        except Exception as exc:
            await interaction.response.send_message(f"Impossible d'ajouter la musique: {exc}", ephemeral=True)
            return

        await self.logger.info(f"Catalogue: ajout `{track.name}` par {interaction.user}.")
        await interaction.response.send_message(f"Musique ajoutée: `{track.name}`.", ephemeral=True)


class EditTrackModal(discord.ui.Modal, title="Modifier une musique"):
    """Modal editing metadata for an existing catalog track."""

    file_path = discord.ui.TextInput(label="Chemin du fichier", required=True, max_length=1000)
    name = discord.ui.TextInput(label="Nom de la musique", required=False, max_length=200)
    tags = discord.ui.TextInput(label="Tags séparés par des espaces", required=False, max_length=500)

    def __init__(self, catalog: CatalogService, logger: BotLogger, track: MusicTrack) -> None:
        """Create an edit modal pre-filled with `track` data."""
        super().__init__()
        self.catalog = catalog
        self.logger = logger
        self.track = track
        self.file_path.default = str(track.file_path)
        self.name.default = track.name
        self.tags.default = " ".join(track.tags)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Validate modal data and update the catalog entry."""
        try:
            updated = await self.catalog.update_track(
                self.track.name,
                self.file_path.value,
                self.name.value or None,
                self.tags.value,
            )
        except Exception as exc:
            await interaction.response.send_message(f"Impossible de modifier la musique: {exc}", ephemeral=True)
            return

        await self.logger.info(f"Catalogue: modification `{self.track.name}` -> `{updated.name}` par {interaction.user}.")
        await interaction.response.send_message(f"Musique modifiée: `{updated.name}`.", ephemeral=True)
