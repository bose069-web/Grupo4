"""Generate the five local test images required by the Day 6 challenge."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "test_images"
FONT = ImageFont.load_default()


def save(name: str, background: str, lines: list[str], shapes: list[tuple[int, int, int, int, str]]) -> None:
    image = Image.new("RGB", (1000, 650), background)
    draw = ImageDraw.Draw(image)
    for x1, y1, x2, y2, color in shapes:
        draw.rectangle((x1, y1, x2, y2), fill=color)
    y = 80
    for line in lines:
        draw.text((70, y), line, fill="black", font=FONT)
        y += 35
    image.save(OUT / name)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    save("01_invoice.png", "white", ["INVOICE 1042", "Client: Nova Labs", "Total: $249.00", "Due: 2026-09-30"], [(55, 40, 945, 580, "white"), (55, 40, 945, 90, "#dbeafe"), (55, 255, 945, 260, "#64748b")])
    save("02_urban.png", "#b8d8ef", [""], [(0, 430, 1000, 650, "#475569"), (80, 170, 280, 430, "#334155"), (330, 110, 550, 430, "#64748b"), (620, 200, 900, 430, "#1e293b"), (480, 300, 520, 430, "#facc15")])
    save("03_product.png", "#f1f5f9", ["ORBIT MUG"], [(350, 180, 650, 500, "#0f766e"), (630, 270, 760, 390, "#0f766e"), (250, 500, 750, 530, "#94a3b8")])
    save("04_receipt.png", "#fff7ed", ["SAMPLE RECEIPT", "Coffee       $4.50", "Tax          $0.45", "TOTAL        $4.95"], [(280, 45, 720, 590, "white")])
    save("05_workspace.png", "#e2e8f0", [""], [(100, 460, 900, 540, "#92400e"), (170, 190, 450, 460, "#f8fafc"), (610, 120, 760, 460, "#1e293b"), (690, 170, 730, 260, "#facc15"), (500, 390, 590, 460, "#334155")])


if __name__ == "__main__":
    main()
