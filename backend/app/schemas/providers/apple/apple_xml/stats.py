from dataclasses import dataclass, field


@dataclass
class XMLParseStats:
    """Statistics for XML parsing progress and errors."""

    records_processed: int = 0
    records_skipped: int = 0
    workouts_processed: int = 0
    workouts_skipped: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)

    def record_skip(self, reason: str) -> None:
        """Record a skipped item with its reason."""
        self.records_skipped += 1
        self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1

    def workout_skip(self, reason: str) -> None:
        """Record a skipped workout with its reason."""
        self.workouts_skipped += 1
        self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1
