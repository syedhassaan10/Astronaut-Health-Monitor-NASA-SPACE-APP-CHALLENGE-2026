"""The look of the OrbitFit prototype (prototype/styles.css in the original project):
a deep-blue space gradient with violet and cyan glows and stars, glassy cards with large
rounded corners, and a cyan-to-violet gradient for headings and main buttons.
System fonts only; nothing is loaded from the internet."""

import html

import streamlit as st

# The prototype's colours.
BG_TOP = "#060914"
BG_BOTTOM = "#0c1330"
CARD = "rgba(255, 255, 255, 0.055)"
CARD_STRONG = "rgba(255, 255, 255, 0.09)"
STROKE = "rgba(255, 255, 255, 0.12)"
TEXT = "#eef2ff"
MUTED = "#94a3c4"
FAINT = "#66728f"
CYAN = "#38bdf8"
VIOLET = "#a78bfa"
GOOD = "#34d399"
WARN = "#fbbf24"
BAD = "#fb7185"
GRADIENT = f"linear-gradient(135deg, {CYAN}, {VIOLET})"

# Names used across the pages (kept so every page picks up the new look).
SPACE_950 = BG_TOP
SPACE_900 = "rgba(255, 255, 255, 0.04)"
SPACE_800 = CARD
SPACE_700 = STROKE
SPACE_600 = "rgba(255, 255, 255, 0.18)"
INK_100 = TEXT
INK_300 = MUTED
INK_500 = FAINT
ACCENT = CYAN
NOMINAL = GOOD
WATCH = WARN
ACT = BAD
MONO = 'ui-monospace, "Cascadia Mono", Consolas, monospace'
SANS = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

STATUS_STYLE = {"NOMINAL": ("●", GOOD), "WATCH": ("▲", WARN), "ACT": ("■", BAD)}
TINT = {GOOD: "52, 211, 153", WARN: "251, 191, 36", BAD: "251, 113, 133", CYAN: "56, 189, 248"}
LEVEL_COLOUR = {"green": GOOD, "amber": WARN, "red": BAD, "neutral": CYAN}

STARS = ", ".join(
    f"radial-gradient({size} {size} at {x}% {y}%, rgba(255, 255, 255, {alpha}), transparent)"
    for size, x, y, alpha in [
        ("1.5px", 8, 18, 0.7), ("1px", 22, 62, 0.5), ("1.5px", 37, 9, 0.6), ("1px", 51, 78, 0.45),
        ("1.5px", 66, 28, 0.7), ("1px", 79, 88, 0.5), ("1.5px", 91, 46, 0.6), ("1px", 14, 90, 0.4),
        ("1px", 58, 5, 0.5), ("1px", 95, 12, 0.45), ("1px", 33, 40, 0.35), ("1.5px", 72, 64, 0.5),
    ]
)

CSS = f"""
<style>
/* ---- space background with glows and stars ---------------------------------------- */
html, body {{ background: {BG_TOP}; }}
.stApp, [data-testid="stAppViewContainer"] {{
  color: {TEXT}; font-family: {SANS}; -webkit-font-smoothing: antialiased;
  background:
    radial-gradient(900px 520px at 85% -8%, rgba(167, 139, 250, 0.28), transparent 60%),
    radial-gradient(760px 480px at -5% 4%, rgba(56, 189, 248, 0.20), transparent 55%),
    linear-gradient(180deg, {BG_TOP}, {BG_BOTTOM}) !important;
  background-attachment: fixed !important;
}}
.stApp::before {{
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0; background: {STARS};
}}
[data-testid="stMainBlockContainer"], .block-container {{
  max-width: 1180px; padding-top: 4.8rem; padding-bottom: 1.5rem; position: relative; z-index: 1;
}}
:focus-visible {{ outline: 2px solid {CYAN} !important; outline-offset: 2px; }}
h1 {{
  font-size: 2rem !important; font-weight: 800 !important; letter-spacing: -0.02em; padding-bottom: 0 !important;
  background: {GRADIENT}; -webkit-background-clip: text; background-clip: text; color: transparent !important;
  width: fit-content;
}}
h2 {{ font-size: 1.2rem !important; font-weight: 700 !important; }}
h3 {{ font-size: 1.05rem !important; font-weight: 700 !important; }}
p, li {{ color: {TEXT}; }}
a {{ color: {CYAN} !important; }}
[data-testid="stCaptionContainer"], .stCaption {{ color: {MUTED} !important; }}

/* ---- header bar ----------------------------------------------------------------------- */
header[data-testid="stHeader"] {{
  background: rgba(6, 9, 20, 0.65) !important; backdrop-filter: blur(14px);
  border-bottom: 1px solid {STROKE};
}}
header[data-testid="stHeader"] a, header[data-testid="stHeader"] span {{ font-size: 0.95rem; }}
img[data-testid="stHeaderLogo"] {{ width: auto !important; height: 32px !important; max-width: none !important; }}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{ display: none; }}

/* ---- glass cards ---------------------------------------------------------------------- */
[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"],
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{
  background: {CARD}; border: 1px solid {STROKE} !important; border-radius: 22px !important;
  backdrop-filter: blur(16px);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.06);
}}
[data-testid="stExpander"] details {{
  background: {CARD}; border: 1px solid {STROKE} !important; border-radius: 16px; backdrop-filter: blur(16px);
}}
[data-testid="stExpander"] summary {{ color: {MUTED}; }}
[data-testid="stAlert"] {{ border-radius: 14px; }}

/* ---- buttons: glass, primary uses the gradient ----------------------------------------- */
.stButton button, .stDownloadButton button, .stFormSubmitButton button {{
  background: {CARD_STRONG}; color: {TEXT}; border: 1px solid {STROKE}; border-radius: 12px;
  font-weight: 600; transition: transform 0.12s, border-color 0.2s, box-shadow 0.2s;
}}
.stButton button:hover:not(:disabled), .stDownloadButton button:hover:not(:disabled),
.stFormSubmitButton button:hover:not(:disabled) {{
  transform: translateY(-1px); border-color: rgba(255, 255, 255, 0.32); color: {TEXT}; background: {CARD_STRONG};
}}
.stButton button[kind="primary"], .stButton button[data-testid="stBaseButton-primary"],
.stFormSubmitButton button[kind="primaryFormSubmit"],
.stFormSubmitButton button[data-testid="stBaseButton-primaryFormSubmit"] {{
  background: {GRADIENT}; color: #04101f; border: 0; box-shadow: 0 8px 24px rgba(56, 189, 248, 0.32);
}}
.stButton button[data-testid="stBaseButton-primary"]:hover:not(:disabled),
.stFormSubmitButton button[data-testid="stBaseButton-primaryFormSubmit"]:hover:not(:disabled) {{
  background: {GRADIENT}; color: #04101f;
}}
.stButton button:disabled {{ opacity: 0.45; }}

/* ---- inputs ----------------------------------------------------------------------------- */
[data-baseweb="select"] > div, [data-baseweb="input"], .stNumberInput input, .stTextInput input,
.stTextArea textarea, [data-testid="stFileUploaderDropzone"] {{
  background: rgba(255, 255, 255, 0.06) !important; border-color: {STROKE} !important; color: {TEXT} !important;
  border-radius: 12px !important;
}}
.stSlider [data-baseweb="slider"] div[role="slider"] {{ background: {CYAN}; box-shadow: 0 0 10px rgba(56, 189, 248, 0.6); }}
[data-testid="stWidgetLabel"] p {{ font-size: 0.9rem; font-weight: 600; color: {TEXT}; }}

/* ---- tabs as pills ---------------------------------------------------------------------- */
.stTabs [role="tablist"] {{ gap: 0.45rem; border-bottom: 0 !important; box-shadow: none !important; }}
.stTabs [data-testid="stTab"] {{
  background: {CARD}; color: {MUTED}; border: 1px solid {STROKE}; border-radius: 999px; padding: 0.35rem 1rem;
  margin-bottom: 0.4rem;
}}
.stTabs [data-testid="stTab"][aria-selected="true"] {{
  background: rgba(56, 189, 248, 0.14); color: {TEXT}; border-color: rgba(56, 189, 248, 0.55);
}}
.stTabs [data-testid="stTab"] p {{ font-weight: 600; }}

/* ---- metrics as the prototype's number tiles -------------------------------------------- */
[data-testid="stMetric"] {{
  background: {CARD}; border: 1px solid {STROKE}; border-radius: 16px; padding: 0.8rem 0.9rem;
  backdrop-filter: blur(12px);
}}
[data-testid="stMetricLabel"] p {{
  font-size: 0.72rem !important; letter-spacing: 0.1em; text-transform: uppercase; color: {MUTED} !important;
  font-weight: 600 !important;
}}
[data-testid="stMetricValue"] {{ font-size: 1.6rem !important; font-weight: 800; color: {TEXT};
  font-variant-numeric: tabular-nums; }}

/* ---- segmented buttons -------------------------------------------------------------------- */
[data-testid="stButtonGroup"] button {{
  background: {CARD}; border: 1px solid {STROKE}; color: {MUTED}; border-radius: 999px !important; margin-right: 0.3rem;
}}
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[kind*="Active"] {{
  border-color: rgba(56, 189, 248, 0.6); color: {TEXT}; background: rgba(56, 189, 248, 0.15);
}}

[data-testid="stDataFrame"] {{ border: 1px solid {STROKE}; border-radius: 14px; }}

/* ---- OrbitFit pieces -------------------------------------------------------------------- */
.of-label {{
  font-size: 0.75rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: {MUTED};
}}
.of-sub {{ color: {MUTED}; margin-top: -0.3rem; margin-bottom: 0.9rem; font-size: 0.98rem; }}
.of-badge {{
  display: inline-flex; align-items: center; gap: 0.4rem; border: 1px solid; border-radius: 999px;
  padding: 0.12rem 0.65rem; font-size: 0.8rem; font-weight: 700; white-space: nowrap; line-height: 1.5;
}}
.of-badge.large {{ padding: 0.35rem 1rem; font-size: 1rem; }}
.of-chip {{
  display: inline-block; font-size: 0.8rem; font-weight: 600; color: {TEXT}; background: {CARD_STRONG};
  border: 1px solid {STROKE}; border-radius: 999px; padding: 0.12rem 0.65rem; margin: 0 0.3rem 0.3rem 0;
  font-variant-numeric: tabular-nums;
}}
.of-row {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.6rem; }}
.of-row .of-right {{ margin-left: auto; }}
.of-title {{ font-weight: 700; font-size: 1.05rem; color: {TEXT}; }}
.of-muted {{ color: {MUTED}; font-size: 0.9rem; }}
.of-box {{
  background: {CARD}; border: 1px solid {STROKE}; border-radius: 16px; padding: 0.7rem 0.9rem;
}}
.of-table {{ width: 100%; border-collapse: separate; border-spacing: 0 5px; font-size: 0.85rem;
  font-variant-numeric: tabular-nums; }}
.of-table th {{
  text-align: left; color: {FAINT}; font-weight: 600; font-size: 0.7rem; letter-spacing: 0.1em;
  text-transform: uppercase; padding: 0 0.6rem;
}}
.of-table td {{ padding: 0.45rem 0.6rem; background: {CARD}; color: {TEXT}; }}
.of-table td:first-child {{ border-radius: 10px 0 0 10px; font-weight: 700; }}
.of-table td:last-child {{ border-radius: 0 10px 10px 0; }}
.of-stat {{ display: flex; justify-content: space-between; padding: 0.35rem 0; border-bottom: 1px solid {STROKE};
  font-size: 0.9rem; color: {MUTED}; }}
.of-stat b {{ color: {TEXT}; font-variant-numeric: tabular-nums; }}
.of-footer {{
  border: 1px solid {STROKE}; background: {CARD}; color: {MUTED}; font-size: 0.8rem; text-align: center;
  padding: 0.7rem 1rem; margin-top: 1.8rem; border-radius: 999px; backdrop-filter: blur(8px);
}}
.of-pill {{
  display: inline-flex; align-items: center; gap: 0.45rem; font-size: 0.8rem; font-weight: 600; border: 1px solid;
  border-radius: 999px; padding: 0.3rem 0.8rem; white-space: nowrap; background: {CARD}; backdrop-filter: blur(8px);
}}
.of-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex: none; }}
.of-overlay {{ display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 0.4rem; }}
.of-overlay span {{
  font-size: 0.78rem; font-weight: 700; background: rgba(0, 0, 0, 0.55); border: 1px solid {STROKE};
  border-radius: 999px; padding: 0.2rem 0.7rem; color: {TEXT}; letter-spacing: 0.03em;
}}
.of-count {{
  font-size: 5rem; font-weight: 800; line-height: 1; letter-spacing: -0.04em; font-variant-numeric: tabular-nums;
  background: {GRADIENT}; -webkit-background-clip: text; background-clip: text; color: transparent;
  display: inline-block;
}}
.of-cue {{
  display: inline-flex; align-items: center; padding: 0.5rem 1.1rem; border-radius: 999px; font-weight: 700;
  font-size: 1.5rem; border: 1px solid; margin-top: 0.6rem;
}}
.of-gradient-text {{
  background: {GRADIENT}; -webkit-background-clip: text; background-clip: text; color: transparent;
}}
</style>
"""


def inject():
    st.html(CSS)


def esc(text):
    return html.escape(str(text))


def tint(colour, alpha):
    """A see-through version of one of the status colours."""
    rgb = TINT.get(colour)
    if rgb is None:
        return colour
    return f"rgba({rgb}, {alpha})"


def label(text):
    """Small uppercase label, like the prototype's card titles."""
    return f'<span class="of-label">{esc(text)}</span>'


def badge(status, large=False):
    """Status pill: shape + word + colour, never colour alone."""
    shape, colour = STATUS_STYLE[status]
    size = " large" if large else ""
    return (f'<span class="of-badge{size}" style="color:{colour};border-color:{tint(colour, 0.5)};'
            f'background:{tint(colour, 0.13)}" aria-label="Status {status}">{shape} {status}</span>')


def chip(text):
    return f'<span class="of-chip">{esc(text)}</span>'


def pill(text, colour, dot=True):
    glow = f'<i class="of-dot" style="background:{colour};box-shadow:0 0 10px {colour}"></i>' if dot else ""
    return f'<span class="of-pill" style="color:{colour};border-color:{tint(colour, 0.5)}">{glow}{esc(text)}</span>'


def cue(text, colour):
    """The big feedback pill ("Good depth", "Go deeper")."""
    return (f'<span class="of-cue" style="color:{colour};border-color:{tint(colour, 0.5)};'
            f'background:{tint(colour, 0.12)}">{esc(text)}</span>')


def page_header(title, subtitle):
    st.title(title)
    st.markdown(f'<div class="of-sub">{esc(subtitle)}</div>', unsafe_allow_html=True)


def html_block(markup):
    st.markdown(markup, unsafe_allow_html=True)
