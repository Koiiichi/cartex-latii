from pydantic import BaseModel, Field 
from typing import Optional
from enum import Enum

# Enum definitions

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

# Base models

class TableModel(BaseModel):
    table_id: str
    role: TableRole
    page_number: int
    headers: list[str]
    rows: list[dict[str, str]]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: Optional[str] = None

class ContextModel(BaseModel):
    context_id: str
    type: ContextType
    page_number: int
    content: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: Optional[str] = None

class TextContextModel(ContextModel):
    category: Optional[str] = None
    scope: Optional[list[str]] = None

class ImageContextModel(ContextModel):
    format: str
    dimensions: tuple[int, int]
    interpretation: Optional[str] = None

# Gemini-specific models

class GeminiResponse(BaseModel):
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: Optional[str] = None

class GeminiTableModel(GeminiResponse):
    headers: list[str]
    rows: list[dict[str, str]]
    role: TableRole
    page_number: int

class GeminiResolutionModel(GeminiResponse):
    matched_value: Optional[str] = None
    match_type: MatchType
    reasoning: str

class MergedRow(BaseModel):
    row_id: str
    data: dict[str, str]
    match_type: MatchType
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    provenance: Optional[str] = None
