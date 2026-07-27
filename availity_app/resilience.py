"""Circuit breaker and failure artifacts for batch runs."""
import json
import os
from datetime import datetime

from availity_app.logging_gui import log_to_gui

SESSION_ERROR_LIMIT = 3
TRANSIENT_ERROR_LIMIT = 5

TRANSIENT_ERROR_MARKERS = frozenset({
    'Navigation failed',
    'Form error',
    'Search failed',
    'Critical error',
    'Unknown row processing error',
})


class BatchCircuitBreaker:
    """Pause or stop the batch after repeated session or transient failures."""

    def __init__(self):
        self.consecutive_session_errors = 0
        self.consecutive_transient_errors = 0
        self.last_transient_stage = ''
        self.tripped = False
        self.trip_reason = ''

    def record_session_failure(self):
        """Record a logged-out / navigation-shell failure."""
        self.consecutive_session_errors += 1
        self.consecutive_transient_errors = 0
        self.last_transient_stage = ''
        if self.consecutive_session_errors >= SESSION_ERROR_LIMIT:
            self.tripped = True
            self.trip_reason = (
                f'Session failed {self.consecutive_session_errors} times in a row'
            )

    def record_session_recovery(self):
        """Reset session counter after successful re-login."""
        self.consecutive_session_errors = 0

    def record_transient_failure(self, stage=''):
        """Record a retryable row/step failure."""
        stage = (stage or '').strip()
        if stage and stage == self.last_transient_stage:
            self.consecutive_transient_errors += 1
        else:
            self.consecutive_transient_errors = 1
            self.last_transient_stage = stage
        if self.consecutive_transient_errors >= TRANSIENT_ERROR_LIMIT:
            self.tripped = True
            self.trip_reason = (
                f'Transient failures on "{self.last_transient_stage}" '
                f'({self.consecutive_transient_errors} in a row)'
            )

    def record_row_success(self):
        """Reset transient counter after a successfully handled row."""
        self.consecutive_transient_errors = 0
        self.last_transient_stage = ''


def classify_row_failure(last_error, claim_status=''):
    """Return a coarse failure stage label for the circuit breaker."""
    err = (last_error or '').strip()
    if err:
        return err
    status = str(claim_status or '').strip()
    for marker in TRANSIENT_ERROR_MARKERS:
        if marker in status:
            return marker
    return err or 'Unknown row processing error'


def capture_row_failure_artifact(page, output_folder, row_index, context=None):
    """Save screenshot and JSON context when a row fails."""
    if not output_folder:
        return None
    context = dict(context or {})
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    artifact_dir = os.path.join(
        output_folder, 'artifacts', ts, f'row_{row_index + 1}',
    )
    try:
        os.makedirs(artifact_dir, exist_ok=True)
    except OSError as e:
        log_to_gui(f"  ⚠️ Could not create artifact dir: {e}\n", "error")
        return None

    meta = {
        'row_index': row_index,
        'row_number': row_index + 1,
        'timestamp': ts,
        **context,
    }

    if page is not None:
        try:
            screenshot_path = os.path.join(artifact_dir, 'screenshot.png')
            page.screenshot(path=screenshot_path, full_page=True)
            meta['screenshot'] = screenshot_path
        except Exception as e:
            meta['screenshot_error'] = str(e)
        try:
            meta['url'] = page.url
        except Exception:
            pass

    context_path = os.path.join(artifact_dir, 'context.json')
    try:
        with open(context_path, 'w', encoding='utf-8') as fh:
            json.dump(meta, fh, indent=2, default=str)
    except OSError as e:
        log_to_gui(f"  ⚠️ Could not write artifact context: {e}\n", "error")
        return None

    log_to_gui(f"  📎 Failure artifact saved: {artifact_dir}\n", "info")
    return artifact_dir
