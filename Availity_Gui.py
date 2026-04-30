import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import pandas as pd
import threading
import time
from datetime import datetime
import traceback
from playwright.sync_api import sync_playwright

# ============================================================================
# GLOBAL STATE
# ============================================================================
is_running = False
current_page = None
current_playwright = None


# ============================================================================
# DATE UTILITIES
# ============================================================================

def normalize_date(date_str):
    """Convert '1/1/2026' to '01/01/2026' for consistent matching"""
    try:
        parts = str(date_str).strip().split('/')
        if len(parts) == 3:
            month = parts[0].zfill(2)
            day = parts[1].zfill(2)
            year = parts[2]
            return f"{month}/{day}/{year}"
        return date_str
    except:
        return date_str


def normalize_date_range(date_str):
    """Convert '1/1/2026-1/1/2026' to '01/01/2026-01/01/2026'"""
    try:
        if '-' in str(date_str):
            parts = str(date_str).strip().split('-')
            from_date = normalize_date(parts[0])
            to_date = normalize_date(parts[1]) if len(parts) > 1 else from_date
            return f"{from_date}-{to_date}"
        else:
            normalized = normalize_date(date_str)
            return f"{normalized}-{normalized}"
    except:
        return date_str


# ============================================================================
# BROWSER MANAGEMENT
# ============================================================================

def setup_browser():
    """Initialize browser connection via CDP"""
    global current_playwright, current_page

    current_playwright = sync_playwright().start()
    browser = current_playwright.chromium.connect_over_cdp("http://localhost:9222")
    default_context = browser.contexts[0]
    current_page = default_context.pages[0] if default_context.pages else default_context.new_page()

    return current_page


def cleanup_browser():
    """Close browser connection"""
    global current_playwright
    if current_playwright:
        try:
            current_playwright.stop()
        except:
            pass


# ============================================================================
# FILE OPERATIONS
# ============================================================================

def load_csv_file(file_path):
    """Load CSV and parse patient names into separate columns"""
    try:
        df = pd.read_csv(file_path)

        if 'PatientName' in df.columns:
            name_parts = df['PatientName'].str.split(',', n=1, expand=True)
            df['Last_Name'] = name_parts[0].str.strip()
            df['First_Name'] = name_parts[1].str.strip() if len(name_parts.columns) > 1 else ''

        return df
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load CSV: {str(e)}")
        return None


def initialize_output_columns(df):
    """Add output columns to dataframe if they don't exist"""
    output_columns = [
        'Claim ID', 'Billed Amount', 'Paid Amount', 'Claim Status',
        'Denial Reason', 'Finalized Date', 'Check Number', 'Check Date'
    ]

    for col in output_columns:
        if col not in df.columns:
            df[col] = ''

    return df


def save_progress_file(df, output_folder, prefix="progress"):
    """Save dataframe to timestamped CSV file"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"{output_folder}/{prefix}_{timestamp}.csv"
        df.to_csv(filepath, index=False)
        log_to_gui(f"  💾 Saved: {filepath}\n", "info")
        return filepath
    except Exception as e:
        log_to_gui(f"  ❌ Save error: {str(e)}\n", "error")
        return None


# ============================================================================
# WEB SCRAPING - SELECTORS
# ============================================================================

SELECTORS = {
    'search_url': "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2Fenhanced-claim-status-ui%2F%23%2Fdashboard%3ForgId%3D34974655%26payerId%3D80141T%26activeTab%3Dby276",
    'iframe': 'iframe#newBodyFrame',
    'member_id': '#subscriberMemberId',
    'last_name': '#patientLastName',
    'first_name': '#patientFirstName',
    'dob': '#patientBirthDate',
    'date_from': '#fromDate',
    'date_to': '#toDate',
    'submit_btn': '#submit-by276',
    'results_table': '#claimsTable',
    'line_table': '#lineLevelTable',
    'codes_table': '#codesTable'
}


# ============================================================================
# WEB SCRAPING - NAVIGATION
# ============================================================================

def wait_for_page_ready(page):
    """Wait for page and iframe to be fully loaded"""
    try:
        # Wait for iframe to exist in DOM
        log_to_gui(f"  → Waiting for iframe...\n")
        page.wait_for_selector(SELECTORS['iframe'], state='attached', timeout=30000)
        time.sleep(2)

        # Get iframe and wait for form
        iframe = page.frame_locator(SELECTORS['iframe'])
        iframe.locator(SELECTORS['member_id']).wait_for(state='visible', timeout=30000)

        log_to_gui(f"  ✓ Page ready\n", "success")
        return iframe

    except Exception as e:
        log_to_gui(f"  ❌ Page not ready: {str(e)}\n", "error")
        return None


def fill_search_form(iframe, row_data):
    """Fill all search form fields with normalized dates"""
    try:
        log_to_gui(f"  → Filling form...\n")

        iframe.locator(SELECTORS['member_id']).fill(str(row_data['AltPatientID']))
        iframe.locator(SELECTORS['last_name']).fill(str(row_data['Last_Name']))
        iframe.locator(SELECTORS['first_name']).fill(str(row_data['First_Name']))
        iframe.locator(SELECTORS['dob']).type(str(row_data['DOB']))

        # Normalize dates before filling
        start_date = normalize_date(str(row_data['StartDate']))
        end_date = normalize_date(str(row_data['EndDate']))

        iframe.locator(SELECTORS['date_from']).type(start_date)
        iframe.locator(SELECTORS['date_to']).type(end_date)

        return True
    except Exception as e:
        log_to_gui(f"  ❌ Form fill error: {str(e)}\n", "error")
        return False


def submit_search_and_wait(iframe):
    """Submit search and wait for results"""
    try:
        log_to_gui(f"  → Submitting search...\n")
        iframe.locator(SELECTORS['submit_btn']).click()
        iframe.locator(SELECTORS['results_table']).wait_for(state='visible', timeout=15000)
        return True
    except Exception as e:
        log_to_gui(f"  ❌ Search failed: {str(e)}\n", "error")
        return False


# ============================================================================
# WEB SCRAPING - DATA EXTRACTION
# ============================================================================

def find_matching_claims(iframe, invoice_number):
    """Find all rows matching the invoice number"""
    try:
        results_body = iframe.locator('#claimsTable tbody')

        if results_body.count() == 0:
            raise Exception("Results table not found")

        matching_rows = iframe.locator(f"#claimsTable tbody tr:has-text('{invoice_number}')")
        match_count = matching_rows.count()

        if match_count == 0:
            raise Exception(f"Invoice {invoice_number} not found")

        log_to_gui(f"  ✓ Found {match_count} claim(s)\n", "success")
        return matching_rows, match_count

    except Exception as e:
        log_to_gui(f"  ⚠️ {str(e)}\n", "error")
        return None, 0


def extract_claim_header_data(iframe):
    """Extract top-level claim information"""
    claim_data = {}

    def safe_extract(selector, label):
        try:
            return iframe.locator(selector).text_content(timeout=5000).strip()
        except:
            log_to_gui(f"    ⚠️ {label} not found\n", "error")
            return '--'

    claim_data['Claim ID'] = safe_extract('[data-testid="testClaim NumberPanel"] p.text-right', 'Claim ID')
    claim_data['Claim Status'] = safe_extract('[data-testid="testClaim StatusPanel"] span.badge', 'Status')
    claim_data['Finalized Date'] = safe_extract('[data-testid="testFinalized DatePanel"] p.text-right',
                                                'Finalized Date')
    claim_data['Check Number'] = safe_extract('[data-testid="testCheck NumberPanel"] p.text-right', 'Check Number')
    claim_data['Check Date'] = safe_extract('[data-testid="testCheck DatePanel"] p.text-right', 'Check Date')

    log_to_gui(f"    • Claim ID: {claim_data['Claim ID']}\n")
    log_to_gui(f"    • Status: {claim_data['Claim Status']}\n")

    return claim_data


def find_matching_line_by_date(iframe, visit_date):
    """Find line item matching visit date and extract amounts"""
    try:
        iframe.locator(SELECTORS['line_table']).wait_for(state='visible', timeout=15000)

        line_rows = iframe.locator('#lineLevelTable tbody tr[role="row"]')
        row_count = line_rows.count()

        # Normalize the target visit date
        normalized_visit = normalize_date_range(visit_date)

        log_to_gui(f"    → Searching {row_count} lines for: {normalized_visit}\n")

        for idx in range(row_count):
            try:
                service_dates_cell = line_rows.nth(idx).locator('td').nth(3)
                date_paragraphs = service_dates_cell.locator('p')

                if date_paragraphs.count() >= 2:
                    # Date range format
                    from_date = date_paragraphs.nth(0).text_content(timeout=3000).strip()
                    to_date = date_paragraphs.nth(1).text_content(timeout=3000).strip()

                    # Normalize scraped dates
                    from_normalized = normalize_date(from_date)
                    to_normalized = normalize_date(to_date)
                    date_range = f"{from_normalized}-{to_normalized}"

                elif date_paragraphs.count() == 1:
                    # Single date
                    single_date = date_paragraphs.nth(0).text_content(timeout=3000).strip()
                    single_normalized = normalize_date(single_date)
                    date_range = f"{single_normalized}-{single_normalized}"
                else:
                    continue

                # Compare normalized dates
                if date_range == normalized_visit:
                    log_to_gui(f"    ✓ Match found: {date_range}\n", "success")

                    matching_row = line_rows.nth(idx)
                    billed = matching_row.locator('td').nth(7).text_content(timeout=3000).strip()
                    paid = matching_row.locator('td').nth(6).text_content(timeout=3000).strip()

                    log_to_gui(f"    • Billed: {billed}, Paid: {paid}\n")

                    return matching_row, idx, billed, paid
            except:
                continue

        log_to_gui(f"    ⚠️ No matching line found\n", "error")
        return None, -1, '--', '--'

    except Exception as e:
        log_to_gui(f"    ⚠️ Line table error: {str(e)}\n", "error")
        return None, -1, '--', '--'


def extract_denial_codes(iframe, matching_row, row_index):
    """Extract and lookup denial reason codes with robust fallback"""
    try:
        log_to_gui(f"    → Extracting denial codes...\n")

        # Expand line item
        expand_button = matching_row.locator('td').first.locator('button')
        expand_button.click()
        time.sleep(2)

        # Extract codes using robust search
        try:
            # Search entire table for visible remark codes (most recently expanded)
            all_remark_headers = iframe.locator('#lineLevelTable').locator(
                'p.font-weight-bold:has-text("Reason/Remark Codes")'
            )

            count = all_remark_headers.count()
            if count > 0:
                remark_header = all_remark_headers.nth(count - 1)
                remark_codes_text = remark_header.locator(
                    'xpath=following-sibling::p[1]'
                ).text_content(timeout=3000).strip()
            else:
                # Fallback: search siblings
                for offset in range(1, 5):
                    sibling_row = matching_row.locator(f'xpath=following-sibling::tr[{offset}]')

                    if sibling_row.locator('p.font-weight-bold:has-text("Reason/Remark Codes")').count() > 0:
                        remark_codes_text = sibling_row.locator(
                            'p.font-weight-bold:has-text("Reason/Remark Codes")'
                        ).locator('xpath=following-sibling::p[1]').text_content(timeout=3000).strip()
                        break
                else:
                    raise Exception("Remark codes not found")

        except Exception as extract_err:
            log_to_gui(f"    ⚠️ Remark codes not found\n", "error")

            # Cleanup
            try:
                expand_button.click()
                time.sleep(0.5)
            except:
                pass

            return '--'

        if not remark_codes_text:
            # Cleanup
            try:
                expand_button.click()
                time.sleep(0.5)
            except:
                pass
            return '--'

        log_to_gui(f"    • Codes: {remark_codes_text}\n")

        # Lookup codes in table
        codes_list = [code.strip() for code in remark_codes_text.split(',')]

        try:
            iframe.locator(SELECTORS['codes_table']).scroll_into_view_if_needed()
            time.sleep(0.5)
        except:
            pass

        descriptions = []
        for code in codes_list:
            try:
                matching_code_row = iframe.locator(
                    f'#codesTable tbody tr:has(td:text("Remark")):has(td:text-is("{code}"))'
                )

                if matching_code_row.count() > 0:
                    desc = matching_code_row.locator('td').nth(2).text_content(timeout=3000).strip()
                    descriptions.append(desc)
                    log_to_gui(f"      • {code}: {desc}\n")
            except:
                continue

        # Cleanup: collapse row
        try:
            log_to_gui(f"    → Collapsing row...\n")
            expand_button.click()
            time.sleep(1)
        except:
            pass

        # Extra cooldown
        time.sleep(1)

        return ', '.join(descriptions) if descriptions else '--'

    except Exception as e:
        log_to_gui(f"    ⚠️ Denial extraction error: {str(e)}\n", "error")

        # Cleanup on error
        try:
            matching_row.locator('td').first.locator('button').click()
            time.sleep(0.5)
        except:
            pass

        return '--'


def determine_denial_reason(iframe, claim_status, billed, paid, matching_row, row_index):
    """Determine if denial reason extraction is needed"""
    if claim_status.upper() == 'PENDING':
        log_to_gui(f"    ℹ️ PENDING - skipping denial codes\n", "info")
        return '--'

    if matching_row is None:
        return '--'

    if claim_status.upper() == 'PAID' and billed == paid:
        log_to_gui(f"    ℹ️ Fully paid - skipping denial codes\n", "info")
        return '--'

    return extract_denial_codes(iframe, matching_row, row_index)


# ============================================================================
# CLAIM PROCESSING LOGIC
# ============================================================================

def create_default_claim_data(status='Not found'):
    """Create default claim data structure"""
    return {
        'Claim ID': '--',
        'Billed Amount': '--',
        'Paid Amount': '--',
        'Claim Status': status,
        'Denial Reason': '--',
        'Finalized Date': '--',
        'Check Number': '--',
        'Check Date': '--'
    }


def process_single_claim(page, iframe, row_data, invoice_number, visit_date, claim_idx, total_claims):
    """Process one claim and extract all data"""
    global is_running

    if not is_running:
        return None

    try:
        log_to_gui(f"  → Processing claim {claim_idx + 1}/{total_claims}...\n", "info")

        # Extract header data
        claim_data = extract_claim_header_data(iframe)

        # Handle pending claims
        if claim_data['Claim Status'].upper() == 'PENDING':
            log_to_gui(f"    ℹ️ PENDING status\n", "info")
            claim_data['Billed Amount'] = '--'
            claim_data['Paid Amount'] = '--'
            claim_data['Denial Reason'] = '--'
            return claim_data

        # Find matching line item
        matching_row, row_index, billed, paid = find_matching_line_by_date(iframe, visit_date)

        claim_data['Billed Amount'] = billed
        claim_data['Paid Amount'] = paid

        # Extract denial reason if needed
        claim_data['Denial Reason'] = determine_denial_reason(
            iframe, claim_data['Claim Status'], billed, paid, matching_row, row_index
        )

        log_to_gui(f"    ✓ Claim {claim_idx + 1} complete\n", "success")
        return claim_data

    except Exception as e:
        log_to_gui(f"    ❌ Claim error: {str(e)}\n", "error")
        return create_default_claim_data('Error')


def process_all_matching_claims(page, iframe, row_data, invoice_number, visit_date, matching_rows, total_matches):
    """Process all claims matching the invoice number"""
    all_claims = []

    for claim_idx in range(total_matches):
        if not is_running:
            break

        try:
            # Click claim
            matching_rows.nth(claim_idx).click()
            iframe.locator('[data-testid="testClaim NumberPanel"]').wait_for(state='visible', timeout=15000)

            # Extract data
            claim_data = process_single_claim(
                page, iframe, row_data, invoice_number, visit_date, claim_idx, total_matches
            )

            if claim_data:
                all_claims.append(claim_data)

            # Navigate back for next claim
            if claim_idx < total_matches - 1:
                try:
                    log_to_gui(f"  → Going back to search...\n")

                    # Reload page
                    page.reload(wait_until='domcontentloaded', timeout=45000)
                    time.sleep(3)

                    # Wait for page ready
                    iframe = wait_for_page_ready(page)

                    if iframe is None:
                        log_to_gui(f"  ❌ Could not reload page\n", "error")
                        break

                    # Re-submit search
                    fill_search_form(iframe, row_data)
                    submit_search_and_wait(iframe)
                    matching_rows = iframe.locator(f"#claimsTable tbody tr:has-text('{invoice_number}')")

                except Exception as nav_err:
                    log_to_gui(f"  ❌ Navigation error: {str(nav_err)}\n", "error")
                    break

        except Exception as e:
            log_to_gui(f"  ❌ Claim error: {str(e)}\n", "error")
            all_claims.append(create_default_claim_data('Error'))

            # Try recovery
            try:
                page.reload(wait_until='domcontentloaded', timeout=45000)
                time.sleep(3)
                iframe = wait_for_page_ready(page)

                if iframe:
                    fill_search_form(iframe, row_data)
                    submit_search_and_wait(iframe)
                    matching_rows = iframe.locator(f"#claimsTable tbody tr:has-text('{invoice_number}')")
                else:
                    break
            except:
                break

    return all_claims


def format_claims_for_dataframe(claims_list):
    """Format list of claim dicts into multi-line strings"""
    if not claims_list:
        return create_default_claim_data('No data')

    formatted = {}
    fields = ['Claim ID', 'Billed Amount', 'Paid Amount', 'Claim Status',
              'Denial Reason', 'Finalized Date', 'Check Number', 'Check Date']

    for field in fields:
        formatted[field] = '\n'.join([
            f"{i + 1}. {claim[field]}" for i, claim in enumerate(claims_list)
        ])

    return formatted


def process_single_row(page, df, row_index, row_data, output_folder):
    """Process one CSV row - complete claim search and extraction"""
    global is_running

    if not is_running:
        return False

    try:
        log_to_gui(f"\n🔄 Row {row_index + 1}...\n", "info")

        invoice_number = str(row_data['InvoiceNumber']).strip()
        visit_date = str(row_data['VisitDate']).strip()

        log_to_gui(f"  → Invoice: {invoice_number}\n")
        log_to_gui(f"  → Visit Date: {visit_date}\n")

        # ============================================
        # Reload + Navigate (except for first row)
        # ============================================
        try:
            if row_index > 0:
                # Log current URL for debugging
                try:
                    current_url = page.url
                    log_to_gui(f"  📍 Current URL: {current_url[:80]}...\n")
                except:
                    log_to_gui(f"  ⚠️ Cannot get current URL\n", "error")

                # Reload first
                try:
                    log_to_gui(f"  → Step 1: Reloading browser...\n")
                    page.reload(wait_until='domcontentloaded', timeout=30000)
                    time.sleep(2)
                    log_to_gui(f"  ✓ Reload complete\n", "success")
                except Exception as reload_err:
                    log_to_gui(f"  ⚠️ Reload failed: {str(reload_err)}\n", "error")

                # Then navigate
                try:
                    log_to_gui(f"  → Step 2: Going to search page...\n")
                    page.goto(SELECTORS['search_url'], wait_until='domcontentloaded', timeout=45000)
                    time.sleep(3)
                    log_to_gui(f"  ✓ Navigation complete\n", "success")
                except Exception as goto_err:
                    log_to_gui(f"  ❌ Navigation failed: {str(goto_err)}\n", "error")
                    raise

            # Verify page is ready
            iframe = wait_for_page_ready(page)

            if iframe is None:
                raise Exception("Page not ready after navigation")

        except Exception as nav_error:
            log_to_gui(f"  ❌ Page setup failed: {str(nav_error)}\n", "error")
            df.loc[row_index, list(create_default_claim_data().keys())] = list(
                create_default_claim_data('Navigation failed').values())
            save_progress_file(df, output_folder)
            return True

        # Fill and submit search
        if not fill_search_form(iframe, row_data):
            df.loc[row_index, list(create_default_claim_data().keys())] = list(
                create_default_claim_data('Form error').values())
            save_progress_file(df, output_folder)
            return True

        if not submit_search_and_wait(iframe):
            df.loc[row_index, list(create_default_claim_data().keys())] = list(
                create_default_claim_data('Search failed').values())
            save_progress_file(df, output_folder)
            return True

        # Find and process claims
        matching_rows, match_count = find_matching_claims(iframe, invoice_number)

        if match_count == 0:
            df.loc[row_index, list(create_default_claim_data().keys())] = list(
                create_default_claim_data('Claim not found. Search manually').values())
            save_progress_file(df, output_folder)
            return True

        all_claims = process_all_matching_claims(
            page, iframe, row_data, invoice_number, visit_date, matching_rows, match_count
        )

        # Store results
        formatted = format_claims_for_dataframe(all_claims)
        for field, value in formatted.items():
            df.at[row_index, field] = value

        save_progress_file(df, output_folder)

        log_to_gui(f"  ✓ Row {row_index + 1} complete\n", "success")

        # Cooldown between rows
        if row_index < len(df) - 1:
            time.sleep(2)

        return True

    except Exception as e:
        log_to_gui(f"  ❌ Row error: {str(e)}\n", "error")
        log_to_gui(f"{traceback.format_exc()}\n", "error")
        df.loc[row_index, list(create_default_claim_data().keys())] = list(
            create_default_claim_data('Critical error').values())
        save_progress_file(df, output_folder)
        return True

# ============================================================================
# BATCH PROCESSING
# ============================================================================

def process_batch(batch_size, csv_path, output_folder, payer):
    """Main batch processing function"""
    global is_running

    try:
        # Setup browser
        log_to_gui("🌐 Connecting to browser...\n", "info")
        page = setup_browser()
        log_to_gui("✓ Browser connected!\n", "success")

        # ============================================
        # NAVIGATE TO SEARCH PAGE ONCE
        # ============================================
        log_to_gui("🔗 Navigating to search page...\n", "info")
        page.goto(SELECTORS['search_url'], wait_until='domcontentloaded', timeout=45000)
        time.sleep(3)

        # Verify page loaded
        iframe = wait_for_page_ready(page)
        if iframe is None:
            log_to_gui("❌ Failed to load initial page\n", "error")
            reset_ui_state()
            return

        log_to_gui("✓ Initial navigation complete!\n", "success")

        # Load data
        log_to_gui(f"📂 Loading CSV...\n", "info")
        df = load_csv_file(csv_path)

        if df is None:
            reset_ui_state()
            return

        df = initialize_output_columns(df)
        log_to_gui(f"✓ Loaded {len(df)} rows\n", "success")

        # Process rows
        rows_to_process = min(batch_size, len(df))
        log_to_gui(f"\n📦 Processing {rows_to_process} rows for {payer}...\n", "info")
        log_to_gui("-" * 60 + "\n")

        for idx in range(rows_to_process):
            if not is_running:
                log_to_gui("⚠ Stopped by user\n", "error")
                break

            process_single_row(page, df, idx, df.iloc[idx], output_folder)

        # Final save
        log_to_gui("-" * 60 + "\n")
        save_progress_file(df, output_folder, "FINAL_results")
        log_to_gui(f"✓ Complete! {rows_to_process} claims processed\n", "success")

    except Exception as e:
        log_to_gui(f"❌ Critical error: {str(e)}\n", "error")
        log_to_gui(f"{traceback.format_exc()}\n", "error")
    finally:
        cleanup_browser()
        reset_ui_state()


# ============================================================================
# THREADING
# ============================================================================

def run_in_background(batch_size, csv_path, output_folder, payer):
    """Run automation in background thread"""
    thread = threading.Thread(
        target=process_batch,
        args=(batch_size, csv_path, output_folder, payer),
        daemon=True
    )
    thread.start()


# ============================================================================
# GUI - LOGGING
# ============================================================================

def log_to_gui(message, tag="info"):
    """Thread-safe logging to GUI"""

    def _insert():
        log_text.config(state="normal")
        log_text.insert(tk.END, message, tag)
        log_text.see(tk.END)
        log_text.config(state="disabled")

    root.after(0, _insert)


# ============================================================================
# GUI - CONTROLS
# ============================================================================

def reset_ui_state():
    """Reset UI to ready state"""
    global is_running
    is_running = False

    def _reset():
        start_button.config(state="normal")
        stop_button.config(state="disabled")

    root.after(0, _reset)


def browse_csv():
    """File dialog for CSV"""
    filename = filedialog.askopenfilename(
        title="Select Collection File",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    if filename:
        collection_file_var.set(filename)


def browse_folder():
    """Folder dialog for output"""
    folder = filedialog.askdirectory(title="Select Output Folder")
    if folder:
        output_folder_var.set(folder)


def validate_and_start():
    """Validate inputs and start"""
    global is_running

    csv_file = collection_file_var.get()
    output_dir = output_folder_var.get()
    payer = payer_var.get()

    try:
        batch = int(batch_size_var.get())
    except ValueError:
        messagebox.showerror("Error", "Batch size must be a number")
        return

    if not csv_file:
        messagebox.showerror("Error", "Select collection file")
        return

    if not output_dir:
        messagebox.showerror("Error", "Select output folder")
        return

    if not payer:
        messagebox.showerror("Error", "Select payer")
        return

    # Update UI
    is_running = True
    start_button.config(state="disabled")
    stop_button.config(state="normal")

    # Clear log
    log_text.config(state="normal")
    log_text.delete(1.0, tk.END)
    log_text.config(state="disabled")

    # Start
    run_in_background(batch, csv_file, output_dir, payer)


def request_stop():
    """Request stop"""
    global is_running
    is_running = False
    log_to_gui("\n⚠ Stop requested...\n", "error")


# ============================================================================
# GUI - LAYOUT
# ============================================================================

def create_gui():
    """Create GUI"""
    global root, log_text, start_button, stop_button
    global collection_file_var, output_folder_var, batch_size_var, payer_var

    root = tk.Tk()
    root.title("Availity Claim Automation")
    root.geometry("850x650")

    # Variables
    collection_file_var = tk.StringVar()
    output_folder_var = tk.StringVar()
    batch_size_var = tk.StringVar(value="10")
    payer_var = tk.StringVar(value="Healthfirst")

    # Main frame
    main_frame = tk.Frame(root, padx=20, pady=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title
    tk.Label(main_frame, text="Availity Claim Status Checker",
             font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=3, pady=(0, 20))

    # Collection File
    tk.Label(main_frame, text="Collection File:",
             font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=5)
    tk.Entry(main_frame, textvariable=collection_file_var,
             width=50).grid(row=1, column=1, pady=5, padx=5)
    tk.Button(main_frame, text="Browse",
              command=browse_csv).grid(row=1, column=2, pady=5)

    # Output Folder
    tk.Label(main_frame, text="Output Folder:",
             font=("Arial", 10)).grid(row=2, column=0, sticky="w", pady=5)
    tk.Entry(main_frame, textvariable=output_folder_var,
             width=50).grid(row=2, column=1, pady=5, padx=5)
    tk.Button(main_frame, text="Browse",
              command=browse_folder).grid(row=2, column=2, pady=5)

    # Batch Size
    tk.Label(main_frame, text="Batch Size:",
             font=("Arial", 10)).grid(row=3, column=0, sticky="w", pady=5)
    tk.Entry(main_frame, textvariable=batch_size_var,
             width=20).grid(row=3, column=1, sticky="w", pady=5, padx=5)

    # Payer
    tk.Label(main_frame, text="Select Payer:",
             font=("Arial", 10)).grid(row=4, column=0, sticky="w", pady=5)
    ttk.Combobox(main_frame, textvariable=payer_var,
                 values=["Healthfirst", "Anthem", "SWHNY"],
                 state="readonly", width=47).grid(row=4, column=1, sticky="w", pady=5, padx=5)

    # Buttons
    button_frame = tk.Frame(main_frame)
    button_frame.grid(row=5, column=0, columnspan=3, pady=20)

    start_button = tk.Button(button_frame, text="Start", command=validate_and_start,
                             bg="green", fg="white", font=("Arial", 10, "bold"), width=15)
    start_button.pack(side=tk.LEFT, padx=10)

    stop_button = tk.Button(button_frame, text="Stop", command=request_stop,
                            bg="red", fg="white", font=("Arial", 10, "bold"),
                            width=15, state="disabled")
    stop_button.pack(side=tk.LEFT, padx=10)

    # Log
    tk.Label(main_frame, text="Log:",
             font=("Arial", 10, "bold")).grid(row=6, column=0, sticky="w", pady=(10, 5))

    log_frame = tk.Frame(main_frame)
    log_frame.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=5)

    scrollbar = tk.Scrollbar(log_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    log_text = tk.Text(log_frame, height=20, width=95,
                       yscrollcommand=scrollbar.set, state="disabled", wrap=tk.WORD)
    log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=log_text.yview)

    # Colors
    log_text.tag_config("info", foreground="blue")
    log_text.tag_config("success", foreground="green")
    log_text.tag_config("error", foreground="red")

    # Grid weights
    main_frame.grid_rowconfigure(7, weight=1)
    main_frame.grid_columnconfigure(1, weight=1)

    return root


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    root = create_gui()
    root.mainloop()