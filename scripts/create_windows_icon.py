"""Create the ICO used by the Windows executable and installer."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "lume-256.png"
target = ROOT / "lume.ico"

with Image.open(source) as image:
    image.convert("RGBA").save(target, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])

print(target)
