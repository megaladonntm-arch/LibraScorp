#!/usr/bin/env python3
"""Create beautiful presentation templates with color variations"""

from PIL import Image, ImageDraw
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets_pdf"
ASSETS_DIR.mkdir(exist_ok=True)

# Color schemes: blue, purple, red, orange, green
COLOR_SCHEMES = {
    "blue": {"color1": "#1a237e", "color2": "#3f51b5", "color3": "#e3f2fd"},
    "purple": {"color1": "#6a1b9a", "color2": "#9c27b0", "color3": "#f3e5f5"},
    "red": {"color1": "#c62828", "color2": "#f44336", "color3": "#ffebee"},
    "orange": {"color1": "#f57f17", "color2": "#ff9800", "color3": "#fff3e0"},
    "green": {"color1": "#2e7d32", "color2": "#4caf50", "color3": "#e8f5e9"},
}


def create_template(num: int, color1: str, color2: str, color3: str) -> Image.Image:
    """Create different beautiful templates with edge designs - CENTER CLEAR"""
    width, height = 800, 600
    img = Image.new('RGB', (width, height), color=color3)
    draw = ImageDraw.Draw(img)
    
    if num == 1:
        draw.polygon([(0, 0), (150, 0), (0, 150)], fill=color1)
        draw.polygon([(width, height), (width - 150, height), (width, height - 150)], fill=color2)
    
    elif num == 2:
        stripe_w = 80
        draw.rectangle([(0, 0), (stripe_w, height)], fill=color1)
        draw.rectangle([(width - stripe_w, 0), (width, height)], fill=color2)
    
    elif num == 3:
        stripe_h = 100
        draw.rectangle([(0, 0), (width, stripe_h)], fill=color1)
        draw.rectangle([(0, height - stripe_h), (width, height)], fill=color2)
    
    elif num == 4:
        corner_size = 200
        draw.polygon([(0, 0), (corner_size, 0), (0, corner_size)], fill=color1)
        draw.polygon([(width, height), (width - corner_size, height), (width, height - corner_size)], fill=color2)
        draw.polygon([(width, 0), (width - 100, 0), (width, 100)], fill=color2)
        draw.polygon([(0, height), (100, height), (0, height - 100)], fill=color1)
    
    elif num == 5:
        zag_size = 30
        for i in range(0, width, zag_size * 2):
            draw.rectangle([(i, 0), (i + zag_size, zag_size)], fill=color1)
            draw.rectangle([(i, height - zag_size), (i + zag_size, height)], fill=color2)
    
    elif num == 6:
        radius = 120
        draw.ellipse([(0 - radius//2, height//2 - radius), (radius, height//2 + radius)], fill=color1)
        draw.ellipse([(width - radius, height//2 - radius), (width + radius//2, height//2 + radius)], fill=color2)
    
    elif num == 7:
        corner_w, corner_h = 120, 100
        draw.rectangle([(0, 0), (corner_w, corner_h)], fill=color1)
        draw.rectangle([(width - corner_w, 0), (width, corner_h)], fill=color2)
        draw.rectangle([(0, height - corner_h), (corner_w, height)], fill=color2)
        draw.rectangle([(width - corner_w, height - corner_h), (width, height)], fill=color1)
    
    elif num == 8:
        wave_w = 60
        for y in range(0, height, 40):
            draw.rectangle([(0, y), (wave_w, y + 20)], fill=color1)
            draw.rectangle([(width - wave_w, y), (width, y + 20)], fill=color2)
    
    elif num == 9:
        block_count = 6
        block_h = height // block_count
        block_w = 70
        for i in range(block_count):
            color = color1 if i % 2 == 0 else color2
            draw.rectangle([(0, i * block_h), (block_w, (i + 1) * block_h)], fill=color)
            draw.rectangle([(width - block_w, i * block_h), (width, (i + 1) * block_h)], fill=color)
    
    elif num == 10:
        diamond_size = 80
        cx, cy = diamond_size, diamond_size
        draw.polygon([(cx, cy - diamond_size), (cx + diamond_size, cy), (cx, cy + diamond_size), (cx - diamond_size, cy)], fill=color1)
        
        cx, cy = width - diamond_size, height - diamond_size
        draw.polygon([(cx, cy - diamond_size), (cx + diamond_size, cy), (cx, cy + diamond_size), (cx - diamond_size, cy)], fill=color2)
    
    return img


def main():
    print("Creating presentation templates with color variations...")
    
    # Create templates 1-10 with 5 color variations each
    for template_num in range(1, 11):
        print(f"\n📐 Template {template_num}:")
        for color_name, colors in COLOR_SCHEMES.items():
            img = create_template(
                template_num,
                colors["color1"],
                colors["color2"],
                colors["color3"]
            )
            # Save with color suffix: 1_blue.png, 1_purple.png, etc.
            # Also save default (without suffix) as first color (blue)
            filename = f"{template_num}_{color_name}.png" if color_name != "blue" else f"{template_num}.png"
            filepath = ASSETS_DIR / filename
            img.save(filepath, "PNG")
            print(f"  ✓ {color_name}: {filename}")
    
    print(f"\n✅ All templates created in {ASSETS_DIR}")
    print("Templates: 1-10 (with _blue, _purple, _red, _orange, _green variations)")
    print("Templates 11+ remain unchanged")


if __name__ == "__main__":
    main()
