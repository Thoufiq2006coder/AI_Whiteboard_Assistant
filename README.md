# 📝 BoardWise AI: AI Whiteboard Companion

A Human-AI Interaction (HAI) project. The student uploads a photo of a classroom whiteboard, Google Gemini turns it into
organized notes, the student **reviews and corrects** them, then asks questions that are answered **from the board**.

## Run it

```bash
pip install -r requirements.txt
# put your key in .env:   GOOGLE_API_KEY=your_key_here
python -m streamlit run app.py
python tests/test_parsing.py                   # optional: unit tests, no API calls
```

## One-page flow
1. **Upload**: drop a whiteboard photo; "What it does well / Where it struggles" is shown first.
2. **Extract**: live progress checklist while Gemini reads the board.
3. **Review**: photo on the left; **Notes** | **Q&A** switch on the right. Flagged items are amber with a *Why flagged* reason.
   Tick *I checked this against the board* to confirm (green). **Save notes** locks in the ground truth.
4. **Ask**: suggested questions + free chat. Each answer has a confidence label, *Why this answer?* (evidence + steps) and *How to verify*.
5. **Export** the notes as Markdown at any time.

## Models
Google retires models often (`gemini-2.0-flash` was shut down in June 2026, `gemini-2.5-flash` is being retired).
The app therefore asks your API key which models it can use and tries, in order: `GEMINI_MODEL` from `.env`, then
`MODEL_CANDIDATES` in `config.py` (currently `gemini-3.6-flash` first). If a model fails with *not found*, *quota* or
*busy*, it automatically tries the next one. To force one model, add `GEMINI_MODEL=...` to `.env`.

## HAI concepts → where they are in the app
| Concept (lecture) | Implementation |
| :-- | :-- |
| Setting expectations (L11) | Capabilities / limitations cards and photo tips before upload; "What this AI can't do" in the sidebar |
| Calibrated trust (L6) | High/Medium/Low labels; nothing is pre-confirmed; green check only after the student confirms |
| Human-in-the-loop & correction (L4, L8) | Every note is editable; saved notes are the ground truth for Q&A |
| Communicating uncertainty (L7) | Amber flagged items, *Why flagged*, board legibility, unclear regions, "not on the board" and "low confidence" banners |
| Explanations (L12) | *Why this answer?*: evidence + reasoning steps, plus *How to verify* |
| Mixed initiative (L4) | AI proposes starter questions from the board content |
| Error recovery (L7) | Friendly errors with a next step (bad key, wrong model, quota, busy, unreadable file); failed questions can simply be asked again |
| Accurate mental model (L5) | States it is an AI, neutral tone, no simulated emotions |

## Files
`app.py` UI & entry point · `gemini_service.py` Gemini calls, model selection, error handling · `schemas.py` structured output ·
`styles.py` CSS · `config.py` settings and HAI text · `tests/` unit tests
