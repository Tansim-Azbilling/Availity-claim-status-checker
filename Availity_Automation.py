"""Availity Automation — entry point for source runs and PyInstaller."""
from availity_app.tk_ui import create_gui

if __name__ == "__main__":
    create_gui().mainloop()
