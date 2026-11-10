"""Google Gemini service: whiteboard extraction and grounded Q&A."""

import io
import time
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageOps
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

import config
from schemas import ExtractionOutput, QAOutput

# Models whose names contain these words cannot do image -> JSON text generation.
_EXCLUDED_WORDS = ("tts", "image", "live", "audio", "embedding", "imagen", "veo", "lyria",
                   "transcribe", "translate", "robotics", "computer-use", "aqa", "learnlm", "gemma")


class GeminiServiceError(RuntimeError):
    """An error whose message is safe and helpful to show directly to the student."""


# ---------------------------------------------------------------- Image preparation
def load_uploaded_image(file_like) -> Image.Image:
    """Opens an uploaded photo, fixes phone rotation (EXIF) and loads it fully into memory."""
    img = Image.open(file_like)
    img = ImageOps.exif_transpose(img)  # phone photos are often stored sideways
    img.load()
    return img.copy()


def prepare_image_payload(image: Image.Image) -> types.Part:
    """Converts to RGB, shrinks the longest side to IMAGE_MAX_DIMENSION and encodes as JPEG."""
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[3])
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    w, h = image.size
    longest = max(w, h)
    if longest > config.IMAGE_MAX_DIMENSION:
        scale = config.IMAGE_MAX_DIMENSION / float(longest)
        image = image.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90, optimize=True)
    return types.Part.from_bytes(data=buffer.getvalue(), mime_type="image/jpeg")


# ---------------------------------------------------------------- Client & model selection
def get_genai_client(api_key: str) -> genai.Client:
    if not config.is_api_key_valid(api_key):
        raise GeminiServiceError(
            "The API key is missing or still the placeholder. "
            "Open the .env file and set GOOGLE_API_KEY, then restart the app."
        )
    return genai.Client(api_key=api_key)


_MODEL_CACHE: Dict[str, List[str]] = {}


def _short(name: str) -> str:
    return name.split("/", 1)[1] if name.startswith("models/") else name


def list_available_models(client: genai.Client) -> List[str]:
    """Model names this API key can call with generateContent (empty list if listing fails)."""
    names: List[str] = []
    try:
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if actions and "generateContent" not in actions:
                continue
            names.append(_short(m.name))
    except Exception:
        return []
    return names


def resolve_models(client: genai.Client, api_key: str) -> List[str]:
    """Ordered list of models to try: .env override, then MODEL_CANDIDATES, filtered by what exists."""
    if api_key in _MODEL_CACHE:
        return _MODEL_CACHE[api_key]

    wanted: List[str] = []
    preferred = config.get_preferred_model()
    if preferred:
        wanted.append(_short(preferred))
    wanted += [m for m in config.MODEL_CANDIDATES if m not in wanted]

    available = list_available_models(client)
    if available:
        ordered = [m for m in wanted if m in available]
        if not ordered:  # none of our names exist -> pick any current Flash model that can read images
            flash = [m for m in available
                     if "flash" in m and not any(w in m for w in _EXCLUDED_WORDS)]
            ordered = sorted(flash, reverse=True)
        if not ordered:
            raise GeminiServiceError(
                "Your API key can't see any Gemini Flash model. Create a new key at "
                "aistudio.google.com/app/apikey, or set GEMINI_MODEL in .env to a model you have access to."
            )
    else:
        ordered = wanted  # listing failed (network/permission) -> just try the configured names

    _MODEL_CACHE[api_key] = ordered
    return ordered


# ---------------------------------------------------------------- Error handling
def _error_code(exc: Exception) -> Optional[int]:
    code = getattr(exc, "code", None)
    return code if isinstance(code, int) else None


def _friendly_error(exc: Exception) -> str:
    text = str(exc)
    low = text.lower()
    code = _error_code(exc)
    if "api key not valid" in low or "api_key_invalid" in low or code in (401, 403) or "permission" in low:
        return ("Google rejected the API key. Check GOOGLE_API_KEY in your .env file "
                "(create a new one at aistudio.google.com/app/apikey) and restart the app.")
    if code == 429 or "quota" in low or "resource_exhausted" in low or "rate limit" in low:
        return "The free-tier quota or rate limit was reached. Wait a minute and try again."
    if code in (500, 502, 503, 504) or "overloaded" in low or "unavailable" in low:
        return "Google's Gemini service is busy right now. Please try again in a moment."
    if "timed out" in low or "timeout" in low or "connect" in low or "network" in low:
        return "Could not reach Google. Check your internet connection and try again."
    if "safety" in low or "blocked" in low:
        return "Gemini declined to process this image. Try a different photo of the whiteboard."
    return f"Gemini request failed: {text[:300]}"


def _is_model_problem(exc: Exception) -> bool:
    """True when switching to another model could help (not found / quota / overloaded)."""
    code = _error_code(exc)
    low = str(exc).lower()
    return code in (404, 429, 500, 502, 503, 504) or "not found" in low or "no longer available" in low


def _build_config(model: str, schema, temperature: float, system_instruction: str):
    kwargs: Dict[str, Any] = dict(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=schema,
    )
    # Gemini 3 models work best at their default temperature; older models accept ours.
    if not model.startswith("gemini-3"):
        kwargs["temperature"] = temperature
    return types.GenerateContentConfig(**kwargs)


def _generate(client, model, contents, gen_config):
    """Single API call (kept separate so tests can replace it)."""
    return client.models.generate_content(model=model, contents=contents, config=gen_config)


def _call_gemini(client, api_key, contents, schema, temperature, system_instruction) -> Tuple[Any, str]:
    """Tries each usable model; retries once on malformed JSON; returns (parsed_object, model_used)."""
    models = resolve_models(client, api_key)
    failures: List[Tuple[str, Exception]] = []

    for model in models:
        gen_config = _build_config(model, schema, temperature, system_instruction)
        for attempt in range(2):
            try:
                response = _generate(client, model, contents, gen_config)
                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, schema):
                    return parsed, model
                text = (getattr(response, "text", None) or "").strip()
                if text:
                    return schema.model_validate_json(text), model
                raise ValueError("Gemini returned an empty response.")
            except genai_errors.APIError as exc:
                failures.append((model, exc))
                if _error_code(exc) in (500, 502, 503, 504) and attempt == 0:
                    time.sleep(1.5)  # brief pause, then one retry on the same model
                    continue
                break  # next model (or raise below)
            except ValueError as exc:  # bad / empty JSON -> retry once, then next model
                failures.append((model, exc))
                continue
            except Exception as exc:  # network etc.
                failures.append((model, exc))
                break

    if not failures:
        raise GeminiServiceError("Gemini returned no result. Please try again.")

    # If every failure was "model not found", say so clearly and tell the user what to change.
    if all(_error_code(e) == 404 or "not found" in str(e).lower() for _, e in failures if not isinstance(e, ValueError)) \
            and not any(isinstance(e, ValueError) for _, e in failures):
        tried = ", ".join(m for m, _ in failures)
        raise GeminiServiceError(
            f"None of these Gemini models are available to your API key: {tried}. "
            "Add a line like GEMINI_MODEL=gemini-3.6-flash to your .env file (see the model list at "
            "ai.google.dev/gemini-api/docs/models) and restart."
        )

    last_model, last_exc = failures[-1]
    if isinstance(last_exc, ValueError):
        raise GeminiServiceError("Gemini's answer could not be read as structured notes. Please try again.")
    raise GeminiServiceError(_friendly_error(last_exc))


# ---------------------------------------------------------------- Extraction
EXTRACTION_PROMPT = (
    "Carefully analyze this classroom whiteboard photo and extract all legible content into the schema:\n"
    "1. title: The main lecture topic or heading on the board.\n"
    "2. equations: Formulas as clean LaTeX WITHOUT $ delimiters (e.g. x(t) = A\\cos(\\omega t + \\phi)).\n"
    "3. key_terms: Defined vocabulary, variable definitions and concept explanations.\n"
    "4. diagram_notes: Descriptions of diagrams, axes, curves, tables or flowcharts.\n"
    "5. other_notes: Remarks, bullet points, reminders or other writing.\n"
    "6. confidence: For EACH item rate 'High', 'Medium' or 'Low'. If handwriting is blurry, faded, "
    "obstructed or ambiguous you MUST rate it Medium or Low and give the exact reason in confidence_reason.\n"
    "7. overall_legibility: 'High', 'Medium' or 'Low'; list unreadable_regions.\n"
    "8. suggested_questions: Exactly 3 starter questions about the board content.\n"
    "Never invent content that is not on the board."
)


def extract_whiteboard_content(image: Image.Image, api_key: str) -> Tuple[ExtractionOutput, str]:
    client = get_genai_client(api_key)
    image_part = prepare_image_payload(image)
    return _call_gemini(
        client, api_key, [image_part, EXTRACTION_PROMPT], ExtractionOutput,
        config.EXTRACTION_TEMPERATURE, config.SYSTEM_INSTRUCTION,
    )


# ---------------------------------------------------------------- Q&A
def answer_whiteboard_question(
    question: str,
    reviewed_notes_text: str,
    image: Optional[Image.Image],
    api_key: str,
    chat_history: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[QAOutput, str]:
    """Answers a question using the student's reviewed notes (+ the photo). `chat_history`
    must contain only PREVIOUS turns (not the current question)."""
    client = get_genai_client(api_key)

    history_snippet = ""
    if chat_history:
        recent = chat_history[-config.CHAT_HISTORY_TURNS:]
        history_snippet = "Recent conversation:\n" + "\n".join(
            f"- {m['role']}: {m['content']}" for m in recent
        ) + "\n\n"

    prompt = (
        f"{history_snippet}"
        "GROUND TRUTH (student-reviewed whiteboard notes; items marked '(unverified)' were not confirmed):\n"
        f'"""\n{reviewed_notes_text}\n"""\n\n'
        f'STUDENT QUESTION: "{question}"\n\n'
        "STRICT GROUNDING RULES:\n"
        "1. Base your answer solely on the notes and what is visible in the whiteboard photo.\n"
        "2. If the question is about something not on the board, set answerable_from_board = false and "
        "explain what is missing in missing_context. Do NOT guess or use outside facts.\n"
        "3. Give concrete evidence from the board and 1-3 short reasoning steps.\n"
        "4. Give a one-line how_to_verify tip pointing to where on the board the student can check this.\n"
        "5. confidence must be 'High', 'Medium' or 'Low'. Lower it if the evidence is unverified or unclear.\n"
        "6. Write math in LaTeX between $ signs."
    )

    contents: list = []
    if image is not None:
        contents.append(prepare_image_payload(image))
    contents.append(prompt)

    return _call_gemini(
        client, api_key, contents, QAOutput, config.QA_TEMPERATURE, config.SYSTEM_INSTRUCTION
    )


# ---------------------------------------------------------------- Notes helpers
def extraction_to_dict(extraction: ExtractionOutput) -> Dict[str, Any]:
    """Editable dict for session state. Every item starts UNCONFIRMED (human must verify)."""
    def note(n):
        return {"content": n.content.strip().strip("$").strip(), "confidence": n.confidence,
                "confidence_reason": n.confidence_reason, "is_confirmed": False}

    return {
        "title": extraction.title or "Whiteboard Notes",
        "equations": [note(e) for e in extraction.equations],
        "key_terms": [
            {"term": t.term, "definition": t.definition, "confidence": t.confidence,
             "confidence_reason": t.confidence_reason, "is_confirmed": False}
            for t in extraction.key_terms
        ],
        "diagram_notes": [note(d) for d in extraction.diagram_notes],
        "other_notes": [note(o) for o in extraction.other_notes],
        "overall_legibility": extraction.overall_legibility or "Medium",
        "unreadable_regions": list(extraction.unreadable_regions or []),
        "suggested_questions": list(extraction.suggested_questions or [])[:3],
    }


def iter_items(notes: Dict[str, Any]):
    """Yields every reviewable item (equations, terms, diagrams, other notes)."""
    for section in ("equations", "key_terms", "diagram_notes", "other_notes"):
        for item in notes.get(section, []):
            yield item


def needs_review(item: Dict[str, Any]) -> bool:
    return item.get("confidence") in ("Medium", "Low") and not item.get("is_confirmed")


def notes_stats(notes: Dict[str, Any]) -> Tuple[int, int, int]:
    """(total, confirmed, needs_review)."""
    items = list(iter_items(notes))
    return len(items), sum(1 for i in items if i.get("is_confirmed")), sum(1 for i in items if needs_review(i))


def format_notes_to_markdown(notes: Dict[str, Any], mark_unverified: bool = False) -> str:
    """Notes as Markdown. With mark_unverified=True, unconfirmed items get an '(unverified)' tag."""
    def tag(item):
        return " *(unverified)*" if mark_unverified and not item.get("is_confirmed") else ""

    lines = [f"# {notes.get('title') or 'Whiteboard Notes'}", ""]

    if notes.get("equations"):
        lines.append("## Equations")
        for eq in notes["equations"]:
            c = eq.get("content", "").strip()
            if c.startswith("$$") and c.endswith("$$"):
                c = c[2:-2].strip()
            lines += [f"$$\n{c}\n$$", tag(eq).strip(), ""]
    if notes.get("key_terms"):
        lines.append("## Key Terms & Definitions")
        for t in notes["key_terms"]:
            lines.append(f"- **{t.get('term', '').strip()}**: {t.get('definition', '').strip()}{tag(t)}")
        lines.append("")
    if notes.get("diagram_notes"):
        lines.append("## Diagrams")
        for d in notes["diagram_notes"]:
            lines.append(f"- {d.get('content', '').strip()}{tag(d)}")
        lines.append("")
    if notes.get("other_notes"):
        lines.append("## Other Notes")
        for o in notes["other_notes"]:
            lines.append(f"- {o.get('content', '').strip()}{tag(o)}")
        lines.append("")
    return "\n".join(l for i, l in enumerate(lines) if l != "" or (i and lines[i - 1] != "")).strip() + "\n"
