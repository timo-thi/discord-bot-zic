"""Voice playback service and per-guild music state."""

import asyncio
import time
from dataclasses import dataclass, field

import discord

from discord_bot_zic.models.entities import MusicTrack
from discord_bot_zic.services.bot_logger import BotLogger
from discord_bot_zic.services.queue_store import QueueStore
from discord_bot_zic.utils.audio_files import validate_audio_file


@dataclass(slots=True)
class GuildMusicState:
    """In-memory playback state for a Discord guild."""

    guild_id: int
    queue: list[MusicTrack] = field(default_factory=list)
    current: MusicTrack | None = None
    volume: float = 1.0
    suppress_after_once: bool = False
    last_activity: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class MusicService:
    """Coordinate Discord voice clients, playback and persistent queues."""

    def __init__(
        self,
        bot: discord.Client,
        queue_store: QueueStore,
        logger: BotLogger,
        ffmpeg_executable: str,
        idle_timeout_seconds: int,
        default_volume_percent: int,
    ) -> None:
        """Create a music playback service."""
        self.bot = bot
        self.queue_store = queue_store
        self.logger = logger
        self.ffmpeg_executable = ffmpeg_executable
        self.idle_timeout_seconds = idle_timeout_seconds
        self.default_volume = default_volume_percent / 100
        self._states: dict[int, GuildMusicState] = {}

    def get_state(self, guild_id: int) -> GuildMusicState:
        """Return existing state for a guild or create an empty one."""
        if guild_id not in self._states:
            self._states[guild_id] = GuildMusicState(guild_id=guild_id, volume=self.default_volume)
        return self._states[guild_id]

    async def mark_activity(self, guild_id: int) -> None:
        """Refresh a guild's activity timestamp after a command or playback event."""
        self.get_state(guild_id).last_activity = time.monotonic()

    async def connect(self, member: discord.Member, resume_queue: bool) -> str:
        """Connect to the member's voice channel and optionally restore the persisted queue."""
        if member.voice is None or member.voice.channel is None:
            raise ValueError("Tu dois être connecté à un salon vocal.")

        guild = member.guild
        state = self.get_state(guild.id)
        async with state.lock:
            await self.mark_activity(guild.id)
            voice_client = guild.voice_client
            if voice_client is None:
                await member.voice.channel.connect()
                await self.logger.info(f"Connecté au vocal `{member.voice.channel}` sur `{guild.name}`.")

            if resume_queue:
                state.queue = await self.queue_store.load_queue(guild.id)
                return f"Connecté. File restaurée: {len(state.queue)} musique(s)."
            return "Connecté au vocal."

    async def play(self, member: discord.Member, track: MusicTrack | None) -> str:
        """Resume, play the next queued track, start `track`, or enqueue it."""
        if member.voice is None or member.voice.channel is None:
            raise ValueError("Tu dois être connecté à un salon vocal.")

        guild = member.guild
        state = self.get_state(guild.id)
        async with state.lock:
            await self.mark_activity(guild.id)
            if guild.voice_client is None:
                await member.voice.channel.connect()
                await self.logger.info(f"Connecté au vocal `{member.voice.channel}` sur `{guild.name}`.")

            voice_client = _require_voice_client(guild)
            if voice_client.is_paused() and track is None:
                voice_client.resume()
                return f"Lecture reprise: `{state.current.name if state.current else 'musique en cours'}`."

            if track is None:
                if state.queue:
                    await self._start_next_locked(guild, state)
                    return f"Lecture: `{state.current.name}`."
                raise ValueError("Aucune musique en pause ou en file d'attente.")

            validate_audio_file(track.file_path)
            if voice_client.is_playing() or voice_client.is_paused():
                state.queue.append(track)
                await self.queue_store.save_queue(guild.id, state.queue)
                return f"Ajouté à la file: `{track.name}`."

            await self._play_track_locked(guild, state, track)
            return f"Lecture: `{track.name}`."

    async def resume_or_play_next(self, guild: discord.Guild) -> str:
        """Resume paused playback or start the next queued track."""
        state = self.get_state(guild.id)
        async with state.lock:
            await self.mark_activity(guild.id)
            voice_client = _require_voice_client(guild)
            if voice_client.is_paused():
                voice_client.resume()
                return f"Lecture reprise: `{state.current.name if state.current else 'musique en cours'}`."
            if voice_client.is_playing():
                return f"Lecture déjà en cours: `{state.current.name if state.current else 'musique en cours'}`."
            if state.queue:
                await self._start_next_locked(guild, state)
                return f"Lecture: `{state.current.name}`."
            raise ValueError("Aucune musique en pause ou en file d'attente.")

    async def pause(self, guild: discord.Guild) -> str:
        """Pause current playback if possible."""
        state = self.get_state(guild.id)
        async with state.lock:
            await self.mark_activity(guild.id)
            voice_client = _require_voice_client(guild)
            if not voice_client.is_playing():
                return "Aucune musique en lecture."
            voice_client.pause()
            return "Musique mise en pause."

    async def skip(self, guild: discord.Guild) -> str:
        """Skip to the next queued track, or pause if the queue is empty."""
        state = self.get_state(guild.id)
        async with state.lock:
            await self.mark_activity(guild.id)
            voice_client = _require_voice_client(guild)
            if state.queue:
                state.suppress_after_once = True
                voice_client.stop()
                await self._start_next_locked(guild, state)
                return f"Musique suivante: `{state.current.name}`."
            if voice_client.is_playing():
                voice_client.pause()
            return "Pas de musique suivante. Lecture mise en pause."

    async def stop(self, guild: discord.Guild) -> str:
        """Stop playback, persist the pending queue, and disconnect from voice."""
        state = self.get_state(guild.id)
        async with state.lock:
            await self.mark_activity(guild.id)
            await self.queue_store.save_queue(guild.id, state.queue)
            state.current = None
            voice_client = guild.voice_client
            if voice_client is not None:
                state.suppress_after_once = True
                voice_client.stop()
                await voice_client.disconnect(force=False)
                await self.logger.info(f"Déconnecté du vocal sur `{guild.name}`.")
            return f"Lecture arrêtée. File sauvegardée: {len(state.queue)} musique(s)."

    async def set_volume(self, guild: discord.Guild, volume_percent: int) -> str:
        """Set the playback volume for a guild from 0 to 100 percent."""
        if volume_percent < 0 or volume_percent > 100:
            raise ValueError("Le volume doit être compris entre 0 et 100.")
        state = self.get_state(guild.id)
        async with state.lock:
            await self.mark_activity(guild.id)
            state.volume = volume_percent / 100
            voice_client = guild.voice_client
            source = getattr(voice_client, "source", None) if voice_client is not None else None
            if isinstance(source, discord.PCMVolumeTransformer):
                source.volume = state.volume
            return f"Volume réglé à {volume_percent}%."

    async def queue_summary(self, guild_id: int) -> tuple[MusicTrack | None, list[MusicTrack], bool, int]:
        """Return current track, pending queue, play-button state and volume percentage."""
        state = self.get_state(guild_id)
        async with state.lock:
            await self.mark_activity(guild_id)
            guild = self.bot.get_guild(guild_id)
            voice_client = guild.voice_client if guild is not None else None
            show_play = bool(voice_client is None or not voice_client.is_playing())
            return state.current, list(state.queue), show_play, round(state.volume * 100)

    async def disconnect_idle_guilds(self) -> None:
        """Disconnect guild voice clients that exceeded the configured idle timeout."""
        now = time.monotonic()
        for guild_id, state in list(self._states.items()):
            async with state.lock:
                guild = self.bot.get_guild(guild_id)
                if guild is None or guild.voice_client is None:
                    continue
                voice_client = guild.voice_client
                active = voice_client.is_playing() or voice_client.is_paused()
                if active:
                    continue
                if now - state.last_activity < self.idle_timeout_seconds:
                    continue
                await self.queue_store.save_queue(guild_id, state.queue)
                await voice_client.disconnect(force=False)
                await self.logger.info(f"Déconnexion automatique pour inactivité sur `{guild.name}`.")

    async def _start_next_locked(self, guild: discord.Guild, state: GuildMusicState) -> None:
        """Pop the next queued track, persist the queue, and start playback."""
        next_track = state.queue.pop(0)
        await self.queue_store.save_queue(guild.id, state.queue)
        await self._play_track_locked(guild, state, next_track)

    async def _play_track_locked(self, guild: discord.Guild, state: GuildMusicState, track: MusicTrack) -> None:
        """Start a track on the guild voice client.

        The `after` callback is invoked by discord.py outside the async flow, so
        it schedules the next-track coroutine back on the bot event loop.
        """
        voice_client = _require_voice_client(guild)
        raw_source = discord.FFmpegPCMAudio(str(track.file_path), executable=self.ffmpeg_executable)
        source = discord.PCMVolumeTransformer(raw_source, volume=state.volume)
        state.current = track
        voice_client.play(source, after=lambda error: self._after_playback(guild.id, error))
        await self.logger.info(f"Lecture `{track.name}` sur `{guild.name}`.")

    def _after_playback(self, guild_id: int, error: Exception | None) -> None:
        """Schedule queue advancement after discord.py finishes a source."""
        if error is not None:
            self.bot.loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.logger.error(f"Erreur de lecture: {error}"))
            )
        self.bot.loop.call_soon_threadsafe(lambda: asyncio.create_task(self._advance_after_playback(guild_id)))

    async def _advance_after_playback(self, guild_id: int) -> None:
        """Advance to the next queued track when a track naturally ends."""
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return
        state = self.get_state(guild_id)
        async with state.lock:
            await self.mark_activity(guild_id)
            if state.suppress_after_once:
                state.suppress_after_once = False
                return
            state.current = None
            if guild.voice_client is None or not state.queue:
                return
            await self._start_next_locked(guild, state)


def _require_voice_client(guild: discord.Guild) -> discord.VoiceClient:
    """Return the guild voice client or raise a user-facing error."""
    voice_client = guild.voice_client
    if not isinstance(voice_client, discord.VoiceClient):
        raise ValueError("Le bot n'est pas connecté à un salon vocal.")
    return voice_client
