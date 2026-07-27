"""Retries, date/amount parsing, and CSV row helpers."""
import random
import re
import time

import pandas as pd

from availity_app.constants import LINE_LEVEL_CONFIG, OUTPUT_COLUMNS, REQUIRED_COLUMNS
from availity_app.logging_gui import log_to_gui

def retry_with_backoff(action_name, fn, attempts=3, base_delay=0.7, max_delay=4.0, jitter=0.2):
    """Run a transient browser action with bounded retries and exponential backoff.

    Delay formula: delay = min(max_delay, base_delay * 2^(attempt-1)) * jitter_factor
    Jitter (±20% by default) spreads retries to avoid synchronized spikes.
    Raises the last exception when all attempts are exhausted.

    Args:
        action_name: Human-readable label shown in retry log messages.
        fn:          Zero-argument callable to execute.
        attempts:    Maximum number of attempts (first try + retries).
        base_delay:  Wait in seconds before the second attempt.
        max_delay:   Cap on wait time between any two attempts.
        jitter:      Fractional spread added to each delay (e.g. 0.2 = ±20%).
    """
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_error = e
            if attempt >= attempts:
                break
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            if jitter > 0:
                delay *= random.uniform(1 - jitter, 1 + jitter)
            log_to_gui(
                f"  ⚠️ {action_name} failed (attempt {attempt}/{attempts}): {e}. "
                f"Retrying in {delay:.2f}s...\n",
                "error",
            )
            time.sleep(delay)
    raise last_error


# ============================================================================
# SECTION 4 — DATE AND AMOUNT UTILITIES
# ============================================================================

def normalize_date(date_str):
    """Zero-pad a date to MM/DD/YYYY for consistent string comparison.

    Availity renders dates as M/D/YYYY; CSVs may use either format.
    Normalising both sides before comparing prevents false mismatches.
    Returns the original string unchanged if it cannot be parsed.
    """
    try:
        parts = str(date_str).strip().split('/')
        if len(parts) == 3:
            return f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2]}"
        return date_str
    except Exception:
        return date_str


def scalar_cell(val, default=None):
    """Reduce a spreadsheet cell to a scalar safe for ``if`` checks and ``pd.isna``."""
    if val is None:
        return default
    if isinstance(val, pd.Series):
        if val.empty:
            return default
        val = val.iloc[0]
    if isinstance(val, (pd.DataFrame, pd.Index)):
        return default
    try:
        if pd.isna(val):
            return default
    except (ValueError, TypeError):
        pass
    return val


def coerce_visit_date(visit_date, default=''):
    """Return a scalar visit-date string safe for truthiness and normalization."""
    val = scalar_cell(visit_date, default=None)
    if val is None:
        return default
    text = str(val).strip()
    if not text or text.lower() == 'nan':
        return default
    return text


_SLASH_DATE_RE = re.compile(r'(\d{1,2}/\d{1,2}/\d{4})')


def parse_service_date_range(text):
    """Extract 'MM/DD/YYYY-MM/DD/YYYY' from Availity line-level cell text.

    Handles a single date, two slash-dates separated by hyphen/space/newline
    (e.g. ``12/25/2024-01/17/2025``), and ISO timestamps from Excel.
    """
    if text is None:
        return None
    s = str(scalar_cell(text, default='')).strip()
    if not s or s.lower() == 'nan':
        return None

    dates = _SLASH_DATE_RE.findall(s)
    if dates:
        start = normalize_date(dates[0])
        end = normalize_date(dates[-1])
        return f"{start}-{end}"

    try:
        dt = pd.to_datetime(s, errors='coerce')
        if pd.notna(dt):
            d = dt.strftime('%m/%d/%Y')
            return f"{d}-{d}"
    except Exception:
        pass
    return None


def normalize_date_range(date_str):
    """Normalise a date or date-range string to 'MM/DD/YYYY-MM/DD/YYYY'.

    The line-level table uses ranges (e.g. '1/1/2026-1/31/2026').
    A single date is treated as a range where start == end.
    """
    try:
        date_str = scalar_cell(date_str, default='')
        s = str(date_str).strip()
        if not s:
            return s
        parsed = parse_service_date_range(s)
        if parsed:
            return parsed
        n = normalize_date(s)
        return f"{n}-{n}"
    except Exception:
        return date_str


def _parse_normalized_date(date_str):
    """Parse a normalised MM/DD/YYYY string to a comparable datetime."""
    try:
        bounds = _line_range_bounds(str(date_str))
        if bounds is None:
            return None
        start, _ = bounds
        dt = pd.to_datetime(start, format='%m/%d/%Y')
        if pd.notna(dt):
            return dt.to_pydatetime()
    except Exception:
        pass
    return None


def _line_range_bounds(line_range):
    """Return (start, end) MM/DD/YYYY strings parsed from a line date range."""
    parsed = parse_service_date_range(line_range)
    if not parsed:
        return None
    start, _, end = parsed.partition('-')
    if not start or not end:
        return None
    return start, end


def visit_date_matches_line(target_range, line_range, match_mode='exact'):
    """Return True when a CSV VisitDate range matches a line's service date range.

    Both arguments are normalised ``MM/DD/YYYY-MM/DD/YYYY`` strings.
    ``match_mode`` options:
      ``exact`` — normalised ranges must be equal (e.g. VisitDate ``01/03/2025``
                  matches line ``01/03/2025-01/03/2025``).
      ``within_range`` — the visit date may fall anywhere inside the line's
                         service range (e.g. VisitDate ``01/08/2025`` matches
                         bundle line ``12/25/2025-01/08/2025``).
      ``contains`` — legacy: visit date equals either bound of the line range.
    """
    target_norm = normalize_date_range(coerce_visit_date(target_range))
    line_norm = normalize_date_range(coerce_visit_date(line_range))
    if not line_norm or not target_norm:
        return False
    if match_mode == 'exact':
        return line_norm == target_norm
    if match_mode == 'within_range':
        visit_dt = _parse_normalized_date(target_norm)
        bounds = _line_range_bounds(line_norm)
        if visit_dt is None or bounds is None:
            return False
        line_start, line_end = bounds
        start_dt = pd.to_datetime(line_start, format='%m/%d/%Y').to_pydatetime()
        end_dt = pd.to_datetime(line_end, format='%m/%d/%Y').to_pydatetime()
        if start_dt > end_dt:
            start_dt, end_dt = end_dt, start_dt
        return start_dt <= visit_dt <= end_dt
    if line_norm == target_norm:
        return True
    target_bounds = _line_range_bounds(target_norm)
    line_bounds = _line_range_bounds(line_norm)
    if not target_bounds or not line_bounds:
        return False
    target_start, target_end = target_bounds
    line_start, line_end = line_bounds
    if target_start in (line_start, line_end):
        return True
    return target_end in (line_start, line_end)


def resolve_line_level_config(payer_config=None):
    """Merge global LINE_LEVEL_CONFIG with optional per-payer ``line_level`` overrides."""
    cfg = dict(LINE_LEVEL_CONFIG)
    if payer_config:
        cfg.update(payer_config.get('line_level', {}))
    return cfg


def filter_line_rows_by_visit_date(line_rows, visit_date, cfg=None, payer_config=None):
    """Filter scraped line-row dicts to those matching ``visit_date``.

    Each row dict must include a ``date_range`` key.  When
    ``filter_by_visit_date`` is False in config, returns all rows unchanged.

    Matching order when ``match_mode`` is ``exact`` (default):
      1. Exact service-date range match
      2. If ``fallback_within_range`` is True and step 1 found nothing,
         match VisitDate inside a multi-day line range (bundle claims)
      3. If ``fallback_to_sole_line`` is True and only one line exists, use it
    """
    cfg = cfg or resolve_line_level_config(payer_config)
    if not cfg.get('filter_by_visit_date', True):
        return list(line_rows)

    visit_date = coerce_visit_date(visit_date)
    if not visit_date:
        return list(line_rows)

    target = normalize_date_range(visit_date)
    match_mode = cfg.get('match_mode', 'exact')
    if match_mode == 'within_range':
        matches = [
            entry for entry in line_rows
            if visit_date_matches_line(target, entry['date_range'], 'within_range')
        ]
    else:
        matches = [
            entry for entry in line_rows
            if visit_date_matches_line(target, entry['date_range'], 'exact')
        ]
        if not matches and cfg.get('fallback_within_range'):
            range_matches = [
                entry for entry in line_rows
                if visit_date_matches_line(target, entry['date_range'], 'within_range')
            ]
            if range_matches:
                log_to_gui(
                    f"    ℹ️ No exact line match for VisitDate {target}; "
                    f"using within-range fallback ({len(range_matches)} row(s))\n",
                    "info",
                )
                matches = range_matches
            else:
                scraped = ', '.join(
                    normalize_date_range(row['date_range']) for row in line_rows
                )
                log_to_gui(
                    f"    ℹ️ Within-range fallback: no line contains VisitDate "
                    f"{target} (scraped: {scraped})\n",
                    "info",
                )

    if not matches and cfg.get('fallback_to_sole_line') and len(line_rows) == 1:
        only = line_rows[0]
        log_to_gui(
            f"    ℹ️ VisitDate {target} did not match line dates "
            f"({only['date_range']}); using sole service line\n",
            "info",
        )
        return [only]
    return matches


_INVALID_DATE_MARKERS = frozenset({
    '--', '-', 'n/a', 'na', 'none', 'null', 'unknown', 'tbd', '#n/a',
    'notfound', 'missing', 'dob nf', 'dob n/a',
})


def _is_invalid_date_marker(date_str):
    """True when a spreadsheet cell is a placeholder, not a real date."""
    s = re.sub(r'\s+', ' ', str(date_str).strip().lower())
    if not s or s == 'nan':
        return True
    if s in _INVALID_DATE_MARKERS:
        return True
    return 'not found' in s


def normalize_dob(dob_str):
    """Normalize DOB to MM/DD/YYYY for Availity form input.

    Handles common CSV quirks:
    - ISO/Timestamp-like values (e.g. 1969-05-11, 1969-05-11 00:00:00)
    - Excel serial dates
    - 3-digit years where leading '1' is dropped (e.g. 05/11/969)
    """
    s = str(dob_str).strip()
    if _is_invalid_date_marker(s):
        return ''

    # Excel date serial (days from 1899-12-30)
    if s.isdigit() and len(s) <= 5:
        try:
            dt = pd.to_datetime('1899-12-30') + pd.to_timedelta(int(s), unit='D')
            return dt.strftime('%m/%d/%Y')
        except Exception:
            pass

    # Heuristic for malformed year like 05/11/969 -> 05/11/1969
    try:
        parts = s.replace('-', '/').split('/')
        if len(parts) == 3:
            mm, dd, yy = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if len(yy) == 3 and yy.isdigit():
                s = f"{mm}/{dd}/1{yy}"
    except Exception:
        pass

    try:
        dt = pd.to_datetime(s, errors='coerce')
        if pd.notna(dt):
            return dt.strftime('%m/%d/%Y')
    except Exception:
        pass

    result = normalize_date(s)
    if _is_invalid_date_marker(result) or not re.match(r'^\d{2}/\d{2}/\d{4}$', result):
        return ''
    return result


def normalize_search_date(date_str):
    """Normalize a service/visit date for Availity search; return '' if unusable."""
    if _is_invalid_date_marker(date_str):
        return ''
    result = normalize_dob(date_str)
    if not result or _is_invalid_date_marker(result):
        return ''
    if not re.match(r'^\d{2}/\d{2}/\d{4}$', result):
        return ''
    return result


def row_has_valid_dob(row_data, safe_field_fn):
    """True when the row has a parseable DOB for the Availity search form."""
    raw = safe_field_fn(row_data, 'DOB')
    if _is_invalid_date_marker(raw):
        return False
    return bool(normalize_dob(raw))


def service_dates_cross_year(from_date, to_date):
    """True when service From and To fall in different calendar years."""
    from_parts = split_date_parts(from_date)
    to_parts = split_date_parts(to_date)
    if not from_parts or not to_parts:
        return False
    return from_parts[2] != to_parts[2]


def service_date_fill_plans(from_date, to_date):
    """Ordered fill plans for MUI service-date range pickers.

    Each plan is a dict with:
      mode  — 'robust' | 'year_first' | 'hidden_input'
      order — ('from', 'to') or ('to', 'from') field fill sequence
    """
    cross = service_dates_cross_year(from_date, to_date)
    if cross:
        plans = [
            {'mode': 'robust', 'order': ('to', 'from')},
            {'mode': 'robust', 'order': ('from', 'to')},
            {'mode': 'year_first', 'order': ('to', 'from')},
        ]
        hidden_orders = [('to', 'from'), ('from', 'to')]
    else:
        plans = [
            {'mode': 'robust', 'order': ('to', 'from')},
            {'mode': 'robust', 'order': ('from', 'to')},
        ]
        hidden_orders = [('to', 'from'), ('from', 'to')]
    for order in hidden_orders:
        plans.append({'mode': 'hidden_input', 'order': order})
    return plans


def resolve_service_search_dates(row_data, safe_field_fn):
    """Return (start_date, end_date) for the claim search form.

    Uses StartDate/EndDate when valid; falls back to VisitDate; mirrors a single
    date to both ends when only one bound is present.
    """
    start = normalize_search_date(safe_field_fn(row_data, 'StartDate'))
    end = normalize_search_date(safe_field_fn(row_data, 'EndDate'))
    visit = normalize_search_date(safe_field_fn(row_data, 'VisitDate'))
    if not start and visit:
        start = visit
    if not end and visit:
        end = visit
    if start and not end:
        end = start
    if end and not start:
        start = end
    return start, end


def split_date_parts(date_str):
    """Split a date into (mm, dd, yyyy) zero-padded strings for MUI spinbutton entry."""
    s = str(date_str).strip()
    if not s or s.lower() == 'nan' or _is_invalid_date_marker(s):
        return None

    # Always parse through pandas first — avoids YYYY-MM-DD read as MM/DD/YY.
    try:
        dt = pd.to_datetime(s, errors='coerce')
        if pd.notna(dt):
            return dt.strftime('%m'), dt.strftime('%d'), dt.strftime('%Y')
    except Exception:
        pass

    normalized = normalize_dob(s)
    if normalized and normalized != s:
        try:
            dt = pd.to_datetime(normalized, errors='coerce')
            if pd.notna(dt):
                return dt.strftime('%m'), dt.strftime('%d'), dt.strftime('%Y')
        except Exception:
            pass
        s = normalized

    if '/' in s:
        parts = s.split('/')
        if len(parts) == 3:
            mm, dd, yy = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if mm.isdigit() and dd.isdigit() and yy.isdigit() and int(mm) <= 12 and int(dd) <= 31:
                if len(yy) == 2:
                    yy = f'19{yy}' if int(yy) > 50 else f'20{yy}'
                return mm.zfill(2), dd.zfill(2), yy.zfill(4)

    digits = ''.join(c for c in s if c.isdigit())
    if len(digits) == 8:
        mm, dd, yyyy = digits[0:2], digits[2:4], digits[4:8]
        if int(mm) <= 12 and int(dd) <= 31:
            return mm, dd, yyyy
    return None


def parse_amount(amount_str):
    """Parse a currency string like '$1,234.50' to float, or None if blank.

    Returns None for empty cells or '--' so callers can distinguish
    "zero dollars paid" from "value not available".
    """
    try:
        cleaned = str(amount_str).strip().replace('$', '').replace(',', '')
        if cleaned in ('', '--'):
            return None
        return float(cleaned)
    except Exception:
        return None


# ============================================================================
# SECTION 5 — DATA SAFETY HELPERS
# ============================================================================

def format_invoice_number(value, default=''):
    """Normalize InvoiceNumber from Excel (float/int/str) to an integer string.

    Excel often stores invoice numbers as floats (e.g. 12345.0); this converts
    them to '12345' for search matching and display.
    """
    if pd.isna(value):
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:  # NaN
            return default
        if value == int(value):
            return str(int(value))
        return str(value).strip().rstrip('0').rstrip('.') if '.' in str(value) else str(int(value))

    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return default

    try:
        as_float = float(text.replace(',', ''))
        if as_float == int(as_float):
            return str(int(as_float))
    except ValueError:
        pass

    try:
        return str(int(text.replace(',', '')))
    except ValueError:
        return text


def safe_invoice_number(row_data, key='InvoiceNumber', default=''):
    """Return InvoiceNumber as an integer string suitable for claim search."""
    try:
        return format_invoice_number(row_data[key], default)
    except Exception:
        return default


def safe_alt_patient_id(row_data, key='AltPatientID', default=''):
    """Return AltPatientID without Excel float artifacts (e.g. 12345.0 → 12345)."""
    try:
        return format_invoice_number(row_data[key], default)
    except Exception:
        return default


def normalize_invoice_column(df):
    """Coerce InvoiceNumber and AltPatientID to clean strings after Excel load."""
    if 'InvoiceNumber' in df.columns:
        df['InvoiceNumber'] = df['InvoiceNumber'].apply(
            lambda v: format_invoice_number(v) if pd.notna(v) else v
        )
    if 'AltPatientID' in df.columns:
        df['AltPatientID'] = df['AltPatientID'].apply(
            lambda v: format_invoice_number(v) if pd.notna(v) else v
        )
    return df


def aggregate_invoice_visit_date_range(df, invoice_number):
    """Min–max VisitDate range for all collection rows sharing an invoice.

    Used when bundle claims omit the invoice number on the results table.
    Returns normalized ``MM/DD/YYYY-MM/DD/YYYY`` or None if no valid VisitDate.
    """
    if not invoice_number or 'InvoiceNumber' not in df.columns:
        return None
    if 'VisitDate' not in df.columns:
        return None

    target_invoice = format_invoice_number(invoice_number)
    if not target_invoice:
        return None

    parsed = []
    for _, row in df.iterrows():
        if format_invoice_number(row.get('InvoiceNumber', ''), '') != target_invoice:
            continue
        normalized = normalize_search_date(row.get('VisitDate', ''))
        if not normalized:
            continue
        try:
            dt = pd.to_datetime(normalized, format='%m/%d/%Y')
            if pd.notna(dt):
                parsed.append(dt)
        except Exception:
            continue

    if not parsed:
        return None

    min_dt = min(parsed)
    max_dt = max(parsed)
    start = min_dt.strftime('%m/%d/%Y')
    end = max_dt.strftime('%m/%d/%Y')
    return normalize_date_range(f"{start}-{end}")


def resolve_bundle_search_dates(df, invoice_number):
    """Return (start_date, end_date) for claim search from invoice VisitDate bundle.

    Aggregates min–max VisitDate across all spreadsheet rows sharing the invoice.
    Returns ('', '') when no valid bundle range exists.
    """
    target_range = aggregate_invoice_visit_date_range(df, invoice_number)
    if not target_range:
        return '', ''
    parsed = parse_service_date_range(target_range)
    if not parsed:
        return '', ''
    start, _, end = parsed.partition('-')
    start = start.strip()
    end = end.strip()
    if not start or not end:
        return '', ''
    return start, end


def normalize_name_part(name_str):
    """Drop single-character tokens (e.g. middle initials) from a name part."""
    text = str(name_str).strip()
    if not text:
        return ''
    tokens = text.split()
    kept = [t for t in tokens if len(t.rstrip('.')) > 1]
    if not kept:
        return text
    return ' '.join(kept)


def normalize_patient_names(last_name, first_name):
    """Normalize last/first names for Availity claim search form fill."""
    return normalize_name_part(last_name), normalize_name_part(first_name)


def safe_field(row_data, key, default=''):
    """Return a stripped string for a pandas row field, converting NaN to default.

    Without this, missing Excel values become the literal string 'nan' which
    would be typed verbatim into Availity form fields and produce bad results.
    """
    try:
        val = scalar_cell(row_data[key])
        if val is None:
            return default
        return str(val).strip()
    except Exception:
        return default


def validate_dataframe(df):
    """Return list of REQUIRED_COLUMNS that are absent in df.

    An empty list means the dataframe is valid.  A non-empty list means
    the batch should be aborted with a clear error before any rows are processed.
    """
    return [col for col in REQUIRED_COLUMNS if col not in df.columns]


def empty_claim_result(status='Not found'):
    """Return a dict with all OUTPUT_COLUMNS set to '--' except Claim Status.

    Used as a placeholder when a row cannot be processed, ensuring the
    output CSV always has a complete and consistent set of columns.
    """
    return {
        'Claim ID':       '--',
        'Billed Amount':  '--',
        'Paid Amount':    '--',
        'Claim Status':   status,
        'Denial Reason':  '--',
        'Finalized Date': '--',
        'Check Number':   '--',
        'Check Date':     '--',
    }
