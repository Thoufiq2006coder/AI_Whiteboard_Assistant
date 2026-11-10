"""Custom styling and small HTML renderers for BoardWise AI."""

import html
import streamlit as st

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ---------- Font -------------------------------------------------------------
   IMPORTANT: Inter is set on the app root only and inherited. The old version forced
   `font-family: Inter !important` on every span/div/button, which also replaced the
   Material icon font, so icon NAMES (e.g. "auto_read_play", "error") were printed as text
   on top of the labels. The rule below protects the icon font explicitly. */
.stApp { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

[data-testid="stIconMaterial"],
.material-icons, .material-symbols-rounded, .material-symbols-outlined,
span[class*="material-symbols"] {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
    font-feature-settings: 'liga' !important;
    -webkit-font-feature-settings: 'liga' !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    overflow: hidden;
}

/* ---------- Streamlit chrome ---------- */
#MainMenu, footer, .stDeployButton, [data-testid="stDecoration"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent; }

.stApp { background: #F5F6FC; }
.block-container {
    max-width: 1240px !important;
    padding-top: 1.4rem !important;
    padding-bottom: 2.5rem !important;
}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E6E8F0; }
[data-testid="stSidebar"] .block-container { padding-top: 1rem !important; }
.bw-brand { font-size: 1.05rem; font-weight: 700; color: #1E202C; display: flex; align-items: center; gap: 8px; }
.bw-brand-sub { font-size: .78rem; color: #6B7185; margin: 2px 0 12px 0; }
.bw-side-title { font-size: .8rem; font-weight: 700; color: #1E202C; text-transform: uppercase;
                 letter-spacing: .05em; margin: 14px 0 6px 0; }
.bw-side-item { font-size: .84rem; color: #4A5068; line-height: 1.45; margin-bottom: 6px; padding-left: 14px;
                position: relative; }
.bw-side-item::before { content: "•"; position: absolute; left: 2px; color: #5B4BDB; }

/* ---------- Typography ---------- */
h1, h2, h3, h4 { color: #1E202C !important; letter-spacing: -0.01em; }
h4 { font-size: 1.02rem !important; font-weight: 600 !important; margin: .4rem 0 .35rem 0 !important; }

.bw-hero { text-align: center; margin: .6rem 0 1.4rem 0; }
.bw-hero .bw-title { font-size: 2.3rem; font-weight: 800; margin: 0 0 .35rem 0; color: #1E202C; letter-spacing: -0.02em; }
.bw-hero .bw-title span { color: #5B4BDB; }
.bw-hero p { color: #5F6475; font-size: 1.02rem; margin: 0; }

/* ---------- Bordered containers = cards ---------- */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {
    border-radius: 14px;
}
div[data-testid="stVerticalBlockBorderWrapper"] { border-color: #E3E6F1; background: #FFFFFF; }

/* Flagged (Medium/Low, not yet confirmed) item = amber, confirmed = green accent */
[class*="st-key-flag_"] { border: 1px solid #FCD9A0 !important; border-left: 4px solid #F59E0B !important;
                          background: #FFFBF2 !important; border-radius: 12px !important; }
[class*="st-key-ok_"]   { border: 1px solid #BFE8D2 !important; border-left: 4px solid #16A34A !important;
                          border-radius: 12px !important; }
[class*="st-key-item_"] { border-radius: 12px !important; }

/* ---------- Pills / banners ---------- */
.bw-pill { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px; font-size: .74rem;
           font-weight: 600; border-radius: 20px; line-height: 1.5; white-space: nowrap; }
.bw-pill-high   { background: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; }
.bw-pill-medium { background: #FEF3C7; color: #B45309; border: 1px solid #FDE68A; }
.bw-pill-low    { background: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA; }
.bw-pill-ok     { background: #DCFCE7; color: #15803D; border: 1px solid #86EFAC; }

.bw-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.bw-label { font-size: .84rem; font-weight: 600; color: #1E202C; }
.bw-why, p.bw-why { color: #B45309; font-size: .8rem !important; margin: 4px 0 2px 0; }

.bw-banner { padding: 10px 14px; border-radius: 10px; font-size: .88rem; font-weight: 500; margin: 6px 0 10px 0;
             border: 1px solid; }
.bw-banner-amber { background: #FFF7E6; border-color: #FCD9A0; color: #92400E; }
.bw-banner-green { background: #ECFDF5; border-color: #A7F3D0; color: #065F46; }
.bw-banner-red   { background: #FEF2F2; border-color: #FECACA; color: #991B1B; }
.bw-banner-blue  { background: #EEF2FF; border-color: #C7D2FE; color: #3730A3; }

/* ---------- Buttons ---------- */
.stButton > button, .stDownloadButton > button { border-radius: 10px; font-weight: 500; }
.stButton > button[kind="primary"] { background: #5B4BDB; border-color: #5B4BDB; color: #fff; }
.stButton > button[kind="primary"]:hover { background: #4939C7; border-color: #4939C7; }

/* ---------- View switch (Notes | Q&A) ---------- */
[data-testid="stSegmentedControl"] { background: #ECEEF8; padding: 4px; border-radius: 12px; }

/* ---------- Processing checklist ---------- */
.bw-steps { display: flex; flex-direction: column; gap: 12px; padding: 6px 4px; }
.bw-step { display: flex; align-items: center; gap: 10px; font-size: .92rem; color: #8A90A6; }
.bw-step.done { color: #1E202C; }
.bw-step.active { color: #1E202C; font-weight: 600; }
.bw-dot { width: 20px; height: 20px; border-radius: 50%; border: 2px solid #CBD0E3; display: inline-flex;
          align-items: center; justify-content: center; font-size: 12px; color: #fff; flex: none; }
.bw-step.done .bw-dot { background: #5B4BDB; border-color: #5B4BDB; }
.bw-step.active .bw-dot { border-color: #5B4BDB; box-shadow: inset 0 0 0 4px #fff, inset 0 0 0 20px #5B4BDB; }

/* ---------- Chat ---------- */
[data-testid="stChatMessage"] { background: #FFFFFF; border: 1px solid #E6E8F0; border-radius: 14px;
                                padding: .8rem 1rem; margin-bottom: .6rem; }

/* ---------- Bottom info tiles ---------- */
.bw-tiles { display: grid; gap: 12px; }
.bw-tiles.f5 { grid-template-columns: repeat(5, 1fr); }
.bw-tiles.f3 { grid-template-columns: repeat(3, 1fr); }
.bw-tile { background: #F8F9FE; border: 1px solid #E6E8F0; border-radius: 12px; padding: 10px 6px; }
.bw-tiles.f3 .bw-tile { padding: 12px; }
.bw-tile.center { text-align: center; }
.bw-tile .ic { font-size: 1.4rem; }
.bw-tile .t { font-weight: 600; font-size: .8rem; overflow-wrap: anywhere; color: #1E202C; margin-top: 2px; }
.bw-tile .d { font-size: .78rem; color: #5F6475; margin-top: 2px; line-height: 1.4; }
.bw-sec-title { font-weight: 700; color: #5B4BDB; font-size: 1.05rem; margin-bottom: 10px; }
@media (max-width: 900px) { .bw-tiles.f5, .bw-tiles.f3 { grid-template-columns: 1fr 1fr; } }
</style>
"""


def apply_custom_styles():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def esc(text) -> str:
    """HTML-escape model output before putting it into raw HTML."""
    return html.escape(str(text or ""))


def pill(level: str, noun: str = "confidence") -> str:
    level = str(level).strip().capitalize()
    level = level if level in ("High", "Medium") else "Low"
    return f'<span class="bw-pill bw-pill-{level.lower()}">{level} {noun}</span>'


def status_pill(item: dict) -> str:
    """Status shown at the top-right of a note: confirmed (green check) or confidence level."""
    if item.get("is_confirmed"):
        return '<span class="bw-pill bw-pill-ok">✓ Confirmed</span>'
    if item.get("confidence") in ("Medium", "Low"):
        return f'<span class="bw-pill bw-pill-{item["confidence"].lower()}">⚠ Check · {item["confidence"]}</span>'
    return pill(item.get("confidence", "High"))


def banner(kind: str, html_text: str):
    st.markdown(f'<div class="bw-banner bw-banner-{kind}">{html_text}</div>', unsafe_allow_html=True)


def render_missing_key_screen():
    st.markdown(
        """
        <div style="max-width:650px;margin:3rem auto;text-align:center;background:#fff;border:1px solid #E6E8F0;
                    border-radius:16px;padding:2.2rem 2rem;box-shadow:0 10px 30px rgba(0,0,0,.04);">
          <div style="font-size:2.6rem;">🔑</div>
          <h2 style="margin:.4rem 0;">Google AI Studio API key required</h2>
          <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:1rem 1.2rem;
                      text-align:left;font-size:.9rem;color:#334155;line-height:1.7;margin-top:1rem;">
            1. Open the <code>.env</code> file in the project folder.<br>
            2. Write <code>GOOGLE_API_KEY=your_key_here</code> (get a free key at
               <a href="https://aistudio.google.com/app/apikey" target="_blank">aistudio.google.com</a>).<br>
            3. Save the file and restart the app.
          </div>
          <p style="color:#94A3B8;font-size:.8rem;margin-top:1rem;">
            The key stays on your machine and is never typed into the web page.</p>
        </div>""",
        unsafe_allow_html=True,
    )
