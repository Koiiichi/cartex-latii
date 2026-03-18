from src.pipeline.extractor import Extractor
from src.pipeline.enrich import Enricher
from src.models import EnrichedRow, UserTableSchema

extractor = Extractor()
enricher = Enricher()

def run(file_path: str, page_number: int, schema: UserTableSchema) -> list[EnrichedRow]:
    extracted_rows = extractor.extract(file_path, page_number)
    results = enricher.enrich(extracted_rows, schema)
    return results

