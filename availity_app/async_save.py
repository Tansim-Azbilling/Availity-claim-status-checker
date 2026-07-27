"""Background Excel save queue — keeps the automation worker off disk I/O."""
import threading
import time

from availity_app import state
from availity_app.logging_gui import log_to_gui
from availity_app.ui_control import set_save_progress_status

_worker_thread = None
_worker_lock = threading.Lock()
_slot_lock = threading.Lock()
_slot_condition = threading.Condition(_slot_lock)
_queued_item = None
_worker_processing = False
_shutdown = False


def _worker_loop():
    global _queued_item, _worker_processing, _shutdown
    while True:
        with _slot_condition:
            while _queued_item is None and not _shutdown:
                _slot_condition.wait()
            if _shutdown and _queued_item is None:
                return
            item = _queued_item
            _queued_item = None

        _worker_processing = True
        try:
            df, output_folder, finalize = item
            from availity_app.automation import _write_results_file

            _write_results_file(df, output_folder, finalize=finalize)
        except Exception as e:
            log_to_gui(f"  ❌ Async save error: {e}\n", "error")
        finally:
            _worker_processing = False
            with _slot_condition:
                _slot_condition.notify_all()


def start_save_worker():
    """Start the background save thread if not already running."""
    global _worker_thread, _shutdown
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _shutdown = False
        _worker_thread = threading.Thread(
            target=_worker_loop, name='availity-async-save', daemon=True,
        )
        _worker_thread.start()


def stop_save_worker(*, wait=True, timeout=120.0):
    """Stop the worker and optionally wait for queued saves to finish."""
    global _worker_thread, _shutdown
    if wait:
        flush_async_saves(timeout=timeout)
    with _worker_lock:
        with _slot_condition:
            _shutdown = True
            _slot_condition.notify_all()
        if _worker_thread is not None and _worker_thread.is_alive():
            if wait:
                _worker_thread.join(timeout=timeout)
        _worker_thread = None
        _shutdown = False


def _save_pending():
    """Return True when a save is queued or in progress."""
    with _slot_condition:
        return _queued_item is not None or _worker_processing


def flush_async_saves(timeout=120.0):
    """Block until all queued saves complete, or until timeout."""
    if _worker_thread is None or not _worker_thread.is_alive():
        return
    if not _save_pending():
        return
    set_save_progress_status("Waiting for save to finish…")
    deadline = time.monotonic() + timeout
    with _slot_condition:
        while _queued_item is not None or _worker_processing:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                log_to_gui(
                    "  ⚠️ Save queue did not finish in time — continuing.\n",
                    "error",
                )
                return
            _slot_condition.wait(timeout=min(remaining, 0.25))


def enqueue_save(df, output_folder, *, finalize=False):
    """Queue a dataframe snapshot for background writing (coalesced to latest)."""
    global _queued_item
    start_save_worker()
    with _slot_condition:
        new_item = (df.copy(), output_folder, finalize)
        if _queued_item is None:
            _queued_item = new_item
        elif finalize:
            _queued_item = new_item
        elif not _queued_item[2]:
            _queued_item = new_item
        _slot_condition.notify()


def save_sync_or_async(df, output_folder, *, finalize=False, force_async=True):
    """Write immediately (finalize/stop) or enqueue for background (progress)."""
    if finalize or not force_async or state.stop_save_requested:
        from availity_app.automation import _write_results_file

        flush_async_saves(timeout=120.0)
        return _write_results_file(df, output_folder, finalize=finalize)
    enqueue_save(df, output_folder, finalize=False)
    return None
