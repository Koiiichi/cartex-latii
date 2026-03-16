from models import ExtractionResult, MergedRow, TableModel

class Merger:
    def __init__(self):
        pass

    def merge(self, resolved_rows: list[MergedRow], main_table: TableModel, main_column: str) -> list[MergedRow]:
        merged_lookup = {row.row_id: row for row in resolved_rows}
        ordered_rows = []
        for main_row in main_table.rows:
            row_id = main_row.get(main_column)
            if row_id in merged_lookup:
                ordered_rows.append(merged_lookup[row_id])
        return ordered_rows