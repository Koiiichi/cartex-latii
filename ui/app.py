import gradio as gr
import pandas as pd
from main import run
from src.models import MatchType
import json
import os
from datetime import datetime
from src.config import config

def process_document(pdf_file, page_number):
    if pdf_file is None:
        return None, "No file uploaded.", ""
    
    try:
        status = "Running extraction..."
        yield None, status, ""
        
        merged_rows = run(pdf_file.name, int(page_number) - 1)
        
        # Convert to dataframe
        rows_data = []
        for row in merged_rows:
            row_dict = row.data.copy()
            row_dict["_match_type"] = row.match_type.value
            row_dict["_confidence"] = str(row.confidence)
            row_dict["_reasoning"] = row.reasoning or ""
            rows_data.append(row_dict)
        
        df = pd.DataFrame(rows_data)
        
        # Write debug log
        debug_log = {
            "timestamp": datetime.now().isoformat(),
            "file": pdf_file.name,
            "page": page_number,
            "total_rows": len(merged_rows),
            "exact_matches": sum(1 for r in merged_rows if r.match_type == MatchType.EXACT),
            "fuzzy_matches": sum(1 for r in merged_rows if r.match_type == MatchType.FUZZY),
            "rule_based_matches": sum(1 for r in merged_rows if r.match_type == MatchType.RULE_BASED),
            "unmatched": sum(1 for r in merged_rows if r.match_type == MatchType.UNMATCHED),
            "rows": [row.model_dump(mode='json') for row in merged_rows]
        }
        
        debug_filename = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        debug_path = config.debug_dir / debug_filename
        with open(debug_path, "w") as f:
            json.dump(debug_log, f, indent=2, default=str)
        
        summary = (
            f"Done — {len(merged_rows)} rows processed\n"
            f"Exact: {debug_log['exact_matches']} | "
            f"Fuzzy: {debug_log['fuzzy_matches']} | "
            f"Rule-based: {debug_log['rule_based_matches']} | "
            f"Unmatched: {debug_log['unmatched']}\n"
            f"Debug log saved to: {debug_filename}"
        )
        
        yield df, summary, ""
        
    except Exception as e:
        yield None, f"Error: {str(e)}", str(e)


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
                label="Pipeline Status",
                lines=4,
                interactive=False
            )
    
    with gr.Row():
        results_table = gr.Dataframe(
            label="Merged Table",
            interactive=False,
            wrap=True
        )
    
    with gr.Row():
        error_output = gr.Textbox(
            label="Error Details",
            lines=3,
            interactive=False,
            visible=False
        )

    run_button.click(
        fn=process_document,
        inputs=[pdf_input, page_number],
        outputs=[results_table, status_output, error_output]
    )

if __name__ == "__main__":
    app.launch()