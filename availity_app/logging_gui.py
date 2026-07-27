"""Thread-safe append to the Tk activity log (batched for responsiveness)."""
import threading

from availity_app import state

_LOG_FLUSH_MS = 100
_LOG_MAX_LINES = 2000

_buffer_lock = threading.Lock()
_buffer = []
_flush_scheduled = False


def _trim_log_widget():
    """Drop oldest lines when the log exceeds the cap."""
    if state.log_text is None:
        return
    line_count = int(state.log_text.index('end-1c').split('.')[0])
    if line_count > _LOG_MAX_LINES:
        excess = line_count - _LOG_MAX_LINES
        state.log_text.delete('1.0', f'{excess + 1}.0')


def _flush_buffer():
    global _flush_scheduled, _buffer
    try:
        with _buffer_lock:
            if not _buffer:
                _flush_scheduled = False
                return
            pending = _buffer
            _buffer = []

        if state.log_text is None:
            with _buffer_lock:
                _flush_scheduled = False
            return

        state.log_text.config(state="normal")
        for message, tag in pending:
            state.log_text.insert("end", message, tag)
        _trim_log_widget()
        state.log_text.see("end")
        state.log_text.config(state="disabled")

        with _buffer_lock:
            if _buffer:
                _flush_scheduled = True
                if state.root is not None:
                    state.root.after(_LOG_FLUSH_MS, _flush_buffer)
            else:
                _flush_scheduled = False
    except Exception:
        raise


def _schedule_deferred_flush():
    if state.root is not None:
        state.root.after(_LOG_FLUSH_MS, _flush_buffer)


def log_to_gui(message, tag="info"):
    global _flush_scheduled
    with _buffer_lock:
        _buffer.append((message, tag))
        if _flush_scheduled:
            return
        _flush_scheduled = True
    if state.root is not None:
        state.root.after(0, _schedule_deferred_flush)
