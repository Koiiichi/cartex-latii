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
    main_tables = [t for t in result.tables if t.role == TableRole.MAIN]
    if not main_tables:
        raise ValueError("No main tables found.")
    merged_rows = merger.merge(resolved_rows + exact_rows, main_tables)
    return merged_rows
