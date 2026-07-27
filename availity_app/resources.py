"""Bundled assets (PyInstaller vs source directory)."""
import os
import sys

import tkinter as tk

def _resource_path(filename):
    """Resolve a bundled-resource path that works in both .py and PyInstaller .exe modes.

    PyInstaller unpacks data files into ``sys._MEIPASS`` at runtime; running
    directly from source we fall back to the script's directory.
    """
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)


def _load_brand_logo(path, target_height=56):
    """Load and resize the brand logo for the header.

    Pillow is preferred for high-quality resampling. When Pillow is not
    available we fall back to tk.PhotoImage and integer ``subsample`` —
    PNG support is built into Tk 8.6+. Returns None (and logs nothing)
    if the file is missing so the GUI still renders without the logo.
    """
    if not os.path.exists(path):
        return None

    try:
        from PIL import Image, ImageTk  # type: ignore
        img = Image.open(path)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        scale = target_height / float(img.height)
        new_size = (max(1, int(img.width * scale)), target_height)
        img = img.resize(new_size, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        pass

    try:
        photo = tk.PhotoImage(file=path)
        if photo.height() > target_height:
            factor = max(1, photo.height() // target_height)
            photo = photo.subsample(factor, factor)
        return photo
    except Exception:
        return None
