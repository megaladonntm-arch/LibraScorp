from __future__ import annotations

import asyncio
import re
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageStat
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Pt

from bot.services.ai_text_presentation_generator import (
    SlideContent,
    resolve_pdf_template_asset,
    resolve_template_asset,
)

try:
    import fitz  # type: ignore
except Exception:  # pragma: no cover
    fitz = None

TITLE_ZONE = (0.08, 0.08, 0.84, 0.16)
BODY_ZONE = (0.10, 0.26, 0.80, 0.58)
TITLE_ZONE_CANDIDATES = (
    (0.07, 0.06, 0.86, 0.18),
    (0.08, 0.08, 0.84, 0.16),
    (0.10, 0.09, 0.80, 0.16),
    (0.12, 0.10, 0.76, 0.16),
    (0.10, 0.14, 0.80, 0.16),
)
BODY_ZONE_CANDIDATES = (
    (0.08, 0.24, 0.84, 0.60),
    (0.10, 0.26, 0.80, 0.58),
    (0.10, 0.30, 0.80, 0.54),
    (0.12, 0.28, 0.76, 0.56),
    (0.12, 0.34, 0.76, 0.50),
    (0.08, 0.32, 0.84, 0.52),
)

# 13 visual variants; if slides >13, style repeats by modulo.
THEMES = [
    ("#F5F7FF", "#2F4B7C", "#6EA8FE", "#FFFFFF"),
    ("#FFF6EA", "#8C4A1A", "#F4A261", "#FFFFFF"),
    ("#EEF9F1", "#1B6B4A", "#7BCFA3", "#FFFFFF"),
    ("#FFF0F4", "#8E204B", "#E87EA1", "#FFFFFF"),
    ("#F2F3F7", "#30343F", "#8D99AE", "#FFFFFF"),
    ("#F9F4FF", "#4C2A85", "#A98ED6", "#FFFFFF"),
    ("#ECFBFF", "#0F5B6E", "#5EC9E2", "#FFFFFF"),
    ("#FFF8E7", "#7B5A12", "#DDBB5A", "#FFFFFF"),
    ("#F1FFF8", "#215E46", "#6ED7A7", "#FFFFFF"),
    ("#FFF1EC", "#7A2E1C", "#E78A70", "#FFFFFF"),
    ("#F0F5FF", "#1E3A8A", "#7FA8FF", "#FFFFFF"),
    ("#F7FFF3", "#355E1D", "#9FCF5B", "#FFFFFF"),
    ("#FFF2FA", "#6C1D45", "#D77AB3", "#FFFFFF"),
]

PDF_RENDER_SCALE = 1.8


def _safe_filename(source: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", source, flags=re.UNICODE).strip("_")
    return cleaned[:40] or "presentation"


def _parse_hex_color(color_hex: str) -> RGBColor:
    value = color_hex.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError("Некорректный цвет")
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _rgb_from_hex(color_hex: str) -> RGBColor:
    value = color_hex.lstrip("#")
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _estimate_body_font_size(slide: SlideContent) -> int:
    max_len = max((len(item) for item in slide.bullets), default=0)
    total_len = sum(len(item) for item in slide.bullets)
    bullet_count = len(slide.bullets)
    if bullet_count >= 4 or max_len > 170 or total_len > 420:
        return 16
    if bullet_count >= 3 or max_len > 130 or total_len > 320:
        return 18
    return 20


def _estimate_title_font_size(title: str) -> int:
    length = len(title.strip())
    if length > 90:
        return 24
    if length > 70:
        return 26
    if length > 50:
        return 28
    return 32


def _fit_inside(width: int, height: int, max_width: int, max_height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0 or max_width <= 0 or max_height <= 0:
        return max(1, max_width), max(1, max_height)
    ratio = min(max_width / float(width), max_height / float(height))
    return max(1, int(width * ratio)), max(1, int(height * ratio))


def _adjust_zones_for_user_image(
    body_zone: tuple[float, float, float, float],
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    left, top, width, height = body_zone
    if width >= 0.56:
        image_width = min(0.30, max(0.20, width * 0.34))
        gutter = 0.02
        text_width = max(0.24, width - image_width - gutter)
        image_left = left + text_width + gutter
        return (left, top, text_width, height), (image_left, top, image_width, height)

    text_height = max(0.24, height * 0.62)
    image_top = top + text_height + 0.02
    image_height = max(0.16, height - text_height - 0.02)
    image_left = left + (width * 0.05)
    image_width = width * 0.90
    return (left, top, width, text_height), (image_left, image_top, image_width, image_height)


def _add_user_image(
    slide,
    image_path: Path,
    image_zone: tuple[float, float, float, float],
    slide_width: int,
    slide_height: int,
) -> None:
    if not image_path.exists():
        return
    zone_left, zone_top, zone_width, zone_height = _ratio_to_emu(image_zone, slide_width, slide_height)
    if zone_width <= 0 or zone_height <= 0:
        return
    try:
        with Image.open(image_path) as img:
            image_width, image_height = img.size
    except Exception:
        return

    fit_width, fit_height = _fit_inside(image_width, image_height, zone_width, zone_height)
    left = zone_left + max(0, (zone_width - fit_width) // 2)
    top = zone_top + max(0, (zone_height - fit_height) // 2)
    slide.shapes.add_picture(
        str(image_path),
        left=left,
        top=top,
        width=fit_width,
        height=fit_height,
    )


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


def _hex_to_rgb(color_hex: str) -> tuple[int, int, int]:
    value = color_hex.strip().lstrip("#")
    if len(value) != 6:
        return 0, 0, 0
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _contrast_ratio(text_rgb: tuple[int, int, int], bg_luma: float) -> float:
    text_luma = (0.2126 * text_rgb[0] + 0.7152 * text_rgb[1] + 0.0722 * text_rgb[2]) / 255.0
    bg_norm = bg_luma / 255.0
    lighter = max(text_luma, bg_norm) + 0.05
    darker = min(text_luma, bg_norm) + 0.05
    return lighter / darker


def _score_candidate(image: Image.Image, box: tuple[float, float, float, float], text_rgb: tuple[int, int, int]) -> float:
    width, height = image.size
    left = int(width * box[0])
    top = int(height * box[1])
    right = int(width * (box[0] + box[2]))
    bottom = int(height * (box[1] + box[3]))

    if right <= left or bottom <= top:
        return float("-inf")

    cropped = image.crop((left, top, right, bottom)).convert("L")
    stat = ImageStat.Stat(cropped)
    mean = stat.mean[0] if stat.mean else 128.0
    stddev = stat.stddev[0] if stat.stddev else 0.0
    contrast = _contrast_ratio(text_rgb, mean)

    # Prefer areas with strong text contrast and lower visual noise.
    return (contrast * 120.0) + (255.0 - stddev) + (box[2] * box[3] * 25.0)


def _detect_text_zones_from_background(
    image_path: Path,
    text_color_hex: str,
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    try:
        with Image.open(image_path) as image:
            rgb = _hex_to_rgb(text_color_hex)
            best_title = max(TITLE_ZONE_CANDIDATES, key=lambda candidate: _score_candidate(image, candidate, rgb))
            body_candidates = [candidate for candidate in BODY_ZONE_CANDIDATES if candidate[1] >= best_title[1] + best_title[3] - 0.01]
            if not body_candidates:
                body_candidates = list(BODY_ZONE_CANDIDATES)
            best_body = max(body_candidates, key=lambda candidate: _score_candidate(image, candidate, rgb))
            return best_title, best_body
    except Exception:
        return TITLE_ZONE, BODY_ZONE


def _theme_for_index(index: int) -> tuple[RGBColor, RGBColor, RGBColor, RGBColor]:
    bg_hex, header_hex, accent_hex, card_hex = THEMES[index % len(THEMES)]
    return (
        _rgb_from_hex(bg_hex),
        _rgb_from_hex(header_hex),
        _rgb_from_hex(accent_hex),
        _rgb_from_hex(card_hex),
    )


def _add_background(slide, slide_width: int, slide_height: int, index: int) -> tuple[RGBColor, RGBColor]:
    bg_color, header_color, accent_color, card_color = _theme_for_index(index)

    background = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        left=0,
        top=0,
        width=slide_width,
        height=slide_height,
    )
    background.fill.solid()
    background.fill.fore_color.rgb = bg_color
    background.line.fill.background()

    top_bar = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        left=0,
        top=0,
        width=slide_width,
        height=int(slide_height * 0.10),
    )
    top_bar.fill.solid()
    top_bar.fill.fore_color.rgb = header_color
    top_bar.line.fill.background()

    decorative_circle = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.OVAL,
        left=int(slide_width * 0.78),
        top=int(slide_height * 0.72),
        width=int(slide_width * 0.26),
        height=int(slide_width * 0.26),
    )
    decorative_circle.fill.solid()
    decorative_circle.fill.fore_color.rgb = accent_color
    decorative_circle.fill.transparency = 0.60
    decorative_circle.line.fill.background()

    content_card = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
        left=int(slide_width * 0.06),
        top=int(slide_height * 0.18),
        width=int(slide_width * 0.88),
        height=int(slide_height * 0.72),
    )
    content_card.fill.solid()
    content_card.fill.fore_color.rgb = card_color
    content_card.line.fill.solid()
    content_card.line.fill.fore_color.rgb = accent_color
    content_card.line.width = Pt(1.6)

    return header_color, accent_color


def _render_pdf_pages_to_png(pdf_path: Path) -> list[Path]:
    if fitz is None:
        raise RuntimeError("Для PDF-шаблона нужен пакет PyMuPDF (pip install pymupdf).")

    output: list[Path] = []
    document = fitz.open(str(pdf_path))
    matrix = fitz.Matrix(PDF_RENDER_SCALE, PDF_RENDER_SCALE)
    try:
        # For ready-made PDF templates, skip the first page/background consistently.
        start_page = 1 if document.page_count > 1 else 0
        for page_index in range(start_page, document.page_count):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = Path(tempfile.mkstemp(prefix="pdf_template_", suffix=".png")[1])
            pixmap.save(str(image_path))
            output.append(image_path)
    finally:
        document.close()
    return output


def _build_presentation_sync(
    topic: str,
    template_types: list[int],
    slides: list[SlideContent],
    font_name: str,
    font_color: str,
    creator_names: str | None = None,
    creator_title: str = "Presentation creators",
    user_image_paths: list[str] | None = None,
) -> Path:
    presentation = Presentation()
    blank_layout = presentation.slide_layouts[6]
    color = _parse_hex_color(font_color)
    temp_images: list[Path] = []
    pdf_pages_cache: dict[str, list[Path]] = {}
    zones_cache: dict[str, tuple[tuple[float, float, float, float], tuple[float, float, float, float]]] = {}
    prepared_user_images: list[Path] = []
    for image_path in user_image_paths or []:
        candidate = Path(image_path)
        if candidate.exists():
            prepared_user_images.append(candidate)

    for index, slide_content in enumerate(slides):
        template_type = template_types[index] if index < len(template_types) else (template_types[0] if template_types else 1)
        slide = presentation.slides.add_slide(blank_layout)

        pdf_template_path = resolve_pdf_template_asset(template_type)
        static_image_asset = resolve_template_asset(template_type)

        if pdf_template_path is not None:
            cache_key = str(pdf_template_path.resolve())
            pdf_pages = pdf_pages_cache.get(cache_key)
            if pdf_pages is None:
                pdf_pages = _render_pdf_pages_to_png(pdf_template_path)
                pdf_pages_cache[cache_key] = pdf_pages
                temp_images.extend(pdf_pages)
            if not pdf_pages:
                raise RuntimeError(f"PDF шаблон пустой: {pdf_template_path}")
            bg_image = pdf_pages[index % len(pdf_pages)]
            slide.shapes.add_picture(
                str(bg_image),
                left=0,
                top=0,
                width=presentation.slide_width,
                height=presentation.slide_height,
            )
            zone_key = str(bg_image.resolve())
        elif static_image_asset is not None:
            slide.shapes.add_picture(
                str(static_image_asset),
                left=0,
                top=0,
                width=presentation.slide_width,
                height=presentation.slide_height,
            )
            zone_key = str(static_image_asset.resolve())
        else:
            _add_background(slide, presentation.slide_width, presentation.slide_height, index)
            zone_key = ""

        if zone_key:
            zones = zones_cache.get(zone_key)
            if zones is None:
                background_path = Path(zone_key)
                zones = _detect_text_zones_from_background(background_path, font_color)
                zones_cache[zone_key] = zones
            title_zone, body_zone = zones
        else:
            title_zone, body_zone = TITLE_ZONE, BODY_ZONE

        user_image_path = prepared_user_images[index] if index < len(prepared_user_images) else None
        image_zone: tuple[float, float, float, float] | None = None
        body_zone_for_text = body_zone
        if user_image_path is not None:
            body_zone_for_text, image_zone = _adjust_zones_for_user_image(body_zone)

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
        title_paragraph.font.size = Pt(_estimate_title_font_size(slide_content.title))
        title_paragraph.font.color.rgb = color
        title_paragraph.alignment = PP_ALIGN.CENTER
        title_paragraph.space_after = Pt(2)

        body_left, body_top, body_width, body_height = _ratio_to_emu(
            body_zone_for_text,
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
        body_frame.vertical_anchor = MSO_ANCHOR.TOP
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
            paragraph.space_after = Pt(5)

        if user_image_path is not None and image_zone is not None:
            _add_user_image(
                slide=slide,
                image_path=user_image_path,
                image_zone=image_zone,
                slide_width=presentation.slide_width,
                slide_height=presentation.slide_height,
            )

    if creator_names:
        creator_index = len(slides)
        final_slide = presentation.slides.add_slide(blank_layout)
        _add_background(
            final_slide,
            presentation.slide_width,
            presentation.slide_height,
            creator_index,
        )

        title_box = final_slide.shapes.add_textbox(
            left=int(presentation.slide_width * 0.10),
            top=int(presentation.slide_height * 0.30),
            width=int(presentation.slide_width * 0.80),
            height=int(presentation.slide_height * 0.16),
        )
        title_frame = title_box.text_frame
        title_frame.clear()
        title_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        title_frame.word_wrap = True
        title_paragraph = title_frame.paragraphs[0]
        title_paragraph.text = creator_title
        title_paragraph.font.bold = True
        title_paragraph.font.name = font_name
        title_paragraph.font.size = Pt(34)
        title_paragraph.font.color.rgb = color
        title_paragraph.alignment = PP_ALIGN.CENTER

        names_box = final_slide.shapes.add_textbox(
            left=int(presentation.slide_width * 0.10),
            top=int(presentation.slide_height * 0.48),
            width=int(presentation.slide_width * 0.80),
            height=int(presentation.slide_height * 0.28),
        )
        names_frame = names_box.text_frame
        names_frame.clear()
        names_frame.vertical_anchor = MSO_ANCHOR.TOP
        names_frame.word_wrap = True
        for idx, raw_name in enumerate([x.strip() for x in creator_names.split(",") if x.strip()][:20]):
            paragraph = names_frame.paragraphs[0] if idx == 0 else names_frame.add_paragraph()
            paragraph.text = raw_name
            paragraph.level = 0
            paragraph.font.name = font_name
            paragraph.font.size = Pt(26)
            paragraph.font.color.rgb = color
            paragraph.alignment = PP_ALIGN.CENTER

    out_dir = Path(tempfile.mkdtemp(prefix="tg_presentation_"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = out_dir / f"{_safe_filename(topic)}_{stamp}.pptx"
    presentation.save(output_path)
    for temp_image in temp_images:
        try:
            temp_image.unlink(missing_ok=True)
        except Exception:
            pass
    return output_path


async def build_presentation_file(
    topic: str,
    template_types: list[int],
    slides: list[SlideContent],
    font_name: str,
    font_color: str,
    creator_names: str | None = None,
    creator_title: str = "Presentation creators",
    user_image_paths: list[str] | None = None,
) -> Path:
    return await asyncio.to_thread(
        _build_presentation_sync,
        topic,
        template_types,
        slides,
        font_name,
        font_color,
        creator_names,
        creator_title,
        user_image_paths,
    )

