"""BoardWise AI - AI Whiteboard Companion (single-page Streamlit app).

Human-AI Interaction concepts demonstrated:
- Setting expectations & limitations (L11)      - Calibrated / appropriate trust (L6)
- Human-in-the-loop & correction (L4, L8)       - Communicating uncertainty & errors (L7)
- Explanations: evidence + reasoning (L12)      - Mixed initiative: suggested questions (L4)
- Accurate mental model: AI identity, neutral tone (L5)
"""

import copy
import re

import streamlit as st

import config
import gemini_service
import styles

# ---------------------------------------------------------------- Page config
st.set_page_config(
    page_title=f"{config.APP_NAME} - {config.APP_TITLE}",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)
styles.apply_custom_styles()

# ---------------------------------------------------------------- API key gate
api_key = config.get_api_key()
if not config.is_api_key_valid(api_key):
    styles.render_missing_key_screen()
    st.stop()

# ---------------------------------------------------------------- Session state
VIEW_NOTES, VIEW_QA = "📝 Notes", "💬 Q&A"
SECTIONS = ("equations", "key_terms", "diagram_notes", "other_notes")

DEFAULTS = {
    "board_id": 0,            # changes for every new board so old widget values never leak in
    "uploader_key": 0,        # changes on "New whiteboard" so the file box is really emptied
    "file_sig": None,
    "raw_image": None,
    "notes": None,
    "saved_notes": None,
    "chat_history": [],
    "filter_review": False,
    "extract_error": None,
    "queued_query": None,
    "view": VIEW_NOTES,
    "view_last": VIEW_NOTES,
}
for _k, _v in DEFAULTS.items():
    st.session_state.setdefault(_k, copy.deepcopy(_v))


# ---------------------------------------------------------------- Callbacks (run BEFORE the script reruns)
def reset_board():
    """Clears everything for a fresh whiteboard (including the file uploader and all widget values)."""
    st.session_state.uploader_key += 1
    st.session_state.board_id += 1
    for key, value in DEFAULTS.items():
        if key not in ("board_id", "uploader_key"):
            st.session_state[key] = copy.deepcopy(value)


def sync_field(section, idx, field, widget_key):
    """Copies an edited widget value into the notes dictionary."""
    st.session_state.notes[section][idx][field] = st.session_state[widget_key]


def confirm_all_high():
    bid = st.session_state.board_id
    for section in SECTIONS:
        for idx, item in enumerate(st.session_state.notes[section]):
            if item.get("confidence") == "High":
                item["is_confirmed"] = True
                st.session_state[f"chk_{bid}_{section}_{idx}"] = True  # keep the checkbox in sync


def save_notes():
    st.session_state.saved_notes = copy.deepcopy(st.session_state.notes)
    st.toast("Notes saved. Questions will now use these notes.", icon="✅")


def go_to_qa():
    st.session_state.view = VIEW_QA


def queue_question(question):
    st.session_state.queued_query = question


def set_feedback(msg_idx, value):
    st.session_state.chat_history[msg_idx]["feedback"] = value


def clear_chat():
    st.session_state.chat_history = []


# ---------------------------------------------------------------- Sidebar
with st.sidebar:
    st.markdown(f"<div class='bw-brand'>📝 {config.APP_NAME}</div>"
                f"<div class='bw-brand-sub'>{config.APP_TITLE} · Human-AI Interaction project</div>",
                unsafe_allow_html=True)
    st.button("New whiteboard", icon=":material/add_photo_alternate:", on_click=reset_board,
              width="stretch", type="primary" if st.session_state.notes else "secondary")

    st.markdown("<div class='bw-side-title'>What this AI can't do</div>", unsafe_allow_html=True)
    for limitation in config.WHAT_IT_CANT_DO:
        st.markdown(f"<div class='bw-side-item'>{styles.esc(limitation)}</div>", unsafe_allow_html=True)

    st.write("")
    with st.expander("🎓 HAI design in this app"):
        for p in config.HAI_PRINCIPLES:
            st.markdown(f"**{p['title']}**")
            st.caption(p["description"])


# ================================================================= UPLOAD SCREEN
def render_progress(placeholder, stage: int, percent: int):
    """Honest progress checklist: `stage` = index of the step currently running (4 = all done)."""
    labels = ["Image uploaded", "Extracting content", "Organizing notes", "Preparing Q&A"]
    rows = []
    for i, label in enumerate(labels):
        cls = "done" if i < stage else ("active" if i == stage else "")
        dot = "✓" if i < stage else ""
        rows.append(f"<div class='bw-step {cls}'><span class='bw-dot'>{dot}</span>{label}</div>")
    with placeholder.container(border=True):
        st.markdown("**Analyzing your whiteboard…**")
        st.markdown(f"<div class='bw-steps'>{''.join(rows)}</div>", unsafe_allow_html=True)
        st.progress(percent, text=f"{percent}%")


def run_extraction(placeholder):
    """Real extraction with live progress. Returns True on success."""
    st.session_state.extract_error = None
    try:
        render_progress(placeholder, 1, 20)
        extraction, _model = gemini_service.extract_whiteboard_content(st.session_state.raw_image, api_key)
        render_progress(placeholder, 2, 70)
        notes = gemini_service.extraction_to_dict(extraction)
        render_progress(placeholder, 3, 90)
        st.session_state.board_id += 1
        st.session_state.notes = notes
        st.session_state.saved_notes = None
        st.session_state.chat_history = []
        st.session_state.view = VIEW_NOTES
        render_progress(placeholder, 4, 100)
        return True
    except gemini_service.GeminiServiceError as exc:
        st.session_state.extract_error = str(exc)
    except Exception as exc:  # unexpected: still show something actionable
        st.session_state.extract_error = f"Something went wrong while reading the photo: {exc}"
    placeholder.empty()
    return False


def render_upload_screen():
    st.markdown(
        f"<div class='bw-hero'><div class='bw-title'>AI <span>Whiteboard</span> Companion</div><p>{config.APP_SUBTITLE}</p></div>",
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([0.1, 0.8, 0.1])
    with mid:
        with st.container(border=True):
            uploaded = st.file_uploader(
                "Upload whiteboard image (drag and drop or click to choose a file)",
                type=["png", "jpg", "jpeg", "webp"],
                key=f"uploader_{st.session_state.uploader_key}",
            )
            if uploaded is not None:
                sig = (uploaded.name, uploaded.size)
                if st.session_state.file_sig != sig:
                    try:
                        st.session_state.raw_image = gemini_service.load_uploaded_image(uploaded)
                        st.session_state.file_sig = sig
                        st.session_state.extract_error = None
                    except Exception:
                        st.session_state.raw_image = None
                        st.session_state.file_sig = None
                        st.session_state.extract_error = (
                            "That file could not be opened as an image. Please upload a PNG, JPG or WEBP photo."
                        )
            else:
                st.session_state.raw_image = None
                st.session_state.file_sig = None

            if st.session_state.raw_image is not None:
                progress_slot = st.empty()  # progress checklist appears here, above the photo
                st.image(st.session_state.raw_image, caption="Whiteboard preview", width="stretch")
                if st.button("Extract notes", type="primary", width="stretch",
                             icon=":material/auto_awesome:", key="extract_btn"):
                    if run_extraction(progress_slot):
                        st.rerun()

            if st.session_state.extract_error:
                st.error(st.session_state.extract_error)
                if st.session_state.raw_image is not None:
                    st.caption("Fix the problem above, then press **Extract notes** again.")

    # Setting expectations (L11)
    st.write("")
    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(border=True):
        st.markdown("#### ✅ What it does well")
        st.markdown(
            "- Reads clear handwritten and printed whiteboard text\n"
            "- Writes equations as clean LaTeX\n"
            "- Extracts key terms, variables and definitions\n"
            "- Describes diagrams, graphs and tables"
        )
    with c2, st.container(border=True):
        st.markdown("#### ⚠️ Where it struggles")
        st.markdown(
            "- Blurry photos, low light or sharp camera angles\n"
            "- Faint or partly erased marker writing\n"
            "- Equations cut off at the edge or hidden by glare\n"
            "- It can misread handwriting, so you review everything"
        )
    st.caption("**Photo tips:** good lighting, shoot straight-on, keep the whole board in frame, avoid glare.")


# ================================================================= NOTES VIEW
def _header(label, item):
    why = ""
    if item.get("confidence") in ("Medium", "Low") and not item.get("is_confirmed") and item.get("confidence_reason"):
        why = f"<div class='bw-why'><strong>Why flagged:</strong> {styles.esc(item['confidence_reason'])}</div>"
    st.markdown(
        f"<div class='bw-row'><span class='bw-label'>{styles.esc(label)}</span>{styles.status_pill(item)}</div>{why}",
        unsafe_allow_html=True,
    )


def _text_widget(kind, label, section, idx, field, item, **kwargs):
    """Edit widget bound to notes[section][idx][field] through a callback (no stale values)."""
    bid = st.session_state.board_id
    key = f"{kind}_{bid}_{section}_{idx}_{field}"
    st.session_state.setdefault(key, item.get(field, ""))
    fn = st.text_input if kind == "ti" else st.text_area
    fn(label, key=key, on_change=sync_field, args=(section, idx, field, key),
       label_visibility="collapsed", **kwargs)


def render_section(title, section, singular, kind, show_only_review):
    notes = st.session_state.notes
    bid = st.session_state.board_id
    entries = [(i, it) for i, it in enumerate(notes[section])
               if not show_only_review or gemini_service.needs_review(it)]
    if not entries:
        return
    st.markdown(f"#### {title}")
    for idx, item in entries:
        state = "ok" if item.get("is_confirmed") else ("flag" if item.get("confidence") in ("Medium", "Low") else "item")
        with st.container(border=True, key=f"{state}_{bid}_{section}_{idx}"):
            _header(f"{singular} {idx + 1}", item)

            if kind == "equation":
                if item.get("content", "").strip():
                    st.latex(item["content"])
                _text_widget("ti", f"LaTeX for equation {idx + 1}", section, idx, "content", item)
            elif kind == "term":
                _text_widget("ti", f"Term {idx + 1}", section, idx, "term", item)
                _text_widget("ta", f"Definition {idx + 1}", section, idx, "definition", item, height=80)
            else:
                _text_widget("ta", f"{singular} {idx + 1}", section, idx, "content", item, height=80)

            ck = f"chk_{bid}_{section}_{idx}"
            st.session_state.setdefault(ck, bool(item.get("is_confirmed")))
            st.checkbox("I checked this against the board", key=ck,
                        on_change=sync_field, args=(section, idx, "is_confirmed", ck))


def render_notes_view():
    notes = st.session_state.notes
    total, confirmed, review = gemini_service.notes_stats(notes)

    if review:
        styles.banner("amber", f"⚠️ <strong>{review} item{'s' if review != 1 else ''} need{'' if review != 1 else 's'} "
                               f"your review.</strong> Check them against the photo, edit if needed, then tick the box.")
    elif total:
        styles.banner("green", "All flagged items have been reviewed. Confirm the rest, then save your notes.")

    st.markdown(f"**{total} items · {confirmed} confirmed · {review} need review**")
    st.progress(confirmed / total if total else 1.0)

    c1, c2 = st.columns([0.5, 0.5])
    with c1:
        st.toggle("Show only items that need review", key="filter_review")
    with c2:
        st.button("Confirm all high-confidence", on_click=confirm_all_high, width="stretch",
                  disabled=not any(i.get("confidence") == "High" and not i.get("is_confirmed")
                                   for i in gemini_service.iter_items(notes)))

    show_only_review = st.session_state.filter_review
    with st.container(height=560, border=True):
        st.markdown("#### Lecture title")
        title_key = f"title_{st.session_state.board_id}"
        st.session_state.setdefault(title_key, notes.get("title", ""))
        st.text_input("Lecture title", key=title_key, label_visibility="collapsed",
                      on_change=lambda k=title_key: notes.__setitem__("title", st.session_state[k]))

        render_section("Equations", "equations", "Equation", "equation", show_only_review)
        render_section("Key terms", "key_terms", "Term", "term", show_only_review)
        render_section("Diagrams", "diagram_notes", "Diagram note", "text", show_only_review)
        render_section("Other notes", "other_notes", "Note", "text", show_only_review)

        if show_only_review and not review:
            st.success("Nothing left to review.")
        if total == 0:
            st.info("No readable content was found. Try a clearer, closer photo.")

    b1, b2 = st.columns(2)
    with b1:
        st.button("Save notes", icon=":material/save:", on_click=save_notes, width="stretch")
    with b2:
        st.button("Ask questions", type="primary", icon=":material/arrow_forward:",
                  on_click=go_to_qa, width="stretch")


# ================================================================= Q&A VIEW
def render_assistant_message(msg, idx):
    if msg.get("error"):
        styles.banner("red", f"<strong>Could not answer.</strong> {styles.esc(msg['error'])}<br>"
                             "You can ask again or rephrase the question.")
        return

    conf = msg.get("confidence", "Medium")
    st.markdown(styles.pill(conf), unsafe_allow_html=True)
    if not msg.get("answerable_from_board", True):
        styles.banner("amber", "<strong>Not on the board:</strong> this question can't be answered from the whiteboard alone."
                               + (f"<br>Missing: {styles.esc(msg['missing_context'])}" if msg.get("missing_context") else ""))
    if conf == "Low":
        styles.banner("red", "⚠️ <strong>Low confidence.</strong> The board is unclear for this question. "
                             "Verify with your textbook or teacher before relying on it.")

    st.markdown(msg["content"])

    if msg.get("evidence") or msg.get("reasoning_steps"):
        with st.expander("Why this answer?"):
            if msg.get("evidence"):
                st.markdown("**Evidence from the whiteboard**")
                for ev in msg["evidence"]:
                    st.markdown(f"- {ev}")
            if msg.get("reasoning_steps"):
                st.markdown("**Reasoning steps**")
                for n, step in enumerate(msg["reasoning_steps"], 1):
                    st.markdown(f"{n}. {step}")
    if msg.get("how_to_verify"):
        st.caption(f"**How to verify:** {msg['how_to_verify']}")

    if msg.get("feedback"):
        st.caption("Thanks for the feedback.")
    else:
        f1, f2, _ = st.columns([0.3, 0.34, 0.36])
        f1.button("Helpful", key=f"fb_up_{st.session_state.board_id}_{idx}", icon=":material/thumb_up:",
                  on_click=set_feedback, args=(idx, "helpful"))
        f2.button("Not helpful", key=f"fb_dn_{st.session_state.board_id}_{idx}", icon=":material/thumb_down:",
                  on_click=set_feedback, args=(idx, "not_helpful"))


def render_qa_view():
    notes = st.session_state.notes
    saved = st.session_state.saved_notes
    qa_notes = saved if saved is not None else notes

    # Which notes are the "ground truth" (L6: be transparent about it)
    _, confirmed, _ = gemini_service.notes_stats(qa_notes)
    total = gemini_service.notes_stats(qa_notes)[0]
    if saved is None:
        styles.banner("blue", "Answers use your <strong>current notes</strong>. Press <em>Save notes</em> in the Notes view to lock them in.")
    elif saved != notes:
        styles.banner("amber", "You edited the notes after saving. Answers still use the <strong>last saved version</strong>.")
    if confirmed < total:
        styles.banner("amber", f"<strong>Notice:</strong> {total - confirmed} of {total} notes are unconfirmed. "
                               "Answers may rely on handwriting the AI misread.")

    head, clear = st.columns([0.7, 0.3])
    head.caption("Ask about the whiteboard. Answers are grounded in your notes and the photo. This is an AI, so verify important answers.")
    clear.button("Clear chat", icon=":material/delete:", on_click=clear_chat, width="stretch",
                 disabled=not st.session_state.chat_history)

    # Mixed initiative: AI suggests starter questions
    starters = notes.get("suggested_questions", [])
    if not st.session_state.chat_history and starters:
        st.markdown("**Suggested questions**")
        for n, q in enumerate(starters[:3]):
            st.button(q, key=f"starter_{st.session_state.board_id}_{n}", on_click=queue_question, args=(q,),
                      width="stretch")

    history_box = st.container()
    typed = st.chat_input("Ask a question about the whiteboard…")
    question = typed or st.session_state.queued_query
    st.session_state.queued_query = None

    if question and question.strip():
        previous = [{"role": m["role"], "content": m["content"]}
                    for m in st.session_state.chat_history if not m.get("error")]
        st.session_state.chat_history.append({"role": "user", "content": question.strip()})

        with history_box:
            for m in st.session_state.chat_history:
                with st.chat_message(m["role"], avatar=None if m["role"] == "user" else "✨"):
                    st.markdown(m["content"])
            with st.chat_message("assistant", avatar="✨"):
                with st.spinner("Reading the board and reasoning…"):
                    try:
                        out, _model = gemini_service.answer_whiteboard_question(
                            question=question.strip(),
                            reviewed_notes_text=gemini_service.format_notes_to_markdown(qa_notes, mark_unverified=True),
                            image=st.session_state.raw_image,
                            api_key=api_key,
                            chat_history=previous,
                        )
                        reply = {
                            "role": "assistant", "content": out.answer, "confidence": out.confidence,
                            "answerable_from_board": out.answerable_from_board,
                            "missing_context": out.missing_context, "evidence": out.evidence,
                            "reasoning_steps": out.reasoning_steps, "how_to_verify": out.how_to_verify,
                        }
                    except gemini_service.GeminiServiceError as exc:
                        reply = {"role": "assistant", "content": "", "error": str(exc)}
                    except Exception as exc:
                        reply = {"role": "assistant", "content": "", "error": f"Unexpected error: {exc}"}
        st.session_state.chat_history.append(reply)
        st.rerun()

    with history_box:
        if not st.session_state.chat_history:
            st.caption("No questions yet.")
        for idx, m in enumerate(st.session_state.chat_history):
            if m["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(m["content"])
            else:
                with st.chat_message("assistant", avatar="✨"):
                    render_assistant_message(m, idx)


# ================================================================= WORKSPACE (after extraction)
def render_workspace():
    notes = st.session_state.notes
    col_img, col_main = st.columns([0.42, 0.58], gap="large")

    with col_img:
        st.markdown("#### Whiteboard photo")
        if st.session_state.raw_image is not None:
            st.image(st.session_state.raw_image, caption="Your uploaded whiteboard", width="stretch")

        legibility = notes.get("overall_legibility", "Medium")
        with st.container(border=True):
            st.markdown(f"<div class='bw-row'><span class='bw-label'>Board legibility</span>"
                        f"{styles.pill(legibility, 'legibility')}</div>", unsafe_allow_html=True)
            if legibility == "Low":
                st.caption("The handwriting is hard to read. Double-check flagged items carefully.")
            if notes.get("unreadable_regions"):
                st.markdown(
                    "<p class='bw-why' style='margin-top:8px'><strong>Unclear regions:</strong> "
                    + styles.esc("; ".join(notes["unreadable_regions"])) + "</p>",
                    unsafe_allow_html=True,
                )

    with col_main:
        top_l, top_r = st.columns([0.62, 0.38])
        with top_l:
            choice = st.segmented_control("View", [VIEW_NOTES, VIEW_QA], key="view", label_visibility="collapsed")
        view = choice or st.session_state.view_last  # clicking the active option can return None
        st.session_state.view_last = view

        with top_r:
            safe = re.sub(r"[^A-Za-z0-9]+", "_", notes.get("title") or "whiteboard_notes").strip("_").lower() or "whiteboard_notes"
            st.download_button(
                "Export notes", data=gemini_service.format_notes_to_markdown(notes, mark_unverified=True),
                file_name=f"{safe}.md", mime="text/markdown", icon=":material/download:", width="stretch",
            )

        if view == VIEW_QA:
            render_qa_view()
        else:
            render_notes_view()


# ================================================================= Bottom info (as in the mockup)
def render_info_tiles():
    st.write("")
    left, right = st.columns([0.5, 0.5], gap="medium")
    with left, st.container(border=True):
        tiles = "".join(
            f"<div class='bw-tile center'><div class='ic'>{ic}</div><div class='t'>{styles.esc(t)}</div></div>"
            for ic, t in config.KEY_FEATURES
        )
        st.markdown(f"<div class='bw-sec-title'>Key Features</div><div class='bw-tiles f5'>{tiles}</div>",
                    unsafe_allow_html=True)
    with right, st.container(border=True):
        tiles = "".join(
            f"<div class='bw-tile'><div class='ic'>{ic}</div><div class='t'>{styles.esc(t)}</div>"
            f"<div class='d'>{styles.esc(d)}</div></div>"
            for ic, t, d in config.HAI_CONCEPTS_APPLIED
        )
        st.markdown(f"<div class='bw-sec-title'>HAI Concepts Applied</div><div class='bw-tiles f3'>{tiles}</div>",
                    unsafe_allow_html=True)


# ================================================================= Router
if st.session_state.notes is None:
    render_upload_screen()
else:
    render_workspace()
render_info_tiles()
