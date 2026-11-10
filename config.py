"""Configuration constants and settings for BoardWise AI."""

import os
from pathlib import Path
from dotenv import load_dotenv

# ----------------------------------------------------------------- Branding
APP_NAME = "BoardWise AI"
APP_TITLE = "AI Whiteboard Companion"
APP_SUBTITLE = "Turn your classroom whiteboard into organized notes and ask questions about it."

# ----------------------------------------------------------------- Models
# Google retires Gemini models regularly (gemini-2.0-flash was shut down in June 2026 and
# gemini-2.5-flash is being retired), so a single hard-coded name is fragile.
#
# How the model is chosen (see gemini_service.resolve_models):
#   1. GEMINI_MODEL in your .env file (if you set it) is tried first.
#   2. Then the names in MODEL_CANDIDATES, in order.
#   3. Only models that your API key can actually see (client.models.list()) are used.
MODEL_CANDIDATES = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
]
IMAGE_MAX_DIMENSION = 1600
EXTRACTION_TEMPERATURE = 0.2
QA_TEMPERATURE = 0.2
CHAT_HISTORY_TURNS = 4

# ----------------------------------------------------------------- Grounding rules
SYSTEM_INSTRUCTION = (
    "You are an AI study assistant (not a human); use a neutral, clear tone; "
    "base answers only on what is visible on the board and the provided notes; "
    "if something is unreadable or missing, say so; never invent text, numbers or citations; "
    "mark uncertain items Medium or Low with the exact reason."
)

# ----------------------------------------------------------------- HAI content (shown in UI)
HAI_PRINCIPLES = [
    {
        "title": "Setting Expectations & Limits (L11)",
        "description": "The upload screen states what the AI does well, where it struggles, and photo tips before anything is processed.",
    },
    {
        "title": "Calibrated Trust (L6)",
        "description": "Confidence labels (High/Medium/Low) with a reason. Nothing is pre-confirmed; a check mark only appears after the student confirms an item.",
    },
    {
        "title": "Human-in-the-Loop & Correction (L4, L8)",
        "description": "The AI proposes notes; the student edits and confirms them. Saved notes become the ground truth for Q&A.",
    },
    {
        "title": "Communicating Uncertainty & Errors (L7)",
        "description": "Amber items with a 'Why flagged' reason, an overall legibility rating, and a list of unreadable regions.",
    },
    {
        "title": "Explainability (L12)",
        "description": "Every answer has a 'Why this answer?' panel with evidence from the board, reasoning steps and a 'How to verify' tip.",
    },
    {
        "title": "Mixed Initiative (L4)",
        "description": "The AI proactively suggests starter questions based on the board content.",
    },
    {
        "title": "Error Recovery (L7)",
        "description": "Clear error messages with a next action (missing key, wrong model, quota, unreadable photo, off-board question).",
    },
    {
        "title": "Accurate Mental Model (L5)",
        "description": "The assistant states that it is an AI, uses a neutral tone and does not simulate emotions.",
    },
]

WHAT_IT_CANT_DO = [
    "Read severely blurry, glared, or cropped whiteboard text.",
    "Guarantee mathematical validity of incomplete formulas written on the board.",
    "Know information that was never written or discussed on the whiteboard.",
    "Replace human verification: always double-check answers.",
]

KEY_FEATURES = [
    ("📤", "Upload Whiteboard"),
    ("🗂️", "AI Extract & Organize"),
    ("✏️", "Review & Edit"),
    ("💬", "Ask Questions (Q&A)"),
    ("📥", "Export Notes"),
]

HAI_CONCEPTS_APPLIED = [
    ("🛡️", "Appropriate Trust", "Indicates possible errors and encourages verification."),
    ("👤", "Human-in-the-Loop", "User reviews and corrects AI-generated content."),
    ("⚠️", "Communicating Uncertainty", "Flags unclear or low-confidence content for the user to check."),
]


# ----------------------------------------------------------------- Environment / API key
def load_environment():
    """Loads environment variables from .env in the script, parent and working directories."""
    script_dir = Path(__file__).resolve().parent
    for candidate in [script_dir / ".env", script_dir.parent / ".env", Path.cwd() / ".env"]:
        if candidate.exists():
            load_dotenv(dotenv_path=candidate, override=False)


load_environment()


def get_api_key() -> str:
    """Reads the Google AI Studio key from the environment or Streamlit secrets."""
    load_environment()
    key = os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if not key:
        try:
            import streamlit as st

            if "GOOGLE_API_KEY" in st.secrets:
                key = st.secrets["GOOGLE_API_KEY"]
        except Exception:
            pass
    return (key or "").strip().strip('"').strip("'")


def is_api_key_valid(key: str) -> bool:
    """True when a key is configured and is not the placeholder."""
    if not key:
        return False
    clean = key.strip()
    if clean in ("PASTE_YOUR_KEY_HERE", "YOUR_API_KEY"):
        return False
    return len(clean) >= 15


def get_preferred_model() -> str:
    """Optional model override from .env (GEMINI_MODEL=...)."""
    load_environment()
    return os.getenv("GEMINI_MODEL", "").strip()
