from src.models import ExtractionResult, MergedRow, TableModel
import logging

logger = logging.getLogger(__name__)


class Merger:
    def __init__(self):
        pass

    def merge(self, resolved_rows: list[MergedRow], main_tables: list[TableModel]) -> list[MergedRow]:
        logger.info(
            "Merging %d resolved rows across %d main table(s)",
            len(resolved_rows), len(main_tables)
        )
        merged_lookup = {row.row_id: row for row in resolved_rows}
        ordered_rows = []
        for main_table in main_tables:
            pk_column = main_table.headers[0]
            for main_row in main_table.rows:
                row_id = main_row.get(pk_column)
                if row_id in merged_lookup:
                    ordered_rows.append(merged_lookup[row_id])
                else:
                    logger.debug("Row '%s' not in resolved set, skipping", row_id)
        logger.info("Final merged output: %d rows", len(ordered_rows))
        return ordered_rows