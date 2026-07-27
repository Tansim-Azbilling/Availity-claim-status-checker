"""Tkinter layout and application callbacks."""
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from availity_app import state
from availity_app.automation import open_edge_and_connect, run_batch, save_results
from availity_app.constants import get_gui_payer_names
from availity_app.driver import close_managed_edge_if_owned
from availity_app.logging_gui import log_to_gui
from availity_app.resources import _load_brand_logo, _resource_path
from availity_app.ui_control import (
    UI_STATE_OPENING,
    UI_STATE_RUNNING,
    _apply_button_style,
    _set_ui_state,
    reset_automation_progress,
    reset_ui_state,
    set_save_progress_indeterminate,
    set_save_progress_status,
)


def _run_open_browser_in_background(payer, excel_path):
    """Spawn the Open Edge & Login worker thread."""
    thread = threading.Thread(
        target=open_edge_and_connect,
        args=(payer, excel_path),
        daemon=True,
    )
    thread.start()


def _run_batch_in_background(batch_size, excel_path, output_folder):
    """Spawn the Excel automation worker thread (Phase 2)."""
    thread = threading.Thread(
        target=run_batch,
        args=(batch_size, excel_path, output_folder),
        daemon=True,
    )
    thread.start()


def browse_excel():
    """Open a file picker restricted to Excel workbooks."""
    filename = filedialog.askopenfilename(
        title="Select Collection File",
        filetypes=[
            ("Excel files", "*.xlsx *.xls"),
            ("All files", "*.*"),
        ],
    )
    if filename:
        state.collection_file_var.set(filename)


def browse_folder():
    """Open a folder picker for the output directory."""
    folder = filedialog.askdirectory(title="Select Output Folder")
    if folder:
        state.output_folder_var.set(folder)


def _validate_all_inputs():
    """Return validated (batch, excel, output_dir, payer) or None.

    Pops a messagebox and returns None if anything is missing/invalid.
    """
    excel_file = state.collection_file_var.get()
    output_dir = state.output_folder_var.get()
    payer = state.payer_var.get()

    try:
        batch = int(state.batch_size_var.get())
        if batch <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("Error", "Batch size must be a positive integer")
        return None

    if not excel_file:
        messagebox.showerror("Error", "Please select a collection file")
        return None
    if not output_dir:
        messagebox.showerror("Error", "Please select an output folder")
        return None
    if not payer or payer not in get_gui_payer_names():
        messagebox.showerror("Error", "Please select a valid payer")
        return None

    return batch, excel_file, output_dir, payer


def validate_and_open_browser():
    """Phase 1 callback: validate inputs, load Excel, then launch Edge."""

    validated = _validate_all_inputs()
    if validated is None:
        return
    _, excel_file, _, payer = validated

    state.is_running = True
    state.log_text.config(state="normal")
    state.log_text.delete(1.0, tk.END)
    state.log_text.config(state="disabled")

    _set_ui_state(UI_STATE_OPENING)
    _run_open_browser_in_background(payer, excel_file)


def validate_and_start_automation():
    """Phase 2 callback: validate inputs (again) and run the Excel automation."""

    if state.selected_payer_config is None:
        messagebox.showerror(
            "Not ready",
            "Click 'Open Edge' and sign in to Availity first.",
        )
        return

    validated = _validate_all_inputs()
    if validated is None:
        return
    batch, excel_file, output_dir, _ = validated

    if state.loaded_df is None:
        messagebox.showerror(
            "Not ready",
            "Excel data is not loaded. Click 'Open Edge' again to reload the file.",
        )
        return

    state.is_running = True
    reset_automation_progress("Starting automation…", 0)
    _set_ui_state(UI_STATE_RUNNING)
    _run_batch_in_background(batch, excel_file, output_dir)


def _run_stop_save_in_background(batch_df, batch_folder):
    """Save progress on a worker thread so the Tk main loop stays responsive."""
    def _worker():
        saved_path = None
        error = None
        try:
            set_save_progress_indeterminate(True)
            set_save_progress_status("Saving progress…")
            saved_path = save_results(batch_df, batch_folder, finalize=True)
        except Exception as e:
            error = e
            log_to_gui(f"  ⚠️ Save on stop failed: {e}\n", "error")
        finally:
            set_save_progress_indeterminate(False)

        def _on_done():
            if error is not None:
                messagebox.showerror("Save failed", f"Could not save progress:\n{error}")
            elif saved_path is None:
                messagebox.showwarning(
                    "Save failed",
                    "Could not save a styled Automated.xlsx.\n\n"
                    "Close the file if it is open in Excel, then try again.",
                )
            if not state.worker_busy:
                close_managed_edge_if_owned()
                reset_ui_state(clear_all=False)

        if state.root is not None:
            state.root.after(0, _on_done)

    threading.Thread(target=_worker, daemon=True).start()


def request_stop():
    """Signal worker threads to stop, flush progress to Excel, and reset the GUI."""
    state.is_running = False
    state.resume_decision = "cancel"
    state.resume_event.set()

    batch_df = state.current_batch_df
    batch_folder = state.current_batch_output_folder
    if batch_df is not None and batch_folder:
        state.stop_save_requested = True
        log_to_gui("💾 Saving progress before stop...\n", "info")
        set_save_progress_status("Saving progress…")
        _apply_button_style(state.stop_button, "stop", False)
        _run_stop_save_in_background(batch_df, batch_folder)
        return

    if not state.worker_busy:
        close_managed_edge_if_owned()
        reset_ui_state(clear_all=False)


def create_gui():
    """Build and return the main application window."""

    COLOR_BG = "#FAFAFA"
    COLOR_SURFACE = "#FFFFFF"
    COLOR_BORDER = "#E5E7EB"
    COLOR_BORDER_HOVER = "#D1D5DB"
    COLOR_TEXT = "#111827"
    COLOR_TEXT_BODY = "#374151"
    COLOR_TEXT_MUTED = "#6B7280"
    COLOR_PRIMARY = "#4F46E5"
    COLOR_LOG_BG = "#F9FAFB"
    COLOR_LOG_INFO = "#2563EB"
    COLOR_LOG_OK = "#16A34A"
    COLOR_LOG_ERR = "#DC2626"
    COLOR_STAT_BG = "#F3F4F6"
    COLOR_PROGRESS_TRACK = "#E5E7EB"
    COLOR_PROGRESS_FILL = "#4F46E5"

    FONT_TITLE = ("Segoe UI", 16, "bold")
    FONT_SUBTITLE = ("Segoe UI", 9)
    FONT_LABEL = ("Segoe UI", 10)
    FONT_BUTTON = ("Segoe UI", 10, "bold")
    FONT_INPUT = ("Segoe UI", 10)
    FONT_LOG = ("Consolas", 9)
    FONT_STAT = ("Segoe UI", 10, "bold")

    state.root = tk.Tk()
    state.root.title("Availity Automation")
    state.root.geometry("880x820")
    state.root.configure(bg=COLOR_BG)

    icon_image = _load_brand_logo(_resource_path("azbilling-new-logo.png"), target_height=64)
    if icon_image is not None:
        try:
            state.root.iconphoto(True, icon_image)
            state.root._brand_icon_ref = icon_image
        except tk.TclError:
            pass

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        "Modern.TCombobox",
        fieldbackground=COLOR_SURFACE,
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT,
        bordercolor=COLOR_BORDER,
        lightcolor=COLOR_BORDER,
        darkcolor=COLOR_BORDER,
        arrowcolor=COLOR_TEXT_BODY,
        padding=6,
        relief="flat",
    )
    style.map(
        "Modern.TCombobox",
        bordercolor=[("focus", COLOR_PRIMARY)],
        lightcolor=[("focus", COLOR_PRIMARY)],
        darkcolor=[("focus", COLOR_PRIMARY)],
    )
    style.configure(
        "Automation.Horizontal.TProgressbar",
        troughcolor=COLOR_PROGRESS_TRACK,
        background=COLOR_PROGRESS_FILL,
        bordercolor=COLOR_BORDER,
        lightcolor=COLOR_PROGRESS_FILL,
        darkcolor=COLOR_PROGRESS_FILL,
        thickness=14,
    )

    state.collection_file_var = tk.StringVar()
    state.output_folder_var = tk.StringVar()
    state.batch_size_var = tk.StringVar(value="10")
    state.payer_var = tk.StringVar(value="Healthfirst")
    state.total_rows_var = tk.StringVar(value="—")
    state.recheck_rows_var = tk.StringVar(value="—")
    state.new_rows_var = tk.StringVar(value="—")
    state.progress_percent_var = tk.StringVar(value="0%")
    state.progress_status_var = tk.StringVar(value="Waiting to start…")

    main_frame = tk.Frame(state.root, padx=28, pady=24, bg=COLOR_BG)
    main_frame.pack(fill=tk.BOTH, expand=True)

    def _label(parent, text, font=FONT_LABEL, fg=COLOR_TEXT_BODY):
        return tk.Label(parent, text=text, font=font, bg=COLOR_BG, fg=fg, anchor="w")

    def _entry(parent, var, width=46):
        return tk.Entry(
            parent, textvariable=var, width=width,
            font=FONT_INPUT, bg=COLOR_SURFACE, fg=COLOR_TEXT,
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
            highlightcolor=COLOR_PRIMARY,
            insertbackground=COLOR_PRIMARY,
        )

    def _browse(parent, command):
        return tk.Button(
            parent, text="Browse", command=command,
            font=("Segoe UI", 9), bg=COLOR_SURFACE, fg=COLOR_TEXT_BODY,
            activebackground=COLOR_LOG_BG, activeforeground=COLOR_TEXT,
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
            highlightcolor=COLOR_BORDER_HOVER,
            padx=16, pady=5, cursor="hand2",
        )

    def _stat_value(parent, var):
        return tk.Label(
            parent, textvariable=var, font=FONT_STAT,
            bg=COLOR_STAT_BG, fg=COLOR_TEXT, anchor="center",
            padx=12, pady=6,
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
        )

    _label(main_frame, "Availity Automation", font=FONT_TITLE, fg=COLOR_TEXT).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 2),
    )

    _label(
        main_frame, "Automate claim status lookups across payers",
        font=FONT_SUBTITLE, fg=COLOR_TEXT_MUTED,
    ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 16))

    tk.Frame(main_frame, height=1, bg=COLOR_BORDER).grid(
        row=2, column=0, columnspan=3, sticky="ew", pady=(0, 20),
    )

    _label(main_frame, "Collection File").grid(row=3, column=0, sticky="w", pady=8, padx=(0, 16))
    _entry(main_frame, state.collection_file_var).grid(row=3, column=1, sticky="ew", pady=8, padx=(0, 10), ipady=6)
    _browse(main_frame, browse_excel).grid(row=3, column=2, sticky="w", pady=8)

    _label(main_frame, "Output Folder").grid(row=4, column=0, sticky="w", pady=8, padx=(0, 16))
    _entry(main_frame, state.output_folder_var).grid(row=4, column=1, sticky="ew", pady=8, padx=(0, 10), ipady=6)
    _browse(main_frame, browse_folder).grid(row=4, column=2, sticky="w", pady=8)

    stats_frame = tk.Frame(main_frame, bg=COLOR_BG)
    stats_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(4, 12))
    for col, (title, var) in enumerate([
        ("Total Rows Read", state.total_rows_var),
        ("Rows with Recheck", state.recheck_rows_var),
        ("New Rows (Recheck empty)", state.new_rows_var),
    ]):
        cell = tk.Frame(stats_frame, bg=COLOR_BG)
        cell.grid(row=0, column=col, sticky="ew", padx=(0, 12 if col < 2 else 0))
        _label(cell, title, fg=COLOR_TEXT_MUTED).pack(anchor="w")
        _stat_value(cell, var).pack(fill=tk.X, pady=(4, 0))
        stats_frame.grid_columnconfigure(col, weight=1)

    _label(main_frame, "Claim Search Limit").grid(row=6, column=0, sticky="w", pady=8, padx=(0, 16))
    _entry(main_frame, state.batch_size_var, width=18).grid(row=6, column=1, sticky="w", pady=8, padx=(0, 10), ipady=6)

    _label(main_frame, "Select Payer").grid(row=7, column=0, sticky="w", pady=8, padx=(0, 16))
    ttk.Combobox(
        main_frame, textvariable=state.payer_var,
        values=get_gui_payer_names(),
        state="readonly", width=43,
        font=FONT_INPUT, style="Modern.TCombobox",
    ).grid(row=7, column=1, sticky="w", pady=8, padx=(0, 10), ipady=2)

    btn_frame = tk.Frame(main_frame, bg=COLOR_BG)
    btn_frame.grid(row=8, column=0, columnspan=3, pady=22)

    button_kwargs = dict(
        font=FONT_BUTTON, relief="flat", bd=0,
        padx=22, pady=9, cursor="hand2",
        highlightthickness=2,
    )

    state.open_edge_button = tk.Button(
        btn_frame, text="Open Edge",
        command=validate_and_open_browser, **button_kwargs,
    )
    state.open_edge_button.pack(side=tk.LEFT, padx=8)

    state.start_button = tk.Button(
        btn_frame, text="Start Automation",
        command=validate_and_start_automation, **button_kwargs,
    )
    state.start_button.pack(side=tk.LEFT, padx=8)

    state.stop_button = tk.Button(
        btn_frame, text="Stop",
        command=request_stop, **button_kwargs,
    )
    state.stop_button.pack(side=tk.LEFT, padx=8)

    _apply_button_style(state.open_edge_button, "open_edge", True)
    _apply_button_style(state.start_button, "start", False)
    _apply_button_style(state.stop_button, "stop", False)

    state.progress_frame = tk.Frame(main_frame, bg=COLOR_SURFACE, highlightthickness=1,
                                    highlightbackground=COLOR_BORDER)
    state.progress_frame.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(0, 16))

    progress_inner = tk.Frame(state.progress_frame, bg=COLOR_SURFACE, padx=16, pady=14)
    progress_inner.pack(fill=tk.X, expand=True)

    progress_header = tk.Frame(progress_inner, bg=COLOR_SURFACE)
    progress_header.pack(fill=tk.X)

    tk.Label(
        progress_header, text="Automation Progress",
        font=("Segoe UI", 10, "bold"), bg=COLOR_SURFACE, fg=COLOR_TEXT,
    ).pack(side=tk.LEFT)

    tk.Label(
        progress_header, textvariable=state.progress_percent_var,
        font=("Segoe UI", 11, "bold"), bg=COLOR_SURFACE, fg=COLOR_PRIMARY,
    ).pack(side=tk.RIGHT)

    state.progress_bar = ttk.Progressbar(
        progress_inner,
        style="Automation.Horizontal.TProgressbar",
        orient="horizontal",
        mode="determinate",
        maximum=100,
        value=0,
    )
    state.progress_bar.pack(fill=tk.X, pady=(10, 8))

    tk.Label(
        progress_inner, textvariable=state.progress_status_var,
        font=("Segoe UI", 9), bg=COLOR_SURFACE, fg=COLOR_TEXT_MUTED, anchor="w",
    ).pack(fill=tk.X)

    reset_automation_progress()

    _label(main_frame, "Activity Log", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT).grid(
        row=10, column=0, sticky="w", pady=(6, 8),
    )

    log_wrap = tk.Frame(main_frame, bg=COLOR_BORDER)
    log_wrap.grid(row=11, column=0, columnspan=3, sticky="nsew")

    log_inner = tk.Frame(log_wrap, bg=COLOR_LOG_BG)
    log_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

    scrollbar = tk.Scrollbar(log_inner, bd=0, highlightthickness=0)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    state.log_text = tk.Text(
        log_inner, height=14, width=95,
        yscrollcommand=scrollbar.set, state="disabled", wrap=tk.WORD,
        bg=COLOR_LOG_BG, fg=COLOR_TEXT_BODY,
        font=FONT_LOG, relief="flat", bd=0,
        padx=14, pady=12,
        insertbackground=COLOR_PRIMARY,
        selectbackground="#DBEAFE", selectforeground=COLOR_TEXT,
    )
    state.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=state.log_text.yview)

    state.log_text.tag_config("info", foreground=COLOR_LOG_INFO)
    state.log_text.tag_config("success", foreground=COLOR_LOG_OK)
    state.log_text.tag_config("error", foreground=COLOR_LOG_ERR)

    main_frame.grid_rowconfigure(11, weight=1)
    main_frame.grid_columnconfigure(1, weight=1)

    return state.root
