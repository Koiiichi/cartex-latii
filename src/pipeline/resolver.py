from models import ExtractionResult, GeminiResolutionResult, ImageContextModel, MatchType, MergedRow, ModelType, TableModel, TableRole, TextContextModel
from gemini import Gemini
from google.genai import types
from ai.prompts import FUZZY_MATCHING, SEMANTIC_MATCHING
import json 


class Resolver:
    def __init__(self):
        self.gemini = Gemini()
    
    def resolve(self, unmatched_rows: list[MergedRow], extraction_result: ExtractionResult) -> list[MergedRow]:
        auxiliary_tables = [table for table in extraction_result.tables if table.role == TableRole.AUXILIARY]
        context = extraction_result.context
        fuzzy_results = self._fuzzy_match(unmatched_rows, auxiliary_tables)
        fuzzy_resolved = [r for r in fuzzy_results if r.match_type == MatchType.FUZZY]
        still_unmatched = [r for r in fuzzy_results if r.match_type == MatchType.UNMATCHED]
        semantic_results = self._semantic_match(still_unmatched, context)
        semantic_resolved = [r for r in semantic_results if r.match_type == MatchType.RULE_BASED]
        final_unmatched = [r for r in semantic_results if r.match_type == MatchType.UNMATCHED]

        return fuzzy_resolved + semantic_resolved + final_unmatched
    
    def _fuzzy_match(self, unmatched_rows: list[MergedRow], auxiliary_tables: list[TableModel]) -> list[MergedRow]:
        rows = [row.model_dump(mode='json') for row in unmatched_rows]
        aux_rows = []

        for table in auxiliary_tables:
            aux_rows.extend(table.rows)
        aux_rows_json = json.dumps(aux_rows, indent=2)

        contents = [
            types.Part.from_text(text=FUZZY_MATCHING),
            types.Part.from_text(text=json.dumps(rows, indent=2)),
            types.Part.from_text(text=aux_rows_json)
        ]

        gemini_result = self.gemini.request(contents, GeminiResolutionResult, model=ModelType.FAST)
        merged_rows = []

        for resolution in gemini_result.resolutions:
            original_data = next((r.data for r in unmatched_rows if r.row_id == resolution.row_id), {})
            resolved_data = {**original_data, "aux_matched_value": resolution.matched_value} if resolution.matched_value else original_data
            merged_rows.append(MergedRow(
                row_id=resolution.row_id,
                data=resolved_data,
                match_type=resolution.match_type,
                confidence=resolution.confidence,
                reasoning=resolution.reasoning
            ))
        return merged_rows
            
    def _semantic_match(self, unmatched_rows: list[MergedRow], context: list[TextContextModel | ImageContextModel]) -> list[MergedRow]:
        rows = [row.model_dump(mode='json') for row in unmatched_rows]
        context_json = json.dumps([c.model_dump(mode='json') for c in context], indent=2)

        contents = [
            types.Part.from_text(text=SEMANTIC_MATCHING),
            types.Part.from_text(text=json.dumps(rows, indent=2)),
            types.Part.from_text(text=context_json)
        ]

        gemini_result = self.gemini.request(contents, GeminiResolutionResult, model=ModelType.ADVANCED)
        merged_rows = []
        
        for resolution in gemini_result.resolutions:
            original_data = next((r.data for r in unmatched_rows if r.row_id == resolution.row_id), {})
            resolved_data = {**original_data, "aux_matched_value": resolution.matched_value} if resolution.matched_value else original_data
            merged_rows.append(MergedRow(
                row_id=resolution.row_id,
                data=resolved_data,
                match_type=resolution.match_type,
                confidence=resolution.confidence,
                reasoning=resolution.reasoning
            ))
        return merged_rows
