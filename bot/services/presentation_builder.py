from __future__ import annotations

import asyncio
import re
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Pt

from bot.services.ai_text_presentation_generator import SlideContent, resolve_template_asset

DEFAULT_TITLE_ZONE = (0.10, 0.08, 0.80, 0.16)
DEFAULT_BODY_ZONE = (0.12, 0.28, 0.76, 0.58)
_ZONE_CACHE: dict[str, tuple[tuple[float, float, float, float], tuple[float, float, float, float]]] = {}


def _optimize_image_quality(image_path: Path) -> Path:
    try:
        img = Image.open(image_path)
        temp_image = Path(tempfile.mktemp(suffix=".png"))
        if img.mode in ("RGBA", "LA", "P"):
            if img.mode == "P":
                img = img.convert("RGBA")
            elif img.mode == "LA":
                img = img.convert("RGBA")
            img.save(temp_image, "PNG", compress_level=9, optimize=True)
        else:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(temp_image, "PNG", compress_level=9, optimize=True)
        return temp_image
    except Exception:
        return image_path


async def _optimize_image_quality_async(image_path: Path) -> Path:
    return await asyncio.to_thread(_optimize_image_quality, image_path)


def _safe_filename(source: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", source, flags=re.UNICODE).strip("_")
    return cleaned[:40] or "presentation"


def _parse_hex_color(color_hex: str) -> RGBColor:
    value = color_hex.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError("Некорректный цвет")
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _estimate_body_font_size(slide: SlideContent) -> int:
    max_len = max((len(item) for item in slide.bullets), default=0)
    bullet_count = len(slide.bullets)
    if bullet_count >= 5 or max_len > 150:
        return 18
    if bullet_count >= 4 or max_len > 110:
        return 20
    return 22


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _ratio_box_to_pixels(
    box: tuple[float, float, float, float],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    left = int(_clamp(box[0], 0.0, 1.0) * width)
    top = int(_clamp(box[1], 0.0, 1.0) * height)
    right = int(_clamp(box[0] + box[2], 0.0, 1.0) * width)
    bottom = int(_clamp(box[1] + box[3], 0.0, 1.0) * height)
    if right <= left:
        right = min(width, left + 1)
    if bottom <= top:
        bottom = min(height, top + 1)
    return left, top, right, bottom


def _zone_score(
    edge_img: Image.Image,
    gray_img: Image.Image,
    box: tuple[float, float, float, float],
    target_top: float,
    target_center_x: float,
) -> float:
    px_box = _ratio_box_to_pixels(box, edge_img.width, edge_img.height)
    edge_crop = edge_img.crop(px_box)
    gray_crop = gray_img.crop(px_box)
    edge_mean = (ImageStat.Stat(edge_crop).mean or [255.0])[0] / 255.0
    gray_std = (ImageStat.Stat(gray_crop).stddev or [127.0])[0] / 127.0
    center_x = box[0] + box[2] / 2.0
    top = box[1]
    anchor_penalty = abs(center_x - target_center_x) * 0.35 + abs(top - target_top) * 0.45
    return edge_mean * 0.65 + gray_std * 0.25 + anchor_penalty * 0.10


def _overlap_ratio(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    area = max(aw * ah, 1e-6)
    return inter / area


def _generate_title_candidates() -> list[tuple[float, float, float, float]]:
    candidates: list[tuple[float, float, float, float]] = []
    widths = [0.60, 0.68, 0.76, 0.84]
    heights = [0.12, 0.14, 0.16, 0.18]
    tops = [0.06, 0.09, 0.12, 0.15, 0.18]
    offsets = [-0.10, -0.05, 0.0, 0.05, 0.10]
    for width in widths:
        for height in heights:
            for top in tops:
                for offset in offsets:
                    left = _clamp((0.5 - width / 2.0) + offset, 0.04, 0.96 - width)
                    candidates.append((left, top, width, height))
    return candidates


def _generate_body_candidates() -> list[tuple[float, float, float, float]]:
    candidates: list[tuple[float, float, float, float]] = []
    widths = [0.56, 0.64, 0.72, 0.80, 0.86]
    heights = [0.40, 0.46, 0.52, 0.58]
    tops = [0.22, 0.27, 0.32, 0.37]
    offsets = [-0.12, -0.06, 0.0, 0.06, 0.12]
    for width in widths:
        for height in heights:
            for top in tops:
                for offset in offsets:
                    left = _clamp((0.5 - width / 2.0) + offset, 0.04, 0.96 - width)
                    if top + height > 0.96:
                        continue
                    candidates.append((left, top, width, height))
    return candidates


def _detect_text_zones(template_asset: Path | None) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    if template_asset is None:
        return DEFAULT_TITLE_ZONE, DEFAULT_BODY_ZONE

    cache_key = str(template_asset.resolve())
    cached = _ZONE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        image = Image.open(template_asset).convert("RGB")
        gray = image.convert("L").filter(ImageFilter.GaussianBlur(radius=1.2))
        edge = gray.filter(ImageFilter.FIND_EDGES)

        title_candidates = _generate_title_candidates()
        body_candidates = _generate_body_candidates()

        best_title = DEFAULT_TITLE_ZONE
        best_body = DEFAULT_BODY_ZONE
        best_score = float("inf")

        for title_box in title_candidates:
            title_score = _zone_score(edge, gray, title_box, target_top=0.10, target_center_x=0.50)
            for body_box in body_candidates:
                gap = body_box[1] - (title_box[1] + title_box[3])
                if gap < 0.02:
                    continue
                overlap = _overlap_ratio(title_box, body_box)
                if overlap > 0.01:
                    continue
                body_score = _zone_score(edge, gray, body_box, target_top=0.30, target_center_x=0.50)
                width_penalty = max(0.0, 0.70 - body_box[2]) * 0.35
                height_penalty = max(0.0, 0.46 - body_box[3]) * 0.35
                score = title_score + body_score + width_penalty + height_penalty
                if score < best_score:
                    best_score = score
                    best_title = title_box
                    best_body = body_box

        _ZONE_CACHE[cache_key] = (best_title, best_body)
        return best_title, best_body
    except Exception:
        return DEFAULT_TITLE_ZONE, DEFAULT_BODY_ZONE


def _ratio_to_emu(
    box: tuple[float, float, float, float],
    slide_width: int,
    slide_height: int,
) -> tuple[int, int, int, int]:
    left = int(slide_width * box[0])
    top = int(slide_height * box[1])
    width = int(slide_width * box[2])
    height = int(slide_height * box[3])
    return left, top, width, height


def _build_presentation_sync(
    topic: str,
    template_types: list[int],
    slides: list[SlideContent],
    font_name: str,
    font_color: str,
) -> Path:
    presentation = Presentation()
    blank_layout = presentation.slide_layouts[6]
    temp_images: list[Path] = []
    color = _parse_hex_color(font_color)

    for index, slide_content in enumerate(slides):
        slide = presentation.slides.add_slide(blank_layout)
        template_type = template_types[index] if index < len(template_types) else template_types[0]
        template_asset = resolve_template_asset(template_type)
        title_zone, body_zone = _detect_text_zones(template_asset)

        if template_asset:
            optimized_image = _optimize_image_quality(template_asset)
            if optimized_image != template_asset:
                temp_images.append(optimized_image)
            slide.shapes.add_picture(
                str(optimized_image),
                left=0,
                top=0,
                width=presentation.slide_width,
                height=presentation.slide_height,
            )

        title_left, title_top, title_width, title_height = _ratio_to_emu(
            title_zone,
            presentation.slide_width,
            presentation.slide_height,
        )
        title_box = slide.shapes.add_textbox(
            left=title_left,
            top=title_top,
            width=title_width,
            height=title_height,
        )
        title_frame = title_box.text_frame
        title_frame.clear()
        title_frame.margin_left = 0
        title_frame.margin_right = 0
        title_frame.margin_top = 0
        title_frame.margin_bottom = 0
        title_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        title_frame.word_wrap = True
        title_paragraph = title_frame.paragraphs[0]
        title_paragraph.text = slide_content.title
        title_paragraph.font.bold = True
        title_paragraph.font.name = font_name
        title_paragraph.font.size = Pt(36)
        title_paragraph.font.color.rgb = color
        title_paragraph.alignment = PP_ALIGN.CENTER

        body_left, body_top, body_width, body_height = _ratio_to_emu(
            body_zone,
            presentation.slide_width,
            presentation.slide_height,
        )
        body_box = slide.shapes.add_textbox(
            left=body_left,
            top=body_top,
            width=body_width,
            height=body_height,
        )
        body_frame = body_box.text_frame
        body_frame.clear()
        body_frame.margin_left = 0
        body_frame.margin_right = 0
        body_frame.margin_top = 0
        body_frame.margin_bottom = 0
        body_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        body_frame.word_wrap = True
        body_font_size = _estimate_body_font_size(slide_content)

        for bullet_index, bullet in enumerate(slide_content.bullets):
            paragraph = body_frame.paragraphs[0] if bullet_index == 0 else body_frame.add_paragraph()
            paragraph.text = f"• {bullet}"
            paragraph.level = 0
            paragraph.font.name = font_name
            paragraph.font.size = Pt(body_font_size)
            paragraph.font.color.rgb = color
            paragraph.alignment = PP_ALIGN.LEFT

    out_dir = Path(tempfile.mkdtemp(prefix="tg_presentation_"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = out_dir / f"{_safe_filename(topic)}_{stamp}.pptx"
    presentation.save(output_path)

    for temp_image in temp_images:
        try:
            temp_image.unlink()
        except Exception:
            pass

    return output_path


async def build_presentation_file(
    topic: str,
    template_types: list[int],
    slides: list[SlideContent],
    font_name: str,
    font_color: str,
) -> Path:
    return await asyncio.to_thread(
        _build_presentation_sync,
        topic,
        template_types,
        slides,
        font_name,
        font_color,
    )
