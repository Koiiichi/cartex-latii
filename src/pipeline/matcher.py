from src.gemini import Gemini
from google.genai import types
from src.models import GeminiColumnDetectionResult, GeminiCompoundResolution, GeminiCompoundResolutionResult, MatchType, MergedRow, ModelType, TableModel, TableRole, ExtractionResult
from src.ai.prompts import COLUMN_DETECTION, COMPOUND_RESOLUTION
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
        all_compound_pending = []
        self.auxiliary_tables = auxiliary_tables
        self.main_tables = main_tables

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
                merged, compound_pending = self._exact_match(
                    main_table,
                    aux_table,
                    match.main_column,
                    match.auxiliary_column,
                    pk_column
                )
                all_merged_rows.extend(merged)
                all_compound_pending.extend(compound_pending)
                exact = sum(1 for r in merged if r.match_type == MatchType.EXACT)
                unmatched = sum(1 for r in merged if r.match_type == MatchType.UNMATCHED)
                logger.info("    → %d exact, %d unmatched", exact, unmatched)

        if all_compound_pending:
            logger.info("Resolving %d compound reference(s) in batch across all main tables...", len(all_compound_pending))
            compound_resolved = self._resolve_compound_batch(all_compound_pending)
            all_merged_rows.extend(compound_resolved)

        return all_merged_rows, column_detection_result

    def _detect_link_columns(self, tables: list[TableModel]) -> GeminiColumnDetectionResult:
        tables_json = json.dumps([table.model_dump(mode='json') for table in tables], indent=2)
        contents = [
            types.Part.from_text(text=COLUMN_DETECTION),
            types.Part.from_text(text=tables_json)
        ]
        return self.gemini.request(contents, GeminiColumnDetectionResult, model=ModelType.ADVANCED)
    
    def _exact_match(self, main_table: TableModel, auxiliary_table: TableModel, main_column: str, auxiliary_column: str, pk_column: str) -> tuple[list[MergedRow], list[dict]]:
        merged_rows = []
        compound_pending = []
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
                if row_value and ("/" in str(row_value) or "," in str(row_value)):
                    compound_pending.append({
                        "row_id": row_id,
                        "row": row,
                        "compound_value": row_value,
                        "main_column": main_column
                    })
                else: 
                    merged_row = MergedRow(
                        row_id=row_id,
                        data=row,
                        match_type=MatchType.UNMATCHED,
                        confidence=0.0,
                        reasoning=f"No match found for value '{row_value}' in auxiliary table"
                    )
                    merged_rows.append(merged_row)
        return merged_rows, compound_pending
    
    def _resolve_compound_batch(self, compound_pending: list[dict]) -> list[MergedRow]:
        rows_json = json.dumps([{
            "row_id": item["row_id"],
            "compound_value": item["compound_value"],
            "data": item["row"]
            } for item in compound_pending], indent=2)
        
        aux_tables_json = json.dumps(
            [t.model_dump(mode='json') for t in self.auxiliary_tables], indent=2
        )
        contents = [
            types.Part.from_text(text=COMPOUND_RESOLUTION),
            types.Part.from_text(text=rows_json),
            types.Part.from_text(text=aux_tables_json),
        ]
        resolutions = self.gemini.request(contents, GeminiCompoundResolutionResult, model=ModelType.ADVANCED)
        merged_rows = []

        for resolution in resolutions.resolutions:
            item = next((i for i in compound_pending if i["row_id"] == resolution.row_id), None)
            original_row = item["row"] if item else {}
            compound_value = item["compound_value"] if item else ""
            primary_aux_data = {}

            for t in self.auxiliary_tables:
                for aux_row in t.rows:
                    if resolution.primary in aux_row.values():
                        primary_aux_data = {f"aux_{k}": v for k, v in aux_row.items()}
                        break
                if primary_aux_data:
                    break

            notes_parts = []
            for secondary_value in resolution.secondary:
                for t in self.auxiliary_tables:
                    for aux_row in t.rows:
                        if secondary_value in aux_row.values():
                            row_str = ", ".join(f"{k}: {v}" for k, v in aux_row.items() if v)
                            notes_parts.append(row_str)
                            break

            notes_string = " | ".join(notes_parts) if notes_parts else ""

            merged_data = {**original_row, **primary_aux_data}
            if notes_string:
                merged_data["_compound_notes"] = notes_string

            merged_rows.append(MergedRow(
                row_id=resolution.row_id,
                data=merged_data,
                match_type=MatchType.EXACT,
                confidence=resolution.confidence,
                reasoning=f"Compound reference '{compound_value}' resolved — primary: '{resolution.primary}', secondary: {resolution.secondary}. {resolution.reasoning}"
            ))
        return merged_rows
