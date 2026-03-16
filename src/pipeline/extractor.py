from gemini import Gemini
from models import ContextType, ExtractionResult, GeminiImageContextModel, GeminiTableResult, GeminiContextResult, GeminiTextContextModel, ImageContextModel, TextContextModel, TableModel, GeminiTableModel, T, ModelType 
from google.genai import types
from config import config
from ai.prompts import CONTEXT_EXTRACTION, TABLE_EXTRACTION
from typing import Type
import pymupdf

class Extractor:
    def __init__(self):
        self.gemini = Gemini()

    def extract(self, file_path: str, page_number: int) -> ExtractionResult:
        image_bytes = self._pdf_to_image(file_path, page_number)
        tables_result = self._extract_tables(image_bytes)
        tables = []
        for i, table in enumerate(tables_result.tables):
            tables.append(TableModel(
                table_id=f"table_{i}_{page_number}",
                role=table.role,
                page_number=table.page_number,
                headers=table.headers,
                rows=table.rows,
                confidence=table.confidence,
                notes=table.notes
            ))

        contexts_result = self._extract_context(image_bytes)
        contexts = []
        for i, context in enumerate(contexts_result.context):
            if isinstance(context, GeminiTextContextModel):
                contexts.append(TextContextModel(
                    context_id=f"context_{i}_{page_number}",
                    type=context.type,
                    page_number=context.page_number,
                    content=context.content,
                    confidence=context.confidence,
                    notes=context.notes,
                    category=context.category,
                    scope=None
                ))
            elif isinstance(context, GeminiImageContextModel):
                contexts.append(ImageContextModel(
                    context_id=f"context_{i}_{page_number}",
                    type=context.type,
                    page_number=context.page_number,
                    content=context.content,
                    confidence=context.confidence,
                    notes=context.notes,
                    format="png",
                    dimensions=(0, 0),
                    interpretation=context.interpretation
                ))
        return ExtractionResult(tables=tables, context=contexts)
            
    def _pdf_to_image(self, file_path: str, page_number: int) -> bytes:
        doc = pymupdf.open(file_path)
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=config.dpi)
        return pix.tobytes()
    
    def _call_gemini(self, image_bytes: bytes, prompt: str, schema: Type[T]) -> T:
        contents = [
        types.Part.from_bytes(data=image_bytes, mime_type='image/png'),
        types.Part.from_text(text=prompt)
        ]
        return self.gemini.request(contents, schema, model=ModelType.ADVANCED)
    
    def _extract_tables(self, image_bytes: bytes) -> GeminiTableResult:
        return self._call_gemini(image_bytes, TABLE_EXTRACTION, GeminiTableResult)

    def _extract_context(self, image_bytes: bytes) -> GeminiContextResult:
        return self._call_gemini(image_bytes, CONTEXT_EXTRACTION, GeminiContextResult)
