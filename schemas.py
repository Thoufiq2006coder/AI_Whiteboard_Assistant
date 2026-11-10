"""Pydantic data models for structured Gemini responses in BoardWise AI."""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


def normalize_level(value) -> str:
    """Coerces anything the model returns ('high', 'Medium confidence', None) into High/Medium/Low."""
    text = str(value or "").strip().lower()
    if text.startswith("high"):
        return "High"
    if text.startswith("low"):
        return "Low"
    return "Medium"  # unknown -> cautious middle value so the student is asked to check


class _Leveled(BaseModel):
    @field_validator("confidence", "overall_legibility", mode="before", check_fields=False)
    @classmethod
    def _norm(cls, v):
        return normalize_level(v)


class NoteItem(_Leveled):
    """An individual note entry (equation, diagram note, or general point)."""
    content: str = Field(description="The note text or equation. If mathematical, use clean LaTeX (no $ delimiters).")
    confidence: str = Field(description="'High', 'Medium', or 'Low'.")
    confidence_reason: Optional[str] = Field(
        default=None, description="Required if confidence is Medium or Low (e.g. 'faint marker')."
    )
    is_confirmed: bool = Field(default=False, description="Whether the student confirmed this item.")


class TermItem(_Leveled):
    """A key term and its definition."""
    term: str = Field(description="The term, variable, concept, or theorem.")
    definition: str = Field(description="The definition or explanation written on the board.")
    confidence: str = Field(description="'High', 'Medium', or 'Low'.")
    confidence_reason: Optional[str] = Field(default=None, description="Required if Medium or Low.")
    is_confirmed: bool = Field(default=False, description="Whether the student confirmed this definition.")


class ExtractionOutput(_Leveled):
    """Structured extraction of whiteboard contents."""
    title: str = Field(description="Main lecture heading or topic of the whiteboard.")
    equations: List[NoteItem] = Field(default_factory=list, description="Formulas in LaTeX.")
    key_terms: List[TermItem] = Field(default_factory=list, description="Vocabulary, variables, theorems.")
    diagram_notes: List[NoteItem] = Field(default_factory=list, description="Descriptions of diagrams, graphs, drawings.")
    other_notes: List[NoteItem] = Field(default_factory=list, description="Other remarks and bullet points.")
    overall_legibility: str = Field(description="'High', 'Medium', or 'Low'.")
    unreadable_regions: List[str] = Field(default_factory=list, description="Blurry, faded or obstructed areas.")
    suggested_questions: List[str] = Field(default_factory=list, description="Exactly 3 starter questions.")


class QAOutput(_Leveled):
    """Structured response for grounded student questions."""
    answer: str = Field(description="Clear, concise answer grounded strictly on the whiteboard notes.")
    confidence: str = Field(description="'High', 'Medium', or 'Low'. Do not invent numbers.")
    answerable_from_board: bool = Field(description="True if the board content can answer the question.")
    missing_context: Optional[str] = Field(default=None, description="If unanswerable, what is missing.")
    evidence: List[str] = Field(default_factory=list, description="Board elements supporting the answer.")
    reasoning_steps: List[str] = Field(default_factory=list, description="1-3 short deduction steps.")
    how_to_verify: str = Field(description="A short tip on where to verify this on the board.")
