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

    def derive_wave_mix_paths(
        self, session_id: str, turn_index: int
    ) -> tuple[str, str]:
        """
        Derive absolute and relative paths for the wave-mix file.

        Returns:
            Tuple of (absolute_path, relative_path)
        """
        rel = f"waves/sessions/{session_id}/turn_{turn_index}/{self.tts_basename}_v3_wave_mix.wav"
        abs_path = Path("artifacts") / rel
        return (str(abs_path.resolve()), rel)


@dataclass
class DialogueSpec:
    """Specification for a dialogue (Turn 2 comments + Turn 3 reply)."""

    dialogue_id: str  # e.g., "turn23-slot2"
    target_slot_id: int  # The slot being commented on / responding
    commenters: list[SlotMeta] = field(default_factory=list)  # Turn 2 commenters
    respondent: SlotMeta | None = None  # Turn 3 respondent


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

    # Dialogue tracking
    dialogues: list[DialogueSpec] = field(default_factory=list)
    dialogues_emitted: set[str] = field(default_factory=set)  # dialogue_ids already sent

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
