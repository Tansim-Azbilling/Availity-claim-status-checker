# Availity Claim Automation - Features and Functional Documentation

## Overview

`Availity_Gui.py` is a desktop automation tool that combines:
- A `Tkinter` GUI for user inputs and run control
- `Playwright` browser automation against Availity Essentials
- `pandas` CSV processing for bulk claim checks
- Payer-specific claim extraction logic
- Resume-aware batch processing with progress/error persistence

The program processes claim-related rows from a CSV and writes enriched output fields such as claim ID, amounts, status, denial reason, and payment dates/check info.

---

## Core Program Features

## 1) GUI-driven Claim Automation
- Launches a desktop app titled **Availity Claim Automation**.
- User selects:
  - Input CSV file
  - Output folder
  - Batch size
  - Payer (Healthfirst, Integra, Villagecaremax)
- Start/Stop controls with a live color-coded log panel.
- Runs automation in a background thread so the GUI remains responsive.

## 2) Browser Lifecycle and Session Handling
- Uses Microsoft Edge with CDP (`--remote-debugging-port=9222`).
- Connects Playwright to existing/live Edge session via `connect_over_cdp`.
- Supports manual login + 2FA flow (user completes this in Edge).
- Detects authenticated navigation shell before continuing.
- Handles tab normalization at startup (chooses best active tab safely).
- Can close only the Edge instance it launched (avoids killing user-owned browser sessions).

## 3) Payer-Configurable Processing Model
- All payer logic is centralized in `PAYER_CONFIG`.
- Each payer defines:
  - Target Availity URL
  - Whether HIPAA tab click is required
  - Whether line-level amount extraction is required
  - Whether remittance-viewer denial extraction is required
- Adding a new payer is mostly config-only and auto-populates GUI dropdown.

## 4) CSV Validation and Safe Data Processing
- Validates required input columns before processing.
- Splits `PatientName` into `Last_Name` and `First_Name`.
- Adds output/status columns if missing.
- Protects against NaN/missing values with safe-read helpers.
- Supports resume behavior by processing only rows not already marked `Done`.

## 5) Claim Search + Multi-Claim Handling
- For each row/invoice:
  - Fills claim search form in iframe
  - Submits search and waits for results table
  - Finds all matching claims by invoice text
- If multiple claims match one invoice:
  - Opens and extracts each claim
  - Merges into one CSV row using numbered multiline values.

## 6) Detailed Claim Data Extraction
- Pulls header panel data:
  - Claim ID
  - Claim Status
  - Finalized Date
  - Check Number
  - Check Date
  - Billed/Paid amounts (selector fallbacks for UI inconsistencies)
- For line-level payers:
  - Locates matching service line by normalized visit date/range
  - Reads billed/paid from line table columns.

## 7) Denial Reason Extraction (Two Paths)
- **Inline code-based path** (Healthfirst/Integra style):
  - Expands selected line
  - Reads Reason/Remark codes
  - Looks up descriptions in codes table
  - Returns combined denial text.
- **Remittance viewer path** (Villagecaremax):
  - Opens remittance viewer in new tab
  - Searches by Claim ID
  - Reads denial from adjustments table
  - Handles "View More" expansion and fallback logic.

## 8) Claim Status Derivation Rules
- Keeps extracted portal status, but may override with rule-based logic:
  - `Denied` when remittance payer and paid amount is `$0`
  - `Partially Paid` when `0 < paid < billed`
- Skips denial extraction when clearly unnecessary (e.g., pending or fully paid).

## 9) Reliability, Retry, and Recovery
- Uses exponential backoff with jitter for transient browser actions.
- Retries critical steps: CDP connection, navigation, page-ready waits, submit actions.
- Row-level recovery path:
  - Reload page
  - Re-run search
  - Continue when possible.
- Maintains stop-safe behavior using cooperative `is_running` flag.

## 10) Persistence and Output Safety
- Saves timestamped progress CSVs during processing (not just at end).
- Saves final output file with `Automated_YYYYMMDD_HHMMSS.csv` style naming.
- Tracks per-row run metadata:
  - `AutomationStatus` (`Pending`, `InProgress`, `Done`, `Error`)
  - `LastError`.

## 11) Error Classification and Summaries
- Standardized known error statuses are recorded in claim output.
- End-of-batch error summary aggregates known failure categories.
- Logs include both user-friendly messages and traceback on critical failures.

---

## End-to-End Workflow

1. User opens app, selects CSV/output folder/batch/payer, clicks Start.
2. App launches or reuses Edge with CDP and connects Playwright.
3. User logs into Availity (including 2FA); app waits until authenticated shell detected.
4. App navigates to selected payer claim page and validates iframe readiness.
5. CSV is loaded, validated, and output/status columns prepared.
6. Pending rows (up to batch size) are processed one-by-one:
   - Search form fill
   - Result match by invoice
   - Claim detail extraction
   - Amount/status/denial enrichment
   - Row update + intermittent saves.
7. Final output is saved, errors summarized, browser session cleaned up, UI reset.

---

## Function Map (What Each Function/Group Does)

## Global State and Constants
- `is_running`, `current_playwright`, `current_browser`, `managed_edge_process`, `browser_owned_by_app`:
  Run-control and browser ownership state.
- `SELECTORS`:
  Centralized UI selectors (iframe, forms, tables, panels, remittance UI).
- `PAYER_CONFIG`:
  Payer-specific behavior toggles and URLs.
- `REQUIRED_COLUMNS`, `OUTPUT_COLUMNS`, `STATUS_COLUMNS`:
  Data schema expectations and output model.
- `KNOWN_ERROR_STATUSES`:
  Canonical row-level error labels for summary counting.

## Retry/Utility
- `retry_with_backoff(...)`:
  Generic retry wrapper with exponential delay + jitter for transient failures.

## Date/Amount Helpers
- `normalize_date(...)`:
  Normalizes to `MM/DD/YYYY`.
- `normalize_date_range(...)`:
  Ensures date range format `MM/DD/YYYY-MM/DD/YYYY`.
- `normalize_dob(...)`:
  Handles DOB quirks (ISO/timestamps, Excel serials, malformed years).
- `parse_amount(...)`:
  Converts currency string to float; returns `None` for blanks/unavailable values.

## Data Safety Helpers
- `safe_field(...)`:
  Safe string extraction from row with NaN protection.
- `validate_dataframe(...)`:
  Detects missing required columns.
- `empty_claim_result(...)`:
  Standard placeholder output payload.

## Browser Management
- `setup_browser()`:
  Starts Playwright and attaches to CDP browser/context/page.
- `disconnect_browser_session()`:
  Detaches Playwright safely.
- `get_live_page(...)`, `_get_all_open_pages(...)`, `_get_open_page_urls(...)`:
  Finds healthy active pages across contexts.
- `_find_edge_executable()`, `ensure_edge_with_cdp()`, `close_managed_edge_if_owned()`:
  Edge process discovery/start/owned-shutdown.
- `is_logged_in_navigation(...)`, `validate_navigation_page_ready(...)`, `_find_logged_in_page(...)`:
  Authenticated-shell detection and readiness checks.
- `reset_tabs_for_session_start(...)`:
  Selects best startup tab.
- `wait_for_login(...)`:
  Waits for user login, with diagnostic logs and navigation probes.

## CSV/File Operations
- `load_csv(...)`:
  Reads CSV and splits patient name.
- `add_output_columns(...)`:
  Adds output + status columns with defaults.
- `save_results(...)`:
  Timestamped exports, excluding derived name-split helper columns.
- `write_row_result(...)`, `safe_mark_row_status(...)`:
  Atomic row updates.

## Navigation and Form Interaction
- `wait_for_page_ready(...)`:
  Waits for claim-search iframe and member field.
- `navigate_to_payer_page(...)`:
  Opens payer page and optional HIPAA tab.
- `fill_search_form(...)`:
  Inputs patient/member/date data safely.
- `submit_search_and_wait(...)`:
  Submits and waits for result table.

## Claim Search and Extraction
- `find_matching_claims(...)`:
  Retrieves matching result rows by invoice text.
- `_read_selector(...)`, `_read_first_selector(...)`:
  Robust field reads with fallback.
- `extract_claim_header(...)`:
  Pulls high-level claim detail panel values.
- `find_line_by_visit_date(...)`:
  Matches line-level service dates and reads billed/paid.

## Denial Extraction (Inline)
- `extract_denial_codes_inline(...)`:
  Expand row, read reason codes, resolve descriptions, collapse row.
- `_read_remark_codes(...)`:
  Gets reason/remark code text from expanded content.
- `_lookup_code_descriptions(...)`:
  Maps remark codes to descriptions from codes table.
- `should_extract_denial(...)`:
  Denial extraction eligibility checks.

## Denial Extraction (Villagecaremax Remittance)
- `extract_denial_reason_villagecaremax(...)`:
  New-tab remittance search and denial read by claim ID.
- `_read_remit_denial(...)`:
  Reads/cleans denial text, with generic-message fallback handling.
- `_expand_view_more(...)`:
  Expands truncated text blocks.

## Payer-Specific Enrichment
- `enrich_claim_with_amounts(...)`:
  Chooses line-level vs header amount source.
- `derive_claim_status(...)`:
  Applies business rules for denied/partially-paid statuses.
- `enrich_claim_with_denial(...)`:
  Routes to remittance or inline denial logic.

## Claim/Row/Batch Pipelines
- `process_one_claim(...)`:
  Full claim detail pipeline with special pending handling.
- `process_all_claims_for_invoice(...)`:
  Iterates every claim for one invoice.
- `_navigate_back_to_results(...)`:
  Returns to search list and pre-opens next claim.
- `_attempt_recovery(...)`:
  Reload + re-search recovery path.
- `format_multi_claim_results(...)`:
  Combines multi-claim output into single-row multiline format.
- `process_one_row(...)`:
  End-to-end single CSV row processing with save-on-failure.
- `_reload_and_navigate(...)`:
  Row transition safety reload and re-navigation.
- `process_batch(...)`:
  Master orchestration for selected batch.
- `_record_error(...)`:
  Error category counting for summary.

## Threading and GUI Functions
- `run_in_background(...)`:
  Launches batch worker as daemon thread.
- `log_to_gui(...)`:
  Thread-safe GUI logging via `root.after`.
- `reset_ui_state(...)`:
  Restores UI controls and optional full clear.
- `browse_csv()`, `browse_folder()`:
  File/folder pickers.
- `validate_and_start()`:
  Input validation and run startup.
- `request_stop()`:
  Cooperative stop signal + owned browser shutdown.
- `create_gui()`:
  Full UI layout construction.

## Entry Point
- `if __name__ == "__main__": ...`:
  Creates GUI and starts Tk main loop.

---

## Input Requirements

Required CSV columns:
- `AltPatientID`
- `PatientName`
- `DOB`
- `StartDate`
- `EndDate`
- `InvoiceNumber`
- `VisitDate`

Derived internal columns:
- `Last_Name`
- `First_Name`

Output enrichment columns:
- `Claim ID`
- `Billed Amount`
- `Paid Amount`
- `Claim Status`
- `Denial Reason`
- `Finalized Date`
- `Check Number`
- `Check Date`

Run-state columns:
- `AutomationStatus`
- `LastError`

---

## Operational and Essential Notes

- Uses real user session/login; no credential storage in code.
- Designed for UI variability using selector fallback lists.
- Uses safer `.type()` for date fields due to Availity datepicker behavior.
- Saves intermediate progress frequently to avoid data loss.
- Supports resume runs by skipping rows already marked `Done`.
- Batch limit applies to pending rows only.
- Stop behavior is cooperative (finishes current operation/row boundary when possible).
- Relies on Availity iframe structure and current selectors; major UI changes require selector updates.

