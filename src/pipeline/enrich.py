from src.gemini import Gemini
from src.models import EnrichedRow, ExtractionResult, GeminiEnrichedRowResult, ModelType, UserTableSchema
from src.ai.prompts import ENRICHMENT

from google.genai import types
import json
import logging

logger = logging.getLogger(__name__)

class Enricher:
    def __init__(self):
        self.gemini = Gemini()
    def enrich(self, extraction_result: ExtractionResult, schema: UserTableSchema) -> list[EnrichedRow]:
        contents = self._build_contents(extraction_result, schema)
        results = self.gemini.request(contents, GeminiEnrichedRowResult, model=ModelType.ADVANCED)
        
        enriched_rows = []

        for result in results.enriched_rows:
            enriched_row = EnrichedRow(
                row_id=result.row_id,
                data=result.data,
                field_sources=result.field_sources,
                confidence=result.confidence,
                reasoning=result.reasoning
            )
            enriched_rows.append(enriched_row)
        return enriched_rows
    
    def _build_contents(self, extraction_result: ExtractionResult, schema: UserTableSchema) -> list[types.Part]:
        tables_json = json.dumps([table.model_dump(mode='json') for table in extraction_result.tables], indent=2)
        context_json = json.dumps([context.model_dump(mode='json') for context in extraction_result.context], indent=2)
        schema_json = json.dumps({"template": schema.template.value, "columns": schema.columns}, indent=2)
        contents = [
            types.Part.from_text(text=ENRICHMENT),
            types.Part.from_text(text=schema_json),
            types.Part.from_text(text=tables_json),
            types.Part.from_text(text=context_json)]
        return contents