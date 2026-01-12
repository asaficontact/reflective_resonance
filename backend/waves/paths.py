"""Path utilities for wave decomposition outputs."""

from pathlib import Path


# Base directory for wave session outputs
WAVES_SESSIONS_BASE = Path("artifacts/waves/sessions")


def tts_path_to_waves_dir(
    tts_audio_path: Path,
    session_id: str,
    turn_index: int,
) -> Path:
    """
    Map TTS audio path to waves output directory.

    Input:  artifacts/tts/sessions/<session>/turn_<N>/slot-1_gpt-5.1_friendly_casual.wav
    Output: artifacts/waves/sessions/<session>/turn_<N>/

    For summary (turn_index=-1):
    Output: artifacts/waves/sessions/<session>/summary/

    The wave files will be written by decompose_audio_to_waves as:
        <output_dir>/<basename>_v3_wave1.wav
        <output_dir>/<basename>_v3_wave2.wav

    Args:
        tts_audio_path: Absolute path to the TTS WAV file
        session_id: The session UUID
        turn_index: Turn number (1, 2, 3, or -1 for summary)

    Returns:
        Path to the output directory for wave files
    """
    if turn_index == -1:
        return WAVES_SESSIONS_BASE / session_id / "summary"
    return WAVES_SESSIONS_BASE / session_id / f"turn_{turn_index}"


def get_wave_output_paths(base_name: str, output_dir: Path) -> tuple[Path, Path]:
    """
    Get the wave output file paths for a given base name.

    Args:
        base_name: The base filename without extension (e.g., "slot-1_gpt-5.1_friendly_casual")
        output_dir: The output directory path

    Returns:
        Tuple of (wave1_path, wave2_path)
    """
    return (
        output_dir / f"{base_name}_v3_wave1.wav",
        output_dir / f"{base_name}_v3_wave2.wav",
    )
