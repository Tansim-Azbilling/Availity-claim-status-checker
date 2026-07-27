"""URLs, selectors, payer config, and Excel column contracts."""

AVAILITY_LOGIN_URL = "https://essentials.availity.com/static/public/onb/onboarding-ui-apps/availity-fr-ui/#/login"
AVAILITY_NAVIGATION_HOME = (
    "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/#/"
)
CDP_ENDPOINT = "http://localhost:9222"
NPI = "1235673930"

# UI state machine identifiers used by `_set_ui_state` to drive button enabling.
UI_STATE_IDLE = "idle"
UI_STATE_OPENING = "opening_browser"
UI_STATE_READY = "ready"
UI_STATE_RUNNING = "running"


# ============================================================================
# SECTION 2 — CONFIGURATION
# ============================================================================

# ---------------------------------------------------------------------------
# CSS / XPath selectors
# ---------------------------------------------------------------------------
# Selector profiles support payers on different Availity UI generations.
# Set ``selector_profile`` on a PAYER_CONFIG entry ('mui' default, 'legacy' for
# older HIPAA-tab forms, 'aetna' for Aetna Better Health).  Keys with a
# ``_selectors`` suffix hold fallback lists tried in order.

_SHARED_SELECTOR_KEYS = {
    # The SPA renders content inside a named iframe
    'iframe':           'iframe#newBodyFrame',
    'member_id':        '#subscriberMemberId',
    'last_name':        '#patientLastName',
    'first_name':       '#patientFirstName',
    'provider_npi':     '#providerNpi',
    'submit_btn':       '#submit-by276',
    'results_table':    '#claimsTable',
    'breadcrumb_search':  'a[aria-label="Search"]',
    'breadcrumb_results': 'a[aria-label="Results"]',
    'claims_finalized_date_header': (
        '#claimsTable th[role="columnheader"][title="Toggle SortBy"]:has-text("Finalized Date")'
    ),
    'line_table':       '#lineLevelTable',
    'codes_table':      '#codesTable',
    'remark_codes_grid': (
        '#lineLevelTable .MuiGrid-root:has(p:has-text("Reason/Remark Codes"))'
    ),
    'remark_codes_value': 'p:last-of-type',
    'claim_not_found_ack': (
        'div.MuiAlert-colorError[role="alert"] li:has-text("Acknowledgement/Not Found")'
    ),
    'claim_not_found_warning': (
        'div.MuiAlert-colorWarning[role="alert"] li:has-text("The payer could not find any results")'
    ),
    'invalid_member_id_alert': (
        'div.MuiAlert-root[role="alert"] .MuiAlert-message'
        ':has-text("Subscriber and subscriber id not found")'
    ),
    # Any visible payer alert after search (message text is classified at runtime).
    'payer_search_alert': 'div.MuiAlert-root[role="alert"]',
    'claim_status_panel':   '[data-testid="testClaim StatusPanel"] span.badge',
    'reason_remark_code_panel_selectors': [
        '[data-testid="testReason/Remark CodePanel"] p:last-of-type',
        '[id="Reason/Remark Code"] p:last-of-type',
    ],
    'remit_claim_tab':    'a.nav-link:has(span:has-text("Claim"))',
    'remit_search_input': '#claimSearchInput',
    'remit_search_btn':   '#claimSearchButton',
    'remit_table':        'div[role="table"][aria-label="Remits"]',
    'remit_adj_table':    'table[aria-label^="Adjustments"]',
    'remit_not_found': (
        'strong:has-text("We did not find remittance data matching your search criteria")'
    ),
    # Service-line summary table on remittance claim-details (Charge Amount = billed).
    'remit_service_line_table': 'table:has(thead th:has-text("Charge"))',
    'remit_charge_header_match': 'charge amount',
    'remit_payment_header_match': 'payment amount',
    'remit_charge_amount_selectors': [
        'xpath=.//*[contains(normalize-space(), "Charge Amount") and not(contains(normalize-space(), "Disclaimer"))]'
        '/ancestor::div[contains(@class,"row")][1]'
        '//*[contains(@class,"text-right")]',
        'xpath=.//*[contains(normalize-space(), "Charge Amount") and not(contains(normalize-space(), "Disclaimer"))]'
        '/ancestor::tr[1]/td[last()]',
        'xpath=.//*[contains(normalize-space(), "Charge Amount") and not(contains(normalize-space(), "Disclaimer"))]'
        '/following::*[self::p or self::span or self::td][contains(text(),"$")][1]',
        'xpath=.//*[contains(normalize-space(), "Charge Amount") and not(contains(normalize-space(), "Disclaimer"))]'
        '/ancestor::div[contains(@class,"MuiGrid")][1]//p[contains(@class,"text-right")][1]',
    ],
    'remit_payment_amount_selectors': [
        'xpath=.//*[contains(normalize-space(), "Payment Amount") and not(contains(normalize-space(), "Disclaimer"))]'
        '/ancestor::div[contains(@class,"row")][1]'
        '//*[contains(@class,"text-right")]',
        'xpath=.//*[contains(normalize-space(), "Paid Amount") and not(contains(normalize-space(), "Disclaimer"))]'
        '/ancestor::div[contains(@class,"row")][1]'
        '//*[contains(@class,"text-right")]',
        'xpath=.//*[contains(normalize-space(), "Payment Amount") and not(contains(normalize-space(), "Disclaimer"))]'
        '/ancestor::tr[1]/td[last()]',
        'xpath=.//*[contains(normalize-space(), "Payment Amount") and not(contains(normalize-space(), "Disclaimer"))]'
        '/following::*[self::p or self::span or self::td][contains(text(),"$")][1]',
    ],
}

SELECTOR_PROFILES = {
    'mui': {
        **_SHARED_SELECTOR_KEYS,
        'date_fill_mode': 'mui_picker',
        # MUI date pickers — legend labels (hidden input ids like :r2b: are dynamic)
        'patient_dob_label':       'Patient Date of Birth',
        'service_from_date_label': 'Service From Date',
        'service_to_date_label':   'Service To Date',
        'claim_id_panel':       '[data-testid="testClaim NumberPanel"] p:last-of-type',
        'finalized_date_panel': '[data-testid="testFinalized DatePanel"] p:last-of-type',
        'check_number_panel':   '[data-testid="testCheck NumberPanel"] p:last-of-type',
        'check_date_panel':     '[data-testid="testCheck DatePanel"] p:last-of-type',
        'billed_amount_selectors': [
            '[data-testid="testBilled AmountPanel"] p:last-of-type',
            '[id="Billed Amount"] p:last-of-type',
            '[data-testid="testBilledAmountPanel"] p:last-of-type',
            'xpath=//*[contains(@data-testid,"Billed") and contains(@data-testid,"Panel")]'
            '//p[last()]',
        ],
        'paid_amount_selectors': [
            '[data-testid="testPaid AmountPanel"] p:last-of-type',
            '[id="Paid Amount"] p:last-of-type',
            '[data-testid="testPaidAmountPanel"] p:last-of-type',
            'xpath=//*[contains(@data-testid,"Paid") and contains(@data-testid,"Panel")]'
            '//p[last()]',
        ],
        'hipaa_tab': (
            '[role="tablist"][aria-label="search tabs"] button[role="tab"]:has-text("HIPAA Standard")'
        ),
    },
    'legacy': {
        **_SHARED_SELECTOR_KEYS,
        'date_fill_mode': 'legacy_input',
        'dob':        '#patientBirthDate',
        'date_from':  '#fromDate',
        'date_to':    '#toDate',
        'claim_id_panel':       '[data-testid="testClaim NumberPanel"] p.text-right',
        'finalized_date_panel': '[data-testid="testFinalized DatePanel"] p.text-right',
        'check_number_panel':   '[data-testid="testCheck NumberPanel"] p.text-right',
        'check_date_panel':     '[data-testid="testCheck DatePanel"] p.text-right',
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
        'hipaa_tab': 'a[id="HIPAA Standard"][role="button"]',
    },
    'aetna': {
        'iframe':           'iframe#newBodyFrame',
        'member_id':        '#patientMemberId',
        'last_name':        '#patientLastName',
        'first_name':       '#patientFirstName',
        'submit_btn':       '#submit-by276',
        'results_table':    '#claimsTable',
        'claims_finalized_date_header': (
            '#claimsTable th[role="columnheader"][title="Toggle SortBy"]:has-text("Finalized Date")'
        ),
        'line_table':       '#lineLevelTable',
        'line_table_body_row': '#lineLevelTable tbody tr[role="row"]',
        # Service Dates=0, Billed Amount=7, Paid Amount=12; expand in last column
        'line_table_col_defaults': {
            'service_dates': 0,
            'billed': 7,
            'paid': 12,
            'remark_codes': 6,
        },
        'line_expand_button': 'button[title="Toggle Row Expanded"]',
        'codes_table':      '#codesTable',
        'remark_codes_grid': (
            '#lineLevelTable .MuiGrid-root:has(p:has-text("Reason/Remark Codes"))'
        ),
        'remark_codes_value': 'p:last-of-type',
        'claim_not_found_ack': (
            'div.MuiAlert-colorError[role="alert"] li:has-text("Acknowledgement/Not Found")'
        ),
        'claim_not_found_warning': (
            'div.MuiAlert-colorWarning[role="alert"] li:has-text("The payer could not find any results")'
        ),
        'invalid_member_id_alert': (
            'div.MuiAlert-root[role="alert"] .MuiAlert-message'
            ':has-text("Subscriber and subscriber id not found")'
        ),
        'payer_search_alert': 'div.MuiAlert-root[role="alert"]',
        # Claim detail info panels — div[id="…"] with value in p.text-right
        'claim_detail_ready':   '[id="Claim Number"]',
        'claim_id_panel':       '[id="Claim Number"] p.text-right',
        'claim_status_selectors': [
            '[id="Status"] p.text-right',
            '[id="Claim Status"] span.badge',
        ],
        'finalized_date_panel': '[id="Finalized Date"] p.text-right',
        'check_number_panel':   '[id="Check Number"] p.text-right',
        'check_date_panel':     '[id="Check Date"] p.text-right',
        'billed_amount_selectors': [
            '[id="Billed Amount"] p.text-right',
            '[data-testid="testBilled AmountPanel"] p.text-right',
        ],
        'paid_amount_selectors': [
            '[id="Paid Amount"] p.text-right',
            '[data-testid="testPaid AmountPanel"] p.text-right',
        ],
        'reason_remark_code_panel_selectors': [
            '[id="Reason/Remark Code"] p.text-right',
            '[data-testid="testReason/Remark CodePanel"] p:last-of-type',
        ],
        'remit_claim_tab':    'a.nav-link:has(span:has-text("Claim"))',
        'remit_search_input': '#claimSearchInput',
        'remit_search_btn':   '#claimSearchButton',
        'remit_table':        'div[role="table"][aria-label="Remits"]',
        'remit_adj_table':    'table[aria-label^="Adjustments"]',
        'remit_not_found': (
            'strong:has-text("We did not find remittance data matching your search criteria")'
        ),
        'date_fill_mode': 'plain_input',
        # Patient is subscriber — id suffix is dynamic (e.g. patientIsSubscriber-18)
        'patient_is_subscriber': 'input[id^="patientIsSubscriber"]',
        'dob':        '#patientBirthDate',
        'date_from':  '#serviceDates-start',
        'date_to':    '#serviceDates-end',
    },
}

DEFAULT_SELECTOR_PROFILE = 'mui'

SELECTORS = SELECTOR_PROFILES[DEFAULT_SELECTOR_PROFILE]


def get_selector_profile(payer_config=None):
    """Return the selector dict for a payer (defaults to the MUI profile)."""
    profile_name = DEFAULT_SELECTOR_PROFILE
    if payer_config:
        profile_name = payer_config.get('selector_profile', DEFAULT_SELECTOR_PROFILE)
    return SELECTOR_PROFILES[profile_name]

# Denial reason written when the remittance viewer returns no matching data.
REMIT_NOT_FOUND_DENIAL = 'Remittance not found'

# ---------------------------------------------------------------------------
# Line-level extraction (service-date rows in #lineLevelTable)
# ---------------------------------------------------------------------------
# filter_by_visit_date — when True, only rows matching the input VisitDate are
#                        processed for amounts and denial codes.
# match_mode — 'exact' (default): normalised range must equal VisitDate
#              (01/03/2025 → 01/03/2025-01/03/2025);
#              'within_range': only within-range matching (no exact pass);
#              'contains': legacy — VisitDate equals either bound of the line.
# fallback_within_range — when True and exact match finds nothing, retry using
#                         within-range matching (bundle lines like
#                         12/25/2025-01/08/2025 for VisitDate 01/08/2025).
# filter_results_by_visit_date — when True (default if fallback_within_range),
#                         narrow #claimsTable invoice matches to rows whose
#                         Service Dates contain the spreadsheet VisitDate.
# fallback_to_sole_line — when no match but the claim has exactly one service
#                         line, use that line so data is still captured.
#
# Per-payer overrides: add a nested ``line_level`` dict to any PAYER_CONFIG entry,
# e.g. ``'line_level': {'fallback_within_range': True}``.

LINE_LEVEL_CONFIG = {
    'filter_by_visit_date': True,
    'match_mode': 'exact',
    'fallback_to_sole_line': True,
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
#   uses_remittance_billed — read Charge Amount (billed) and Payment Amount
#                      (paid) from the remittance viewer claim-details line
#                      item summary (skips line-level amount scraping when
#                      uses_line_level is False)
#   remittance_amount_profile — optional pin after first run logs the winner:
#                      {'charge': {'method':'table_column','root':'service_line_table',...},
#                       'payment': {...}}
#   uses_results_finalized_date — read Finalized Date from the #claimsTable
#                      row being opened (before claim detail); False = detail
#                      panel and/or Check Date promotion
#   uses_claim_level_remark_fallback — when line-level remark read finds nothing,
#                      read the claim info panel and resolve via codes table
#   selector_profile — 'mui' (default), 'legacy' (HIPAA-tab plain inputs), or
#                      'aetna' (Aetna Better Health — no HIPAA tab)
#   informational_alert_phrases — optional tuple of substrings; visible MUI
#                      alerts containing any phrase are ignored (not treated as
#                      search errors). Global phrases apply to all payers.
#   bundle_search_date_fallback — when True, if the first search used StartDate/
#                      EndDate and fails (not found or no results match), retry
#                      once with min–max VisitDate bundle dates for the invoice.

PAYER_CONFIG = {
    'Healthfirst': {
        'url': (
            "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2Fenhanced-claim-status-ui%2F%23%2Felement%2Fdashboard%3ForgId%3D35022783%26payerId%3D80141T"
        ),
        'uses_hipaa_tab':  True,
        'uses_line_level': True,
        'uses_remittance': False,
        'uses_results_finalized_date': False,
        'bundle_search_date_fallback': True,
    },
    'Integra': {
        'url': (
            "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2Fenhanced-claim-status-ui%2F%23%2Felement%2Fdashboard%3ForgId%3D50456729%26payerId%3D303"
        ),
        'uses_hipaa_tab':  True,
        'uses_line_level': True,
        'uses_remittance': False,
        'uses_results_finalized_date': False,
        'gui_enabled': False,
    },
    'SWHNY': {
        'url': (
            "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2Fenhanced-claim-status-ui%2F%23%2Felement%2Fdashboard%3ForgId%3D35022783%26payerId%3D303"
        ),
        'uses_hipaa_tab':  True,
        'uses_line_level': True,
        'uses_remittance': False,
        'uses_results_finalized_date': False,
        'uses_claim_level_remark_fallback': True,
        'informational_alert_phrases': (
            'allow up to 5 business days for it to appear',
            'poa (present on admission) indicator issue',
        ),
    },
    'Villagecaremax': {
        'url': (
            "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2Fenhanced-claim-status-ui%2F%23%2Felement%2Fdashboard%3ForgId%3D35022783%26payerId%3D26545"
        ),
        'uses_hipaa_tab':  False,
        'uses_line_level': False,
        'uses_remittance': True,
        'uses_results_finalized_date': True,
    },
    'Aetna Better Health': {
        'url': (
            "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2Fenhanced-claim-status-ui%2F%23%2Fdashboard%3ForgId%3D11255438%26payerId%3DAETNA"
        ),
        'uses_hipaa_tab':  False,
        'uses_line_level': True,
        'uses_remittance': False,
        'uses_results_finalized_date': False,
        'selector_profile': 'aetna',
        'gui_enabled': False,
    },
    'Anthem BCBS': {
        'url': (
            "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2Fenhanced-claim-status-ui%2F%23%2Felement%2Fdashboard%3ForgId%3D34974655%26payerId%3D26545"
        ),
        'uses_hipaa_tab':  True,
        'uses_line_level': True,
        'uses_remittance': False,
        'uses_results_finalized_date': False,
        'bundle_search_date_fallback': True,
        'gui_enabled': False,
    },
    'Fidelis': {
        'url': (
            "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2Fenhanced-claim-status-ui%2F%23%2Felement%2Fdashboard%3ForgId%3D36696393%26payerId%3D11315"
        ),
        'uses_hipaa_tab': True,
        'uses_line_level': True,
        'uses_remittance': False,
        'uses_results_finalized_date': False,
        'informational_alert_phrases': (
            'complete provider record in the provider list',
        ),
        'bundle_search_date_fallback': True,
        'gui_enabled': False,
    },
    'Empire': {
        'url': (
            "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2Fenhanced-claim-status-ui%2F%23%2Felement%2Fdashboard%3ForgId%3D35022783%26payerId%3D303"
        ),
        'uses_hipaa_tab':  True,
        'uses_line_level': True,
        'uses_remittance': False,
        'uses_results_finalized_date': False,
        'line_level': {
            'match_mode': 'exact',
            'filter_by_visit_date': True,
            'fallback_to_sole_line': False,
        },
    },
    'Molina Home Health': {
        'url': (
            "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/navigation/#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2Fenhanced-claim-status-ui%2F%23%2Felement%2Fdashboard%3ForgId%3D11255438%26payerId%3D16146"
        ),
        'uses_hipaa_tab':  True,
        'uses_line_level': False,
        'uses_remittance': True,
        'uses_remittance_billed': True,
        'uses_results_finalized_date': False,
        'gui_enabled': False,
    },
}

def get_gui_payer_names():
    """Return payer names shown in the GUI dropdown."""
    return [
        name
        for name, cfg in PAYER_CONFIG.items()
        if cfg.get('gui_enabled', True)
    ]

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

# Columns that MUST exist in the input Excel before any processing starts.
# Optional: Recheck — process "yes" (re-runs Done rows on resume) or empty; skip "no".
# validate_dataframe() checks these and aborts early if any are absent.
REQUIRED_COLUMNS = [
    'AltPatientID', 'PatientName', 'DOB',
    'StartDate', 'EndDate', 'InvoiceNumber', 'VisitDate',
]

# Columns appended to the dataframe to hold automation output.
OUTPUT_COLUMNS = [
    'Claim ID', 'Billed Amount', 'Paid Amount', 'Claim Status',
    'Denial Reason', 'Last Action Taken', 'Finalized Date', 'Check Number', 'Check Date',
    'Recheck',
]
STATUS_COLUMNS = ['AutomationStatus', 'LastError']

# Claim Status value when Availity shows the acknowledgement/not-found alert.
CLAIM_NOT_FOUND_STATUS = 'Claim Not found'

# Claim Status when search returns subscriber/member id not found (MUI alert, no results table).
INVALID_MEMBER_ID_STATUS = 'Invalid Member ID'

# Claim Status when the input row has no usable DOB (e.g. spreadsheet says Not Found).
DOB_NOT_FOUND_STATUS = 'DOB Not Found'

# Claim Status when Availity shows an unrecognized payer error after search.
PAYER_SEARCH_ERROR_STATUS = 'Payer search error'

# Claim Status value when paid amount exceeds billed amount.
PAID_OVERPAYMENT_STATUS = 'Paid (Overpayment)'

# Error labels written into Claim Status when a row cannot be processed.
# Used by _record_error(), _row_has_prior_error(), and batch retry eligibility.
KNOWN_ERROR_STATUSES = frozenset({
    'Navigation failed', 'Form error', 'Search failed',
    'No claims found. Advised to search manually',
    'Claim not found. Search manually', 'Critical error',
    'Missing InvoiceNumber', 'Error', INVALID_MEMBER_ID_STATUS,
})
