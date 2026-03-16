from src.pipeline.extractor import Extractor
from src.pipeline.matcher import Matcher
from src.pipeline.merger import Merger
from src.pipeline.resolver import Resolver
from src.models import MatchType, MergedRow, TableRole

extractor = Extractor()
matcher = Matcher()
resolver = Resolver()
merger = Merger()

def run(file_path: str, page_number: int) -> list[MergedRow]:
    result = extractor.extract(file_path, page_number)
    rows, column_detection_result = matcher.match(result)
    exact_rows = [row for row in rows if row.match_type == MatchType.EXACT]
    unmatched_rows = [row for row in rows if row.match_type == MatchType.UNMATCHED]
    resolved_rows = resolver.resolve(unmatched_rows, result)
    main_table = next(t for t in result.tables if t.role == TableRole.MAIN)
    main_column = column_detection_result.matches[0].main_column if column_detection_result.matches else None
    if not main_column:
        raise ValueError("No column matches detected.")
    merged_rows = merger.merge(resolved_rows + exact_rows, main_table, main_column)
    return merged_rows