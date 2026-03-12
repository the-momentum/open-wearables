import io
import re
from datetime import datetime, timedelta, timezone
from logging import Logger
from uuid import UUID, uuid4

import pdfplumber

from app.schemas.series_types import SeriesType
from app.schemas.timeseries import TimeSeriesSampleCreate
from app.services.cgm_csv.stats import CSVParseStats

# mmol/L to mg/dL conversion factor
MMOL_TO_MGDL = 18.0182

# Patterns to identify glucose data header rows
_GLUCOSE_HEADER_KEYWORDS = {"glucose", "time", "record type"}

# Common LibreView PDF timestamp formats
_TIMESTAMP_FORMATS = (
    "%d-%m-%Y %H:%M",
    "%m-%d-%Y %H:%M",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%m/%d/%Y %H:%M",
    "%d-%m-%Y %H:%M:%S",
    "%m-%d-%Y %H:%M:%S",
)


def _find_glucose_table(
    tables: list[list[list[str | None]]],
) -> tuple[list[str], list[list[str | None]]] | None:
    """Find the glucose data table by scanning for header rows with glucose-related keywords.

    Returns (headers, data_rows) or None if no matching table found.
    """
    for table in tables:
        if not table or len(table) < 2:
            continue
        # Check first few rows for a header row
        for row_idx, row in enumerate(table[:5]):
            if not row:
                continue
            row_text = " ".join((cell or "").lower() for cell in row)
            matches = sum(1 for kw in _GLUCOSE_HEADER_KEYWORDS if kw in row_text)
            if matches >= 2:
                headers = [(cell or "").strip() for cell in row]
                data_rows = table[row_idx + 1 :]
                return headers, data_rows
    return None


def _detect_unit_from_headers(headers: list[str]) -> str:
    """Detect glucose unit from header text. Returns 'mg/dl' or 'mmol/l'."""
    joined = " ".join(headers).lower()
    if "mg/dl" in joined:
        return "mg/dl"
    return "mmol/l"


def _build_col_map(headers: list[str]) -> dict[str, int]:
    """Build column index map from header row using substring matching."""
    col_map: dict[str, int] = {}
    for i, h in enumerate(headers):
        h_lower = h.lower()
        if "record type" in h_lower:
            col_map["record_type"] = i
        elif "historic glucose" in h_lower:
            col_map["historic_glucose"] = i
        elif "scan glucose" in h_lower:
            col_map["scan_glucose"] = i
        elif "glucose" in h_lower and "historic" not in h_lower and "scan" not in h_lower:
            # Generic glucose column (fallback)
            if "glucose" not in col_map:
                col_map["glucose"] = i
        elif "time" in h_lower or "timestamp" in h_lower:
            if "device" in h_lower or "timestamp" not in col_map:
                col_map["timestamp"] = i
        elif h_lower == "id":
            col_map["id"] = i
    return col_map


def _parse_timestamp(timestamp_str: str) -> datetime | None:
    """Try multiple timestamp formats, return datetime or None."""
    for fmt in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(timestamp_str)
    except ValueError:
        return None


def _is_glucose_value(value: str) -> bool:
    """Check if a string looks like a numeric glucose value."""
    return bool(re.match(r"^\d+\.?\d*$", value.strip()))


# Regex patterns for Daily Log PDF format
_DAY_HEADER_RE = re.compile(r"(MON|TUE|WED|THU|FRI|SAT|SUN)\s+(\d{1,2})\s+(\w+)")
_MAX_LINE_RE = re.compile(r"Max\s+([\d.\s]+)")
_MIN_LINE_RE = re.compile(r"Min\s+([\d.\s]+)")
_DATE_RANGE_RE = re.compile(r"(\d{1,2}\s+\w+\s+\d{4})\s*-\s*(\d{1,2}\s+\w+\s+\d{4})")

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}


def _parse_daily_log_pdf(
    pages_text: list[str],
    user_id: UUID,
    log: Logger,
    stats: CSVParseStats,
) -> list[TimeSeriesSampleCreate]:
    """Parse a LibreView Daily Log PDF (chart-based with hourly Max/Min summaries).

    These PDFs show daily glucose charts with Max and Min values per hour.
    Each day has a header like "WED 25 Feb" followed by Max/Min lines with 24 hourly values.
    """
    # Extract year from date range header (e.g., "16 February 2026 - 1 March 2026")
    year = None
    full_text = "\n".join(pages_text)
    range_match = _DATE_RANGE_RE.search(full_text)
    if range_match:
        try:
            end_date = datetime.strptime(range_match.group(2), "%d %B %Y")
            year = end_date.year
        except ValueError:
            pass
    if year is None:
        year = datetime.now(timezone.utc).year

    # Detect unit from text
    needs_conversion = "mg/dl" not in full_text.lower()

    # Collect max and min values per (date, hour), then average them into one sample
    # Keys: (date_str, hour) -> {"max": value, "min": value}
    hourly_data: dict[tuple[str, int], dict[str, float]] = {}
    samples: list[TimeSeriesSampleCreate] = []

    for page_text in pages_text:
        lines = page_text.split("\n")
        current_date: datetime | None = None

        for line in lines:
            # Match day header: "WED 25 Feb"
            day_match = _DAY_HEADER_RE.search(line)
            if day_match:
                day_num = int(day_match.group(2))
                month_str = day_match.group(3).lower()
                month_num = _MONTH_MAP.get(month_str)
                if month_num:
                    try:
                        current_date = datetime(year, month_num, day_num, tzinfo=timezone.utc)
                    except ValueError:
                        current_date = None
                continue

            if current_date is None:
                continue

            # Collect Max/Min values per hour
            max_match = _MAX_LINE_RE.match(line.strip())
            min_match = _MIN_LINE_RE.match(line.strip())

            if max_match or min_match:
                match = max_match or min_match
                label = "max" if max_match else "min"
                vals_str = match.group(1).strip().split()
                date_str = current_date.strftime("%Y-%m-%d")

                for hour_idx, val_str in enumerate(vals_str):
                    if hour_idx >= 24:
                        break
                    try:
                        glucose_raw = float(val_str)
                    except ValueError:
                        stats.record_skip("invalid_glucose_value")
                        continue

                    glucose_value = round(glucose_raw * MMOL_TO_MGDL, 1) if needs_conversion else round(glucose_raw, 1)

                    # For partial days, values start from the last hours of the day
                    if len(vals_str) < 24:
                        hour = 24 - len(vals_str) + hour_idx
                    else:
                        hour = hour_idx

                    key = (date_str, hour)
                    if key not in hourly_data:
                        hourly_data[key] = {}
                    hourly_data[key][label] = glucose_value

    # Create one sample per hour using the average of max and min
    for (date_str, hour), values in sorted(hourly_data.items()):
        if not values:
            continue
        avg_value = round(sum(values.values()) / len(values), 1)
        recorded_at = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=hour, tzinfo=timezone.utc)
        external_id = f"libreview_daily_{date_str}_{hour:02d}"

        samples.append(
            TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user_id,
                recorded_at=recorded_at,
                value=avg_value,
                series_type=SeriesType.blood_glucose,
                source="libreview",
                external_id=external_id,
            )
        )
        stats.records_processed += 1

    return samples


def _is_daily_log_pdf(pages_text: list[str]) -> bool:
    """Detect if this is a LibreView Daily Log PDF by looking for characteristic patterns."""
    full_text = "\n".join(pages_text[:2])
    has_daily_log = "Daily Log" in full_text
    has_day_headers = bool(_DAY_HEADER_RE.search(full_text))
    has_glucose_label = "Glucose mmol/L" in full_text or "Glucose mg/dL" in full_text
    return has_daily_log and has_day_headers and has_glucose_label


def parse_libreview_pdf(
    file_contents: bytes,
    user_id: UUID,
    log: Logger,
) -> tuple[list[TimeSeriesSampleCreate], CSVParseStats]:
    """Parse a LibreView PDF report and extract glucose readings.

    Args:
        file_contents: Raw PDF file bytes.
        user_id: User ID to associate samples with.
        log: Logger instance.

    Returns:
        Tuple of (list of samples, parse stats).
    """
    stats = CSVParseStats()
    stats.detected_format = "libreview_pdf"
    samples: list[TimeSeriesSampleCreate] = []

    with pdfplumber.open(io.BytesIO(file_contents)) as pdf:
        all_tables: list[list[list[str | None]]] = []
        pages_text: list[str] = []
        for page in pdf.pages:
            page_tables = page.extract_tables()
            if page_tables:
                all_tables.extend(page_tables)
            pages_text.append(page.extract_text() or "")

    # Try Daily Log format first (chart-based with hourly Max/Min)
    if _is_daily_log_pdf(pages_text):
        stats.detected_format = "libreview_daily_log_pdf"
        log.info("Detected LibreView Daily Log PDF format")
        samples = _parse_daily_log_pdf(pages_text, user_id, log, stats)
        log.info(
            "LibreView Daily Log PDF parse complete: processed=%d, skipped=%d",
            stats.records_processed,
            stats.records_skipped,
        )
        return samples, stats

    if not all_tables:
        log.warning("No tables found in PDF")
        return samples, stats

    result = _find_glucose_table(all_tables)
    if result is None:
        log.warning("No glucose data table found in PDF")
        return samples, stats

    headers, data_rows = result
    col_map = _build_col_map(headers)
    unit = _detect_unit_from_headers(headers)
    needs_conversion = unit != "mg/dl"

    timestamp_col = col_map.get("timestamp")
    historic_glucose_col = col_map.get("historic_glucose")
    scan_glucose_col = col_map.get("scan_glucose")
    generic_glucose_col = col_map.get("glucose")
    record_type_col = col_map.get("record_type")
    id_col = col_map.get("id")

    if timestamp_col is None:
        log.warning("PDF glucose table missing timestamp column")
        return samples, stats

    for row in data_rows:
        if not row or all(not (cell or "").strip() for cell in row):
            continue
        try:
            # Parse timestamp
            if len(row) <= timestamp_col or not (row[timestamp_col] or "").strip():
                stats.record_skip("missing_timestamp")
                continue
            timestamp_str = (row[timestamp_col] or "").strip()
            recorded_at = _parse_timestamp(timestamp_str)
            if recorded_at is None:
                stats.record_skip("invalid_timestamp")
                continue

            # Determine glucose column based on record type (if available)
            glucose_col: int | None = None
            if record_type_col is not None and len(row) > record_type_col:
                record_type = (row[record_type_col] or "").strip()
                if record_type == "0":
                    glucose_col = historic_glucose_col
                elif record_type == "1":
                    glucose_col = scan_glucose_col
                elif record_type:
                    stats.record_skip("unsupported_record_type")
                    continue
            # Fallback: use whichever glucose column has data
            if glucose_col is None:
                for col in (historic_glucose_col, scan_glucose_col, generic_glucose_col):
                    if col is not None and len(row) > col and _is_glucose_value((row[col] or "")):
                        glucose_col = col
                        break

            if glucose_col is None:
                stats.record_skip("missing_glucose_value")
                continue

            # Parse glucose value
            if len(row) <= glucose_col or not (row[glucose_col] or "").strip():
                stats.record_skip("missing_glucose_value")
                continue
            glucose_raw = (row[glucose_col] or "").strip()
            try:
                glucose_mmol = float(glucose_raw)
            except ValueError:
                stats.record_skip("invalid_glucose_value")
                continue

            # Convert mmol/L → mg/dL if needed
            glucose_value = round(glucose_mmol * MMOL_TO_MGDL, 1) if needs_conversion else round(glucose_mmol, 1)

            # External ID for idempotency
            if id_col is not None and len(row) > id_col and (row[id_col] or "").strip():
                external_id = f"libreview_pdf_{(row[id_col] or '').strip()}"
            else:
                external_id = f"libreview_pdf_{timestamp_str}"

            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    recorded_at=recorded_at,
                    value=glucose_value,
                    series_type=SeriesType.blood_glucose,
                    source="libreview",
                    external_id=external_id,
                )
            )
            stats.records_processed += 1

        except Exception:
            log.warning("Failed to parse PDF row", exc_info=True)
            stats.record_skip("parse_error")

    log.info(
        "LibreView PDF parse complete: processed=%d, skipped=%d",
        stats.records_processed,
        stats.records_skipped,
    )
    return samples, stats
