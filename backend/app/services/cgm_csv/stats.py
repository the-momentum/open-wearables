from dataclasses import dataclass, field


@dataclass
class CSVParseStats:
    """Statistics for CGM CSV parsing progress and errors."""

    records_processed: int = 0
    records_skipped: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)
    detected_format: str | None = None  # "dexcom_clarity" or "libreview"

    def record_skip(self, reason: str) -> None:
        """Record a skipped item with its reason."""
        self.records_skipped += 1
        self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1
