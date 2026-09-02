"""Generate the Windows application icon from simple original artwork."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "resources"
OUTPUT.mkdir(parents=True, exist_ok=True)

size = 512
image = Image.new("RGBA", (size, size), "#101417")
draw = ImageDraw.Draw(image)
gold = "#d5ad48"
draw.rounded_rectangle((18, 18, size - 18, size - 18), radius=86, outline="#293136", width=10)
draw.polygon([(256, 72), (440, 256), (256, 440), (72, 256)], outline=gold, width=14)

font_path = Path("C:/Windows/Fonts/georgiab.ttf")
font = ImageFont.truetype(str(font_path), 132) if font_path.exists() else ImageFont.load_default()
text = "CA"
box = draw.textbbox((0, 0), text, font=font)
draw.text(((size - (box[2] - box[0])) / 2, (size - (box[3] - box[1])) / 2 - box[1]), text, fill="#f2e7c7", font=font)

image.save(OUTPUT / "icon.png")
image.save(OUTPUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(f"Generated {OUTPUT / 'icon.ico'}")
