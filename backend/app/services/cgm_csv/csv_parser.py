import csv
import io
from datetime import datetime
from logging import Logger
from uuid import UUID, uuid4

from app.schemas.series_types import SeriesType
from app.schemas.timeseries import TimeSeriesSampleCreate
from app.services.cgm_csv.pdf_parser import parse_libreview_pdf
from app.services.cgm_csv.stats import CSVParseStats

# Dexcom boundary values
DEXCOM_LOW_MG_DL = 40
DEXCOM_HIGH_MG_DL = 400

# mmol/L to mg/dL conversion factor
MMOL_TO_MGDL = 18.0182


def detect_format(lines: list[str]) -> str:
    """Detect CSV format from the first ~20 lines.

    Returns:
        "dexcom_clarity" or "libreview"

    Raises:
        ValueError: If format cannot be determined.
    """
    for line in lines[:20]:
        if "Glucose Value (mg/dL)" in line and "Event Type" in line:
            return "dexcom_clarity"
        if "Record Type" in line and "Historic Glucose" in line:
            return "libreview"
    raise ValueError(
        "Unrecognized CSV format. Expected Dexcom Clarity or LibreView CSV. "
        "Could not find expected column headers in the first 20 lines."
    )


def _find_header_row(lines: list[str]) -> tuple[int, list[str]]:
    """Find the header row in a Dexcom Clarity CSV (variable metadata rows)."""
    for i, line in enumerate(lines):
        if "Glucose Value (mg/dL)" in line and "Event Type" in line:
            reader = csv.reader(io.StringIO(line))
            headers = next(reader)
            return i, [h.strip() for h in headers]
    raise ValueError("Could not find Dexcom Clarity header row")


def _parse_dexcom_clarity(
    csv_content: str,
    user_id: UUID,
    log: Logger,
    stats: CSVParseStats,
) -> list[TimeSeriesSampleCreate]:
    """Parse Dexcom Clarity CSV export."""
    lines = csv_content.splitlines()
    header_idx, headers = _find_header_row(lines)

    # Build column index map
    col_map: dict[str, int] = {}
    for i, h in enumerate(headers):
        col_map[h] = i

    timestamp_col = col_map.get("Timestamp (YYYY-MM-DDThh:mm:ss)")
    event_type_col = col_map.get("Event Type")
    glucose_col = col_map.get("Glucose Value (mg/dL)")

    if timestamp_col is None or event_type_col is None or glucose_col is None:
        raise ValueError("Dexcom Clarity CSV missing required columns")

    samples: list[TimeSeriesSampleCreate] = []
    data_lines = lines[header_idx + 1 :]
    reader = csv.reader(io.StringIO("\n".join(data_lines)))

    for row in reader:
        if not row or all(c.strip() == "" for c in row):
            continue
        try:
            # Only process EGV (estimated glucose value) rows
            if len(row) <= event_type_col:
                stats.record_skip("missing_event_type")
                continue
            event_type = row[event_type_col].strip()
            if event_type != "EGV":
                stats.record_skip("unsupported_event_type")
                continue

            # Parse timestamp
            if len(row) <= timestamp_col or not row[timestamp_col].strip():
                stats.record_skip("missing_timestamp")
                continue
            timestamp_str = row[timestamp_col].strip()
            try:
                recorded_at = datetime.fromisoformat(timestamp_str)
            except ValueError:
                stats.record_skip("invalid_timestamp")
                continue

            # Parse glucose value
            if len(row) <= glucose_col or not row[glucose_col].strip():
                stats.record_skip("missing_glucose_value")
                continue
            glucose_raw = row[glucose_col].strip()

            if glucose_raw == "Low":
                glucose_value = float(DEXCOM_LOW_MG_DL)
            elif glucose_raw == "High":
                glucose_value = float(DEXCOM_HIGH_MG_DL)
            else:
                try:
                    glucose_value = float(glucose_raw)
                except ValueError:
                    stats.record_skip("invalid_glucose_value")
                    continue

            external_id = f"dexcom_clarity_{timestamp_str}"

            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    recorded_at=recorded_at,
                    value=glucose_value,
                    series_type=SeriesType.blood_glucose,
                    source="dexcom_clarity",
                    external_id=external_id,
                )
            )
            stats.records_processed += 1

        except Exception:
            log.warning("Failed to parse Dexcom Clarity row", exc_info=True)
            stats.record_skip("parse_error")

    return samples


def _parse_libreview(
    csv_content: str,
    user_id: UUID,
    log: Logger,
    stats: CSVParseStats,
) -> list[TimeSeriesSampleCreate]:
    """Parse LibreView CSV export."""
    lines = csv_content.splitlines()
    if len(lines) < 3:
        raise ValueError("LibreView CSV too short — expected at least 3 lines")

    # Line 1: patient metadata (skip)
    # Line 2: column headers (use substring matching for locale variation)
    header_line = lines[1]
    reader = csv.reader(io.StringIO(header_line))
    headers = [h.strip() for h in next(reader)]

    # Build column index map using substring matching
    col_map: dict[str, int] = {}
    for i, h in enumerate(headers):
        h_lower = h.lower()
        if "record type" in h_lower:
            col_map["record_type"] = i
        elif "historic glucose" in h_lower:
            col_map["historic_glucose"] = i
        elif "scan glucose" in h_lower:
            col_map["scan_glucose"] = i
        elif "timestamp" in h_lower or "time" == h_lower or h_lower == "device timestamp":
            # Prefer device timestamp but fall back to any timestamp-like column
            if "device timestamp" in h_lower or "timestamp" not in col_map:
                col_map["timestamp"] = i
        elif h_lower == "id":
            col_map["id"] = i

    record_type_col = col_map.get("record_type")
    historic_glucose_col = col_map.get("historic_glucose")
    scan_glucose_col = col_map.get("scan_glucose")
    timestamp_col = col_map.get("timestamp")
    id_col = col_map.get("id")

    if record_type_col is None or timestamp_col is None:
        raise ValueError("LibreView CSV missing required columns (Record Type, timestamp)")

    samples: list[TimeSeriesSampleCreate] = []
    data_lines = lines[2:]
    data_reader = csv.reader(io.StringIO("\n".join(data_lines)))

    for row in data_reader:
        if not row or all(c.strip() == "" for c in row):
            continue
        try:
            if len(row) <= record_type_col:
                stats.record_skip("missing_record_type")
                continue
            record_type = row[record_type_col].strip()

            # Determine which glucose column to use
            if record_type == "0":
                glucose_col = historic_glucose_col
            elif record_type == "1":
                glucose_col = scan_glucose_col
            else:
                stats.record_skip("unsupported_record_type")
                continue

            if glucose_col is None:
                stats.record_skip("missing_glucose_value")
                continue

            # Parse timestamp
            if len(row) <= timestamp_col or not row[timestamp_col].strip():
                stats.record_skip("missing_timestamp")
                continue
            timestamp_str = row[timestamp_col].strip()
            try:
                # LibreView uses various timestamp formats
                for fmt in ("%d-%m-%Y %H:%M", "%m-%d-%Y %H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        recorded_at = datetime.strptime(timestamp_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    # Final fallback: try ISO format
                    recorded_at = datetime.fromisoformat(timestamp_str)
            except ValueError:
                stats.record_skip("invalid_timestamp")
                continue

            # Parse glucose value
            if len(row) <= glucose_col or not row[glucose_col].strip():
                stats.record_skip("missing_glucose_value")
                continue
            glucose_raw = row[glucose_col].strip()
            try:
                glucose_mmol = float(glucose_raw)
            except ValueError:
                stats.record_skip("invalid_glucose_value")
                continue

            # Convert mmol/L → mg/dL
            glucose_value = round(glucose_mmol * MMOL_TO_MGDL, 1)

            # External ID from ID column or fallback to timestamp
            if id_col is not None and len(row) > id_col and row[id_col].strip():
                external_id = f"libreview_{row[id_col].strip()}"
            else:
                external_id = f"libreview_{timestamp_str}"

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
            log.warning("Failed to parse LibreView row", exc_info=True)
            stats.record_skip("parse_error")

    return samples


def parse_cgm_csv(
    csv_content: str,
    user_id: UUID,
    log: Logger,
) -> tuple[list[TimeSeriesSampleCreate], CSVParseStats]:
    """Parse a CGM CSV file (auto-detects Dexcom Clarity or LibreView format).

    Args:
        csv_content: The full CSV file content as a string.
        user_id: User ID to associate samples with.
        log: Logger instance.

    Returns:
        Tuple of (list of samples, parse stats).

    Raises:
        ValueError: If the CSV format cannot be detected.
    """
    stats = CSVParseStats()
    lines = csv_content.splitlines()
    fmt = detect_format(lines)
    stats.detected_format = fmt

    if fmt == "dexcom_clarity":
        samples = _parse_dexcom_clarity(csv_content, user_id, log, stats)
    else:
        samples = _parse_libreview(csv_content, user_id, log, stats)

    log.info(
        "CGM CSV parse complete: format=%s, processed=%d, skipped=%d",
        fmt,
        stats.records_processed,
        stats.records_skipped,
    )
    return samples, stats


def _decode_csv(file_contents: bytes) -> str:
    """Decode CSV bytes with encoding fallback: UTF-8 → UTF-8-SIG → Latin-1."""
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return file_contents.decode(encoding)
        except (UnicodeDecodeError, ValueError):
            continue
    raise ValueError("Unable to decode CSV file with supported encodings (UTF-8, UTF-8-SIG, Latin-1)")


def parse_cgm_file(
    file_contents: bytes,
    filename: str,
    user_id: UUID,
    log: Logger,
) -> tuple[list[TimeSeriesSampleCreate], CSVParseStats]:
    """Parse a CGM file (CSV or PDF), auto-detecting format.

    Args:
        file_contents: Raw file bytes.
        filename: Original filename (used to detect PDF vs CSV).
        user_id: User ID to associate samples with.
        log: Logger instance.

    Returns:
        Tuple of (list of samples, parse stats).
    """
    if filename.lower().endswith(".pdf"):
        return parse_libreview_pdf(file_contents, user_id, log)
    csv_content = _decode_csv(file_contents)
    return parse_cgm_csv(csv_content, user_id, log)
