import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr
import pandas as pd
import traceback
import json
import logging
from datetime import datetime

from main import extractor, matcher, resolver, merger
from src.models import MatchType, TableRole
from src.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def process_document(pdf_file, page_number):
    if pdf_file is None:
        yield None, "No file uploaded.", gr.update(visible=False)
        return

    lines: list[str] = []

    def log(msg: str):
        lines.append(msg)
        logger.info(msg)
        return "\n".join(lines)

    try:
        page_idx = int(page_number) - 1

        # --- Stage 1: Extraction ---
        yield None, log(f"[1/4] Extracting tables and context from page {int(page_number)}..."), gr.update(visible=False)
        result = extractor.extract(pdf_file.name, page_idx)

        main_tables = [t for t in result.tables if t.role == TableRole.MAIN]
        aux_tables  = [t for t in result.tables if t.role == TableRole.AUXILIARY]
        yield None, log(
            f"      Done — {len(result.tables)} table(s) found "
            f"({len(main_tables)} main, {len(aux_tables)} auxiliary), "
            f"{len(result.context)} context item(s)"
        ), gr.update(visible=False)

        # --- Stage 2: Matching ---
        yield None, log("[2/4] Matching rows between main and auxiliary tables..."), gr.update(visible=False)
        rows, column_detection_result = matcher.match(result)

        exact_count     = sum(1 for r in rows if r.match_type == MatchType.EXACT)
        unmatched_count = sum(1 for r in rows if r.match_type == MatchType.UNMATCHED)
        yield None, log(
            f"      Done — {exact_count} exact match(es), {unmatched_count} unmatched"
        ), gr.update(visible=False)

        # --- Stage 3: Resolution ---
        exact_rows     = [r for r in rows if r.match_type == MatchType.EXACT]
        unmatched_rows = [r for r in rows if r.match_type == MatchType.UNMATCHED]

        if unmatched_rows:
            yield None, log(f"[3/4] Resolving {len(unmatched_rows)} unmatched row(s) (fuzzy + semantic)..."), gr.update(visible=False)
            resolved_rows = resolver.resolve(unmatched_rows, result)

            fuzzy_count   = sum(1 for r in resolved_rows if r.match_type == MatchType.FUZZY)
            rule_count    = sum(1 for r in resolved_rows if r.match_type == MatchType.RULE_BASED)
            still_count   = sum(1 for r in resolved_rows if r.match_type == MatchType.UNMATCHED)
            yield None, log(
                f"      Done — {fuzzy_count} fuzzy, {rule_count} rule-based, {still_count} still unmatched"
            ), gr.update(visible=False)
        else:
            yield None, log("[3/4] No unmatched rows — skipping resolution"), gr.update(visible=False)
            resolved_rows = []

        # --- Stage 4: Merging ---
        yield None, log("[4/4] Merging and ordering final results..."), gr.update(visible=False)
        main_tables_for_merge = [t for t in result.tables if t.role == TableRole.MAIN]
        if not main_tables_for_merge:
            raise ValueError("No main tables found — cannot merge.")

        merged_rows = merger.merge(resolved_rows + exact_rows, main_tables_for_merge)
        yield None, log(f"      Done — {len(merged_rows)} row(s) in final output"), gr.update(visible=False)

        # --- Build dataframe ---
        rows_data = []
        for row in merged_rows:
            row_dict = row.data.copy()
            row_dict["_match_type"]  = row.match_type.value
            row_dict["_confidence"]  = str(row.confidence)
            row_dict["_reasoning"]   = row.reasoning or ""
            rows_data.append(row_dict)
        df = pd.DataFrame(rows_data)

        # --- Write debug log ---
        debug_log = {
            "timestamp":         datetime.now().isoformat(),
            "file":              pdf_file.name,
            "page":              int(page_number),
            "total_rows":        len(merged_rows),
            "exact_matches":     sum(1 for r in merged_rows if r.match_type == MatchType.EXACT),
            "fuzzy_matches":     sum(1 for r in merged_rows if r.match_type == MatchType.FUZZY),
            "rule_based_matches":sum(1 for r in merged_rows if r.match_type == MatchType.RULE_BASED),
            "unmatched":         sum(1 for r in merged_rows if r.match_type == MatchType.UNMATCHED),
            "rows":              [row.model_dump(mode='json') for row in merged_rows],
        }
        debug_filename = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        debug_path = config.debug_dir / debug_filename
        with open(debug_path, "w") as f:
            json.dump(debug_log, f, indent=2, default=str)

        summary = (
            f"Exact: {debug_log['exact_matches']}  |  "
            f"Fuzzy: {debug_log['fuzzy_matches']}  |  "
            f"Rule-based: {debug_log['rule_based_matches']}  |  "
            f"Unmatched: {debug_log['unmatched']}\n"
            f"Debug log → {debug_filename}"
        )
        yield df, log(f"\nComplete — {len(merged_rows)} rows\n{summary}"), gr.update(visible=False)

    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Pipeline failed:\n%s", tb)
        yield None, log(f"\nPipeline failed: {type(e).__name__}: {e}"), gr.update(value=tb, visible=True)


with gr.Blocks(title="Cartex — Type 1 Extraction") as app:
    gr.Markdown("# Cartex")
    gr.Markdown("### Sub-Item / Sub-Table Extraction — Type 1: Contextual Tables")

    with gr.Row():
        with gr.Column(scale=1):
            pdf_input = gr.File(
                label="Upload PDF",
                file_types=[".pdf"]
            )
            page_number = gr.Number(
                label="Page Number",
                value=1,
                minimum=1,
                precision=0
            )
            run_button = gr.Button("Run Pipeline", variant="primary")

        with gr.Column(scale=2):
            status_output = gr.Textbox(
                label="Pipeline Log",
                lines=10,
                max_lines=20,
                interactive=False,
                autoscroll=True,
            )

    with gr.Row():
        results_table = gr.Dataframe(
            label="Merged Table",
            interactive=False,
            wrap=True
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
        inputs=[pdf_input, page_number],
        outputs=[results_table, status_output, error_output]
    )

if __name__ == "__main__":
    app.launch()
