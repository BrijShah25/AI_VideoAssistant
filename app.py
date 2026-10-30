import html
import os
import re
import tempfile
import time

import streamlit as st
from dotenv import load_dotenv

from utils.audio_processor import process_input
from core.transcriber import transcribe_all
from core.summarizer import summarize, generate_title
from core.extractor import (
    extract_action_items,
    extract_key_decisions,
    extract_questions,
)
from core.rag_engine import build_rag_chain, ask_question

load_dotenv()

st.set_page_config(
    page_title="Clip Chat",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════
# Design system: "night console"  (works without any config.toml)
# Void #05070D · Panel #0B1020 · Text #E6EAF7 · Muted #8892B0
# Signal cyan #22E4FF → violet #8B5CF6 · Emerald #34D399 · Amber #FBBF24
# The whole theme is forced here, so it looks the same on light or dark systems.
# ══════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');

@property --a { syntax: '<angle>'; inherits: false; initial-value: 0deg; }

:root {
  --void: #05070D; --panel: #0B1020; --text: #E6EAF7; --muted: #8892B0;
  --line: rgba(148,163,255,.15); --glass: rgba(255,255,255,.04);
  --cyan: #22E4FF; --violet: #8B5CF6; --emerald: #34D399; --amber: #FBBF24;
}
html { color-scheme: dark; }
html, body { background: var(--void) !important; }

html, body, [class*="css"], .stApp, button, input, textarea { font-family: 'Space Grotesk', sans-serif !important; }
.stApp {
  color: var(--text);
  background:
    radial-gradient(900px 560px at 6% -10%, rgba(139,92,246,.32), transparent 62%),
    radial-gradient(820px 520px at 98% 0%, rgba(34,228,255,.22), transparent 62%),
    radial-gradient(700px 400px at 50% 110%, rgba(244,114,182,.10), transparent 70%),
    linear-gradient(rgba(148,163,255,.05) 1px, transparent 1px) 0 0 / 54px 54px,
    linear-gradient(90deg, rgba(148,163,255,.05) 1px, transparent 1px) 0 0 / 54px 54px,
    var(--void);
}
[data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stBottom"],
[data-testid="stBottomBlockContainer"], [data-testid="stHeader"] { background: transparent !important; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
section[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
.block-container { max-width: 1200px; padding-top: .6rem; padding-bottom: 3rem; }

/* Force readable text on every Streamlit element, whatever the system theme */
[data-testid="stMarkdownContainer"] { color: var(--text) !important; }
[data-testid="stMarkdownContainer"] :is(p, li, strong, em, h1, h2, h3, h4, h5, h6):not([class]) { color: inherit !important; }
[data-testid="stMarkdownContainer"] a { color: var(--cyan) !important; }
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label { color: #B6C0E0 !important; font-weight: 500; font-size: .88rem; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color: var(--muted) !important; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: rgba(148,163,255,.25); border-radius: 8px; }
::-webkit-scrollbar-track { background: transparent; }

/* ── Navigation ── */
.nav { display: flex; align-items: center; justify-content: space-between;
       padding: .9rem 0 1.1rem; border-bottom: 1px solid var(--line); margin-bottom: 2.2rem; }
.brand { display: flex; align-items: center; gap: .7rem; font-weight: 700; font-size: 1.15rem; letter-spacing: -.01em; color: #fff; }
.logo { width: 36px; height: 36px; border-radius: 11px; display: grid; place-items: center; color: #04121A;
        background: linear-gradient(135deg, #22E4FF, #8B5CF6); box-shadow: 0 0 24px rgba(34,228,255,.6); }
.live { display: inline-flex; align-items: center; gap: .5rem; font-family: 'JetBrains Mono', monospace !important;
        font-size: .78rem; font-weight: 500; color: #9FB0D8; padding: .35rem .8rem; border: 1px solid var(--line);
        border-radius: 999px; background: var(--glass); }
.live i { width: 8px; height: 8px; border-radius: 50%; background: var(--emerald); box-shadow: 0 0 10px var(--emerald);
          animation: pulse 2s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: .3; } }

/* ── Hero ── */
.hero { max-width: 820px; margin: 0 0 1.4rem; }
.hero .hl { font-size: 3.5rem; line-height: 1.03; letter-spacing: -.038em; font-weight: 700; margin: 0 0 1rem;
            background: linear-gradient(95deg, #FFFFFF 0%, #B9C4FF 42%, #22E4FF 100%);
            -webkit-background-clip: text; background-clip: text; color: transparent !important; }
.hero .lede { font-size: 1.15rem; line-height: 1.65; color: var(--muted) !important; margin: 0; max-width: 690px; }

/* Audio-visualizer strip (decorative) */
.wave { display: flex; align-items: center; justify-content: space-between; gap: 5px; height: 64px; margin: 0 0 1.3rem;
        -webkit-mask-image: linear-gradient(90deg, transparent, #000 14%, #000 86%, transparent);
                mask-image: linear-gradient(90deg, transparent, #000 14%, #000 86%, transparent); }
.wave i { flex: 1; max-width: 7px; height: var(--h); border-radius: 6px; opacity: .8;
          background: linear-gradient(180deg, #22E4FF, #8B5CF6 70%, #F472B6);
          animation: eq var(--d) ease-in-out infinite alternate; }
@keyframes eq { from { transform: scaleY(.22); } to { transform: scaleY(1); } }

/* ── Panels with gradient hairline edge ── */
[class*="st-key-card_"], .kpi {
  position: relative;
  background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.02));
  border-radius: 18px; padding: 1.4rem 1.55rem; backdrop-filter: blur(14px);
  box-shadow: 0 18px 50px rgba(0,0,0,.4), inset 0 1px 0 rgba(255,255,255,.06);
}
[class*="st-key-card_"]::before, .kpi::before {
  content: ""; position: absolute; inset: 0; border-radius: inherit; padding: 1px; pointer-events: none;
  background: linear-gradient(135deg, rgba(34,228,255,.55), rgba(148,163,255,.10) 38%, rgba(148,163,255,.08) 62%, rgba(139,92,246,.5));
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude;
}
.kpi { padding: 1.05rem 1.25rem; border-radius: 16px; }

/* Input card: rotating gradient edge */
.st-key-input_card {
  border: 1.5px solid transparent; border-radius: 20px; padding: 1.5rem 1.6rem 1.5rem;
  background: linear-gradient(var(--panel), var(--panel)) padding-box,
              conic-gradient(from var(--a), #22E4FF, #8B5CF6, #F472B6, #22E4FF) border-box;
  animation: spin 7s linear infinite;
  box-shadow: 0 0 70px rgba(139,92,246,.2), 0 24px 70px rgba(0,0,0,.55);
}
@keyframes spin { to { --a: 360deg; } }

.sec-h { display: flex; align-items: center; gap: .7rem; margin-bottom: .85rem; }
.sec-h .ico { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; box-shadow: 0 0 18px var(--glow, transparent); }
.sec-h .t { font-weight: 700; font-size: 1.08rem; letter-spacing: -.01em; color: #fff; }
.sec-h .badge { margin-left: auto; font-family: 'JetBrains Mono', monospace !important; font-size: .74rem; font-weight: 500;
                padding: .25rem .65rem; border-radius: 999px; background: rgba(255,255,255,.07); color: #B6C0E0; border: 1px solid var(--line); }
.sec-note { color: var(--muted); font-size: .88rem; margin: -.3rem 0 .8rem; }
[class*="st-key-card_"] [data-testid="stMarkdownContainer"] :is(p, li) { line-height: 1.72; font-size: 1rem; }

/* ── Result header ── */
.res-title { font-size: 2.25rem; font-weight: 700; letter-spacing: -.03em; line-height: 1.15; margin: .2rem 0 .8rem; color: #fff; }
.chips { display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: 1.3rem; }
.chip { display: inline-flex; align-items: center; gap: .45rem; font-family: 'JetBrains Mono', monospace !important;
        font-size: .76rem; font-weight: 500; color: #AEB9DD; background: var(--glass); border: 1px solid var(--line);
        padding: .32rem .8rem; border-radius: 999px; }
.chip .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--emerald); box-shadow: 0 0 8px var(--emerald); }

/* ── KPI ── */
.kpi .l { color: var(--muted); font-size: .84rem; font-weight: 500; }
.kpi .v { font-family: 'JetBrains Mono', monospace !important; font-size: 2.05rem; font-weight: 700; line-height: 1.15; margin-top: .2rem;
          background: linear-gradient(90deg, var(--c1, #fff), var(--c2, #A9B8FF)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.kpi .h { color: #66709A; font-size: .8rem; margin-top: .1rem; }

/* ── Feature cards ── */
.feat { background: linear-gradient(180deg, rgba(255,255,255,.055), rgba(255,255,255,.015)); border: 1px solid var(--line);
        border-radius: 16px; padding: 1.25rem 1.35rem; height: 100%; }
.feat .ico { width: 38px; height: 38px; border-radius: 11px; display: grid; place-items: center; margin-bottom: .85rem; box-shadow: 0 0 20px var(--glow, transparent); }
.feat .ft { display: block; font-size: 1.05rem; font-weight: 700; margin-bottom: .3rem; color: #fff; }
.feat .fs { display: block; color: var(--muted); font-size: .94rem; line-height: 1.6; }
.support { color: #66709A; font-size: .84rem; margin-top: 1rem; font-family: 'JetBrains Mono', monospace !important; }

/* ── Pipeline stepper ── */
.stepper { display: flex; margin: .6rem 0 .4rem; }
.stp { flex: 1; position: relative; text-align: center; }
.stp .n { position: relative; z-index: 1; width: 32px; height: 32px; margin: 0 auto .55rem; border-radius: 50%; display: grid; place-items: center;
          font-family: 'JetBrains Mono', monospace !important; font-weight: 700; font-size: .85rem;
          border: 1.5px solid rgba(148,163,255,.3); color: #66709A; background: var(--panel); }
.stp .lb { font-size: .82rem; color: #66709A; }
.stp:not(:last-child)::after { content: ""; position: absolute; top: 15px; left: calc(50% + 22px); right: calc(-50% + 22px); height: 2px; background: rgba(148,163,255,.2); }
.stp.done:not(:last-child)::after { background: linear-gradient(90deg, #22E4FF, #8B5CF6); }
.stp.done .n { background: #22E4FF; border-color: #22E4FF; color: #04121A; box-shadow: 0 0 16px rgba(34,228,255,.5); }
.stp.done .lb { color: #AEB9DD; }
.stp.active .n { background: linear-gradient(135deg, #22E4FF, #8B5CF6); border-color: transparent; color: #04121A;
                 box-shadow: 0 0 22px rgba(139,92,246,.8); animation: pulse 1.4s ease-in-out infinite; }
.stp.active .lb { color: #fff; font-weight: 600; }

/* ── Notices ── */
.notice { border: 1px solid; border-radius: 12px; padding: .8rem 1rem; margin: .9rem 0; font-size: .95rem; line-height: 1.5; }
.notice.warn { background: rgba(251,191,36,.08); border-color: rgba(251,191,36,.4); color: #FDE68A; }
.notice.err  { background: rgba(244,63,94,.08);  border-color: rgba(244,63,94,.4);  color: #FDA4AF; }

/* ── Inputs (forced dark) ── */
[data-baseweb="input"], [data-baseweb="base-input"], .stTextInput [data-baseweb="input"] > div {
  background: rgba(255,255,255,.05) !important; border-color: rgba(148,163,255,.24) !important; border-radius: 12px !important;
}
[data-baseweb="input"] { border: 1px solid rgba(148,163,255,.24) !important; min-height: 48px; }
[data-baseweb="input"]:focus-within { border-color: var(--cyan) !important; box-shadow: 0 0 0 3px rgba(34,228,255,.18) !important; }
.stTextInput input { background: transparent !important; color: var(--text) !important; -webkit-text-fill-color: var(--text); }
.stTextInput input::placeholder { color: #66709A !important; -webkit-text-fill-color: #66709A; }
[data-baseweb="select"] > div { background: rgba(255,255,255,.05) !important; border: 1px solid rgba(148,163,255,.24) !important;
  border-radius: 12px !important; min-height: 48px; color: var(--text) !important; }
[data-baseweb="select"] * { color: var(--text) !important; }
[data-baseweb="select"] svg { fill: var(--muted) !important; }
[data-baseweb="popover"], [data-baseweb="popover"] > div, [data-baseweb="menu"], ul[role="listbox"] { background: #0F1424 !important; border-radius: 12px; }
[data-baseweb="popover"] li { color: var(--text) !important; background: transparent !important; }
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] li[aria-selected="true"] { background: rgba(34,228,255,.12) !important; }

[data-testid="stFileUploaderDropzone"] { background: rgba(34,228,255,.04) !important; border: 1.5px dashed rgba(34,228,255,.45) !important; border-radius: 14px !important; }
[data-testid="stFileUploaderDropzone"] *, [data-testid="stFileUploader"] small { color: #AEB9DD !important; }
[data-testid="stFileUploaderFile"] * { color: var(--text) !important; }

/* ── Buttons ── */
.stButton > button, .stDownloadButton > button, [data-testid="stFileUploaderDropzone"] button {
  border-radius: 12px; font-weight: 600; min-height: 48px;
}
button[kind="secondary"], button[data-testid="stBaseButton-secondary"] {
  background: rgba(255,255,255,.05) !important; color: var(--text) !important; border: 1px solid rgba(148,163,255,.28) !important;
}
button[kind="secondary"]:hover, button[data-testid="stBaseButton-secondary"]:hover { border-color: var(--cyan) !important; color: var(--cyan) !important; }
button[kind="secondary"] *, button[data-testid="stBaseButton-secondary"] * { color: inherit !important; }
button[kind="primary"], button[data-testid="stBaseButton-primary"] {
  background: linear-gradient(90deg, #06B6D4, #7C3AED) !important; color: #fff !important; border: none !important;
  box-shadow: 0 0 28px rgba(34,228,255,.38), 0 10px 26px rgba(124,58,237,.38);
}
button[kind="primary"] *, button[data-testid="stBaseButton-primary"] * { color: #fff !important; }
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover { filter: brightness(1.12); }

/* ── Checklist (replaces the default red checkbox) ── */
.stCheckbox label p { font-size: 1rem !important; line-height: 1.55; color: var(--text) !important; }
.stCheckbox span[data-baseweb="checkbox"] > div:first-child { background: transparent !important; border: 1.5px solid rgba(148,163,255,.5) !important; }
.stCheckbox label:has(input:checked) span[data-baseweb="checkbox"] > div:first-child { background: var(--emerald) !important; border-color: var(--emerald) !important; }
.stCheckbox label:has(input:checked) svg { color: #04121A !important; fill: #04121A !important; }
.stCheckbox label:has(input:checked) p { color: #8892B0 !important; text-decoration: line-through; text-decoration-color: rgba(136,146,176,.6); }

/* ── Chat ── */
div[data-testid="stColumn"]:has(.st-key-card_chat) { position: sticky; top: 1rem; align-self: flex-start; }
.st-key-card_chat { padding-bottom: 1rem; }
[data-testid="stChatMessage"] { background: rgba(255,255,255,.045) !important; border: 1px solid var(--line); border-radius: 14px; color: var(--text); }
[data-testid="stChatInput"], [data-testid="stChatInput"] > div { background: rgba(255,255,255,.05) !important; border-radius: 14px !important; border-color: rgba(148,163,255,.24) !important; }
[data-testid="stChatInput"]:focus-within, [data-testid="stChatInput"] > div:focus-within { border-color: var(--cyan) !important; box-shadow: 0 0 0 3px rgba(34,228,255,.15) !important; }
[data-testid="stChatInput"] textarea { color: var(--text) !important; -webkit-text-fill-color: var(--text); background: transparent !important; }
[data-testid="stChatInput"] textarea::placeholder { color: #66709A !important; -webkit-text-fill-color: #66709A; }
[data-testid="stChatInput"] button { background: transparent !important; box-shadow: none !important; }
[data-testid="stChatInput"] svg { fill: var(--cyan) !important; }
[data-testid="stVerticalBlockBorderWrapper"] { border-color: rgba(148,163,255,.12) !important; }
.thinking { display: flex; align-items: center; gap: .35rem; color: var(--muted); font-size: .92rem; }
.thinking i { width: 7px; height: 7px; border-radius: 50%; background: var(--cyan); animation: pulse 1s ease-in-out infinite; }
.thinking i:nth-child(2) { animation-delay: .2s; } .thinking i:nth-child(3) { animation-delay: .4s; }

/* ── Expander ── */
[data-testid="stExpander"] { background: var(--glass) !important; border: 1px solid var(--line) !important; border-radius: 16px !important; }
[data-testid="stExpander"] details, [data-testid="stExpander"] summary { background: transparent !important; color: var(--text) !important; }
[data-testid="stExpander"] summary p, [data-testid="stExpander"] summary svg { color: var(--text) !important; font-weight: 600; }

.disclaimer { color: #5B6486; font-size: .82rem; margin-top: 1.4rem; }
.gap { height: 1rem; }

@media (max-width: 800px) { .hero .hl { font-size: 2.3rem; } .res-title { font-size: 1.7rem; } .stp .lb { font-size: .7rem; } }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# Small UI helpers
# ══════════════════════════════════════════════════════════════
ICONS = {
    "summary": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h6"/>',
    "check": '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
    "flag": '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/>',
    "chat": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "play": '<path d="M7 4v16l13-8z" fill="currentColor"/>',
}


def icon(name, size=18):
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>'
    )


def card_header(name, title, color, badge=None):
    badge_html = f'<span class="badge">{badge}</span>' if badge else ""
    st.markdown(
        f'<div class="sec-h"><span class="ico" style="background:{color}22;color:{color};--glow:{color}55">{icon(name)}</span>'
        f'<span class="t">{title}</span>{badge_html}</div>',
        unsafe_allow_html=True,
    )


def gap():
    st.markdown('<div class="gap"></div>', unsafe_allow_html=True)


def kpi(label, value, hint, c1, c2):
    st.markdown(
        f'<div class="kpi" style="--c1:{c1};--c2:{c2}"><div class="l">{label}</div>'
        f'<div class="v">{value}</div><div class="h">{hint}&nbsp;</div></div>',
        unsafe_allow_html=True,
    )


def notice(kind, text):
    st.markdown(f'<div class="notice {kind}">{html.escape(text)}</div>', unsafe_allow_html=True)


def waveform():
    bars = "".join(
        f'<i style="--h:{20 + (i * 53) % 78}%;--d:{0.55 + ((i * 37) % 11) / 10:.2f}s;animation-delay:-{(i * 0.13) % 1.7:.2f}s"></i>'
        for i in range(60)
    )
    st.markdown(f'<div class="wave">{bars}</div>', unsafe_allow_html=True)


STEPS = ["Fetch audio", "Transcribe", "Summarize", "Extract insights", "Prepare chat"]


def stepper_html(active, finished=False):
    nodes = []
    for i, label in enumerate(STEPS):
        state = "done" if (finished or i < active) else ("active" if i == active else "todo")
        mark = "✓" if state == "done" else str(i + 1)
        nodes.append(f'<div class="stp {state}"><div class="n">{mark}</div><div class="lb">{label}</div></div>')
    return f'<div class="stepper">{"".join(nodes)}</div>'


# ══════════════════════════════════════════════════════════════
# Logic helpers
# ══════════════════════════════════════════════════════════════
def clean_youtube_url(text):
    """Return a full watch URL if the text contains a YouTube video ID, else None."""
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", text.strip())
    return f"https://www.youtube.com/watch?v={m.group(1)}" if m else None


def parse_items(text):
    if isinstance(text, (list, tuple)):
        return [str(t).strip() for t in text if str(t).strip()]
    items = []
    for line in str(text or "").splitlines():
        m = re.match(r"^\s*(?:[-*•]|\d+[.)])\s+(.*)$", line)
        if m and m.group(1).strip():
            items.append(m.group(1).strip())
    return items


def count_items(text):
    n = len(parse_items(text))
    return n or (1 if str(text or "").strip() else 0)


def friendly_error(e):
    msg = str(e)
    low = msg.lower()
    if "401" in msg or "api key" in low:
        return "The AI service rejected the API key. Add a valid key to your .env file and restart the app."
    if "ffmpeg" in low or "ffprobe" in low:
        return "ffmpeg wasn't found. Install it, then open a new terminal so it's on your PATH."
    if "404" in msg or "unable to download" in low:
        return "That link couldn't be opened. Check that the video is public and the URL is complete."
    if "reshape tensor of 0 elements" in low:
        return "An audio chunk came back empty. Try again, or use a different video."
    return msg


def run_pipeline_with_progress(source, language, label):
    t0 = time.time()
    with st.container(key="card_progress"):
        st.markdown(
            '<div class="sec-h"><span class="t">Analyzing your video</span>'
            '<span class="badge">this can take a few minutes</span></div>',
            unsafe_allow_html=True,
        )
        slot = st.empty()

        def step(i):
            slot.markdown(stepper_html(i), unsafe_allow_html=True)

        step(0)
        chunks = process_input(source)

        step(1)
        transcript = transcribe_all(chunks, language)

        step(2)
        title = generate_title(transcript)
        summary = summarize(transcript)

        step(3)
        action_items = extract_action_items(transcript)
        decisions = extract_key_decisions(transcript)
        questions = extract_questions(transcript)

        step(4)
        rag_chain = build_rag_chain(transcript)

        slot.markdown(stepper_html(len(STEPS), finished=True), unsafe_allow_html=True)

    elapsed = round(time.time() - t0)
    return {
        "id": str(int(time.time() * 1000)),
        "title": title,
        "transcript": transcript,
        "summary": summary,
        "action_items": action_items,
        "key_decisions": decisions,
        "open_questions": questions,
        "rag_chain": rag_chain,
        "meta": {"language": language, "source": label, "seconds": elapsed},
    }


def build_report(r):
    return (
        f"# {r['title']}\n\n"
        f"## Summary\n{r['summary']}\n\n"
        f"## Action items\n{r['action_items']}\n\n"
        f"## Key decisions\n{r['key_decisions']}\n\n"
        f"## Open questions\n{r['open_questions']}\n\n"
        f"## Transcript\n{r['transcript']}\n"
    )


def input_form():
    c1, c2, c3 = st.columns([3.4, 1.2, 1.3], vertical_alignment="bottom")
    with c1:
        source = st.text_input("Video link", placeholder="Paste a YouTube link", key="src")
    with c2:
        language = st.selectbox("Spoken language", ["english", "hinglish"], key="lang")
    with c3:
        go = st.button("Analyze video", type="primary", use_container_width=True, key="go")
    uploaded = st.file_uploader(
        "Or upload a video or audio file",
        type=["mp4", "mov", "mkv", "avi", "webm", "mp3", "wav", "m4a"],
        key="upl",
    )
    return source, uploaded, language, go


# ══════════════════════════════════════════════════════════════
# State
# ══════════════════════════════════════════════════════════════
st.session_state.setdefault("result", None)
st.session_state.setdefault("messages", [])
st.session_state.setdefault("pending_question", None)

# ══════════════════════════════════════════════════════════════
# Navigation bar
# ══════════════════════════════════════════════════════════════
st.markdown(
    f'<div class="nav"><div class="brand"><span class="logo">{icon("play", 16)}</span>Clip Chat</div>'
    f'<div class="live"><i></i>online</div></div>',
    unsafe_allow_html=True,
)

result = st.session_state.result

# ══════════════════════════════════════════════════════════════
# Input area
# ══════════════════════════════════════════════════════════════
if not result:
    st.markdown(
        '<div class="hero"><div class="hl">Get the full picture of any video in minutes</div>'
        '<p class="lede">Add a YouTube link or a recording. You get a clear summary, a checklist of action items, '
        "the decisions that were made, and a chat that answers from what was actually said.</p></div>",
        unsafe_allow_html=True,
    )
    waveform()
    with st.container(key="input_card"):
        source, uploaded, language, analyze = input_form()
    st.markdown(
        '<div class="support">YouTube · MP4 · MOV · MKV · WEBM · MP3 · WAV · M4A &nbsp;|&nbsp; English and Hinglish</div>',
        unsafe_allow_html=True,
    )
else:
    with st.expander("Analyze a different video"):
        source, uploaded, language, analyze = input_form()

# ══════════════════════════════════════════════════════════════
# Run
# ══════════════════════════════════════════════════════════════
if analyze:
    path, label = None, ""
    if uploaded is not None:
        suffix = os.path.splitext(uploaded.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.getbuffer())
            path = tmp.name
        label = uploaded.name
    elif source and source.strip():
        raw = source.strip()
        path = clean_youtube_url(raw) or (raw if raw.startswith("http") else None)
        label = "YouTube" if clean_youtube_url(raw) else "Web link"
        if path is None:
            notice("warn", "That doesn't look like a full video link. Paste the whole URL, starting with https://")
            st.stop()

    if not path:
        notice("warn", "Add a YouTube link or upload a file first.")
    else:
        gap()
        try:
            st.session_state.result = run_pipeline_with_progress(path, language, label)
            st.session_state.messages = []
            st.rerun()
        except Exception as e:
            notice("err", f"Couldn't process this video. {friendly_error(e)}")

# ══════════════════════════════════════════════════════════════
# Empty state: how it works
# ══════════════════════════════════════════════════════════════
if not result:
    gap()
    f1, f2, f3 = st.columns(3, gap="medium")
    feats = [
        (f1, "summary", "#22E4FF", "Understand it fast", "A concise summary and a title, so you know what the video covers without watching it."),
        (f2, "check", "#34D399", "Know what to do next", "Action items as a checklist you can tick off, plus the decisions and open questions."),
        (f3, "chat", "#A78BFA", "Ask anything", "Chat with the video and get answers based on the transcript."),
    ]
    for col, ic, color, head, body in feats:
        with col:
            st.markdown(
                f'<div class="feat"><div class="ico" style="background:{color}22;color:{color};--glow:{color}55">{icon(ic, 20)}</div>'
                f'<span class="ft">{head}</span><span class="fs">{body}</span></div>',
                unsafe_allow_html=True,
            )

# ══════════════════════════════════════════════════════════════
# Results dashboard
# ══════════════════════════════════════════════════════════════
if result:
    meta = result["meta"]
    rid = result["id"]
    words = len(result["transcript"].split())
    items = parse_items(result["action_items"])
    n_actions = count_items(result["action_items"])
    n_decisions = count_items(result["key_decisions"])
    n_questions = count_items(result["open_questions"])

    st.markdown(f'<div class="res-title">{html.escape(str(result["title"]))}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="chips"><span class="chip"><span class="dot"></span>analysis complete</span>'
        f'<span class="chip">{html.escape(meta["source"])}</span>'
        f'<span class="chip">{html.escape(meta["language"])}</span>'
        f'<span class="chip">{meta["seconds"]}s</span></div>',
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4, gap="medium")
    with k1:
        kpi("Words spoken", f"{words:,}", f"about {max(1, round(words / 200))} min to read", "#FFFFFF", "#22E4FF")
    with k2:
        kpi("Action items", n_actions, "to follow up on", "#34D399", "#22E4FF")
    with k3:
        kpi("Key decisions", n_decisions, "agreed in the video", "#A78BFA", "#F472B6")
    with k4:
        kpi("Open questions", n_questions, "still unresolved", "#FBBF24", "#F472B6")

    gap()
    main, side = st.columns([1.55, 1], gap="large")

    # ── Left: analysis ──────────────────────────────────────
    with main:
        with st.container(key="card_summary"):
            card_header("summary", "Summary", "#22E4FF")
            st.markdown(result["summary"] or "_No summary was generated._")

        gap()
        with st.container(key="card_actions"):
            done = sum(1 for i in range(len(items)) if st.session_state.get(f"chk_{rid}_{i}"))
            badge = f"{done}/{len(items)} done" if items else None
            card_header("check", "Action items", "#34D399", badge)
            if items:
                for i, it in enumerate(items):
                    st.checkbox(it, key=f"chk_{rid}_{i}")
            else:
                st.markdown(result["action_items"] or "_No action items found in this video._")

        gap()
        with st.container(key="card_decisions"):
            card_header("flag", "Key decisions", "#A78BFA")
            st.markdown(result["key_decisions"] or "_No decisions found in this video._")

        gap()
        with st.container(key="card_questions"):
            card_header("help", "Open questions", "#FBBF24")
            st.markdown(result["open_questions"] or "_No open questions found in this video._")

    # ── Right: chat ─────────────────────────────────────────
    with side:
        with st.container(key="card_chat"):
            card_header("chat", "Ask this video", "#67E8F9")
            st.markdown('<div class="sec-note">Answers come from what was said in the video.</div>', unsafe_allow_html=True)

            msg_box = st.container(height=430)
            typed = st.chat_input("Ask a question about the video", key="chat_in")
            question = typed or st.session_state.pending_question
            st.session_state.pending_question = None

            with msg_box:
                if not st.session_state.messages and not question:
                    st.caption("Try one of these")
                    for text in ["What are the main points?", "Who is responsible for what?", "What was decided?"]:
                        if st.button(text, key=f"sugg_{text}", use_container_width=True):
                            st.session_state.pending_question = text
                            st.rerun()

                for m in st.session_state.messages:
                    with st.chat_message(m["role"]):
                        st.markdown(m["content"])

                if question:
                    st.session_state.messages.append({"role": "user", "content": question})
                    with st.chat_message("user"):
                        st.markdown(question)
                    with st.chat_message("assistant"):
                        slot = st.empty()
                        slot.markdown(
                            '<div class="thinking"><i></i><i></i><i></i>&nbsp;Searching the transcript</div>',
                            unsafe_allow_html=True,
                        )
                        try:
                            answer = ask_question(result["rag_chain"], question)
                        except Exception as e:
                            answer = f"I couldn't answer that. {friendly_error(e)}"
                        slot.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})

    # ── Footer: transcript and export ───────────────────────
    gap()
    with st.expander("Full transcript"):
        st.markdown(result["transcript"])

    gap()
    b1, b2, _ = st.columns([1.3, 1, 3])
    with b1:
        st.download_button(
            "Download report",
            data=build_report(result),
            file_name="video_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with b2:
        if st.button("Start over", use_container_width=True):
            st.session_state.result = None
            st.session_state.messages = []
            st.rerun()

    st.markdown(
        '<div class="disclaimer">Transcripts and summaries are generated by AI. Check anything important against the video.</div>',
        unsafe_allow_html=True,
    )