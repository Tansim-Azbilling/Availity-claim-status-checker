"""Tk button states and mid-batch re-login dialog (main thread)."""
import tkinter as tk
from tkinter import messagebox

from availity_app import state as app_state
from availity_app.constants import (
    UI_STATE_IDLE,
    UI_STATE_OPENING,
    UI_STATE_READY,
    UI_STATE_RUNNING,
)

# Per-button color tokens for active / disabled states.
# Centralized so _apply_button_style() is the single source of truth for
# button appearance across UI state transitions (idle → opening → ready → running).
# Disabled states keep each button's hue (indigo/green/red) but use a soft
# tinted background + lighter border + readable mid-tone text. The colored
# fill keeps each button identifiable at a glance while signaling "inactive."
BUTTON_STYLES = {
    "open_edge": {
        "active":   {"bg": "#4F46E5", "fg": "white",   "border": "#4F46E5"},
        "disabled": {"bg": "#E0E7FF", "fg": "#818CF8", "border": "#E0E7FF"},
    },
    "start": {
        "active":   {"bg": "#16A34A", "fg": "white",   "border": "#16A34A"},
        "disabled": {"bg": "#DCFCE7", "fg": "#16A34A", "border": "#86EFAC"},
    },
    "stop": {
        "active":   {"bg": "#DC2626", "fg": "white",   "border": "#DC2626"},
        "disabled": {"bg": "#FEE2E2", "fg": "#DC2626", "border": "#FCA5A5"},
    },
}


def _apply_button_style(btn, variant, enabled):
    """Apply a variant's active or disabled color set to a Tk button.

    Tk's default disabled rendering ignores ``bg``/``fg`` overrides and
    produces low-contrast OS gray. We instead set both ``fg`` and
    ``disabledforeground`` to the slate text color so the disabled state
    stays readable and consistent across Windows themes.
    """
    if btn is None:
        return
    palette = BUTTON_STYLES[variant]["active" if enabled else "disabled"]
    btn.config(
        state="normal" if enabled else "disabled",
        bg=palette["bg"],
        activebackground=palette["bg"],
        fg=palette["fg"],
        activeforeground=palette["fg"],
        disabledforeground=palette["fg"],
        highlightbackground=palette["border"],
        highlightcolor=palette["border"],
    )


def _set_ui_state(ui_state):
    """Flip the button enables on the Tk main thread.

    All button enable/disable logic lives here so the rest of the code never
    fiddles with Tk widgets from worker threads. Always schedules the actual
    config call via ``app_state.root.after(0, ...)``.
    """
    def _apply():
        if ui_state == UI_STATE_IDLE:
            _apply_button_style(app_state.open_edge_button, "open_edge", True)
            _apply_button_style(app_state.start_button,     "start",     False)
            _apply_button_style(app_state.stop_button,      "stop",      False)
        elif ui_state == UI_STATE_OPENING:
            _apply_button_style(app_state.open_edge_button, "open_edge", False)
            _apply_button_style(app_state.start_button,     "start",     False)
            _apply_button_style(app_state.stop_button,      "stop",      True)
        elif ui_state == UI_STATE_READY:
            _apply_button_style(app_state.open_edge_button, "open_edge", False)
            _apply_button_style(app_state.start_button,     "start",     True)
            _apply_button_style(app_state.stop_button,      "stop",      True)
        elif ui_state == UI_STATE_RUNNING:
            _apply_button_style(app_state.open_edge_button, "open_edge", False)
            _apply_button_style(app_state.start_button,     "start",     False)
            _apply_button_style(app_state.stop_button,      "stop",      True)

    if app_state.root is not None:
        app_state.root.after(0, _apply)


def reset_automation_progress(status="Waiting to start…", percent=0):
    """Reset the automation progress bar to an idle/neutral state."""
    def _apply():
        if app_state.progress_bar is None:
            return
        try:
            app_state.progress_bar.stop()
        except tk.TclError:
            pass
        app_state.progress_bar.configure(mode='determinate', maximum=100, value=percent)
        if app_state.progress_percent_var is not None:
            app_state.progress_percent_var.set(f"{percent}%")
        if app_state.progress_status_var is not None:
            app_state.progress_status_var.set(status)

    if app_state.root is not None:
        app_state.root.after(0, _apply)


def update_automation_progress(current, total, detail=""):
    """Update progress during a batch (call from worker threads).

    Args:
        current: Number of rows completed so far.
        total: Total rows in this batch.
        detail: Optional status line (e.g. current invoice).
    """
    def _apply():
        if app_state.progress_bar is None:
            return
        total_safe = max(int(total), 1)
        current_safe = max(0, min(int(current), total_safe))
        pct = int(round(100 * current_safe / total_safe))
        app_state.progress_bar.configure(maximum=total_safe, value=current_safe)
        if app_state.progress_percent_var is not None:
            app_state.progress_percent_var.set(f"{pct}%")
        if app_state.progress_status_var is not None:
            if detail:
                app_state.progress_status_var.set(detail)
            else:
                app_state.progress_status_var.set(
                    f"{current_safe} of {total_safe} claims processed"
                )

    if app_state.root is not None:
        app_state.root.after(0, _apply)


def finish_automation_progress(current, total, *, stopped=False, complete=False):
    """Set final progress state after batch ends or is stopped."""
    def _apply():
        if app_state.progress_bar is None:
            return
        total_safe = max(int(total), 1)
        current_safe = max(0, min(int(current), total_safe))
        app_state.progress_bar.configure(maximum=total_safe, value=current_safe)
        pct = int(round(100 * current_safe / total_safe)) if total_safe else 0
        if app_state.progress_percent_var is not None:
            app_state.progress_percent_var.set(f"{pct}%")
        if app_state.progress_status_var is not None:
            if complete and current_safe >= total_safe:
                app_state.progress_status_var.set(
                    f"Complete — {current_safe} of {total_safe} claims processed"
                )
            elif stopped:
                app_state.progress_status_var.set(
                    f"Stopped — {current_safe} of {total_safe} claims saved"
                )
            else:
                app_state.progress_status_var.set(
                    f"Finished — {current_safe} of {total_safe} claims processed"
                )

    if app_state.root is not None:
        app_state.root.after(0, _apply)


def set_save_progress_status(status):
    """Update the progress status line during save lock waits (worker or Stop thread)."""
    def _apply():
        if app_state.progress_status_var is not None:
            app_state.progress_status_var.set(status)

    if app_state.root is not None:
        app_state.root.after(0, _apply)


def set_save_progress_indeterminate(active):
    """Switch the progress bar to indeterminate mode during long saves."""
    def _apply():
        if app_state.progress_bar is None:
            return
        if active:
            app_state.progress_bar.configure(mode='indeterminate')
            app_state.progress_bar.start(12)
            if app_state.progress_percent_var is not None:
                app_state.progress_percent_var.set("…")
        else:
            app_state.progress_bar.stop()
            app_state.progress_bar.configure(mode='determinate')

    if app_state.root is not None:
        app_state.root.after(0, _apply)


def update_excel_row_stats(stats):
    """Update the read-only row summary labels on the Tk main thread."""
    if stats is None:
        return

    def _apply():
        if app_state.total_rows_var is not None:
            app_state.total_rows_var.set(str(stats.get('total', 0)))
        if app_state.recheck_rows_var is not None:
            app_state.recheck_rows_var.set(str(stats.get('recheck_yes', 0)))
        if app_state.new_rows_var is not None:
            app_state.new_rows_var.set(str(stats.get('recheck_empty', 0)))

    if app_state.root is not None:
        app_state.root.after(0, _apply)


def reset_ui_state(clear_all=False):
    """Return the UI to idle state.

    Args:
        clear_all: If True (Stop button), clears input fields, row stats, and the log.
                   If False (batch finished naturally), only resets buttons.
    """
    app_state.is_running = False
    app_state.selected_payer_config = None
    app_state.loaded_df = None
    app_state.loaded_excel_path = None
    app_state.excel_row_stats = None
    app_state.current_batch_df = None
    app_state.current_batch_output_folder = None
    app_state.stop_save_requested = False
    app_state.rows_since_last_save = 0
    app_state.resume_event.set()  # release any worker still blocked on the mid-batch dialog

    def _reset():
        _apply_button_style(app_state.open_edge_button, "open_edge", True)
        _apply_button_style(app_state.start_button,     "start",     False)
        _apply_button_style(app_state.stop_button,      "stop",      False)
        if clear_all:
            app_state.collection_file_var.set("")
            app_state.output_folder_var.set("")
            app_state.batch_size_var.set("10")
            app_state.payer_var.set("Healthfirst")
            if app_state.total_rows_var is not None:
                app_state.total_rows_var.set("—")
            if app_state.recheck_rows_var is not None:
                app_state.recheck_rows_var.set("—")
            if app_state.new_rows_var is not None:
                app_state.new_rows_var.set("—")
            app_state.log_text.config(state="normal")
            app_state.log_text.delete(1.0, tk.END)
            app_state.log_text.config(state="disabled")
        reset_automation_progress()

    if app_state.root is not None:
        app_state.root.after(0, _reset)


def _prompt_user_relogin(reason):
    """Show a modal asking the user to re-login, then unblock the worker.

    Always invoked on the Tk main thread via ``app_state.root.after(0, ...)``.
    """
    try:
        proceed = messagebox.askokcancel(
            "Availity session expired",
            (
                "Your Availity session is no longer usable.\n\n"
                f"Reason: {reason}\n\n"
                "Sign in to Availity in Edge, then click OK to resume "
                "the batch. Click Cancel to stop."
            ),
        )
        app_state.resume_decision = "resume" if proceed else "cancel"
    except Exception:
        app_state.resume_decision = "cancel"
    finally:
        app_state.resume_event.set()
