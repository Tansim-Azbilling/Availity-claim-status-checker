"""Shared process state (GUI refs, Playwright, batch coordination)."""
import threading

is_running = False
worker_busy = False
current_playwright = None
current_browser = None
playwright_thread_id = None
playwright_disconnect_requested = False
playwright_lock = threading.Lock()
managed_edge_process = None
browser_owned_by_app = False

selected_payer_config = None
selected_payer_name = None
current_payer_name = None

resume_event = threading.Event()
resume_decision = "cancel"

current_batch_df = None
current_batch_output_folder = None
save_lock = threading.Lock()
stop_save_requested = False
rows_since_last_save = 0
_large_autofit_notice_logged = False

loaded_df = None
loaded_excel_path = None
excel_row_stats = None

root = None
open_edge_button = None
start_button = None
stop_button = None
log_text = None
collection_file_var = None
output_folder_var = None
batch_size_var = None
payer_var = None
total_rows_var = None
recheck_rows_var = None
new_rows_var = None
progress_frame = None
progress_bar = None
progress_percent_var = None
progress_status_var = None
