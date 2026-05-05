import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import pandas as pd
import threading
import time
import random
from datetime import datetime
import traceback
from playwright.sync_api import sync_playwright


# ============================================================================
# SECTION 1 — GLOBAL STATE
# ============================================================================
# `is_running` is a cooperative stop flag shared between the GUI thread
# (which sets it to False on Stop) and the background worker (which reads
# it between rows).  A threading.Event would be marginally cleaner, but
# this is simple enough for a single flag with a single writer.

is_running        = False
current_playwright = None   # kept here so cleanup_browser() can always stop it


# ============================================================================
# SECTION 2 — CONFIGURATION
# ============================================================================

# ---------------------------------------------------------------------------
# CSS / XPath selectors
# ---------------------------------------------------------------------------
# All selectors live here so a UI change only requires editing this block —
# no hunting through business logic.  Keys with a `_selectors` suffix hold
# lists of fallback selectors tried in order.

SELECTORS = {
    # The SPA renders content inside a named iframe
    'iframe':           'iframe#newBodyFrame',

    # Claim search form fields
    'member_id':        '#subscriberMemberId',
    'last_name':        '#patientLastName',
    'first_name':       '#patientFirstName',
    'dob':              '#patientBirthDate',
    'date_from':        '#fromDate',
    'date_to':          '#toDate',
    'submit_btn':       '#submit-by276',

    # Result and detail tables
    'results_table':    '#claimsTable',
    'line_table':       '#lineLevelTable',
    'codes_table':      '#codesTable',

    # Claim detail info panels (data-testid attributes set by the SPA)
    'claim_id_panel':       '[data-testid="testClaim NumberPanel"] p.text-right',
    'claim_status_panel':   '[data-testid="testClaim StatusPanel"] span.badge',
    'finalized_date_panel': '[data-testid="testFinalized DatePanel"] p.text-right',
    'check_number_panel':   '[data-testid="testCheck NumberPanel"] p.text-right',
    'check_date_panel':     '[data-testid="testCheck DatePanel"] p.text-right',

    # Billed / Paid panels — Availity uses inconsistent attribute casing
    # across deployments, so we supply multiple fallback selectors for each.
    'billed_amount_selectors': [
        '[data-testid="testBilled AmountPanel"] p.text-right',
        '[data-testid="testBilledAmountPanel"] p.text-right',
        'xpath=//*[contains(@data-testid,"Billed") and contains(@data-testid,"Panel")]'
        '//p[contains(@class,"text-right")]',
    ],
    'paid_amount_selectors': [
        '[data-testid="testPaid AmountPanel"] p.text-right',
        '[data-testid="testPaidAmountPanel"] p.text-right',
        'xpath=//*[contains(@data-testid,"Paid") and contains(@data-testid,"Panel")]'
        '//p[contains(@class,"text-right")]',
    ],

    # HIPAA Standard tab shown on Healthfirst / Integra after navigation
    'hipaa_tab':        'a[id="HIPAA Standard"][role="button"]',

    # Remittance viewer elements (Villagecaremax only)
    'remit_claim_tab':    'a.nav-link:has(span:has-text("Claim"))',
    'remit_search_input': '#claimSearchInput',
    'remit_search_btn':   '#claimSearchButton',
    'remit_table':        'div[role="table"][aria-label="Remits"]',
    'remit_adj_table':    'table[aria-label="Adjustments"]',
}

# ---------------------------------------------------------------------------
# Payer configuration table
# ---------------------------------------------------------------------------
# TO ADD A NEW PAYER — only two steps are needed:
#   1. Add an entry to PAYER_CONFIG with the keys described below.
#   2. Done.  The dropdown, navigation, extraction, and denial logic all
#      read from this dict, so no other code changes are required.
#
# Config keys:
#   url              — Availity page URL for this payer's claim search
#   uses_hipaa_tab   — whether to click the HIPAA Standard tab after load
#   uses_line_level  — whether to scrape line-level service-date rows for
#                      billed/paid amounts (False = read from header panels)
#   uses_remittance  — whether to open the remittance viewer for denial
#                      reasons (True = Villagecaremax path)

PAYER_CONFIG = {
    'Healthfirst': {
        'url': (
            "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/"
            "#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2Fenhanced-claim-status-ui%2F"
            "%23%2Fdashboard%3ForgId%3D34974655%26payerId%3D80141T%26activeTab%3Dby276"
        ),
        'uses_hipaa_tab':  True,
        'uses_line_level': True,
        'uses_remittance': False,
    },
    'Integra': {
        'url': (
            "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/"
            "#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2Fenhanced-claim-status-ui%2F"
            "%23%2Fdashboard%3ForgId%3D34974655%26payerId%3D80141T%26activeTab%3Dby276"
        ),
        'uses_hipaa_tab':  True,
        'uses_line_level': True,
        'uses_remittance': False,
    },
    'Villagecaremax': {
        'url': (
            "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/"
            "#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2Fenhanced-claim-status-ui%2F"
            "%23%2Fdashboard%3ForgId%3D34974655%26payerId%3D26545"
        ),
        'uses_hipaa_tab':  False,
        'uses_line_level': False,
        'uses_remittance': True,
    },
}

REMITTANCE_URLS = {
    'search': (
        "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/"
        "#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Frm%2Fremitviewerui%2F"
    ),
    # Navigate here after reading denial data to reset the remit viewer state
    'home': (
        "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/"
        "#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Frm%2Fremitviewerui%2F%23%2F"
    ),
}

# Columns that MUST exist in the input CSV before any processing starts.
# validate_dataframe() checks these and aborts early if any are absent.
REQUIRED_COLUMNS = [
    'AltPatientID', 'PatientName', 'DOB',
    'StartDate', 'EndDate', 'InvoiceNumber', 'VisitDate',
]

# Columns appended to the dataframe to hold automation output.
OUTPUT_COLUMNS = [
    'Claim ID', 'Billed Amount', 'Paid Amount', 'Claim Status',
    'Denial Reason', 'Finalized Date', 'Check Number', 'Check Date',
]

# Error labels written into Claim Status when a row cannot be processed.
# Used by _record_error() to build the end-of-batch summary.
KNOWN_ERROR_STATUSES = frozenset({
    'Navigation failed', 'Form error', 'Search failed',
    'No claims found. Advised to search manually',
    'Claim not found. Search manually', 'Critical error',
    'Missing InvoiceNumber', 'Error',
})


# ============================================================================
# SECTION 3 — RETRY / BACKOFF UTILITY
# ============================================================================

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


def normalize_date_range(date_str):
    """Normalise a date or date-range string to 'MM/DD/YYYY-MM/DD/YYYY'.

    The line-level table uses ranges (e.g. '1/1/2026-1/31/2026').
    A single date is treated as a range where start == end.
    """
    try:
        s = str(date_str).strip()
        if '-' in s:
            left, right = s.split('-', 1)
            return f"{normalize_date(left)}-{normalize_date(right)}"
        n = normalize_date(s)
        return f"{n}-{n}"
    except Exception:
        return date_str


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

def safe_field(row_data, key, default=''):
    """Return a stripped string for a pandas row field, converting NaN to default.

    Without this, missing CSV values become the literal string 'nan' which
    would be typed verbatim into Availity form fields and produce bad results.
    """
    try:
        val = row_data[key]
        if pd.isna(val):
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


# ============================================================================
# SECTION 6 — BROWSER MANAGEMENT
# ============================================================================

def setup_browser():
    """Connect to a running Chrome instance via CDP and return its first page.

    Chrome must already be running with remote debugging enabled:
        chrome.exe --remote-debugging-port=9222

    Raises PlaywrightError if the browser is not reachable at that port.
    """
    global current_playwright
    current_playwright = sync_playwright().start()
    browser  = current_playwright.chromium.connect_over_cdp("http://localhost:9222")
    context  = browser.contexts[0]
    # Reuse the existing open tab rather than forcing a new blank one
    return context.pages[0] if context.pages else context.new_page()


def cleanup_browser():
    """Stop the Playwright connection.  Safe to call even if setup never ran."""
    global current_playwright
    if current_playwright:
        try:
            current_playwright.stop()
        except Exception as e:
            log_to_gui(f"  ⚠️ Browser cleanup error: {e}\n", "error")
        finally:
            current_playwright = None


# ============================================================================
# SECTION 7 — CSV / FILE OPERATIONS
# ============================================================================

def load_csv(file_path):
    """Load the input CSV and split PatientName into Last_Name / First_Name.

    PatientName is expected in 'LastName, FirstName' format.
    Returns a DataFrame on success, or None (with a GUI error dialog) on failure.
    """
    try:
        df = pd.read_csv(file_path)
        if 'PatientName' in df.columns:
            parts = df['PatientName'].str.split(',', n=1, expand=True)
            df['Last_Name']  = parts[0].str.strip()
            df['First_Name'] = parts[1].str.strip() if len(parts.columns) > 1 else ''
        return df
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load CSV: {e}")
        return None


def add_output_columns(df):
    """Append OUTPUT_COLUMNS to df with empty defaults where they don't exist."""
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ''
    return df


def save_results(df, output_folder, prefix="progress"):
    """Write df to a timestamped CSV in output_folder.

    Last_Name and First_Name are excluded from the output because they are
    derived from PatientName and are not needed by downstream consumers.
    Returns the saved file path, or None on failure.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path      = os.path.join(output_folder, f"{prefix}_{timestamp}.csv")
        export_df = df.drop(columns=['Last_Name', 'First_Name'], errors='ignore')
        export_df.to_csv(path, index=False)
        log_to_gui(f"  💾 Saved: {path}\n", "info")
        return path
    except Exception as e:
        log_to_gui(f"  ❌ Save error: {e}\n", "error")
        return None


def write_row_result(df, row_index, result_dict):
    """Apply every key/value in result_dict to the given dataframe row in-place."""
    for field, value in result_dict.items():
        df.at[row_index, field] = value


# ============================================================================
# SECTION 8 — PAGE NAVIGATION
# ============================================================================

def wait_for_page_ready(page):
    """Block until the claim-search iframe and its member-ID field are visible.

    Raises on failure (instead of returning None) so retry_with_backoff()
    can transparently retry the whole step.
    Returns the FrameLocator for the search iframe.
    """
    log_to_gui("  → Waiting for iframe...\n")
    page.wait_for_selector(SELECTORS['iframe'], state='attached', timeout=30000)
    # Brief pause for JS to finish wiring up the iframe contents after attach
    time.sleep(2)
    iframe = page.frame_locator(SELECTORS['iframe'])
    iframe.locator(SELECTORS['member_id']).wait_for(state='visible', timeout=30000)
    log_to_gui("  ✓ Page ready\n", "success")
    return iframe


def navigate_to_payer_page(page, payer_config):
    """Navigate to the payer's claim-search URL and click the HIPAA tab if required.

    Separating navigation from page-readiness lets each step use its own
    retry budget independently.

    Args:
        page:         Playwright Page object.
        payer_config: Entry from PAYER_CONFIG for the selected payer.
    """
    retry_with_backoff(
        "Navigate to search page",
        lambda: page.goto(payer_config['url'], wait_until='domcontentloaded', timeout=45000),
        attempts=3,
    )
    # Extra pause for the SPA's client-side routing to settle after navigation
    time.sleep(3)

    if payer_config['uses_hipaa_tab']:
        hipaa_tab = page.frame_locator(SELECTORS['iframe']).locator(SELECTORS['hipaa_tab'])
        hipaa_tab.first.wait_for(state='visible', timeout=20000)
        hipaa_tab.first.click(timeout=15000)
        log_to_gui("  ✓ HIPAA tab selected\n", "success")


# ============================================================================
# SECTION 9 — FORM INTERACTION
# ============================================================================

def fill_search_form(iframe, row_data):
    """Populate the claim search form with data from a CSV row.

    Uses safe_field() throughout to guard against NaN values.
    .type() is used for date fields because Availity's datepicker widget
    does not respond correctly to .fill() (it clears the field on blur).

    Returns True on success, False if a required field is empty or a
    Playwright action raises.
    """
    try:
        log_to_gui("  → Filling search form...\n")
        member_id  = safe_field(row_data, 'AltPatientID')
        last_name  = safe_field(row_data, 'Last_Name')
        first_name = safe_field(row_data, 'First_Name')
        dob        = safe_field(row_data, 'DOB')
        start_date = normalize_date(safe_field(row_data, 'StartDate'))
        end_date   = normalize_date(safe_field(row_data, 'EndDate'))

        # AltPatientID and Last_Name are required for a meaningful search
        if not member_id:
            raise ValueError("AltPatientID is empty or missing")
        if not last_name:
            raise ValueError("Last_Name is empty or missing")

        iframe.locator(SELECTORS['member_id']).fill(member_id)
        iframe.locator(SELECTORS['last_name']).fill(last_name)
        iframe.locator(SELECTORS['first_name']).fill(first_name)
        iframe.locator(SELECTORS['dob']).type(dob)
        iframe.locator(SELECTORS['date_from']).type(start_date)
        iframe.locator(SELECTORS['date_to']).type(end_date)
        return True
    except Exception as e:
        log_to_gui(f"  ❌ Form fill error: {e}\n", "error")
        return False


def submit_search_and_wait(iframe):
    """Click Search and wait for the results table to appear.

    Wrapped in retry_with_backoff() because the results table sometimes
    takes an extra moment to render after a fast network response.
    Returns True on success, False on timeout or error.
    """
    try:
        log_to_gui("  → Submitting search...\n")
        retry_with_backoff(
            "Submit search",
            lambda: (
                iframe.locator(SELECTORS['submit_btn']).click(),
                iframe.locator(SELECTORS['results_table']).wait_for(state='visible', timeout=15000),
            ),
            attempts=3,
        )
        return True
    except Exception as e:
        log_to_gui(f"  ❌ Search failed: {e}\n", "error")
        return False


# ============================================================================
# SECTION 10 — CLAIM LIST EXTRACTION
# ============================================================================

def find_matching_claims(iframe, invoice_number):
    """Locate all result rows whose visible text contains invoice_number.

    Returns (locator, count).  count == 0 means the invoice was not found.
    Playwright locators are lazy, so the returned locator is safe to
    re-evaluate after page changes.
    """
    try:
        if iframe.locator('#claimsTable tbody').count() == 0:
            raise Exception("Results table body not found")

        rows  = iframe.locator(f"#claimsTable tbody tr:has-text('{invoice_number}')")
        count = rows.count()
        if count == 0:
            raise Exception(f"Invoice {invoice_number} not found in results")

        log_to_gui(f"  ✓ Found {count} claim(s)\n", "success")
        return rows, count
    except Exception as e:
        log_to_gui(f"  ⚠️ {e}\n", "error")
        return None, 0


# ============================================================================
# SECTION 11 — CLAIM DETAIL EXTRACTION
# ============================================================================

def _read_selector(iframe, selector, label, timeout=5000):
    """Read visible text from a single selector.  Returns '--' if absent.

    Prefixed with _ because it is an implementation detail used only by
    the extraction functions in this section.
    """
    try:
        return iframe.locator(selector).text_content(timeout=timeout).strip()
    except Exception:
        log_to_gui(f"    ⚠️ {label} not found\n", "error")
        return '--'


def _read_first_selector(selectors, iframe, label, timeout=3000):
    """Try each selector in order and return the first non-empty result.

    Used for fields (Billed/Paid Amount) where Availity uses different
    attribute casing across environments — we try all known variants.
    """
    for sel in selectors:
        try:
            val = iframe.locator(sel).text_content(timeout=timeout).strip()
            if val:
                return val
        except Exception:
            continue
    log_to_gui(f"    ⚠️ {label} not found (tried {len(selectors)} selectors)\n", "error")
    return '--'


def extract_claim_header(iframe):
    """Scrape the summary panels on the open claim detail page.

    Returns a dict whose keys match OUTPUT_COLUMNS.
    """
    data = {
        'Claim ID':       _read_selector(iframe, SELECTORS['claim_id_panel'],       'Claim ID'),
        'Claim Status':   _read_selector(iframe, SELECTORS['claim_status_panel'],   'Claim Status'),
        'Finalized Date': _read_selector(iframe, SELECTORS['finalized_date_panel'], 'Finalized Date'),
        'Check Number':   _read_selector(iframe, SELECTORS['check_number_panel'],   'Check Number'),
        'Check Date':     _read_selector(iframe, SELECTORS['check_date_panel'],     'Check Date'),
        'Billed Amount':  _read_first_selector(SELECTORS['billed_amount_selectors'], iframe, 'Billed Amount'),
        'Paid Amount':    _read_first_selector(SELECTORS['paid_amount_selectors'],   iframe, 'Paid Amount'),
    }
    log_to_gui(f"    • Claim ID: {data['Claim ID']}\n")
    log_to_gui(f"    • Status:   {data['Claim Status']}\n")
    return data


def find_line_by_visit_date(iframe, visit_date):
    """Search the line-level table for a row matching visit_date.

    Both the target date (from CSV) and the scraped dates are normalised to
    'MM/DD/YYYY-MM/DD/YYYY' before comparison to avoid false mismatches.

    Returns (row_locator, row_index, billed_str, paid_str).
    Returns (None, -1, '--', '--') if no match is found.
    """
    try:
        iframe.locator(SELECTORS['line_table']).wait_for(state='visible', timeout=15000)
        rows   = iframe.locator('#lineLevelTable tbody tr[role="row"]')
        target = normalize_date_range(visit_date)
        log_to_gui(f"    → Searching {rows.count()} line(s) for: {target}\n")

        for idx in range(rows.count()):
            try:
                date_cell  = rows.nth(idx).locator('td').nth(3)
                paragraphs = date_cell.locator('p')
                p_count    = paragraphs.count()

                if p_count >= 2:
                    # Two <p> elements: from-date on first, to-date on second
                    from_d = normalize_date(paragraphs.nth(0).text_content(timeout=3000).strip())
                    to_d   = normalize_date(paragraphs.nth(1).text_content(timeout=3000).strip())
                    date_range = f"{from_d}-{to_d}"
                elif p_count == 1:
                    # Single <p>: treat as a one-day service range
                    single = normalize_date(paragraphs.nth(0).text_content(timeout=3000).strip())
                    date_range = f"{single}-{single}"
                else:
                    continue

                if date_range == target:
                    log_to_gui(f"    ✓ Line match: {date_range}\n", "success")
                    row    = rows.nth(idx)
                    # Column indices are 0-based: 6 = Paid Amount, 7 = Billed Amount
                    billed = row.locator('td').nth(7).text_content(timeout=3000).strip()
                    paid   = row.locator('td').nth(6).text_content(timeout=3000).strip()
                    log_to_gui(f"    • Billed: {billed}, Paid: {paid}\n")
                    return row, idx, billed, paid
            except Exception:
                continue

        log_to_gui("    ⚠️ No matching line found\n", "error")
        return None, -1, '--', '--'
    except Exception as e:
        log_to_gui(f"    ⚠️ Line table error: {e}\n", "error")
        return None, -1, '--', '--'


# ============================================================================
# SECTION 12 — DENIAL REASON EXTRACTION (INLINE)
# ============================================================================

def extract_denial_codes_inline(iframe, matching_row, _row_index):
    """Expand a line row, read Reason/Remark codes, and resolve their descriptions.

    The row is always collapsed after extraction (even on error) so that
    subsequent rows render correctly in the same session.
    Returns a comma-separated string of descriptions, or '--'.
    """
    expand_btn = matching_row.locator('td').first.locator('button')
    try:
        log_to_gui("    → Expanding line for denial codes...\n")
        expand_btn.click()
        time.sleep(2)   # wait for expand animation to settle

        remark_text = _read_remark_codes(iframe, matching_row)
        if not remark_text:
            return '--'

        log_to_gui(f"    • Codes: {remark_text}\n")
        descriptions = _lookup_code_descriptions(iframe, remark_text)
        return ', '.join(descriptions) if descriptions else '--'

    except Exception as e:
        log_to_gui(f"    ⚠️ Denial extraction error: {e}\n", "error")
        return '--'
    finally:
        # Always collapse — if we leave it open, the next row's expand may
        # attach to the wrong element and read stale codes
        try:
            expand_btn.click()
            time.sleep(1)
        except Exception:
            pass


def _read_remark_codes(iframe, matching_row):
    """Find and return the Reason/Remark Codes text from the expanded inline panel.

    Strategy:
      1. Search the whole line table for the most recently expanded header
         (the last one in DOM order belongs to the most recently expanded row).
      2. Fallback: walk up to 4 sibling <tr> elements of the expanded row.
    Returns an empty string if nothing is found.
    """
    try:
        headers = iframe.locator('#lineLevelTable').locator(
            'p.font-weight-bold:has-text("Reason/Remark Codes")'
        )
        count = headers.count()
        if count > 0:
            return headers.nth(count - 1).locator(
                'xpath=following-sibling::p[1]'
            ).text_content(timeout=3000).strip()

        # Fallback: scan sibling rows
        for offset in range(1, 5):
            sibling = matching_row.locator(f'xpath=following-sibling::tr[{offset}]')
            header  = sibling.locator('p.font-weight-bold:has-text("Reason/Remark Codes")')
            if header.count() > 0:
                return header.locator('xpath=following-sibling::p[1]').text_content(timeout=3000).strip()

        log_to_gui("    ⚠️ Remark codes panel not found\n", "error")
        return ''
    except Exception as e:
        log_to_gui(f"    ⚠️ Remark codes read error: {e}\n", "error")
        return ''


def _lookup_code_descriptions(iframe, remark_codes_text):
    """Resolve remark code abbreviations to full descriptions via the codes table.

    Returns a list of description strings (may be shorter than the input list
    when some codes are absent from the table).
    """
    # Scroll the codes table into view so all its rows are in the DOM
    try:
        iframe.locator(SELECTORS['codes_table']).scroll_into_view_if_needed()
        time.sleep(0.5)
    except Exception:
        pass

    descriptions = []
    for code in (c.strip() for c in remark_codes_text.split(',')):
        try:
            row = iframe.locator(
                f'#codesTable tbody tr:has(td:text("Remark")):has(td:text-is("{code}"))'
            )
            if row.count() > 0:
                desc = row.locator('td').nth(2).text_content(timeout=3000).strip()
                descriptions.append(desc)
                log_to_gui(f"      • {code}: {desc}\n")
        except Exception:
            continue
    return descriptions


def should_extract_denial(claim_status, billed, paid, matching_row):
    """Decide whether inline denial code extraction is worth attempting.

    Returns False (skip) when:
      - Claim is PENDING — no adjudication data exists yet.
      - No line-level row was found — we have nothing to expand.
      - Claim was fully paid — billed == paid (both non-zero), so no denial.
    """
    if claim_status.upper() == 'PENDING':
        log_to_gui("    ℹ️ PENDING — skipping denial codes\n", "info")
        return False
    if matching_row is None:
        return False
    billed_val = parse_amount(billed)
    paid_val   = parse_amount(paid)
    if billed_val is not None and paid_val is not None and billed_val > 0 and billed_val == paid_val:
        log_to_gui("    ℹ️ Fully paid — skipping denial codes\n", "info")
        return False
    return True


# ============================================================================
# SECTION 13 — DENIAL REASON EXTRACTION (REMITTANCE VIEWER)
# ============================================================================

def extract_denial_reason_villagecaremax(page, claim_id):
    """Open the Villagecaremax remittance viewer in a new tab and read denial reason.

    Opens a new tab, searches by claim_id, reads the Adjustments table,
    then closes the tab.  Returns '--' on any failure.
    """
    if not claim_id or claim_id == '--':
        return '--'

    remit_page = None
    try:
        remit_page = page.context.new_page()
        remit_page.goto(REMITTANCE_URLS['search'], wait_until='domcontentloaded', timeout=45000)
        remit_page.wait_for_selector(SELECTORS['iframe'], state='attached', timeout=30000)
        time.sleep(2)

        iframe = remit_page.frame_locator(SELECTORS['iframe'])

        # Navigate to the Claim search tab inside the remittance viewer
        claim_tab = iframe.locator(SELECTORS['remit_claim_tab'])
        claim_tab.first.wait_for(state='visible', timeout=20000)
        claim_tab.first.click(timeout=15000)

        # Enter the claim ID and submit the search
        search_input = iframe.locator(SELECTORS['remit_search_input'])
        search_input.first.wait_for(state='visible', timeout=20000)
        search_input.first.fill(claim_id)
        iframe.locator(SELECTORS['remit_search_btn']).first.click(timeout=15000)

        # Wait for remit results and click through to the matching claim
        iframe.locator(SELECTORS['remit_table']).first.wait_for(state='visible', timeout=30000)
        claim_link = iframe.locator(f'a[id^="claimNumber"]:has-text("{claim_id}")')
        claim_link.first.wait_for(state='visible', timeout=20000)
        claim_link.first.click(timeout=15000)

        # Read the Adjustments table on the claim detail page
        remit_page.wait_for_url("**claim-details**", timeout=45000)
        adj_table = iframe.locator(SELECTORS['remit_adj_table'])
        adj_table.first.wait_for(state='visible', timeout=30000)

        denial = _read_remit_denial(iframe, adj_table)

        # Navigate away so the next tab open starts from a clean state
        remit_page.goto(REMITTANCE_URLS['home'], wait_until='domcontentloaded', timeout=45000)
        return denial

    except Exception as e:
        log_to_gui(f"    ⚠️ Villagecaremax remittance failed: {e}\n", "error")
        return '--'
    finally:
        if remit_page is not None:
            try:
                remit_page.close()
            except Exception:
                pass


def _read_remit_denial(iframe, adj_table):
    """Read and clean the denial reason text from the Adjustments table.

    Expands 'View More' buttons before reading to capture full text.
    Falls back to the Claim Adjustment column when the remark column
    only contains the generic 'No remittance advice codes applicable.' message.
    """
    remark_cell = adj_table.locator('tbody tr td').nth(2)
    if remark_cell.count() == 0:
        return '--'

    _expand_view_more(remark_cell)
    denial = remark_cell.inner_text(timeout=10000).strip()
    denial = denial.replace("View More", "").replace("View Less", "").strip()

    if denial != "No remittance advice codes applicable.":
        return denial or '--'

    # Generic remark → fall back to the Claim Adjustment column (index 3)
    adj_cell = adj_table.locator('tbody tr td').nth(3)
    if adj_cell.count() == 0:
        return '--'
    _expand_view_more(adj_cell)
    code_desc = adj_cell.locator('div[role="row"] div[role="cell"]').nth(1)
    if code_desc.count() == 0:
        return '--'
    text = code_desc.inner_text(timeout=10000).strip()
    text = text.replace("View More", "").replace("View Less", "").strip()
    return text or '--'


def _expand_view_more(container):
    """Click all 'View More' buttons inside container to reveal truncated text."""
    buttons = container.locator('button:has-text("View More")')
    for idx in range(buttons.count()):
        try:
            buttons.nth(idx).click(timeout=3000)
            time.sleep(0.2)
        except Exception:
            pass


# ============================================================================
# SECTION 14 — PAYER-SPECIFIC CLAIM ENRICHMENT
# ============================================================================
# These three functions encapsulate all payer-branching logic so that
# process_one_claim() is fully payer-agnostic.

def enrich_claim_with_amounts(iframe, claim_data, row_data, payer_config):
    """Populate Billed Amount and Paid Amount based on payer config.

    uses_line_level=True  → find the matching service-date row in the line table.
    uses_line_level=False → amounts are already on the header panels;
                            also promote Check Date to Finalized Date if present.

    Returns (matching_row, row_index, billed_str, paid_str).
    """
    if payer_config['uses_line_level']:
        visit_date = safe_field(row_data, 'VisitDate')
        row, idx, billed, paid = find_line_by_visit_date(iframe, visit_date)
        claim_data['Billed Amount'] = billed
        claim_data['Paid Amount']   = paid
        return row, idx, billed, paid
    else:
        billed = claim_data.get('Billed Amount', '--')
        paid   = claim_data.get('Paid Amount',   '--')
        if claim_data.get('Check Date') and claim_data['Check Date'] != '--':
            claim_data['Finalized Date'] = claim_data['Check Date']
        return None, -1, billed, paid


def derive_claim_status(claim_data, billed, paid, payer_config):
    """Override Claim Status where the portal-reported status is insufficient.

    Rules applied in priority order:
      1. uses_remittance payer + paid == $0           → Denied
      2. Any payer: paid > $0 but paid < billed       → Partially Paid
    """
    billed_val = parse_amount(billed)
    paid_val   = parse_amount(paid)

    if payer_config['uses_remittance'] and paid_val is not None and paid_val == 0:
        claim_data['Claim Status'] = 'Denied'
        log_to_gui("    ℹ️ Paid $0 — marked as Denied\n", "info")

    if (billed_val is not None and paid_val is not None
            and billed_val > 0 and paid_val > 0 and paid_val < billed_val):
        claim_data['Claim Status'] = 'Partially Paid'
        log_to_gui("    ℹ️ Partial payment — marked as Partially Paid\n", "info")


def enrich_claim_with_denial(page, iframe, claim_data, billed, paid,
                              matching_row, row_idx, payer_config):
    """Determine and set the Denial Reason field based on payer config.

    Dispatches to extract_denial_reason_villagecaremax() for remittance payers,
    and to extract_denial_codes_inline() for all others (when relevant).
    """
    if payer_config['uses_remittance']:
        billed_val = parse_amount(billed)
        paid_val   = parse_amount(paid)
        # Fully paid remittance claims do not need remittance denial lookup.
        if (billed_val is not None and paid_val is not None
                and billed_val > 0 and billed_val == paid_val):
            log_to_gui("    ℹ️ Fully paid — skipping remittance denial lookup\n", "info")
            claim_data['Denial Reason'] = '--'
        else:
            claim_data['Denial Reason'] = extract_denial_reason_villagecaremax(
                page, claim_data['Claim ID']
            )
    elif should_extract_denial(claim_data['Claim Status'], billed, paid, matching_row):
        claim_data['Denial Reason'] = extract_denial_codes_inline(
            iframe, matching_row, row_idx
        )
    else:
        claim_data['Denial Reason'] = '--'


# ============================================================================
# SECTION 15 — SINGLE-CLAIM PROCESSING PIPELINE
# ============================================================================

def process_one_claim(page, iframe, row_data, claim_idx, total, payer_config):
    """Extract all data fields for the claim currently open in the detail view.

    Returns a filled result dict, or empty_claim_result('Error') on failure.
    Returns None if the user has requested a stop.
    """
    global is_running
    if not is_running:
        return None

    try:
        log_to_gui(f"  → Processing claim {claim_idx + 1}/{total}...\n", "info")
        claim_data = extract_claim_header(iframe)

        # Pending claims have no adjudicated amounts or denial data yet
        if claim_data['Claim Status'].upper() == 'PENDING':
            log_to_gui("    ℹ️ PENDING — no amounts available\n", "info")
            claim_data.update({'Billed Amount': '--', 'Paid Amount': '--', 'Denial Reason': '--'})
            return claim_data

        matching_row, row_idx, billed, paid = enrich_claim_with_amounts(
            iframe, claim_data, row_data, payer_config
        )
        derive_claim_status(claim_data, billed, paid, payer_config)
        enrich_claim_with_denial(
            page, iframe, claim_data, billed, paid, matching_row, row_idx, payer_config
        )

        log_to_gui(f"    ✓ Claim {claim_idx + 1} complete\n", "success")
        return claim_data

    except Exception as e:
        log_to_gui(f"    ❌ Claim error: {e}\n", "error")
        return empty_claim_result('Error')


def process_all_claims_for_invoice(page, iframe, row_data, invoice_number,
                                   matching_rows, total, payer_config):
    """Open and extract data for every claim row that matched the invoice number.

    After each claim (except the last), navigates back to the results list
    via the breadcrumb link inside the iframe.
    Returns a list of result dicts.
    """
    results            = []
    claim_already_open = False  # avoids double-clicking when back-nav already opened next claim

    for claim_idx in range(total):
        if not is_running:
            break

        try:
            if not claim_already_open:
                matching_rows.nth(claim_idx).click()
                iframe.locator('[data-testid="testClaim NumberPanel"]').wait_for(
                    state='visible', timeout=15000
                )
            claim_already_open = False

            claim_data = process_one_claim(
                page, iframe, row_data, claim_idx, total, payer_config
            )
            if claim_data:
                results.append(claim_data)

            # Navigate back to the results list before processing the next claim
            if claim_idx < total - 1:
                iframe, matching_rows, claim_already_open = _navigate_back_to_results(
                    page, iframe, invoice_number, claim_idx
                )
                if iframe is None:
                    break   # back-navigation failed; stop iterating this invoice

        except Exception as e:
            log_to_gui(f"  ❌ Claim iteration error: {e}\n", "error")
            results.append(empty_claim_result('Error'))
            # Attempt a page reload and re-search so subsequent claims can still run
            iframe = _attempt_recovery(page, row_data)
            if iframe is None:
                break
            matching_rows = iframe.locator(f"#claimsTable tbody tr:has-text('{invoice_number}')")

    return results


def _navigate_back_to_results(page, iframe, invoice_number, current_idx):
    """Click the Results breadcrumb and open the next claim.

    Returns (iframe, matching_rows, True) on success so the main loop
    knows the next claim is already open.
    Returns (None, None, False) if navigation fails.
    """
    try:
        log_to_gui("  → Going back to results...\n")
        results_link = iframe.locator('a[aria-label="Results"]')
        results_link.first.wait_for(state='visible', timeout=20000)
        results_link.first.click(timeout=15000)

        page.wait_for_load_state('domcontentloaded', timeout=45000)
        time.sleep(2)

        iframe        = retry_with_backoff("Return to results", lambda: wait_for_page_ready(page), attempts=3)
        matching_rows = iframe.locator(f"#claimsTable tbody tr:has-text('{invoice_number}')")

        # Pre-open the next claim so the main loop skips the click
        next_idx = current_idx + 1
        matching_rows.nth(next_idx).click()
        iframe.locator('[data-testid="testClaim NumberPanel"]').wait_for(state='visible', timeout=15000)

        log_to_gui("  ✓ Back to results\n", "success")
        return iframe, matching_rows, True
    except Exception as e:
        log_to_gui(f"  ❌ Back-navigation failed: {e}\n", "error")
        return None, None, False


def _attempt_recovery(page, row_data):
    """Reload the page and re-run the search after a claim processing error.

    Returns a fresh iframe if successful, or None if recovery also fails.
    """
    try:
        log_to_gui("  → Attempting recovery reload...\n", "error")
        page.reload(wait_until='domcontentloaded', timeout=45000)
        time.sleep(3)
        iframe = retry_with_backoff("Recovery page ready", lambda: wait_for_page_ready(page), attempts=2)
        fill_search_form(iframe, row_data)
        submit_search_and_wait(iframe)
        return iframe
    except Exception as e:
        log_to_gui(f"  ❌ Recovery failed: {e}\n", "error")
        return None


def format_multi_claim_results(results):
    """Merge multiple claim result dicts into a single dict with numbered values.

    When one invoice has several matching claims, all values are numbered
    and joined with newlines so the output CSV stays one row per invoice.
    """
    if not results:
        return empty_claim_result('No data')
    return {
        field: '\n'.join(f"{i + 1}. {r[field]}" for i, r in enumerate(results))
        for field in OUTPUT_COLUMNS
    }


# ============================================================================
# SECTION 16 — ROW PROCESSING  (one CSV row = one invoice)
# ============================================================================

def process_one_row(page, df, row_index, row_data, output_folder, payer_config):
    """Full pipeline for one CSV row: navigate → search → extract → save.

    Always returns True so the batch loop advances regardless of outcome.
    Errors are written to the dataframe and a progress file is saved
    immediately so no work is lost if the process is interrupted.
    """
    global is_running
    if not is_running:
        return False

    try:
        log_to_gui(f"\n🔄 Row {row_index + 1}\n", "info")
        invoice_number = safe_field(row_data, 'InvoiceNumber')
        visit_date     = safe_field(row_data, 'VisitDate')

        if not invoice_number:
            log_to_gui(f"  ⚠️ Row {row_index + 1}: InvoiceNumber is empty — skipping\n", "error")
            write_row_result(df, row_index, empty_claim_result('Missing InvoiceNumber'))
            return True

        log_to_gui(f"  → Invoice: {invoice_number}  |  Visit: {visit_date}\n")

        # Re-navigate for every row after the first to flush any stale UI state
        if row_index > 0:
            _reload_and_navigate(page, payer_config)

        try:
            iframe = retry_with_backoff("Wait for page ready", lambda: wait_for_page_ready(page), attempts=3)
        except Exception as nav_error:
            log_to_gui(f"  ❌ Page setup failed: {nav_error}\n", "error")
            write_row_result(df, row_index, empty_claim_result('Navigation failed'))
            save_results(df, output_folder)
            return True

        if not fill_search_form(iframe, row_data):
            write_row_result(df, row_index, empty_claim_result('Form error'))
            save_results(df, output_folder)
            return True

        if not submit_search_and_wait(iframe):
            write_row_result(df, row_index, empty_claim_result('No claims found. Advised to search manually'))
            save_results(df, output_folder)
            return True

        matching_rows, match_count = find_matching_claims(iframe, invoice_number)
        if match_count == 0:
            write_row_result(df, row_index, empty_claim_result('Claim not found. Search manually'))
            save_results(df, output_folder)
            return True

        all_results = process_all_claims_for_invoice(
            page, iframe, row_data, invoice_number, matching_rows, match_count, payer_config
        )
        write_row_result(df, row_index, format_multi_claim_results(all_results))
        log_to_gui(f"  ✓ Row {row_index + 1} complete\n", "success")

        # Brief pause between rows to let the browser settle before the next reload
        if row_index < len(df) - 1:
            time.sleep(2)
        return True

    except Exception as e:
        log_to_gui(f"  ❌ Row error: {e}\n", "error")
        log_to_gui(traceback.format_exc(), "error")
        write_row_result(df, row_index, empty_claim_result('Critical error'))
        save_results(df, output_folder)
        return True


def _reload_and_navigate(page, payer_config):
    """Reload the current page then navigate to the payer search URL.

    A reload before navigating clears any leftover modal or loading overlay
    from the previous row.  Reload failures are logged but not re-raised
    because the subsequent wait_for_page_ready will surface the real error.
    """
    try:
        log_to_gui("  → Reloading...\n")
        retry_with_backoff(
            "Page reload",
            lambda: page.reload(wait_until='domcontentloaded', timeout=30000),
            attempts=3,
        )
        time.sleep(2)
        log_to_gui("  ✓ Reload complete\n", "success")
    except Exception as e:
        log_to_gui(f"  ⚠️ Reload failed: {e}\n", "error")

    log_to_gui("  → Navigating to search page...\n")
    navigate_to_payer_page(page, payer_config)
    log_to_gui("  ✓ Navigation complete\n", "success")


# ============================================================================
# SECTION 17 — BATCH PROCESSING
# ============================================================================

def process_batch(batch_size, csv_path, output_folder, payer_name):
    """Main entry point for the background worker thread.

    Orchestrates: browser setup → initial navigation → CSV load + validation
    → row-by-row processing → final save → error summary.
    """
    global is_running
    df = None

    try:
        payer_config = PAYER_CONFIG.get(payer_name)
        if not payer_config:
            log_to_gui(f"❌ Unknown payer '{payer_name}'\n", "error")
            return

        log_to_gui("🌐 Connecting to browser...\n", "info")
        page = setup_browser()
        log_to_gui("✓ Browser connected\n", "success")

        # Navigate before loading the CSV so we fail fast on browser issues
        log_to_gui("🔗 Navigating to search page...\n", "info")
        navigate_to_payer_page(page, payer_config)
        retry_with_backoff("Initial page ready", lambda: wait_for_page_ready(page), attempts=3)
        log_to_gui("✓ Initial navigation complete\n", "success")

        log_to_gui("📂 Loading CSV...\n", "info")
        df = load_csv(csv_path)
        if df is None:
            return

        missing = validate_dataframe(df)
        if missing:
            log_to_gui(f"❌ Missing columns: {', '.join(missing)}\n", "error")
            log_to_gui("   Check your CSV headers and try again.\n", "error")
            return

        df = add_output_columns(df)
        log_to_gui(f"✓ Loaded {len(df)} rows\n", "success")

        rows_to_process = min(batch_size, len(df))
        log_to_gui(f"\n📦 Processing {rows_to_process} rows for {payer_name}...\n", "info")
        log_to_gui("-" * 60 + "\n")

        processed    = 0
        error_counts = {}

        for idx in range(rows_to_process):
            if not is_running:
                log_to_gui("⚠ Stopped by user\n", "error")
                break
            process_one_row(page, df, idx, df.iloc[idx], output_folder, payer_config)
            processed += 1
            _record_error(df, idx, error_counts)

        log_to_gui("-" * 60 + "\n")
        save_results(df, output_folder, "FINAL_results")

        if processed == rows_to_process:
            log_to_gui(f"✓ Complete! {processed} rows processed\n", "success")
        else:
            log_to_gui(f"⚠ Stopped. {processed}/{rows_to_process} rows saved\n", "error")

        if error_counts:
            log_to_gui("\n📊 Error summary:\n", "error")
            for reason, count in sorted(error_counts.items(), key=lambda x: -x[1]):
                log_to_gui(f"   • {reason}: {count} row(s)\n", "error")

    except Exception as e:
        log_to_gui(f"❌ Critical batch error: {e}\n", "error")
        log_to_gui(traceback.format_exc(), "error")
        if df is not None:
            save_results(df, output_folder)
    finally:
        cleanup_browser()
        reset_ui_state()


def _record_error(df, row_index, error_counts):
    """Increment the counter for a known error status written into Claim Status."""
    status_val = df.at[row_index, 'Claim Status']
    if not isinstance(status_val, str):
        return
    for line in status_val.split('\n'):
        val = line.split('. ', 1)[-1].strip()
        if val in KNOWN_ERROR_STATUSES:
            error_counts[val] = error_counts.get(val, 0) + 1


# ============================================================================
# SECTION 18 — BACKGROUND THREAD
# ============================================================================

def run_in_background(batch_size, csv_path, output_folder, payer):
    """Spawn a daemon thread so the Tkinter main loop stays responsive."""
    thread = threading.Thread(
        target=process_batch,
        args=(batch_size, csv_path, output_folder, payer),
        daemon=True,
    )
    thread.start()


# ============================================================================
# SECTION 19 — GUI: THREAD-SAFE LOGGING
# ============================================================================

def log_to_gui(message, tag="info"):
    """Append a message to the log widget from any thread.

    Tkinter widgets are not thread-safe, so we use root.after(0, ...) to
    schedule the update on the main (GUI) thread.

    Tags: "info" = blue, "success" = green, "error" = red
    """
    def _insert():
        log_text.config(state="normal")
        log_text.insert(tk.END, message, tag)
        log_text.see(tk.END)
        log_text.config(state="disabled")

    root.after(0, _insert)


# ============================================================================
# SECTION 20 — GUI: CONTROL CALLBACKS
# ============================================================================

def reset_ui_state(clear_all=False):
    """Return the UI to idle state.

    Args:
        clear_all: If True (Stop button), clears input fields and the log.
                   If False (batch finished naturally), only re-enables Start.
    """
    global is_running
    is_running = False

    def _reset():
        start_button.config(state="normal")
        stop_button.config(state="disabled")
        if clear_all:
            collection_file_var.set("")
            output_folder_var.set("")
            batch_size_var.set("10")
            payer_var.set("Healthfirst")
            log_text.config(state="normal")
            log_text.delete(1.0, tk.END)
            log_text.config(state="disabled")

    root.after(0, _reset)


def browse_csv():
    """Open a file picker restricted to CSV files."""
    filename = filedialog.askopenfilename(
        title="Select Collection File",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
    )
    if filename:
        collection_file_var.set(filename)


def browse_folder():
    """Open a folder picker for the output directory."""
    folder = filedialog.askdirectory(title="Select Output Folder")
    if folder:
        output_folder_var.set(folder)


def validate_and_start():
    """Validate all inputs before starting the background automation."""
    global is_running

    csv_file   = collection_file_var.get()
    output_dir = output_folder_var.get()
    payer      = payer_var.get()

    try:
        batch = int(batch_size_var.get())
        if batch <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("Error", "Batch size must be a positive integer")
        return

    if not csv_file:
        messagebox.showerror("Error", "Please select a collection file")
        return
    if not output_dir:
        messagebox.showerror("Error", "Please select an output folder")
        return
    if not payer or payer not in PAYER_CONFIG:
        messagebox.showerror("Error", f"Please select a valid payer")
        return

    is_running = True
    start_button.config(state="disabled")
    stop_button.config(state="normal")

    log_text.config(state="normal")
    log_text.delete(1.0, tk.END)
    log_text.config(state="disabled")

    run_in_background(batch, csv_file, output_dir, payer)


def request_stop():
    """Signal the worker thread to stop after the current row completes."""
    global is_running
    is_running = False
    reset_ui_state(clear_all=True)


# ============================================================================
# SECTION 21 — GUI: LAYOUT
# ============================================================================

def create_gui():
    """Build and return the main application window."""
    global root, log_text, start_button, stop_button
    global collection_file_var, output_folder_var, batch_size_var, payer_var

    root = tk.Tk()
    root.title("Availity Claim Automation")
    root.geometry("850x650")

    collection_file_var = tk.StringVar()
    output_folder_var   = tk.StringVar()
    batch_size_var      = tk.StringVar(value="10")
    payer_var           = tk.StringVar(value="Healthfirst")

    main_frame = tk.Frame(root, padx=20, pady=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        main_frame, text="Availity Claim Status Checker", font=("Arial", 16, "bold")
    ).grid(row=0, column=0, columnspan=3, pady=(0, 20))

    # Row 1 — CSV file
    tk.Label(main_frame, text="Collection File:", font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=5)
    tk.Entry(main_frame, textvariable=collection_file_var, width=50).grid(row=1, column=1, pady=5, padx=5)
    tk.Button(main_frame, text="Browse", command=browse_csv).grid(row=1, column=2, pady=5)

    # Row 2 — Output folder
    tk.Label(main_frame, text="Output Folder:", font=("Arial", 10)).grid(row=2, column=0, sticky="w", pady=5)
    tk.Entry(main_frame, textvariable=output_folder_var, width=50).grid(row=2, column=1, pady=5, padx=5)
    tk.Button(main_frame, text="Browse", command=browse_folder).grid(row=2, column=2, pady=5)

    # Row 3 — Batch size
    tk.Label(main_frame, text="Batch Size:", font=("Arial", 10)).grid(row=3, column=0, sticky="w", pady=5)
    tk.Entry(main_frame, textvariable=batch_size_var, width=20).grid(row=3, column=1, sticky="w", pady=5, padx=5)

    # Row 4 — Payer dropdown
    # Populated from PAYER_CONFIG.keys() so adding a new payer entry above
    # automatically makes it appear in the dropdown with no extra code.
    tk.Label(main_frame, text="Select Payer:", font=("Arial", 10)).grid(row=4, column=0, sticky="w", pady=5)
    ttk.Combobox(
        main_frame,
        textvariable=payer_var,
        values=list(PAYER_CONFIG.keys()),
        state="readonly",
        width=47,
    ).grid(row=4, column=1, sticky="w", pady=5, padx=5)

    # Row 5 — Start / Stop buttons
    btn_frame = tk.Frame(main_frame)
    btn_frame.grid(row=5, column=0, columnspan=3, pady=20)

    start_button = tk.Button(
        btn_frame, text="Start", command=validate_and_start,
        bg="green", fg="white", font=("Arial", 10, "bold"), width=15,
    )
    start_button.pack(side=tk.LEFT, padx=10)

    stop_button = tk.Button(
        btn_frame, text="Stop", command=request_stop,
        bg="red", fg="white", font=("Arial", 10, "bold"), width=15, state="disabled",
    )
    stop_button.pack(side=tk.LEFT, padx=10)

    # Rows 6-7 — Log output
    tk.Label(main_frame, text="Log:", font=("Arial", 10, "bold")).grid(
        row=6, column=0, sticky="w", pady=(10, 5)
    )

    log_frame = tk.Frame(main_frame)
    log_frame.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=5)

    scrollbar = tk.Scrollbar(log_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    log_text = tk.Text(
        log_frame, height=20, width=95,
        yscrollcommand=scrollbar.set, state="disabled", wrap=tk.WORD,
    )
    log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=log_text.yview)

    log_text.tag_config("info",    foreground="blue")
    log_text.tag_config("success", foreground="green")
    log_text.tag_config("error",   foreground="red")

    main_frame.grid_rowconfigure(7, weight=1)
    main_frame.grid_columnconfigure(1, weight=1)

    return root


# ============================================================================
# SECTION 22 — ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    root = create_gui()
    root.mainloop()
