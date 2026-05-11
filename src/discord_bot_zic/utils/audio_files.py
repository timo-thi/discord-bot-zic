"""Validation helpers for local audio files."""

from pathlib import Path

SUPPORTED_AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".webm"}


class AudioFileValidationError(ValueError):
    """Raised when a catalog path does not point to a supported local audio file."""


def resolve_audio_path(raw_path: str, music_root: Path | None) -> Path:
    """Resolve an absolute or `music_root`-relative audio path."""
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        if music_root is None:
            raise AudioFileValidationError("Le chemin doit être absolu si MUSIC_ROOT n'est pas configuré.")
        path = music_root.expanduser() / path
    return path.resolve()


def validate_audio_file(path: Path) -> None:
    """Ensure `path` exists, is a file, and uses a supported audio extension."""
    if not path.exists():
        raise AudioFileValidationError(f"Le fichier n'existe pas: {path}")
    if not path.is_file():
        raise AudioFileValidationError(f"Le chemin n'est pas un fichier: {path}")
    if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
        raise AudioFileValidationError(f"Format audio non supporté `{path.suffix}`. Formats: {supported}.")


def default_track_name(path: Path) -> str:
    """Return the default catalog name for an audio file."""
    return path.stem


def parse_tags(raw_tags: str) -> tuple[str, ...]:
    """Parse a space-separated tag list and reject tags containing whitespace."""
    tags = tuple(tag.strip() for tag in raw_tags.split() if tag.strip())
    for tag in tags:
        if any(character.isspace() for character in tag):
            raise ValueError("Les tags ne peuvent pas contenir d'espace.")
    return tags
