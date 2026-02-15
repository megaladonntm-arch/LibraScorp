from __future__ import annotations

import asyncio
import re
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from bot.services.ai_text_presentation_generator import SlideContent, resolve_template_asset


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

        title_box = slide.shapes.add_textbox(
            left=Inches(0.8),
            top=Inches(0.8),
            width=presentation.slide_width - Inches(1.6),
            height=Inches(1.3),
        )
        title_frame = title_box.text_frame
        title_frame.clear()
        title_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        title_frame.word_wrap = True
        title_paragraph = title_frame.paragraphs[0]
        title_paragraph.text = slide_content.title
        title_paragraph.font.bold = True
        title_paragraph.font.name = font_name
        title_paragraph.font.size = Pt(40)
        title_paragraph.font.color.rgb = color
        title_paragraph.alignment = PP_ALIGN.CENTER

        body_box = slide.shapes.add_textbox(
            left=Inches(1.0),
            top=Inches(2.3),
            width=presentation.slide_width - Inches(2.0),
            height=presentation.slide_height - Inches(3.0),
        )
        body_frame = body_box.text_frame
        body_frame.clear()
        body_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        body_frame.word_wrap = True

        for bullet_index, bullet in enumerate(slide_content.bullets):
            paragraph = body_frame.paragraphs[0] if bullet_index == 0 else body_frame.add_paragraph()
            paragraph.text = bullet
            paragraph.level = 0
            paragraph.font.name = font_name
            paragraph.font.size = Pt(24)
            paragraph.font.color.rgb = color
            paragraph.alignment = PP_ALIGN.CENTER

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
