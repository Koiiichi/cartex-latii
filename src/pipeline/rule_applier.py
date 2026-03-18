from src.gemini import Gemini
from src.models import ContextCategory, GeminiRuleApplicationResult, ImageContextModel, MergedRow, ModelType, TextContextModel
from src.ai.prompts import RULE_APPLICATION
from google.genai import types
import json
import logging

logger = logging.getLogger(__name__)

class RuleApplier:
    def __init__(self):
        self.gemini = Gemini()
    def apply_rules(self, merged_rows: list[MergedRow], contexts: list[TextContextModel | ImageContextModel]) -> list[MergedRow]:
        text_contexts = [c for c in contexts if isinstance(c, TextContextModel)]
        image_contexts = [c for c in contexts if isinstance(c, ImageContextModel) and c.interpretation]

        if not text_contexts:
            logger.info("No applicable contexts found for rule application.")
            return merged_rows

        rows_json = json.dumps([r.model_dump(mode='json') for r in merged_rows], indent=2)
        text_contexts_json = json.dumps([c.model_dump(mode='json') for c in text_contexts], indent=2)
        image_contexts_json = json.dumps([c.model_dump(mode='json') for c in image_contexts], indent=2)
        contents = [
            types.Part.from_text(text=RULE_APPLICATION),
            types.Part.from_text(text=rows_json),
            types.Part.from_text(text=text_contexts_json),
            types.Part.from_text(text=image_contexts_json)
        ]
        results = self.gemini.request(contents, GeminiRuleApplicationResult, model=ModelType.ADVANCED)
        
        for result in results.applications:
            if result.row_id == "ALL":
                for merged_row in merged_rows:
                    merged_row.document_rules.append(result.rule)
            else:
                for merged_row in merged_rows:
                    if merged_row.row_id == result.row_id:
                        merged_row.applied_rules.append(result.rule)
        return merged_rows