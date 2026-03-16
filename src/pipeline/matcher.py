from gemini import Gemini
from google.genai import types
from models import GeminiColumnDetectionResult, MatchType, MergedRow, ModelType, TableModel, TableRole, ExtractionResult
from ai.prompts import COLUMN_DETECTION
import json


class Matcher:
    def __init__(self):
        self.gemini = Gemini()

    def match(self, extraction_results: ExtractionResult) -> list[MergedRow]:
        main_table = None
        auxiliary_tables = []
        for table in extraction_results.tables:
            if table.role == TableRole.MAIN:
                main_table = table
            if table.role == TableRole.AUXILIARY:
                auxiliary_tables.append(table)
        if not main_table:
            raise ValueError("No main table found for matching.")
        if not auxiliary_tables:
            raise ValueError("No auxiliary tables found for matching.")
        
        column_detection_result = self._detect_link_columns(extraction_results.tables)

        all_merged_rows = []
        for match in column_detection_result.matches:
            aux_table = next((t for t in auxiliary_tables if t.table_id == match.auxiliary_table_id), None)
            if aux_table is None:
                continue
        
            merged = self._exact_match(
                main_table,
                aux_table,
                match.main_column,
                match.auxiliary_column
            )
            all_merged_rows.extend(merged)

        return all_merged_rows

    def _detect_link_columns(self, tables: list[TableModel]) -> GeminiColumnDetectionResult:
        tables_json = json.dumps([table.model_dump() for table in tables], indent=2)
        contents = [
            types.Part.from_text(text=COLUMN_DETECTION),
            types.Part.from_text(text=tables_json)
        ]
        return self.gemini.request(contents, GeminiColumnDetectionResult, model=ModelType.ADVANCED)
    
    def _exact_match(self, main_table: TableModel, auxiliary_table: TableModel, main_column: str, auxiliary_column: str) -> list[MergedRow]:
        merged_rows = []
        for row in main_table.rows:
            row_value = row.get(main_column)
            for aux_row in auxiliary_table.rows:
                aux_value = aux_row.get(auxiliary_column)
                if row_value == aux_value:
                    aux_data = {f"aux_{k}": v for k, v in aux_row.items()}
                    merged_row = MergedRow(
                    row_id=row.get(main_column) or f"row_{main_table.rows.index(row)}",
                    data={**row, **aux_data},
                    match_type=MatchType.EXACT,
                    confidence=1.0,
                    reasoning=f"Exact match on column '{main_column}' with value '{row_value}'"
                    )
                    merged_rows.append(merged_row)
                    break
            else:
                merged_row = MergedRow(
                    row_id=row.get(main_column) or f"row_{main_table.rows.index(row)}",
                    data=row,
                    match_type=MatchType.UNMATCHED,
                    confidence=0.0,
                    reasoning=f"No match found for value '{row_value}' in auxiliary table"
                )
                merged_rows.append(merged_row)
        return merged_rows