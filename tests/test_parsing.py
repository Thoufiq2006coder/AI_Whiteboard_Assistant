"""Unit tests for BoardWise AI (no real network / API calls).  Run:  python tests/test_parsing.py"""

import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import AI_Whiteboard_Assistant.config
import AI_Whiteboard_Assistant.gemini_service as gs
from google.genai import errors as genai_errors
from AI_Whiteboard_Assistant.schemas import ExtractionOutput, NoteItem, QAOutput, TermItem, normalize_level

KEY = "AIzaSyDUMMYKEYFORTESTING123456789"


def api_error(code, msg="x"):
    return genai_errors.APIError(code, {"error": {"code": code, "message": msg, "status": "X"}})


def fake_client(models):
    """Client whose models.list() returns the given names."""
    lst = [SimpleNamespace(name=f"models/{m}", supported_actions=["generateContent"]) for m in models]
    return SimpleNamespace(models=SimpleNamespace(list=lambda: lst))


def reset_cache():
    gs._MODEL_CACHE.clear()


# ---------------------------------------------------------------- config / schema
def test_api_key_validation():
    assert not config.is_api_key_valid("")
    assert not config.is_api_key_valid("PASTE_YOUR_KEY_HERE")
    assert not config.is_api_key_valid("short")
    assert config.is_api_key_valid(KEY)


def test_confidence_normalisation():
    assert normalize_level("high") == "High"
    assert normalize_level("Medium confidence") == "Medium"
    assert normalize_level("LOW") == "Low"
    assert normalize_level(None) == "Medium"
    assert NoteItem(content="x", confidence="low").confidence == "Low"
    assert TermItem(term="a", definition="b", confidence="HIGH").confidence == "High"


def test_no_dead_models_in_candidates():
    assert "gemini-2.0-flash" not in config.MODEL_CANDIDATES


# ---------------------------------------------------------------- image
def test_image_payload_handles_modes_and_resizes():
    for mode in ("RGB", "RGBA", "P", "L"):
        part = gs.prepare_image_payload(Image.new(mode, (3200, 1800)))
        assert part.inline_data.mime_type == "image/jpeg"
        out = Image.open(__import__("io").BytesIO(part.inline_data.data))
        assert max(out.size) == config.IMAGE_MAX_DIMENSION


# ---------------------------------------------------------------- model resolution
def test_resolve_prefers_candidates_that_exist():
    reset_cache()
    c = fake_client(["gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash-tts"])
    assert gs.resolve_models(c, "k1")[0] == "gemini-3.6-flash"


def test_resolve_skips_retired_models_and_falls_back_to_any_flash():
    reset_cache()
    c = fake_client(["gemini-9.9-flash", "gemini-9.9-flash-image", "gemini-9.9-pro"])
    assert gs.resolve_models(c, "k2") == ["gemini-9.9-flash"]


def test_resolve_uses_env_override(monkeypatch_env=None):
    reset_cache()
    import os
    os.environ["GEMINI_MODEL"] = "gemini-3.5-flash-lite"
    try:
        c = fake_client(["gemini-3.6-flash", "gemini-3.5-flash-lite"])
        assert gs.resolve_models(c, "k3")[0] == "gemini-3.5-flash-lite"
    finally:
        del os.environ["GEMINI_MODEL"]


# ---------------------------------------------------------------- calling with fallbacks
def _run(side_effects, models=("gemini-a-flash", "gemini-b-flash")):
    """Runs _call_gemini where each model name maps to a result or an exception."""
    reset_cache()
    gs._MODEL_CACHE["kk"] = list(models)
    calls = []

    def fake_generate(client, model, contents, cfg):
        calls.append(model)
        r = side_effects[model]
        if isinstance(r, Exception):
            raise r
        return r

    orig = gs._generate
    gs._generate = fake_generate
    try:
        return gs._call_gemini(object(), "kk", ["x"], QAOutput, 0.2, "sys"), calls
    finally:
        gs._generate = orig


GOOD = QAOutput(answer="a", confidence="High", answerable_from_board=True, how_to_verify="v")


def test_falls_back_when_first_model_404():
    (res, used), calls = _run({"gemini-a-flash": api_error(404, "not found"),
                               "gemini-b-flash": SimpleNamespace(parsed=GOOD, text="")})
    assert used == "gemini-b-flash" and calls == ["gemini-a-flash", "gemini-b-flash"]


def test_falls_back_on_quota_for_first_model():
    (res, used), _ = _run({"gemini-a-flash": api_error(429, "quota"),
                           "gemini-b-flash": SimpleNamespace(parsed=GOOD, text="")})
    assert used == "gemini-b-flash"


def test_parses_text_when_parsed_missing():
    (res, used), _ = _run({"gemini-a-flash": SimpleNamespace(parsed=None, text=GOOD.model_dump_json()),
                           "gemini-b-flash": None})
    assert res.answer == "a" and used == "gemini-a-flash"


def test_all_models_404_gives_actionable_message():
    try:
        _run({"gemini-a-flash": api_error(404, "not found"), "gemini-b-flash": api_error(404, "not found")})
        assert False
    except gs.GeminiServiceError as e:
        assert "GEMINI_MODEL" in str(e) and "gemini-a-flash" in str(e)


def test_bad_key_message():
    try:
        _run({"gemini-a-flash": api_error(400, "API key not valid. Please pass a valid API key."),
              "gemini-b-flash": api_error(400, "API key not valid. Please pass a valid API key.")})
        assert False
    except gs.GeminiServiceError as e:
        assert "API key" in str(e) and ".env" in str(e)


def test_gemini3_gets_no_temperature():
    assert gs._build_config("gemini-3.6-flash", QAOutput, 0.2, "s").temperature is None
    assert gs._build_config("gemini-2.5-flash", QAOutput, 0.2, "s").temperature == 0.2


# ---------------------------------------------------------------- notes
def _extraction():
    return ExtractionOutput(
        title="SHM", overall_legibility="medium",
        equations=[NoteItem(content="$x=A\\cos t$", confidence="High"),
                   NoteItem(content="T=2\\pi/\\omega", confidence="low", confidence_reason="faint")],
        key_terms=[TermItem(term="A", definition="Amplitude", confidence="High")],
        suggested_questions=["q1", "q2", "q3", "q4"],
    )


def test_extraction_dict_starts_unconfirmed_and_strips_dollars():
    d = gs.extraction_to_dict(_extraction())
    assert all(not i["is_confirmed"] for i in gs.iter_items(d))
    assert d["equations"][0]["content"] == "x=A\\cos t"
    assert len(d["suggested_questions"]) == 3
    assert gs.notes_stats(d) == (3, 0, 1)


def test_markdown_marks_unverified():
    d = gs.extraction_to_dict(_extraction())
    d["key_terms"][0]["is_confirmed"] = True
    md = gs.format_notes_to_markdown(d, mark_unverified=True)
    assert "# SHM" in md and "$$\nx=A\\cos t\n$$" in md and "*(unverified)*" in md
    assert "Amplitude *(unverified)*" not in md  # confirmed term is not tagged
    assert "unverified" not in gs.format_notes_to_markdown(d)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    print("Running BoardWise AI test suite...")
    for name, fn in tests:
        fn()
        print(f"  ok  {name}")
    print(f"All {len(tests)} tests passed.")
