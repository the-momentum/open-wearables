from collections import Counter
from dataclasses import dataclass, field


@dataclass
class ParseMetric:
    processed: int = 0
    skipped: int = 0
    reasons: Counter[str] = field(default_factory=Counter)

    def mark_processed(self) -> None:
        self.processed += 1

    def skip(self, reason: str) -> None:
        self.skipped += 1
        self.reasons[reason] += 1


@dataclass
class XMLParseStats:
    """Statistics for XML parsing progress and errors."""

    records: ParseMetric = field(default_factory=ParseMetric)
    workouts: ParseMetric = field(default_factory=ParseMetric)
    sleep: ParseMetric = field(default_factory=ParseMetric)

    def any_skipped(self) -> bool:
        return self.records.skipped > 0 or self.workouts.skipped > 0 or self.sleep.skipped > 0

    def get_skip_summary(self) -> dict[str, str]:
        record_reasons = ", ".join(f"{reason}: {count}" for reason, count in sorted(self.records.reasons.items()))
        workout_reasons = ", ".join(f"{reason}: {count}" for reason, count in sorted(self.workouts.reasons.items()))
        sleep_reasons = ", ".join(f"{reason}: {count}" for reason, count in sorted(self.sleep.reasons.items()))
        return {"records": record_reasons, "workouts": workout_reasons, "sleep": sleep_reasons}
