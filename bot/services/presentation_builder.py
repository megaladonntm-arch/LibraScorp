from __future__ import annotations

import re
import tempfile
from datetime import datetime
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from bot.services.ai_text_presentation_generator import SlideContent, resolve_template_asset


def _safe_filename(source: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", source, flags=re.UNICODE).strip("_")
    return cleaned[:40] or "presentation"


def build_presentation_file(
    topic: str,
    template_type: int,
    slides: list[SlideContent],
) -> Path:
    presentation = Presentation()
    blank_layout = presentation.slide_layouts[6]
    template_asset = resolve_template_asset(template_type)

    for slide_content in slides:
        slide = presentation.slides.add_slide(blank_layout)

        if template_asset:
            slide.shapes.add_picture(
                str(template_asset),
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
        title_paragraph = title_frame.paragraphs[0]
        title_paragraph.text = slide_content.title
        title_paragraph.font.bold = True
        title_paragraph.font.name = "Times New Roman"
        title_paragraph.font.size = Pt(40)
        title_paragraph.font.color.rgb = RGBColor(255, 255, 255)
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

        for index, bullet in enumerate(slide_content.bullets):
            paragraph = body_frame.paragraphs[0] if index == 0 else body_frame.add_paragraph()
            paragraph.text = f"- {bullet}"
            paragraph.level = 0
            paragraph.font.name = "Times New Roman"
            paragraph.font.size = Pt(24)
            paragraph.font.color.rgb = RGBColor(255, 255, 255)
            paragraph.alignment = PP_ALIGN.CENTER

    out_dir = Path(tempfile.mkdtemp(prefix="tg_presentation_"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = out_dir / f"{_safe_filename(topic)}_{stamp}.pptx"
    presentation.save(output_path)
    return output_path
