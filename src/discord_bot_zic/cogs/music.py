"""Slash commands for music playback controls."""

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot_zic.services.catalog import CatalogService
from discord_bot_zic.services.music import MusicService
from discord_bot_zic.ui.views import QueueControlView
from discord_bot_zic.utils.autocomplete import track_choice


class MusicCog(commands.GroupCog, name="music"):
    """Slash-command group controlling music playback."""

    def __init__(self, catalog: CatalogService, music: MusicService, autocomplete_limit: int) -> None:
        """Create the music command group."""
        self.catalog = catalog
        self.music = music
        self.autocomplete_limit = autocomplete_limit
        super().__init__()

    async def track_autocomplete(self, _: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Return known tracks matching the current autocomplete query."""
        tracks = await self.catalog.search_tracks(current, self.autocomplete_limit)
        return [track_choice(track) for track in tracks]

    @app_commands.command(name="connect", description="Connecte le bot au salon vocal.")
    @app_commands.describe(resume_queue="Restaurer la file d'attente sauvegardée")
    async def connect(self, interaction: discord.Interaction, resume_queue: bool = False) -> None:
        """Connect the bot to the caller's voice channel."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Commande disponible uniquement dans un serveur.", ephemeral=True)
            return
        try:
            message = await self.music.connect(interaction.user, resume_queue)
        except Exception as exc:
            message = str(exc)
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="play", description="Joue, reprend, ou ajoute une musique à la file.")
    @app_commands.describe(filter="Filtre sur le nom ou les tags de la musique")
    @app_commands.autocomplete(filter=track_autocomplete)
    async def play(self, interaction: discord.Interaction, filter: str | None = None) -> None:
        """Play a track matching the filter or resume/continue when no filter is provided."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Commande disponible uniquement dans un serveur.", ephemeral=True)
            return
        track = None
        if filter:
            track = await self.catalog.get_track_by_name(filter)
            if track is None:
                matches = await self.catalog.search_tracks(filter, 2)
                if len(matches) == 1:
                    track = matches[0]
                elif len(matches) > 1:
                    await interaction.response.send_message(
                        "Plusieurs musiques correspondent à ce filtre. Choisis une option dans l'autocomplete.",
                        ephemeral=True,
                    )
                    return
                else:
                    await interaction.response.send_message(f"Aucune musique ne correspond à: `{filter}`.", ephemeral=True)
                    return
        try:
            message = await self.music.play(interaction.user, track)
        except Exception as exc:
            message = str(exc)
        await interaction.response.send_message(message)

    @app_commands.command(name="pause", description="Met la musique en pause.")
    async def pause(self, interaction: discord.Interaction) -> None:
        """Pause current playback."""
        if interaction.guild is None:
            await interaction.response.send_message("Commande disponible uniquement dans un serveur.", ephemeral=True)
            return
        try:
            message = await self.music.pause(interaction.guild)
        except Exception as exc:
            message = str(exc)
        await interaction.response.send_message(message)

    @app_commands.command(name="skip", description="Passe à la musique suivante.")
    async def skip(self, interaction: discord.Interaction) -> None:
        """Skip to the next queued track."""
        if interaction.guild is None:
            await interaction.response.send_message("Commande disponible uniquement dans un serveur.", ephemeral=True)
            return
        try:
            message = await self.music.skip(interaction.guild)
        except Exception as exc:
            message = str(exc)
        await interaction.response.send_message(message)

    @app_commands.command(name="stop", description="Arrête la musique et quitte le vocal.")
    async def stop(self, interaction: discord.Interaction) -> None:
        """Stop playback, persist queue, and disconnect."""
        if interaction.guild is None:
            await interaction.response.send_message("Commande disponible uniquement dans un serveur.", ephemeral=True)
            return
        try:
            message = await self.music.stop(interaction.guild)
        except Exception as exc:
            message = str(exc)
        await interaction.response.send_message(message)

    @app_commands.command(name="volume", description="Ajuste le volume du bot.")
    @app_commands.describe(value="Volume de 0 à 100")
    async def volume(self, interaction: discord.Interaction, value: app_commands.Range[int, 0, 100]) -> None:
        """Set playback volume for this guild."""
        if interaction.guild is None:
            await interaction.response.send_message("Commande disponible uniquement dans un serveur.", ephemeral=True)
            return
        try:
            message = await self.music.set_volume(interaction.guild, int(value))
        except Exception as exc:
            message = str(exc)
        await interaction.response.send_message(message)

    @app_commands.command(name="queue", description="Affiche la file d'attente.")
    async def queue(self, interaction: discord.Interaction) -> None:
        """Display current track, queue, and simple control buttons."""
        if interaction.guild is None:
            await interaction.response.send_message("Commande disponible uniquement dans un serveur.", ephemeral=True)
            return
        current, queued, show_play, volume = await self.music.queue_summary(interaction.guild.id)
        lines = ["File d'attente"]
        lines.append(f"En cours: `{current.name}`" if current else "En cours: aucune musique")
        lines.append(f"Volume: {volume}%")
        if queued:
            lines.extend(f"{index}. `{track.name}`" for index, track in enumerate(queued, start=1))
        else:
            lines.append("File vide.")
        await interaction.response.send_message("\n".join(lines), view=QueueControlView(self.music, show_play))
