from pydantic import BaseModel, Field 
from typing import Optional, TypeVar
from enum import Enum

# Enum for table roles

class TableRole(Enum):
    MAIN = "main"
    AUXILIARY = "auxiliary"
    OTHER = "other"

class ContextType(Enum):
    TEXT = "text"
    IMAGE = "image"

class MatchType(Enum):
    FUZZY = "fuzzy"
    RULE_BASED = "rule_based"
    EXACT = "exact"
    UNMATCHED = "unmatched"

# Enum for Gemini model types

class ModelType(Enum):
    FAST = "fast"
    ADVANCED = "advanced"

# Type variable for Gemini response models

T = TypeVar('T', bound=BaseModel)

# Base models

class BoundingBox(BaseModel):
    x: int = Field(description="Normalised horizontal position of the left edge, in the range 0–1000 where 0 is the left edge and 1000 is the right edge of the image.")
    y: int = Field(description="Normalised vertical position of the top edge, in the range 0–1000 where 0 is the top edge and 1000 is the bottom edge of the image.")
    width: int = Field(description="Normalised width of the element, in the range 0–1000.")
    height: int = Field(description="Normalised height of the element, in the range 0–1000.")

class TableModel(BaseModel):
    table_id: str
    role: TableRole
    page_number: int
    headers: list[str]
    rows: list[dict[str, str]]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: Optional[str] = None
    bbox: Optional[BoundingBox] = None  # x, y, width, height in pixels

class ContextModel(BaseModel):
    context_id: str
    type: ContextType
    page_number: int
    content: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: Optional[str] = None
    bbox: Optional[BoundingBox] = None  # x, y, width, height in pixels

class TextContextModel(ContextModel):
    category: Optional[str] = None
    scope: Optional[list[str]] = None

class ImageContextModel(ContextModel):
    format: str
    dimensions: tuple[int, int]
    interpretation: Optional[str] = None

class MergedRow(BaseModel):
    row_id: str
    data: dict[str, str]
    match_type: MatchType
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reasoning: Optional[str] = None

class ExtractionResult(BaseModel):
    tables: list[TableModel] = []
    context: list[TextContextModel | ImageContextModel] = []

# Gemini-specific models

class GeminiResponse(BaseModel):
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Confidence score between 0 and 1 representing how certain you are about this extraction. Use 1.0 for clear, unambiguous content and lower values when the content is unclear, partially visible, or ambiguous."
    )
    notes: Optional[str] = Field(
        default=None,
        description="Any observations about irregularities, ambiguities, or anything unusual encountered during extraction that may affect accuracy."
    )

class GeminiTableModel(GeminiResponse):
    headers: list[str] = Field(
        description="List of column header names exactly as they appear in the table, from left to right. Include merged or multi-level headers as a single combined string e.g. 'Type / Subtype'."
    )
    rows: list[dict[str, str]] = Field(
        description="List of rows where each row is a dictionary mapping column header name to cell value. Every key must exactly match a header from the headers list. Use empty string for blank cells, never null."
    )
    role: TableRole = Field(
        description="Role of this table in the document. Use 'main' for the primary schedule being extracted (e.g. Window Schedule, Door Schedule). Use 'auxiliary' for supplementary reference tables (e.g. Glazing Schedule, Hardware Schedule). Use 'other' if the table is neither."
    )
    page_number: int = Field(
        description="Page number where this table was found, as it appears in the document."
    )
    bbox: Optional[BoundingBox] = Field(
        default=None,
        description="Bounding box coordinates of the table on the page. Provide if you can determine the location reliably, otherwise leave null."
    )

class GeminiContextModel(GeminiResponse):
    content: str = Field(
        description="The full extracted text content of this context item. For text blocks, include the complete text verbatim. For images, provide a file path or placeholder identifier."
    )
    type: ContextType = Field(
        description="Type of context. Use 'text' for notes, specifications, legends described in text, or any readable text block. Use 'image' for diagrams, drawings, visual legends, or item cards that are primarily visual."
    )
    page_number: int = Field(
        description="Page number where this context item was found."
    )
    bbox: Optional[BoundingBox] = Field(
        default=None,
        description="Bounding box coordinates of this context item on the page. Provide if you can determine the location reliably, otherwise leave null."
    )

class GeminiTextContextModel(GeminiContextModel):
    category: Optional[str] = Field(
        default=None,
        description="Category of this text context. Examples: 'general_note', 'performance_spec', 'material_requirement', 'structural_criteria', 'code_requirement'. Use your best judgment based on the content."
    )

class GeminiImageContextModel(GeminiContextModel):
    interpretation: Optional[str] = Field(
        default=None,
        description="A detailed textual description of what this image shows. Include all visible labels, codes, dimensions, operability types, configurations, and any other information that would help link this image to items in the main schedule."
    )

class GeminiTableResult(BaseModel):
    tables: list[GeminiTableModel] = Field(
        default=[],
        description="All tables detected on the page."
    )
class GeminiContextResult(BaseModel):
    context: list[GeminiTextContextModel | GeminiImageContextModel] = Field(
        default=[],
        description="All non-table context detected on the page, including text notes and visual diagrams."
    )

class GeminiResolutionModel(GeminiResponse):
    matched_value: Optional[str] = Field(
        default=None,
        description="The resolved value from the auxiliary table that this item maps to. Leave null if no match could be found."
    )
    match_type: MatchType = Field(
        description="How this match was determined. Use 'fuzzy' for near-identical string matches, 'rule_based' for matches derived from notes or rules, 'exact' for perfect string matches, 'unmatched' if no match could be found."
    )
    reasoning: str = Field(
        description="Explanation of why this match was made or why no match could be found. Be specific — reference the exact strings compared or the rule applied."
    )
    row_id: str = Field(
        description="The row_id of the main schedule item being resolved. This should correspond to the row_id in the MergedRow data model."
    )

class GeminiResolutionResult(BaseModel):
    resolutions: list[GeminiResolutionModel] = Field(
        default=[],
        description="List of resolution results for each unmatched item. Each entry should indicate the row_id of the item being resolved, the matched value from the auxiliary table (if any), the type of match, and the reasoning behind it."
    )

# Gemini models for mapping auxiliary tables to main schedule items

class GeminiColumnMatch(BaseModel):
    main_column: str = Field(description="The column header from the main schedule.")
    auxiliary_column: str = Field(description="The column header from the auxiliary table that matches the main column.")
    auxiliary_table_id: str = Field(description="The table_id of the auxiliary table where the matching column was found.")

class GeminiColumnDetectionResult(GeminiResponse):
    matches: list[GeminiColumnMatch] = Field(
        default=[],
        description="List of all detected column matches between the main schedule and auxiliary tables. Each match indicates which column in the main schedule corresponds to which column in which auxiliary table."
    )

class GeminiCompoundResolution(GeminiResponse):
    row_id: str = Field(description="The row_id of the main schedule row being resolved. Must match the row_id from the input.")
    components: list[str] = Field(description="List of the individual components or attributes that were identified as part of this compound item. For example, if a row in the main schedule includes a note that references multiple items in an auxiliary table, list each of those items here.")
    primary: str = Field(description="The primary component or attribute that best represents the main item. This is the value that should be used for matching against the auxiliary table.")
    secondary: list[str] = Field(description="Any secondary components or attributes that provide additional context or information about the main item, but are not the primary basis for matching.")
    reasoning: str = Field(description="Detailed explanation of why the primary component was chosen for matching. Reference specific text from the main schedule and auxiliary tables that informed this decision.")

class GeminiCompoundResolutionResult(BaseModel):
    resolutions: list[GeminiCompoundResolution] = Field(
        default=[],
        description="One resolution per compound row. Each entry must include the row_id from the input so results can be matched back to their source rows."
    )