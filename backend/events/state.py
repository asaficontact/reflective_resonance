"""Per-session state tracking for events orchestration."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SlotMeta:
    """Metadata for a slot's TTS output."""

    slot_id: int
    agent_id: str
    voice_profile: str
    tts_basename: str  # Base filename for deriving wave-mix path
    audio_duration_ms: float = 0.0  # Audio duration in milliseconds

    def derive_wave_paths(
        self, session_id: str, turn_index: int
    ) -> tuple[str, str, str, str]:
        """
        Derive absolute and relative paths for wave1 and wave2 files.

        Returns:
            Tuple of (wave1_abs, wave1_rel, wave2_abs, wave2_rel)
        """
        base_rel = f"waves/sessions/{session_id}/turn_{turn_index}/{self.tts_basename}_v3"

        wave1_rel = f"{base_rel}_wave1.wav"
        wave2_rel = f"{base_rel}_wave2.wav"

        wave1_abs = str((Path("artifacts") / wave1_rel).resolve())
        wave2_abs = str((Path("artifacts") / wave2_rel).resolve())

        return (wave1_abs, wave1_rel, wave2_abs, wave2_rel)


@dataclass
class DialogueSpec:
    """Specification for a dialogue (Turn 2 comments + Turn 3 reply)."""

    dialogue_id: str  # e.g., "turn23-slot2"
    target_slot_id: int  # The slot being commented on / responding
    commenters: list[SlotMeta] = field(default_factory=list)  # Turn 2 commenters
    respondent: SlotMeta | None = None  # Turn 3 respondent


@dataclass
class SummaryMeta:
    """Metadata for summary TTS output."""

    voice_profile: str
    tts_basename: str
    text: str
    n_waves: int = 6  # Number of waves for summary (6 for 6 slots)
    audio_duration_ms: float = 0.0  # Audio duration in milliseconds

    def derive_wave_paths(self, session_id: str) -> list[tuple[int, str, str]]:
        """Derive wave paths for summary (6 waves mapped to slots 1-6).

        Returns:
            List of tuples: [(slot_id, wave_abs, wave_rel), ...]
        """
        base_rel = f"waves/sessions/{session_id}/summary/{self.tts_basename}_v3"

        paths = []
        for i in range(1, self.n_waves + 1):
            wave_rel = f"{base_rel}_wave{i}.wav"
            wave_abs = str((Path("artifacts") / wave_rel).resolve())
            slot_id = i  # wave1 → slot 1, wave2 → slot 2, etc.
            paths.append((slot_id, wave_abs, wave_rel))

        return paths


@dataclass
class SessionEventsState:
    """
    Per-session state for tracking wave-mix readiness and event emission.

    Lifecycle:
    1. Created when begin_session() is called
    2. turn1_expected populated with slot IDs
    3. As wave decomposition jobs complete, turn1_ready is populated
    4. When all Turn 1 ready (or timeout), turn1.waves.ready is emitted
    5. After Turn 3, dialogues are computed and tracked
    6. As dialogue wave files become ready, dialogue.waves.ready events are emitted
    """

    session_id: str

    # Turn 1 tracking
    turn1_expected: set[int] = field(default_factory=set)  # Slot IDs expecting Turn 1
    turn1_ready: dict[int, SlotMeta] = field(default_factory=dict)  # slot_id -> metadata
    turn1_emitted: bool = False
    turn1_timed_out: bool = False

    # Turn 2 tracking (for dialogue construction)
    turn2_ready: dict[int, SlotMeta] = field(default_factory=dict)  # slot_id -> metadata

    # Turn 3 tracking (for dialogue construction)
    turn3_ready: dict[int, SlotMeta] = field(default_factory=dict)  # slot_id -> metadata

    # Turn 2 expected (for batch readiness check)
    turn2_expected: set[int] = field(default_factory=set)

    # Turn 3 expected (for batch readiness check)
    turn3_expected: set[int] = field(default_factory=set)

    # Dialogue tracking
    dialogues: list[DialogueSpec] = field(default_factory=list)
    dialogues_emitted: set[str] = field(default_factory=set)  # dialogue_ids already sent

    # Workflow completion tracking for batch emission
    workflow_complete: bool = False  # True after turn3_complete() called
    batch_emitted: bool = False  # True after batch emission (prevents duplicates)

    # Summary (Turn 4) tracking
    summary_expected: bool = False  # True after workflow requests summary
    summary_ready: bool = False  # True after summary wave decomposition completes
    summary_emitted: bool = False  # True after final_summary.ready emitted
    summary_meta: SummaryMeta | None = None  # Metadata for summary wave paths

    # Sequence counter for events
    seq_counter: int = 0

    def next_seq(self) -> int:
        """Get next sequence number for this session."""
        self.seq_counter += 1
        return self.seq_counter

    def is_turn1_complete(self) -> bool:
        """Check if all expected Turn 1 slots have wave-mix files ready."""
        return self.turn1_expected == set(self.turn1_ready.keys())

    def get_missing_turn1_slots(self) -> list[int]:
        """Get list of slot IDs that are expected but not ready."""
        return sorted(self.turn1_expected - set(self.turn1_ready.keys()))

    def is_dialogue_ready(self, dialogue: DialogueSpec) -> bool:
        """
        Check if all wave-mix files for a dialogue are ready.

        A dialogue is ready when:
        - All commenters have Turn 2 wave-mix files ready
        - The respondent has Turn 3 wave-mix file ready
        """
        if dialogue.respondent is None:
            return False

        # Check respondent (Turn 3) is ready
        if dialogue.respondent.slot_id not in self.turn3_ready:
            return False

        # Check all commenters (Turn 2) are ready
        for commenter in dialogue.commenters:
            if commenter.slot_id not in self.turn2_ready:
                return False

        return True

    def is_turn2_complete(self) -> bool:
        """Check if all expected Turn 2 slots have waves ready."""
        if not self.turn2_expected:
            return True  # No Turn 2 expected (edge case)
        return self.turn2_expected <= set(self.turn2_ready.keys())

    def is_turn3_complete(self) -> bool:
        """Check if all expected Turn 3 slots have waves ready."""
        if not self.turn3_expected:
            return True  # No Turn 3 expected (edge case)
        return self.turn3_expected <= set(self.turn3_ready.keys())

    def is_all_waves_ready(self) -> bool:
        """Check if ALL waves (Turn 1, 2, 3) are ready for batch emission."""
        if not self.workflow_complete:
            return False
        return (
            self.is_turn1_complete()
            and self.is_turn2_complete()
            and self.is_turn3_complete()
        )

    def get_ready_dialogues(self) -> list[DialogueSpec]:
        """Get all dialogues that have their waves ready."""
        return [d for d in self.dialogues if self.is_dialogue_ready(d)]
