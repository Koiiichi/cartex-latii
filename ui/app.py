import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr
import pandas as pd
import traceback
import json
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io
import pymupdf

from main import extractor, enricher
from src.models import TableRole, UserTableSchema, FieldSource
from src.templates import TEMPLATES, TemplateType, FIELD_LIBRARY
from src.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Bbox overlay colours (RGBA)
_COLOUR_MAIN    = (30,  120, 255, 200)
_COLOUR_AUX     = (40,  200, 100, 200)
_COLOUR_CONTEXT = (255, 160,  30, 180)

_LABEL_BG_MAIN    = (30,  120, 255, 220)
_LABEL_BG_AUX     = (40,  200, 100, 220)
_LABEL_BG_CONTEXT = (255, 160,  30, 220)

_TEMPLATE_DISPLAY_NAMES = {
    "standard_takeoff": "Standard Takeoff",
    "standard_takeoff_tdl": "Standard Takeoff + TDL/SDL",
    "glass_schedule": "Glass Schedule",
    "shop_details": "Shop Details",
}


def _render_page_pil(file_path: str, page_idx: int) -> Image.Image:
    """Render a PDF page to a PIL Image."""
    doc = pymupdf.open(file_path)
    page = doc.load_page(page_idx)
    pix = page.get_pixmap(dpi=config.dpi)
    return Image.open(io.BytesIO(pix.tobytes()))


def _draw_bboxes(img: Image.Image, tables, contexts) -> Image.Image:
    """Draw coloured bbox rectangles + role labels onto a copy of img.

    Gemini returns coordinates in a normalised 0–1000 space regardless of the
    prompt asking for pixels, so we scale to the actual image dimensions here.
    """
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    img_w, img_h = img.size

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=22)
    except Exception:
        font = ImageFont.load_default()

    def draw_box(bbox, colour, label_bg, label):
        if bbox is None:
            return
        # Scale from Gemini's 0-1000 normalised space to image pixels
        x = int(bbox.x * img_w / 1000)
        y = int(bbox.y * img_h / 1000)
        w = int(bbox.width  * img_w / 1000)
        h = int(bbox.height * img_h / 1000)
        # Semi-transparent fill
        draw.rectangle([x, y, x + w, y + h], fill=(*colour[:3], 40), outline=colour, width=3)
        # Label background + text
        label_w = len(label) * 13 + 8
        label_h = 28
        draw.rectangle([x, y - label_h, x + label_w, y], fill=label_bg)
        draw.text((x + 4, y - label_h + 4), label, fill=(255, 255, 255, 255), font=font)

    for table in tables:
        if table.role == TableRole.MAIN:
            draw_box(table.bbox, _COLOUR_MAIN, _LABEL_BG_MAIN,
                     f"MAIN  ({len(table.rows)} rows)")
        elif table.role == TableRole.AUXILIARY:
            draw_box(table.bbox, _COLOUR_AUX, _LABEL_BG_AUX,
                     f"AUX  ({len(table.rows)} rows)")

    for ctx in contexts:
        draw_box(ctx.bbox, _COLOUR_CONTEXT, _LABEL_BG_CONTEXT,
                 f"CTX  {getattr(ctx, 'category', '') or 'context'}")

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def preview_page(pdf_file, page_number):
    """Render plain page preview whenever file or page number changes."""
    if pdf_file is None:
        return None
    try:
        img = _render_page_pil(pdf_file.name, int(page_number) - 1)
        return img
    except Exception:
        return None


def process_document(pdf_file, page_number, template_value, extra_columns):
    if pdf_file is None:
        yield None, None, "", gr.update(visible=False)
        return

    lines: list[str] = []

    def log(msg: str):
        lines.append(msg)
        logger.info(msg)
        return "\n".join(lines)

    page_idx = int(page_number) - 1
    plain_img = _render_page_pil(pdf_file.name, page_idx)

    # Build schema from UI selections
    template = TemplateType(template_value)
    base_columns = TEMPLATES[template].copy()
    all_columns = base_columns + [c for c in extra_columns if c not in base_columns]
    schema = UserTableSchema(template=template, columns=all_columns)

    try:
        # --- Stage 1: Extraction ---
        yield None, plain_img, log(f"[1/2] Extracting tables and context from page {int(page_number)}..."), gr.update(visible=False)
        result = extractor.extract(pdf_file.name, page_idx)

        main_tables = [t for t in result.tables if t.role == TableRole.MAIN]
        aux_tables  = [t for t in result.tables if t.role == TableRole.AUXILIARY]
        status = log(
            f"      Done — {len(result.tables)} table(s) found "
            f"({len(main_tables)} main, {len(aux_tables)} auxiliary), "
            f"{len(result.context)} context item(s)"
        )

        # Overlay bboxes as soon as extraction is done
        annotated_img = _draw_bboxes(plain_img, result.tables, result.context)
        yield None, annotated_img, status, gr.update(visible=False)

        # --- Stage 2: Enrichment ---
        yield None, annotated_img, log("[2/2] Enriching rows..."), gr.update(visible=False)
        enriched_rows = enricher.enrich(result, schema)
        yield None, annotated_img, log(f"      Done — {len(enriched_rows)} enriched row(s)"), gr.update(visible=False)

        # --- Build dataframe ---
        rows_data = []
        for row in enriched_rows:
            row_dict = {}
            for col in schema.columns:
                row_dict[col] = row.data.get(col, "")
            row_dict["_confidence"] = str(row.confidence)
            row_dict["_reasoning"] = row.reasoning or ""
            row_dict["_field_sources"] = json.dumps(
                {k: v.value for k, v in row.field_sources.items()},
                default=str,
            )
            rows_data.append(row_dict)
        df = pd.DataFrame(rows_data)

        # --- Write debug log ---
        debug_log = {
            "timestamp": datetime.now().isoformat(),
            "file": pdf_file.name,
            "page": int(page_number),
            "template": template.value,
            "columns": schema.columns,
            "total_rows": len(enriched_rows),
            "context": [c.model_dump(mode='json') for c in result.context],
            "rows": [row.model_dump(mode='json') for row in enriched_rows],
        }
        debug_filename = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(config.debug_dir / debug_filename, "w") as f:
            json.dump(debug_log, f, indent=2, default=str)

        summary = (
            f"Rows: {len(enriched_rows)}  |  "
            f"Template: {_TEMPLATE_DISPLAY_NAMES.get(template.value, template.value)}\n"
            f"Debug log → {debug_filename}"
        )
        yield df, annotated_img, log(f"\nComplete — {len(enriched_rows)} rows\n{summary}"), gr.update(visible=False)

    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Pipeline failed:\n%s", tb)
        yield None, plain_img, log(f"\nPipeline failed: {type(e).__name__}: {e}"), gr.update(value=tb, visible=True)


# ── UI ─────────────────────────────────────────────────────────────────────────

with gr.Blocks(title="Cartex") as app:
    gr.Markdown("# Cartex")
    gr.Markdown("### Sub-Item / Sub-Table Contextualization")

    with gr.Row():
        # Controls
        with gr.Column(scale=1, min_width=220):
            pdf_input   = gr.File(label="Upload PDF", file_types=[".pdf"])
            page_number = gr.Number(label="Page Number", value=1, minimum=1, precision=0)
            template_dropdown = gr.Dropdown(
                label="Template",
                choices=[(display, value) for value, display in _TEMPLATE_DISPLAY_NAMES.items()],
                value="standard_takeoff",
            )
            extra_columns = gr.CheckboxGroup(
                label="Additional Columns",
                choices=FIELD_LIBRARY,
            )
            run_button  = gr.Button("Run Pipeline", variant="primary")

        # Page viewer
        with gr.Column(scale=3):
            page_image = gr.Image(
                label="Page Preview  ·  Blue = main table  ·  Green = auxiliary  ·  Orange = context",
                type="pil",
                interactive=False,
            )

    # Live preview triggers
    pdf_input.change(fn=preview_page,   inputs=[pdf_input, page_number], outputs=[page_image])
    page_number.change(fn=preview_page, inputs=[pdf_input, page_number], outputs=[page_image])

    with gr.Row():
        status_output = gr.Textbox(
            label="Pipeline Log",
            lines=10,
            max_lines=20,
            interactive=False,
            autoscroll=True,
        )

    with gr.Row():
        results_table = gr.Dataframe(
            label="Enriched Table",
            interactive=False,
            wrap=True,
        )

    with gr.Row():
        error_output = gr.Textbox(
            label="Error Traceback",
            lines=15,
            interactive=False,
            visible=False,
        )

    run_button.click(
        fn=process_document,
        inputs=[pdf_input, page_number, template_dropdown, extra_columns],
        outputs=[results_table, page_image, status_output, error_output],
    )

if __name__ == "__main__":
    app.launch()
