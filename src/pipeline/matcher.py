from src.gemini import Gemini
from google.genai import types
from src.models import GeminiColumnDetectionResult, MatchType, MergedRow, ModelType, TableModel, TableRole, ExtractionResult
from src.ai.prompts import COLUMN_DETECTION
import json
import logging

logger = logging.getLogger(__name__)


class Matcher:
    def __init__(self):
        self.gemini = Gemini()

    def match(self, extraction_results: ExtractionResult) -> tuple[list[MergedRow], GeminiColumnDetectionResult]:
        main_tables = []
        auxiliary_tables = []
        for table in extraction_results.tables:
            if table.role == TableRole.MAIN:
                main_tables.append(table)
            if table.role == TableRole.AUXILIARY:
                auxiliary_tables.append(table)
        if not main_tables:
            raise ValueError("No main table found for matching.")
        if not auxiliary_tables:
            raise ValueError("No auxiliary tables found for matching.")

        logger.info(
            "Detecting link columns across %d tables (%d main, %d auxiliary)...",
            len(extraction_results.tables), len(main_tables), len(auxiliary_tables)
        )
        column_detection_result = self._detect_link_columns(extraction_results.tables)
        logger.info("Detected %d column link(s)", len(column_detection_result.matches))

        all_merged_rows = []
        for main_table in main_tables:
            pk_column = main_table.headers[0]
            logger.info("Processing main table '%s' (pk='%s', %d rows)", main_table.table_id, pk_column, len(main_table.rows))

            for match in column_detection_result.matches:
                if match.main_column not in main_table.headers:
                    continue
                aux_table = next((t for t in auxiliary_tables if t.table_id == match.auxiliary_table_id), None)
                if aux_table is None:
                    logger.warning("Auxiliary table '%s' not found, skipping match", match.auxiliary_table_id)
                    continue

                logger.info(
                    "  Exact matching: %s.%s ↔ %s.%s",
                    main_table.table_id, match.main_column, match.auxiliary_table_id, match.auxiliary_column
                )
                merged = self._exact_match(
                    main_table,
                    aux_table,
                    match.main_column,
                    match.auxiliary_column,
                    pk_column
                )
                exact = sum(1 for r in merged if r.match_type == MatchType.EXACT)
                unmatched = sum(1 for r in merged if r.match_type == MatchType.UNMATCHED)
                logger.info("    → %d exact, %d unmatched", exact, unmatched)
                all_merged_rows.extend(merged)

        return all_merged_rows, column_detection_result

    def _detect_link_columns(self, tables: list[TableModel]) -> GeminiColumnDetectionResult:
        tables_json = json.dumps([table.model_dump(mode='json') for table in tables], indent=2)
        contents = [
            types.Part.from_text(text=COLUMN_DETECTION),
            types.Part.from_text(text=tables_json)
        ]
        return self.gemini.request(contents, GeminiColumnDetectionResult, model=ModelType.ADVANCED)
    
    def _exact_match(self, main_table: TableModel, auxiliary_table: TableModel, main_column: str, auxiliary_column: str, pk_column: str) -> list[MergedRow]:
        merged_rows = []
        for idx, row in enumerate(main_table.rows):
            row_id = row.get(pk_column) or f"row_{idx}"
            row_value = row.get(main_column)
            for aux_row in auxiliary_table.rows:
                aux_value = aux_row.get(auxiliary_column)
                if row_value == aux_value:
                    aux_data = {f"aux_{k}": v for k, v in aux_row.items()}
                    merged_row = MergedRow(
                        row_id=row_id,
                        data={**row, **aux_data},
                        match_type=MatchType.EXACT,
                        confidence=1.0,
                        reasoning=f"Exact match on column '{main_column}' with value '{row_value}'"
                    )
                    merged_rows.append(merged_row)
                    break
            else:
                merged_row = MergedRow(
                    row_id=row_id,
                    data=row,
                    match_type=MatchType.UNMATCHED,
                    confidence=0.0,
                    reasoning=f"No match found for value '{row_value}' in auxiliary table"
                )
                merged_rows.append(merged_row)
        return merged_rows