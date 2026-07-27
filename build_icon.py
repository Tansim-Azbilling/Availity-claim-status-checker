"""Convert azbilling-new-logo.png to a multi-size .ico for PyInstaller."""
import sys
from pathlib import Path

from PIL import Image


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: build_icon.py <input.png> <output.ico>", file=sys.stderr)
        return 1

    png = Path(sys.argv[1])
    ico = Path(sys.argv[2])
    img = Image.open(png)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico, format="ICO", sizes=sizes)
    print(f"Wrote {ico}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
