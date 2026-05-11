"""Interactive Discord views for music controls."""

import discord

from discord_bot_zic.models.entities import MusicTrack
from discord_bot_zic.services.catalog import CatalogService
from discord_bot_zic.services.music import MusicService


class QueueControlView(discord.ui.View):
    """Simple control buttons shown with the queue command."""

    def __init__(self, music: MusicService, show_play: bool) -> None:
        """Create queue controls bound to a music service."""
        super().__init__(timeout=180)
        self.music = music
        self._set_toggle_button(show_play)

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.secondary)
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Toggle pause and play from a queue message button."""
        if interaction.guild is None:
            await interaction.response.send_message("Commande disponible uniquement dans un serveur.", ephemeral=True)
            return
        try:
            if button.label == "Play":
                if not isinstance(interaction.user, discord.Member):
                    raise ValueError("Commande disponible uniquement dans un serveur.")
                message = await self.music.play(interaction.user, None)
            else:
                message = await self.music.pause(interaction.guild)
            await self._refresh_toggle_button(interaction.guild.id)
        except Exception as exc:
            message = str(exc)
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(message, ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        """Skip playback from a queue message button."""
        if interaction.guild is None:
            await interaction.response.send_message("Commande disponible uniquement dans un serveur.", ephemeral=True)
            return
        try:
            message = await self.music.skip(interaction.guild)
            await self._refresh_toggle_button(interaction.guild.id)
        except Exception as exc:
            message = str(exc)
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(message, ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        """Stop playback from a queue message button."""
        if interaction.guild is None:
            await interaction.response.send_message("Commande disponible uniquement dans un serveur.", ephemeral=True)
            return
        try:
            message = await self.music.stop(interaction.guild)
            await self._refresh_toggle_button(interaction.guild.id)
        except Exception as exc:
            message = str(exc)
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(message, ephemeral=True)

    async def _refresh_toggle_button(self, guild_id: int) -> None:
        """Refresh the play/pause button from the current playback state."""
        _, _, show_play, _ = await self.music.queue_summary(guild_id)
        self._set_toggle_button(show_play)

    def _set_toggle_button(self, show_play: bool) -> None:
        """Update the first button to reflect the current play/pause action."""
        button = self.children[0]
        if not isinstance(button, discord.ui.Button):
            return
        button.label = "Play" if show_play else "Pause"
        button.style = discord.ButtonStyle.success if show_play else discord.ButtonStyle.secondary


class StoreListView(discord.ui.View):
    """Paginated embed view for catalog tracks."""

    def __init__(self, catalog: CatalogService, page_size: int, total_tracks: int) -> None:
        """Create pagination controls for the store list command."""
        super().__init__(timeout=180)
        self.catalog = catalog
        self.page_size = page_size
        self.total_tracks = total_tracks
        self.page_index = 0
        self._sync_buttons()

    async def build_embed(self) -> discord.Embed:
        """Build the embed for the current catalog page."""
        tracks = await self.catalog.list_tracks(self.page_size, self.page_index * self.page_size)
        total_pages = self.total_pages
        embed = discord.Embed(
            title="Catalogue des musiques",
            description=f"{self.total_tracks} musique(s) connue(s)",
            color=discord.Color.blurple(),
        )
        if tracks:
            for track in tracks:
                embed.add_field(name=track.name, value=_format_track_details(track), inline=False)
        else:
            embed.description = "Aucune musique connue."
        embed.set_footer(text=f"Page {self.page_index + 1}/{total_pages}")
        return embed

    @property
    def total_pages(self) -> int:
        """Return the number of pages needed for the current total."""
        return max(1, (self.total_tracks + self.page_size - 1) // self.page_size)

    @discord.ui.button(label="Précédent", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        """Move to the previous catalog page."""
        self.page_index = max(0, self.page_index - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=await self.build_embed(), view=self)

    @discord.ui.button(label="Suivant", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        """Move to the next catalog page."""
        self.page_index = min(self.total_pages - 1, self.page_index + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=await self.build_embed(), view=self)

    def _sync_buttons(self) -> None:
        """Disable pagination buttons when the current page is at a boundary."""
        previous_button = self.children[0]
        next_button = self.children[1]
        if isinstance(previous_button, discord.ui.Button):
            previous_button.disabled = self.page_index <= 0
        if isinstance(next_button, discord.ui.Button):
            next_button.disabled = self.page_index >= self.total_pages - 1


def _format_track_details(track: MusicTrack) -> str:
    """Format one catalog track for an embed field."""
    tags = " | ".join(track.tags) if track.tags else "aucun tag"
    return f"Tags: {tags}\nFichier: `{track.file_path}`"
