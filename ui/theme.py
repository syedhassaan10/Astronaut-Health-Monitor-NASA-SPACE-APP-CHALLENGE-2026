"""The OrbitFit look: the prototype's style (prototype/styles.css in the original project) in a light
version, easy to read on a laptop or a tablet in a bright cabin. Soft white-blue background with
faint cyan and violet glows, white glass cards with large rounded corners, a cyan-to-violet gradient
for headings and main buttons. Big text and buttons, so it works 1 to 2 metres from the screen.
System fonts only; nothing is loaded from the internet."""

import html

import streamlit as st

# Colours (darker shades of the prototype's colours, so they stay readable on white).
BG_TOP = "#f7f9ff"
BG_BOTTOM = "#e9effb"
CARD = "rgba(255, 255, 255, 0.82)"
CARD_STRONG = "#ffffff"
STROKE = "rgba(15, 23, 42, 0.10)"
TEXT = "#0f172a"
MUTED = "#475569"
FAINT = "#64748b"
CYAN = "#0284c7"
VIOLET = "#7c3aed"
GOOD = "#047857"
WARN = "#b45309"
BAD = "#e11d48"
GRADIENT = f"linear-gradient(135deg, {CYAN}, {VIOLET})"

# Names used across the pages.
SPACE_950 = BG_TOP
SPACE_900 = "#f1f5fd"
SPACE_800 = CARD
SPACE_700 = STROKE
SPACE_600 = "rgba(15, 23, 42, 0.14)"
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
TINT = {GOOD: "4, 120, 87", WARN: "180, 83, 9", BAD: "225, 29, 72", CYAN: "2, 132, 199"}
LEVEL_COLOUR = {"green": GOOD, "amber": WARN, "red": BAD, "neutral": CYAN}

CSS = f"""
<style>
/* ---- light background with soft glows ------------------------------------------------ */
html, body {{ background: {BG_TOP}; }}
.stApp, [data-testid="stAppViewContainer"] {{
  color: {TEXT}; font-family: {SANS}; -webkit-font-smoothing: antialiased; font-size: 1.08rem;
  background:
    radial-gradient(900px 520px at 85% -8%, rgba(167, 139, 250, 0.22), transparent 60%),
    radial-gradient(760px 480px at -5% 4%, rgba(56, 189, 248, 0.18), transparent 55%),
    linear-gradient(180deg, {BG_TOP}, {BG_BOTTOM}) !important;
  background-attachment: fixed !important;
}}
[data-testid="stMainBlockContainer"], .block-container {{
  max-width: 1180px; padding-top: 5rem; padding-bottom: 1.5rem;
}}
:focus-visible {{ outline: 3px solid {CYAN} !important; outline-offset: 2px; }}
h1 {{
  font-size: 2.3rem !important; font-weight: 800 !important; letter-spacing: -0.02em; padding-bottom: 0 !important;
  background: {GRADIENT}; -webkit-background-clip: text; background-clip: text; color: transparent !important;
  width: fit-content;
}}
h2 {{ font-size: 1.35rem !important; font-weight: 700 !important; color: {TEXT}; }}
h3 {{ font-size: 1.15rem !important; font-weight: 700 !important; color: {TEXT}; }}
p, li, label {{ color: {TEXT}; font-size: 1.05rem; }}
a {{ color: {CYAN} !important; font-weight: 600; }}
[data-testid="stCaptionContainer"], .stCaption {{ color: {MUTED} !important; font-size: 0.95rem !important; }}

/* ---- header bar ----------------------------------------------------------------------- */
header[data-testid="stHeader"] {{
  background: rgba(255, 255, 255, 0.85) !important; backdrop-filter: blur(14px);
  border-bottom: 1px solid {STROKE};
}}
header[data-testid="stHeader"] a, header[data-testid="stHeader"] span {{
  font-size: 1.05rem; color: {TEXT}; font-weight: 600;
}}
img[data-testid="stHeaderLogo"] {{ width: auto !important; height: 36px !important; max-width: none !important; }}
/* On phones and tablets Streamlit folds the top menu into this side panel (opened with the » button). */
[data-testid="stSidebar"] {{
  background: rgba(255, 255, 255, 0.97) !important; border-right: 1px solid {STROKE};
  box-shadow: 8px 0 30px rgba(15, 23, 42, 0.12);
}}
[data-testid="stSidebarNavLink"] {{ border-radius: 12px; padding: 0.55rem 0.8rem; min-height: 2.8rem; }}
[data-testid="stSidebarNavLink"] span {{ font-size: 1.1rem !important; font-weight: 700; color: {TEXT}; }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: {GRADIENT}; }}
[data-testid="stSidebarNavLink"][aria-current="page"] span {{ color: #ffffff !important; }}
header[data-testid="stHeader"] button {{ color: {TEXT}; }}
header[data-testid="stHeader"] button svg {{ width: 1.6rem; height: 1.6rem; }}
/* Say "Menu" next to the » button, so everyone knows where the pages are on a phone. */
[data-testid="stExpandSidebarButton"] {{
  border: 1px solid {SPACE_600} !important; border-radius: 999px !important; padding: 0.3rem 0.9rem !important;
  background: #ffffff !important; gap: 0.3rem;
}}
[data-testid="stExpandSidebarButton"]::after {{ content: "Menu"; font-size: 1.05rem; font-weight: 700; color: {TEXT}; }}

/* ---- white glass cards ---------------------------------------------------------------- */
[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"],
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{
  background: {CARD}; border: 1px solid {STROKE} !important; border-radius: 22px !important;
  backdrop-filter: blur(16px); box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
}}
[data-testid="stExpander"] details {{
  background: {CARD}; border: 1px solid {STROKE} !important; border-radius: 16px;
}}
[data-testid="stExpander"] summary p {{ color: {TEXT}; font-weight: 600; }}
[data-testid="stAlert"] {{ border-radius: 14px; font-size: 1.05rem; }}

/* ---- buttons: big; primary uses the gradient ------------------------------------------ */
.stButton button, .stDownloadButton button, .stFormSubmitButton button {{
  background: {CARD_STRONG}; color: {TEXT}; border: 1px solid {SPACE_600}; border-radius: 14px;
  font-weight: 700; min-height: 3rem; padding: 0.5rem 1.2rem; font-size: 1.05rem;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.06); transition: transform 0.12s, border-color 0.2s;
}}
.stButton button p, .stDownloadButton button p, .stFormSubmitButton button p {{ font-size: 1.05rem; font-weight: 700; }}
.stButton button:hover:not(:disabled), .stDownloadButton button:hover:not(:disabled),
.stFormSubmitButton button:hover:not(:disabled) {{
  transform: translateY(-1px); border-color: {CYAN}; color: {TEXT}; background: {CARD_STRONG};
}}
.stButton button[kind="primary"], .stButton button[data-testid="stBaseButton-primary"],
.stFormSubmitButton button[kind="primaryFormSubmit"],
.stFormSubmitButton button[data-testid="stBaseButton-primaryFormSubmit"] {{
  background: {GRADIENT}; color: #ffffff; border: 0; box-shadow: 0 8px 22px rgba(2, 132, 199, 0.28);
}}
.stButton button[data-testid="stBaseButton-primary"] p,
.stFormSubmitButton button[data-testid="stBaseButton-primaryFormSubmit"] p {{ color: #ffffff; }}
.stButton button[data-testid="stBaseButton-primary"]:hover:not(:disabled),
.stFormSubmitButton button[data-testid="stBaseButton-primaryFormSubmit"]:hover:not(:disabled) {{
  background: {GRADIENT}; color: #ffffff;
}}
.stButton button:disabled {{ opacity: 0.45; }}

/* ---- inputs ----------------------------------------------------------------------------- */
[data-baseweb="select"] > div, [data-baseweb="input"], .stNumberInput input, .stTextInput input,
.stTextArea textarea, [data-testid="stFileUploaderDropzone"] {{
  background: #ffffff !important; border-color: {SPACE_600} !important; color: {TEXT} !important;
  border-radius: 12px !important; font-size: 1.05rem !important; min-height: 2.8rem;
}}
.stSlider [data-baseweb="slider"] div[role="slider"] {{ background: {CYAN}; width: 1.3rem; height: 1.3rem; }}
[data-testid="stWidgetLabel"] p {{ font-size: 1.05rem; font-weight: 700; color: {TEXT}; }}
.stRadio label p {{ font-size: 1.05rem; }}

/* ---- tabs as big pills ---------------------------------------------------------------- */
.stTabs [role="tablist"] {{ gap: 0.5rem; border-bottom: 0 !important; box-shadow: none !important; }}
.stTabs [data-testid="stTab"] {{
  background: {CARD_STRONG}; color: {MUTED}; border: 1px solid {SPACE_600}; border-radius: 999px;
  padding: 0.55rem 1.3rem; margin-bottom: 0.5rem;
}}
.stTabs [data-testid="stTab"][aria-selected="true"] {{
  background: {GRADIENT}; color: #ffffff; border-color: transparent;
}}
.stTabs [data-testid="stTab"] p {{ font-weight: 700; font-size: 1.05rem; }}
.stTabs [data-testid="stTab"][aria-selected="true"] p {{ color: #ffffff; }}

/* ---- metrics as big number tiles ------------------------------------------------------ */
[data-testid="stMetric"] {{
  background: {CARD}; border: 1px solid {STROKE}; border-radius: 18px; padding: 0.9rem 1rem;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
}}
[data-testid="stMetricLabel"] p {{
  font-size: 0.85rem !important; letter-spacing: 0.08em; text-transform: uppercase; color: {MUTED} !important;
  font-weight: 700 !important;
}}
[data-testid="stMetricValue"] {{ font-size: 2rem !important; font-weight: 800; color: {TEXT};
  font-variant-numeric: tabular-nums; }}

/* ---- segmented buttons ---------------------------------------------------------------- */
[data-testid="stButtonGroup"] button {{
  background: {CARD_STRONG}; border: 1px solid {SPACE_600}; color: {MUTED}; border-radius: 999px !important;
  margin-right: 0.35rem; min-height: 2.8rem; padding: 0.4rem 1.2rem;
}}
[data-testid="stButtonGroup"] button p {{ font-size: 1.05rem; font-weight: 700; }}
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[kind*="Active"] {{
  background: {GRADIENT}; border-color: transparent; color: #ffffff;
}}
[data-testid="stButtonGroup"] button[kind*="Active"] p {{ color: #ffffff; }}

[data-testid="stDataFrame"] {{ border: 1px solid {STROKE}; border-radius: 14px; }}

/* ---- OrbitFit pieces -------------------------------------------------------------------- */
.of-label {{
  font-size: 0.85rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: {MUTED};
}}
.of-sub {{ color: {MUTED}; margin-top: -0.3rem; margin-bottom: 1rem; font-size: 1.15rem; }}
.of-badge {{
  display: inline-flex; align-items: center; gap: 0.4rem; border: 1px solid; border-radius: 999px;
  padding: 0.15rem 0.75rem; font-size: 0.95rem; font-weight: 800; white-space: nowrap; line-height: 1.5;
}}
.of-badge.large {{ padding: 0.4rem 1.1rem; font-size: 1.15rem; }}
.of-chip {{
  display: inline-block; font-size: 0.95rem; font-weight: 700; color: {TEXT}; background: {SPACE_900};
  border: 1px solid {STROKE}; border-radius: 999px; padding: 0.15rem 0.75rem; margin: 0 0.35rem 0.35rem 0;
  font-variant-numeric: tabular-nums;
}}
.of-row {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.7rem; }}
.of-row .of-right {{ margin-left: auto; }}
.of-title {{ font-weight: 800; font-size: 1.25rem; color: {TEXT}; }}
.of-muted {{ color: {MUTED}; font-size: 1rem; }}
.of-big {{ font-size: 1.2rem; color: {TEXT}; }}
.of-do {{
  margin-top: 0.6rem; padding: 0.6rem 0.9rem; border-radius: 14px; font-size: 1.1rem; font-weight: 600;
  background: {SPACE_900}; border: 1px solid {STROKE};
}}
.of-box {{
  background: {CARD_STRONG}; border: 1px solid {STROKE}; border-radius: 16px; padding: 0.8rem 1rem;
}}
.of-table {{ width: 100%; border-collapse: separate; border-spacing: 0 6px; font-size: 1rem;
  font-variant-numeric: tabular-nums; }}
.of-table th {{
  text-align: left; color: {FAINT}; font-weight: 700; font-size: 0.8rem; letter-spacing: 0.08em;
  text-transform: uppercase; padding: 0 0.6rem;
}}
.of-table td {{ padding: 0.5rem 0.6rem; background: {SPACE_900}; color: {TEXT}; }}
.of-table td:first-child {{ border-radius: 10px 0 0 10px; font-weight: 800; }}
.of-table td:last-child {{ border-radius: 0 10px 10px 0; }}
.of-stat {{ display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid {STROKE};
  font-size: 1rem; color: {MUTED}; }}
.of-stat b {{ color: {TEXT}; font-variant-numeric: tabular-nums; }}
.of-footer {{
  border: 1px solid {STROKE}; background: {CARD}; color: {MUTED}; font-size: 0.92rem; text-align: center;
  padding: 0.8rem 1rem; margin-top: 2rem; border-radius: 999px;
}}
.of-pill {{
  display: inline-flex; align-items: center; gap: 0.5rem; font-size: 0.98rem; font-weight: 700; border: 1px solid;
  border-radius: 999px; padding: 0.4rem 0.95rem; white-space: nowrap; background: {CARD_STRONG};
}}
.of-dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: none; }}
.of-overlay {{ display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 0.4rem; }}
.of-overlay span {{
  font-size: 0.95rem; font-weight: 700; background: rgba(15, 23, 42, 0.78); border-radius: 999px;
  padding: 0.25rem 0.8rem; color: #ffffff;
}}
.of-count {{
  font-size: 6rem; font-weight: 800; line-height: 1; letter-spacing: -0.04em; font-variant-numeric: tabular-nums;
  background: {GRADIENT}; -webkit-background-clip: text; background-clip: text; color: transparent;
  display: inline-block;
}}
.of-cue {{
  display: inline-flex; align-items: center; padding: 0.6rem 1.3rem; border-radius: 999px; font-weight: 800;
  font-size: 1.8rem; border: 2px solid; margin-top: 0.7rem;
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
    """Small uppercase label."""
    return f'<span class="of-label">{esc(text)}</span>'


def badge(status, large=False):
    """Status pill: shape + word + colour, never colour alone."""
    shape, colour = STATUS_STYLE[status]
    size = " large" if large else ""
    return (f'<span class="of-badge{size}" style="color:{colour};border-color:{tint(colour, 0.45)};'
            f'background:{tint(colour, 0.10)}" aria-label="Status {status}">{shape} {status}</span>')


def chip(text):
    return f'<span class="of-chip">{esc(text)}</span>'


def pill(text, colour, dot=True):
    glow = f'<i class="of-dot" style="background:{colour}"></i>' if dot else ""
    return (f'<span class="of-pill" style="color:{colour};border-color:{tint(colour, 0.45)};'
            f'background:{tint(colour, 0.08)}">{glow}{esc(text)}</span>')


def cue(text, colour):
    """The big feedback pill ("Good depth", "Go deeper")."""
    return (f'<span class="of-cue" style="color:{colour};border-color:{tint(colour, 0.5)};'
            f'background:{tint(colour, 0.10)}">{esc(text)}</span>')


def page_header(title, subtitle):
    st.title(title)
    st.markdown(f'<div class="of-sub">{esc(subtitle)}</div>', unsafe_allow_html=True)


def html_block(markup):
    st.markdown(markup, unsafe_allow_html=True)
