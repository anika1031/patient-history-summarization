import streamlit as st
import requests
import time

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
API = "http://localhost:8000"

st.set_page_config(
    page_title="DMH · Clinical Intelligence",
    page_icon="⚕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────
for key, default in {
    "dark_mode": True,
    "current_patient": None,
    "query_result": None,
    "summary_result": None,
    "med_result": None,
    "upload_result": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

DM = st.session_state.dark_mode

# ─────────────────────────────────────────
# THEME TOKENS
# ─────────────────────────────────────────
if DM:
    T = {
        "bg_page":       "#070B10",
        "bg_sidebar":    "#0A0F16",
        "bg_card":       "#0E1520",
        "bg_elevated":   "#121A27",
        "bg_input":      "#0D1421",
        "bg_hover":      "#172130",
        "border":        "#1C2A3A",
        "border_mid":    "#243549",
        "border_bright": "#2E4560",
        "accent":        "#22D3A8",
        "accent_dim":    "#0F9974",
        "accent_glow":   "rgba(34,211,168,0.15)",
        "accent_soft":   "rgba(34,211,168,0.07)",
        "amber":         "#FBB040",
        "amber_bg":      "rgba(251,176,64,0.10)",
        "red":           "#F06060",
        "red_bg":        "rgba(240,96,96,0.10)",
        "green":         "#34D399",
        "green_bg":      "rgba(52,211,153,0.10)",
        "blue":          "#60A5FA",
        "blue_bg":       "rgba(96,165,250,0.10)",
        "text_primary":  "#E2EAF4",
        "text_secondary":"#6B8BAE",
        "text_muted":    "#304560",
        "shadow":        "0 8px 32px rgba(0,0,0,0.5)",
        "shadow_sm":     "0 2px 8px rgba(0,0,0,0.4)",
        "scrollbar_bg":  "#0A0F16",
        "btn_fg":        "#050D08",
    }
else:
    T = {
        "bg_page":       "#F0F4F8",
        "bg_sidebar":    "#FFFFFF",
        "bg_card":       "#FFFFFF",
        "bg_elevated":   "#F7F9FC",
        "bg_input":      "#FFFFFF",
        "bg_hover":      "#EEF3F8",
        "border":        "#DDE4EE",
        "border_mid":    "#C8D4E3",
        "border_bright": "#B0C2D8",
        "accent":        "#0EA87D",
        "accent_dim":    "#09785A",
        "accent_glow":   "rgba(14,168,125,0.12)",
        "accent_soft":   "rgba(14,168,125,0.06)",
        "amber":         "#D97706",
        "amber_bg":      "rgba(217,119,6,0.08)",
        "red":           "#DC2626",
        "red_bg":        "rgba(220,38,38,0.07)",
        "green":         "#059669",
        "green_bg":      "rgba(5,150,105,0.08)",
        "blue":          "#2563EB",
        "blue_bg":       "rgba(37,99,235,0.07)",
        "text_primary":  "#0F1C2E",
        "text_secondary":"#4A6280",
        "text_muted":    "#8FA8C3",
        "shadow":        "0 4px 24px rgba(15,28,46,0.08)",
        "shadow_sm":     "0 1px 6px rgba(15,28,46,0.06)",
        "scrollbar_bg":  "#F0F4F8",
        "btn_fg":        "#FFFFFF",
    }

# ─────────────────────────────────────────
# MASTER CSS
# ─────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}
html, body, [class*="css"] {{
    font-family: 'Plus Jakarta Sans', -apple-system, sans-serif !important;
    background: {T['bg_page']} !important;
    color: {T['text_primary']} !important;
}}
#MainMenu, footer, header, .stDeployButton, [data-testid="stToolbar"] {{ display: none !important; }}
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {T['scrollbar_bg']}; }}
::-webkit-scrollbar-thumb {{ background: {T['border_bright']}; border-radius: 6px; }}
.main, .main > div {{ background: {T['bg_page']} !important; }}
.main .block-container {{
    background: {T['bg_page']} !important;
    padding: 1.75rem 2.25rem 3rem !important;
    max-width: 100% !important;
}}

/* SIDEBAR */
[data-testid="stSidebar"] {{
    background: {T['bg_sidebar']} !important;
    border-right: 1px solid {T['border']} !important;
    min-width: 258px !important; max-width: 258px !important;
}}
[data-testid="stSidebar"] > div:first-child {{ padding: 0 !important; background: {T['bg_sidebar']} !important; }}
[data-testid="stSidebar"] .stRadio > label {{ display: none !important; }}
[data-testid="stSidebar"] .stRadio > div {{ gap: 2px !important; display: flex !important; flex-direction: column !important; }}
[data-testid="stSidebar"] .stRadio label {{
    display: flex !important; align-items: center !important;
    padding: 10px 18px !important; border-radius: 10px !important;
    font-size: 13.5px !important; font-weight: 500 !important;
    color: {T['text_secondary']} !important; cursor: pointer !important;
    transition: all 0.18s ease !important; margin: 1px 8px !important;
    border: 1px solid transparent !important;
}}
[data-testid="stSidebar"] .stRadio label:hover {{
    background: {T['bg_hover']} !important; color: {T['text_primary']} !important;
    border-color: {T['border']} !important;
}}
[data-testid="stSidebar"] .stRadio > div > label:has(input:checked) {{
    background: {T['accent_glow']} !important; color: {T['accent']} !important;
    border-color: {T['accent_soft']} !important; font-weight: 600 !important;
}}

/* INPUTS */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {{
    background: {T['bg_input']} !important; border: 1.5px solid {T['border_mid']} !important;
    border-radius: 11px !important; color: {T['text_primary']} !important;
    font-family: 'JetBrains Mono', monospace !important; font-size: 13px !important;
    padding: 11px 15px !important; transition: all 0.2s ease !important;
    box-shadow: {T['shadow_sm']} !important; outline: none !important;
}}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: {T['accent']} !important;
    box-shadow: 0 0 0 3px {T['accent_glow']}, {T['shadow_sm']} !important;
}}
.stTextInput > div > div > input::placeholder,
.stTextArea > div > div > textarea::placeholder {{ color: {T['text_muted']} !important; font-style: italic !important; }}
.stTextInput > label, .stTextArea > label, .stSelectbox > label {{
    color: {T['text_secondary']} !important; font-size: 11px !important; font-weight: 700 !important;
    text-transform: uppercase !important; letter-spacing: 0.1em !important; margin-bottom: 5px !important;
}}
.stSelectbox > div > div {{
    background: {T['bg_input']} !important; border: 1.5px solid {T['border_mid']} !important;
    border-radius: 11px !important; color: {T['text_primary']} !important;
    font-family: 'JetBrains Mono', monospace !important; font-size: 13px !important;
    box-shadow: {T['shadow_sm']} !important;
}}
.stSelectbox > div > div:focus-within {{ border-color: {T['accent']} !important; box-shadow: 0 0 0 3px {T['accent_glow']} !important; }}
[data-baseweb="select"] span {{ color: {T['text_primary']} !important; }}
[data-baseweb="popover"], [data-baseweb="menu"] {{
    background: {T['bg_card']} !important; border: 1px solid {T['border_mid']} !important;
    border-radius: 11px !important; box-shadow: {T['shadow']} !important;
}}
[role="option"] {{ background: transparent !important; color: {T['text_primary']} !important; font-family: 'JetBrains Mono', monospace !important; font-size: 13px !important; }}
[role="option"]:hover {{ background: {T['bg_hover']} !important; }}

/* BUTTONS */
.stButton > button {{
    font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 600 !important;
    font-size: 12.5px !important; border-radius: 10px !important; padding: 9px 22px !important;
    transition: all 0.2s ease !important; border: 1.5px solid {T['border_mid']} !important;
    background: {T['bg_elevated']} !important; color: {T['text_secondary']} !important;
    box-shadow: {T['shadow_sm']} !important;
}}
.stButton > button:hover {{
    background: {T['bg_hover']} !important; color: {T['text_primary']} !important;
    border-color: {T['border_bright']} !important; transform: translateY(-1px) !important; box-shadow: {T['shadow']} !important;
}}
.stButton > button:active {{ transform: translateY(0) scale(0.98) !important; }}
.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {T['accent']}, {T['accent_dim']}) !important;
    color: {T['btn_fg']} !important; border: none !important; font-weight: 700 !important;
    box-shadow: 0 4px 18px {T['accent_glow']} !important;
}}
.stButton > button[kind="primary"]:hover {{
    filter: brightness(1.1) !important; box-shadow: 0 6px 28px {T['accent_glow']} !important;
    transform: translateY(-2px) !important;
}}

/* FILE UPLOADER */
[data-testid="stFileUploader"] {{
    background: {T['bg_elevated']} !important; border: 2px dashed {T['border_mid']} !important;
    border-radius: 14px !important;
}}
[data-testid="stFileUploader"]:hover {{ border-color: {T['accent_dim']} !important; }}
[data-testid="stFileUploaderDropzoneInstructions"] p,
[data-testid="stFileUploader"] label,
[data-testid="stFileUploaderDropzone"] small {{ color: {T['text_secondary']} !important; }}

.stSpinner > div {{ border-top-color: {T['accent']} !important; }}
.stAlert {{
    background: {T['bg_elevated']} !important; border: 1px solid {T['border_mid']} !important;
    border-radius: 10px !important; color: {T['text_primary']} !important;
}}

/* ═══ CUSTOM COMPONENTS ═══ */

.page-header {{
    display: flex; align-items: flex-end; justify-content: space-between;
    margin-bottom: 2rem; padding-bottom: 1.25rem; border-bottom: 1px solid {T['border']};
}}
.page-eyebrow {{
    font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.18em;
    color: {T['accent']}; font-family: 'JetBrains Mono', monospace; margin-bottom: 6px;
}}
.page-title {{ font-size: 30px; font-weight: 800; color: {T['text_primary']}; letter-spacing: -0.04em; line-height: 1.05; }}
.page-subtitle {{ font-size: 13.5px; color: {T['text_secondary']}; margin-top: 5px; font-weight: 400; letter-spacing: -0.01em; }}

.g-card {{
    background: {T['bg_card']}; border: 1px solid {T['border']}; border-radius: 18px;
    padding: 1.4rem 1.6rem; margin-bottom: 1rem; box-shadow: {T['shadow_sm']};
    position: relative; overflow: hidden;
}}
.g-card::before {{
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, {T['border_bright']}, transparent);
}}
.g-card-hdr {{
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 1.1rem; padding-bottom: 0.85rem; border-bottom: 1px solid {T['border']};
}}
.g-card-hdr-text {{
    font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em;
    color: {T['text_secondary']};
}}
.g-accent-bar {{
    width: 3px; height: 16px; background: {T['accent']}; border-radius: 3px; flex-shrink: 0;
    box-shadow: 0 0 10px {T['accent_glow']};
}}

.info-cell {{
    background: {T['bg_elevated']}; border: 1px solid {T['border']}; border-radius: 11px;
    padding: 11px 14px; transition: border-color 0.2s, transform 0.15s;
}}
.info-cell:hover {{ border-color: {T['border_bright']}; transform: translateY(-1px); }}
.cell-lbl {{ font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.14em; color: {T['text_muted']}; margin-bottom: 5px; font-family: 'JetBrains Mono', monospace; }}
.cell-val {{ font-size: 13.5px; font-weight: 600; color: {T['text_primary']}; letter-spacing: -0.01em; }}
.cell-mono {{ font-family: 'JetBrains Mono', monospace; color: {T['accent']}; font-size: 12.5px; background: {T['accent_soft']}; display: inline-block; padding: 2px 7px; border-radius: 5px; }}

.badge {{ display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 6px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; font-family: 'JetBrains Mono', monospace; margin-right: 5px; }}
.b-teal  {{ background:{T['accent_glow']}; color:{T['accent']};         border:1px solid {T['accent_soft']}; }}
.b-amber {{ background:{T['amber_bg']};    color:{T['amber']};          border:1px solid rgba(251,176,64,0.2); }}
.b-green {{ background:{T['green_bg']};    color:{T['green']};          border:1px solid rgba(52,211,153,0.2); }}
.b-blue  {{ background:{T['blue_bg']};     color:{T['blue']};           border:1px solid rgba(96,165,250,0.2); }}
.b-muted {{ background:{T['bg_elevated']}; color:{T['text_secondary']}; border:1px solid {T['border_mid']}; }}

.answer-panel {{
    background: {T['bg_page']}; border: 1px solid {T['border_mid']};
    border-left: 3px solid {T['accent']}; border-radius: 0 13px 13px 0;
    padding: 1.3rem 1.5rem; font-size: 13px; line-height: 1.75;
    color: {T['text_primary']};
    font-family: 'Inter', sans-serif; box-shadow: {T['shadow_sm']};
}}
.answer-panel table {{
    width: 100%; border-collapse: collapse; margin: 0.5rem 0;
    font-size: 12px; font-family: 'JetBrains Mono', monospace;
}}
.answer-panel table th {{
    background: {T['accent_glow']}; color: {T['accent']};
    padding: 7px 12px; text-align: left; border: 1px solid {T['border_mid']};
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
}}
.answer-panel table td {{
    padding: 6px 12px; border: 1px solid {T['border_mid']};
    color: {T['text_primary']}; vertical-align: top;
}}
.answer-panel table tr:nth-child(even) td {{
    background: {T['bg_card']};
}}
.answer-panel p {{
    margin: 0.3rem 0; line-height: 1.75;
}}
.ans-list {{
    margin: 0.4rem 0 0.4rem 1.2rem;
    padding: 0;
    list-style: none;
}}
.ans-list li {{
    position: relative;
    padding: 0.25rem 0 0.25rem 1.2rem;
    line-height: 1.7;
    color: {T['text_primary']};
    font-size: 13px;
    border-bottom: 1px solid {T['border_mid']};
}}
.ans-list li::before {{
    content: "▸";
    position: absolute; left: 0;
    color: {T['accent']}; font-size: 11px;
}}
.ans-list li:last-child {{ border-bottom: none; }}

.q-pill {{
    display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px;
    background: {T['accent_glow']}; border: 1px solid {T['accent_soft']};
    border-radius: 20px; font-size: 10px; font-weight: 700;
    color: {T['accent']}; text-transform: uppercase; letter-spacing: 0.1em;
    font-family: 'JetBrains Mono', monospace;
}}
.q-dot {{ width:6px; height:6px; border-radius:50%; background:{T['accent']}; box-shadow:0 0 6px {T['accent']}; animation:pdot 2s ease-in-out infinite; }}
@keyframes pdot {{ 0%,100%{{opacity:1;transform:scale(1)}} 50%{{opacity:.5;transform:scale(.7)}} }}

.src-item {{
    display: flex; align-items: flex-start; gap: 12px;
    padding: 11px 14px; border: 1px solid {T['border']}; border-radius: 10px;
    margin-bottom: 7px; background: {T['bg_elevated']}; transition: all 0.18s ease;
}}
.src-item:hover {{ border-color: {T['accent_dim']}; background: {T['bg_hover']}; transform: translateX(2px); }}
.src-num {{
    width: 24px; height: 24px; border-radius: 50%; background: {T['accent_glow']};
    color: {T['accent']}; font-size: 10px; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; border: 1px solid {T['accent_soft']}; font-family: 'JetBrains Mono', monospace;
}}
.src-sec {{ font-size: 9.5px; font-weight: 700; color: {T['accent']}; text-transform: uppercase; letter-spacing: 0.1em; font-family: 'JetBrains Mono', monospace; margin-bottom: 4px; }}
.src-prev {{ font-size: 11.5px; color: {T['text_secondary']}; line-height: 1.55; font-family: 'JetBrains Mono', monospace; }}
.src-meta {{ font-size: 10px; color: {T['text_muted']}; margin-top: 4px; font-family: 'JetBrains Mono', monospace; }}

.summary-text, .med-text {{ font-size: 12.5px; line-height: 1.95; color: {T['text_primary']}; white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; padding: 0.25rem 0; }}
.feedback-bar {{ display:flex; align-items:center; gap:8px; margin:0.9rem 0; flex-wrap:wrap; }}
.s-dot {{ width:8px; height:8px; border-radius:50%; flex-shrink:0; }}
.s-online  {{ background:{T['green']};  animation:pdot 2.5s ease-in-out infinite; }}
.s-offline {{ background:{T['red']}; }}
.sb-section {{ font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:0.15em; color:{T['text_muted']}; padding:0 18px; margin:1.25rem 0 0.4rem; font-family:'JetBrains Mono',monospace; }}
.sb-patient {{
    margin: 0.75rem 12px; background:{T['bg_elevated']}; border:1px solid {T['border_mid']};
    border-radius:13px; padding:13px 14px; position:relative; overflow:hidden;
}}
.sb-patient::before {{ content:''; position:absolute; top:0; left:0; width:3px; height:100%; background:{T['accent']}; box-shadow:0 0 16px {T['accent_glow']}; }}
.sb-avatar {{ width:36px; height:36px; border-radius:50%; background:linear-gradient(135deg,{T['accent_dim']},{T['accent']}); color:{T['btn_fg']}; font-size:13px; font-weight:800; display:flex; align-items:center; justify-content:center; margin-bottom:9px; }}
.sb-name {{ font-size:13px; font-weight:700; color:{T['text_primary']}; margin-bottom:3px; }}
.sb-meta {{ font-size:10.5px; color:{T['text_secondary']}; font-family:'JetBrains Mono',monospace; line-height:1.6; }}
.sb-brand {{ display:flex; align-items:center; gap:11px; padding:1.4rem 18px 1rem; border-bottom:1px solid {T['border']}; margin-bottom:0.5rem; }}
.sb-logo {{ width:34px; height:34px; background:linear-gradient(135deg,{T['accent_dim']},{T['accent']}); border-radius:9px; display:flex; align-items:center; justify-content:center; flex-shrink:0; box-shadow:0 4px 16px {T['accent_glow']}; }}
.sb-title {{ font-size:15px; font-weight:800; color:{T['text_primary']}; letter-spacing:-0.02em; }}
.sb-tagline {{ font-size:9.5px; color:{T['text_muted']}; font-family:'JetBrains Mono',monospace; text-transform:uppercase; letter-spacing:0.1em; margin-top:1px; }}
.file-prev {{ display:flex; align-items:center; gap:10px; background:{T['accent_soft']}; border:1px solid {T['accent_glow']}; border-radius:10px; padding:10px 14px; margin:8px 0; }}
.f-name {{ font-family:'JetBrains Mono',monospace; font-size:12.5px; color:{T['text_primary']}; font-weight:500; }}
.f-size {{ font-family:'JetBrains Mono',monospace; font-size:11px; color:{T['text_muted']}; margin-left:auto; }}
.upload-ok {{ background:{T['green_bg']}; border:1px solid rgba(52,211,153,0.25); border-radius:10px; padding:11px 15px; font-size:12.5px; color:{T['green']}; margin-top:10px; font-family:'JetBrains Mono',monospace; display:flex; align-items:center; gap:8px; }}

/* ═══ STEP LOADER ═══ */
.loader-card {{
    background: {T['bg_card']}; border: 1px solid {T['border']};
    border-radius: 16px; padding: 1.2rem 1.5rem; margin-bottom: 1rem;
    box-shadow: {T['shadow_sm']};
}}
.loader-header {{
    font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em;
    color: {T['text_secondary']}; margin-bottom: 1rem; display: flex; align-items: center; gap: 8px;
    padding-bottom: 0.75rem; border-bottom: 1px solid {T['border']};
}}
.loader-header .lh-dot {{
    width: 7px; height: 7px; border-radius: 50%;
    background: {T['accent']}; animation: pdot 1.5s ease-in-out infinite;
    box-shadow: 0 0 8px {T['accent_glow']};
}}
.step-row {{
    display: flex; align-items: flex-start; gap: 14px;
    margin-bottom: 4px; position: relative;
}}
.step-row:not(:last-child)::after {{
    content: ''; position: absolute; left: 17px; top: 36px;
    width: 1px; height: calc(100% - 6px);
    background: {T['border_mid']};
}}
.step-icon {{
    width: 34px; height: 34px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; border: 1px solid {T['border_mid']};
    background: {T['bg_elevated']}; font-size: 15px;
    transition: all 0.3s ease;
}}
.step-icon.active {{
    background: {T['accent_glow']}; border-color: {T['accent_soft']};
    box-shadow: 0 0 12px {T['accent_glow']};
}}
.step-icon.done  {{ background: {T['green_bg']};  border-color: rgba(52,211,153,0.3); }}
.step-icon.error {{ background: {T['red_bg']};    border-color: rgba(240,96,96,0.3); }}
.step-body {{ padding-top: 7px; flex: 1; min-width: 0; }}
.step-title {{
    font-size: 13px; font-weight: 600; color: {T['text_secondary']};
    transition: color 0.3s; letter-spacing: -0.01em;
}}
.step-title.active {{ color: {T['accent']}; }}
.step-title.done   {{ color: {T['green']}; }}
.step-title.error  {{ color: {T['red']}; }}
.step-sub {{
    font-size: 11px; color: {T['text_muted']}; margin-top: 2px;
    font-family: 'JetBrains Mono', monospace;
}}
.spinner-ring {{
    width: 16px; height: 16px; border-radius: 50%;
    border: 2px solid {T['accent_soft']};
    border-top-color: {T['accent']};
    animation: spin 0.65s linear infinite;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
.idle-dot {{ width: 8px; height: 8px; border-radius: 50%; background: {T['border_bright']}; }}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# ANIMATED LOADER HELPERS
# ─────────────────────────────────────────

ICONS = {
    "db":       "🗄️",
    "search":   "🔍",
    "extract":  "📄",
    "render":   "🖥️",
    "classify": "🧭",
    "embed":    "🧬",
    "vector":   "⚡",
    "ai":       "🤖",
    "format":   "✅",
    "upload":   "📤",
    "chunk":    "✂️",
    "index":    "🗂️",
    "meds":     "💊",
    "safety":   "🛡️",
    "clock":    "📅",
    "compile":  "📊",
}

def render_step(icon_key, title, subtitle, state="idle"):
    """Render one step row. state = idle | active | done | error"""
    icon_char = ICONS.get(icon_key, "•")

    if state == "active":
        icon_html = f'<div class="spinner-ring"></div>'
    elif state == "done":
        icon_html = f'<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><polyline points="3,8 6.5,11.5 13,4.5" stroke="{T["green"]}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    elif state == "error":
        icon_html = f'<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><line x1="2" y1="2" x2="12" y2="12" stroke="{T["red"]}" stroke-width="2" stroke-linecap="round"/><line x1="12" y1="2" x2="2" y2="12" stroke="{T["red"]}" stroke-width="2" stroke-linecap="round"/></svg>'
    else:
        # idle — show the emoji directly in the circle
        icon_html = f'<span style="font-size:16px;line-height:1;">{icon_char}</span>'

    return f"""
    <div class="step-row">
        <div class="step-icon {state}">{icon_html}</div>
        <div class="step-body">
            <div class="step-title {state}">{title}</div>
            <div class="step-sub">{subtitle}</div>
        </div>
    </div>
    """


def loader_card(title, steps_html):
    dot = "" if "done" not in steps_html.lower() else ""
    return f"""
    <div class="loader-card">
        <div class="loader-header">
            <span class="lh-dot"></span>
            {title}
        </div>
        {steps_html}
    </div>
    """


def run_patient_loader(mrn: str):
    """
    Show animated patient-load steps, call API, return result.
    Steps: DB connect → MRN lookup → Extract record → Render card
    """
    placeholder = st.empty()
    steps = [
        ("db",      "🗄️  Connecting to database",   f"PostgreSQL · patient table"),
        ("search",  "🔍  Running MRN lookup",        f"SELECT WHERE mrn = '{mrn}'"),
        ("extract", "📄  Extracting patient record", "name, dob, gender, contact"),
        ("render",  "🖥️  Rendering patient card",    "Building UI components"),
    ]
    states = ["idle"] * len(steps)

    def draw(states):
        rows = ""
        for i, (icon, title, sub) in enumerate(steps):
            rows += render_step(icon, title, sub, states[i])
        placeholder.markdown(loader_card("🏥  Loading patient record", rows), unsafe_allow_html=True)

    draw(states)

    # Step 0 — connecting
    states[0] = "active"; draw(states); time.sleep(0.4)
    patient, err = load_patient(mrn)
    if err:
        states[0] = "error"; draw(states)
        placeholder.empty()
        return None, err
    states[0] = "done"; draw(states); time.sleep(0.2)

    # Step 1 — lookup
    states[1] = "active"; draw(states); time.sleep(0.5)
    states[1] = "done";   draw(states); time.sleep(0.2)

    # Step 2 — extract
    states[2] = "active"; draw(states); time.sleep(0.4)
    states[2] = "done";   draw(states); time.sleep(0.2)

    # Step 3 — render
    states[3] = "active"; draw(states); time.sleep(0.35)
    states[3] = "done";   draw(states); time.sleep(0.5)

    placeholder.empty()
    return patient, None


def run_query_loader(mrn: str, question: str):
    """
    Animated query loader: classify → embed → AstraDB → Nova Lite → format
    """
    placeholder = st.empty()
    steps = [
        ("classify", "🧭  Classifying query",          "RDBMS vs Vector routing"),
        ("embed",    "🧬  Generating embedding",        "Encoding clinical question"),
        ("vector",   "⚡  Searching AstraDB",           "Top-3 vector similarity"),
        ("ai",       "🤖  Analysing with Nova Lite",    "AWS Bedrock inference"),
        ("format",   "✅  Formatting clinical answer",  "Structured output"),
    ]
    states = ["idle"] * len(steps)

    def draw(states):
        rows = ""
        for i, (icon, title, sub) in enumerate(steps):
            rows += render_step(icon, title, sub, states[i])
        placeholder.markdown(loader_card("🔬  Processing clinical query", rows), unsafe_allow_html=True)

    draw(states)

    # Step 0 — classify (fast, local)
    states[0] = "active"; draw(states); time.sleep(0.35)
    states[0] = "done";   draw(states); time.sleep(0.15)

    # Step 1 — embed (fast)
    states[1] = "active"; draw(states); time.sleep(0.5)
    states[1] = "done";   draw(states); time.sleep(0.15)

    # Step 2 — AstraDB search (network)
    states[2] = "active"; draw(states); time.sleep(0.4)

    # Step 3 — Nova Lite (do actual API call here, longest step)
    states[2] = "done"; states[3] = "active"; draw(states)
    result, err = query_api(mrn, question)
    if err:
        states[3] = "error"; draw(states); time.sleep(0.5)
        placeholder.empty()
        return None, err
    states[3] = "done"; draw(states); time.sleep(0.2)

    # Step 4 — format
    states[4] = "active"; draw(states); time.sleep(0.35)
    states[4] = "done";   draw(states); time.sleep(0.5)

    placeholder.empty()
    return result, None


def run_summary_loader(mrn: str, time_range: str):
    """Animated loader for time-based summary."""
    placeholder = st.empty()
    steps = [
        ("clock",   "📅  Fetching clinical records",     f"MRN: {mrn} · {time_range}"),
        ("extract", "📂  Selecting priority sections",    "Diagnosis, Meds, Follow-up"),
        ("ai",      "🤖  Summarising with Nova Lite",     "AWS Bedrock inference"),
        ("compile", "📊  Compiling chronological view",   "Structured timeline"),
    ]
    states = ["idle"] * len(steps)

    def draw(s):
        rows = "".join(render_step(icon, title, sub, s[i]) for i, (icon, title, sub) in enumerate(steps))
        placeholder.markdown(loader_card("Generating clinical summary", rows), unsafe_allow_html=True)

    draw(states)
    states[0] = "active"; draw(states); time.sleep(0.4)
    states[0] = "done";   draw(states); time.sleep(0.2)
    states[1] = "active"; draw(states); time.sleep(0.45)
    states[1] = "done";   draw(states); time.sleep(0.2)
    states[2] = "active"; draw(states)
    result, err = time_summary_api(mrn, time_range)
    if err:
        states[2] = "error"; draw(states); time.sleep(0.5)
        placeholder.empty()
        return None, err
    states[2] = "done"; draw(states); time.sleep(0.2)
    states[3] = "active"; draw(states); time.sleep(0.35)
    states[3] = "done";   draw(states); time.sleep(0.5)
    placeholder.empty()
    return result, None


def run_medication_loader(mrn: str):
    """Animated loader for medication safety check."""
    placeholder = st.empty()
    steps = [
        ("meds",   "💊  Locating medication records",   f"Vector search · MRN: {mrn}"),
        ("extract","📋  Extracting discharge meds",      "DISCHARGE MEDICATIONS section"),
        ("ai",     "🤖  Running safety analysis",        "Nova Lite drug interaction check"),
        ("safety", "🛡️  Generating safety report",       "Flagging high-risk drugs"),
    ]
    states = ["idle"] * len(steps)

    def draw(s):
        rows = "".join(render_step(icon, title, sub, s[i]) for i, (icon, title, sub) in enumerate(steps))
        placeholder.markdown(loader_card("💊  Running medication safety check", rows), unsafe_allow_html=True)

    draw(states)
    states[0] = "active"; draw(states); time.sleep(0.4)
    states[0] = "done";   draw(states); time.sleep(0.2)
    states[1] = "active"; draw(states); time.sleep(0.45)
    states[1] = "done";   draw(states); time.sleep(0.2)
    states[2] = "active"; draw(states)
    result, err = medication_api(mrn)
    if err:
        states[2] = "error"; draw(states); time.sleep(0.5)
        placeholder.empty()
        return None, err
    states[2] = "done"; draw(states); time.sleep(0.2)
    states[3] = "active"; draw(states); time.sleep(0.35)
    states[3] = "done";   draw(states); time.sleep(0.5)
    placeholder.empty()
    return result, None


def run_upload_loader(mrn: str, file_bytes, filename: str):
    """Animated loader for PDF upload & indexing."""
    placeholder = st.empty()
    steps = [
        ("upload",  "📤  Uploading PDF to server",        filename),
        ("extract", "📄  Extracting text from PDF",        "pdfplumber / pdfminer"),
        ("chunk",   "✂️  Chunking by clinical sections",   "Section-based splitter"),
        ("embed",   "🧬  Generating section embeddings",   "Embedding each chunk"),
        ("index",   "🗂️  Indexing into AstraDB",           f"patient_chunks · MRN: {mrn}"),
    ]
    states = ["idle"] * len(steps)

    def draw(s):
        rows = "".join(render_step(icon, title, sub, s[i]) for i, (icon, title, sub) in enumerate(steps))
        placeholder.markdown(loader_card("  Uploading & indexing clinical record", rows), unsafe_allow_html=True)

    draw(states)
    for i in range(2):
        states[i] = "active"; draw(states); time.sleep(0.4)
        states[i] = "done";   draw(states); time.sleep(0.2)

    states[2] = "active"; draw(states)
    result, err = upload_pdf_api(mrn, file_bytes, filename)
    if err:
        states[2] = "error"; draw(states); time.sleep(0.5)
        placeholder.empty()
        return None, err
    states[2] = "done"; draw(states); time.sleep(0.2)

    for i in range(3, 5):
        states[i] = "active"; draw(states); time.sleep(0.4)
        states[i] = "done";   draw(states); time.sleep(0.2)

    time.sleep(0.4)
    placeholder.empty()
    return result, None


# ─────────────────────────────────────────
# API HELPERS
# ─────────────────────────────────────────
def api_status():
    try:
        return requests.get(f"{API}/", timeout=3).ok
    except:
        return False

def load_patient(mrn):
    try:
        r = requests.get(f"{API}/api/patient/{mrn}", timeout=10)
        return (r.json(), None) if r.ok else (None, r.json().get("detail","Patient not found."))
    except Exception as e:
        return None, f"Cannot connect to API: {e}"

def query_api(mrn, question):
    try:
        r = requests.post(f"{API}/api/query", json={"mrn": mrn, "question": question}, timeout=120)
        return (r.json(), None) if r.ok else (None, r.json().get("detail","Query failed."))
    except Exception as e:
        return None, str(e)

def time_summary_api(mrn, time_range):
    try:
        r = requests.post(f"{API}/api/time_summary", json={"mrn": mrn, "time_range": time_range}, timeout=300)
        return (r.json(), None) if r.ok else (None, r.json().get("detail","Failed."))
    except Exception as e:
        return None, str(e)

def medication_api(mrn):
    try:
        r = requests.post(f"{API}/api/medication_safety", json={"mrn": mrn}, timeout=120)
        return (r.json(), None) if r.ok else (None, r.json().get("detail","Failed."))
    except Exception as e:
        return None, str(e)

def upload_pdf_api(mrn, file_bytes, filename):
    try:
        r = requests.post(f"{API}/api/upload?mrn={mrn}",
                          files={"file": (filename, file_bytes, "application/pdf")}, timeout=120)
        return (r.json(), None) if r.ok else (None, r.json().get("detail","Upload failed."))
    except Exception as e:
        return None, str(e)


# ─────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────
with st.sidebar:
    icon_color = T['btn_fg']
    st.markdown(f"""
    <div class="sb-brand">
        <div class="sb-logo">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none"
                 stroke="{icon_color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
            </svg>
        </div>
        <div>
            <div class="sb-title">DMH</div>
            <div class="sb-tagline">Clinical Intelligence</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    online = api_status()
    st.markdown(f"""
    <div style="padding:0 18px 12px;">
        <div style="display:flex;align-items:center;gap:8px;padding:6px 0;">
            <span class="s-dot {'s-online' if online else 's-offline'}"></span>
            <span style="font-size:12.5px;font-weight:600;color:{T['text_primary']};">
                {'API Connected' if online else 'API Offline'}
            </span>
        </div>
        <div style="font-size:10px;color:{T['text_muted']};font-family:'JetBrains Mono',monospace;padding-left:16px;">localhost:8000</div>
    </div>
    """, unsafe_allow_html=True)

   

    st.markdown('<div class="sb-section">Navigation</div>', unsafe_allow_html=True)
    tab = st.radio("nav",
        ["⚕   Patient Query","📅   Time Summary","💊   Medication Safety","📤   Upload Records"],
        label_visibility="collapsed", key="nav_tab")

    if st.session_state.current_patient:
        p = st.session_state.current_patient
        initials = "".join(w[0] for w in (p.get("name") or "?").split()[:2]).upper()
        st.markdown('<div class="sb-section">Active Patient</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="sb-patient">
            <div class="sb-avatar">{initials}</div>
            <div class="sb-name">{p.get('name','–')}</div>
            <div class="sb-meta">{p.get('mrn','–')} · {p.get('gender') or '–'}</div>
            <div class="sb-meta">{str(p.get('birth_date') or '–')}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="position:absolute;bottom:1.25rem;left:0;right:0;padding:12px 18px 0;border-top:1px solid {T['border']};">
       
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# PAGE HEADER
# ─────────────────────────────────────────
mode_badge = f'<span class="badge b-teal"></span>' if DM else f'<span class="badge b-muted"></span>'
st.markdown(f"""
<div class="page-header">
    <div>
        <div class="page-eyebrow">⚕️ Patient History Summarization System</div>
        <div class="page-title">Clinical Intelligence</div>
        <div class="page-subtitle">AI-powered medical record analysis</div>
    </div>
   
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# TAB 1 — PATIENT QUERY
# ─────────────────────────────────────────
if tab == "⚕   Patient Query":

    st.markdown(f"""
    <div class="g-card">
        <div class="g-card-hdr">
            <span class="g-accent-bar"></span>
            <span class="g-card-hdr-text"> Patient Identification</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        mrn_input = st.text_input("Medical Record Number", placeholder="e.g. MRN-010 or 010", key="q_mrn")
    with col2:
        st.markdown("<div style='height:29px'></div>", unsafe_allow_html=True)
        load_btn = st.button("🔍 Load Patient", type="primary", use_container_width=True, key="load_btn")

    if load_btn and mrn_input.strip():
        patient, err = run_patient_loader(mrn_input.strip())
        if patient:
            st.session_state.current_patient = patient
            st.rerun()
        else:
            st.error(err)

    if st.session_state.current_patient:
        p = st.session_state.current_patient
        c1, c2, c3, c4, c5 = st.columns(5)
        data = [
            (" Name",          p.get("name","–"),                                               False),
            (" MRN",           p.get("mrn","–"),                                                True),
            (" Date of Birth", str(p.get("birth_date","–")) if p.get("birth_date") else "–",   False),
            (" Gender",        p.get("gender","–"),                                             False),
            (" Last Encounter",p.get("last_encounter","–"),                                     False),
        ]
        for col, (lbl, val, mono) in zip([c1,c2,c3,c4,c5], data):
            v = f'<div class="cell-mono">{val}</div>' if mono else f'<div class="cell-val">{val}</div>'
            col.markdown(f'<div class="info-cell"><div class="cell-lbl">{lbl}</div>{v}</div>', unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    st.markdown(f"""
    <div class="g-card">
        <div class="g-card-hdr">
            <span class="g-accent-bar"></span>
            <span class="g-card-hdr-text"> Natural Language Query</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    question = st.text_area("🩺 Clinical Question",
        placeholder="e.g. What medications was the patient discharged with?\nWhat were the chief complaints on admission?\nAny red flag signs documented?",
        height=105, key="q_question")

    ca, cb, _ = st.columns([1.5, 1, 5])
    with ca:
        ask_btn = st.button("Run Query", type="primary", use_container_width=True, key="ask_btn")
    with cb:
        if st.button(" Clear", use_container_width=True, key="clear_btn"):
            st.session_state.query_result = None
            st.rerun()

    if ask_btn:
        mrn = (st.session_state.current_patient or {}).get("mrn") or mrn_input.strip()
        if not mrn:
            st.warning("Please load a patient first.")
        elif not question.strip():
            st.warning("Please enter a clinical question.")
        else:
            result, err = run_query_loader(mrn, question.strip())
            if result:
                st.session_state.query_result = result
                st.rerun()
            else:
                st.error(err)

    if st.session_state.query_result:
        r = st.session_state.query_result
        qtype = r.get("query_type","VECTOR")
        strategy = "RDBMS Only" if qtype == "RDBMS" else "AstraDB → Nova Lite"

        st.markdown(f"""
        <div class="feedback-bar">
            <span class="q-pill"><span class="q-dot"></span>⚙️ {qtype}</span>
            <span class="badge b-muted"> {strategy}</span>
            <span class="badge b-green"> Resolved</span>
        </div>
        """, unsafe_allow_html=True)

        # ── Format answer: convert • bullets and markdown tables to HTML ──
        def format_answer_html(text: str) -> str:
            import re
            text = text.strip()

            # ── Handle markdown tables ──────────────────────────────────
            def md_table_to_html(match):
                lines = match.group(0).strip().split("\n")
                headers = [c.strip() for c in lines[0].strip("|").split("|")]
                # skip separator line (lines[1])
                rows    = []
                for line in lines[2:]:
                    cells = [c.strip() for c in line.strip("|").split("|")]
                    rows.append(cells)
                th = "".join(f"<th>{h}</th>" for h in headers)
                trs = ""
                for row in rows:
                    tds = "".join(f"<td>{c}</td>" for c in row)
                    trs += f"<tr>{tds}</tr>"
                return f'<table class="ans-table"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'

            table_pattern = r'(\|.+\|\n)(\|[-| :]+\|\n)((?:\|.+\|\n?)+)'
            text = re.sub(table_pattern, md_table_to_html, text)

            # ── Handle • bullet lines → <ul><li> ───────────────────────
            lines = text.split("\n")
            out   = []
            in_ul = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("•") or stripped.startswith("-"):
                    content = stripped.lstrip("•").lstrip("-").strip()
                    if not in_ul:
                        out.append("<ul class='ans-list'>")
                        in_ul = True
                    out.append(f"<li>{content}</li>")
                else:
                    if in_ul:
                        out.append("</ul>")
                        in_ul = False
                    if stripped:
                        out.append(f"<p>{stripped}</p>")
            if in_ul:
                out.append("</ul>")
            return "\n".join(out)

        answer_html = format_answer_html(r.get("answer", "No answer returned."))

        st.markdown(f"""
        <div class="g-card">
            <div class="g-card-hdr">
                <span class="g-accent-bar"></span>
                <span class="g-card-hdr-text">🧠 Clinical Answer</span>
                <span style="margin-left:auto;" class="badge b-teal">🤖 AI Analysis</span>
            </div>
            <div class="answer-panel">{answer_html}</div>
        </div>
        """, unsafe_allow_html=True)




# ─────────────────────────────────────────
# TAB 2 — TIME SUMMARY
# ─────────────────────────────────────────
elif tab == "📅   Time Summary":

    st.markdown(f"""
    <div class="g-card">
        <div class="g-card-hdr">
            <span class="g-accent-bar"></span>
            <span class="g-card-hdr-text">⚙️ Chronological Summary Configuration</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([2, 2, 1.5])
    with c1:
        summary_mrn = st.text_input("🪪 Patient MRN",
            value=(st.session_state.current_patient or {}).get("mrn",""),
            placeholder="e.g. 010", key="s_mrn")
    with c2:
        time_range = st.selectbox("📆 Time Range",
            ["Last 1 Month","Last 3 Months","Last 6 Months","Last 1 Year"], index=2)
    with c3:
        st.markdown("<div style='height:29px'></div>", unsafe_allow_html=True)
        if st.button("📊 Generate Summary", type="primary", use_container_width=True, key="gen_btn"):
            if not summary_mrn.strip():
                st.warning("⚠️ Please enter a MRN.")
            else:
                result, err = run_summary_loader(summary_mrn.strip(), time_range)
                if result:
                    st.session_state.summary_result = result
                    st.rerun()
                else:
                    st.error(err)

    if st.session_state.summary_result:
        r = st.session_state.summary_result
        st.markdown(f"""
        <div class="g-card">
            <div class="g-card-hdr">
                <span class="g-accent-bar"></span>
                <span class="g-card-hdr-text">📋 Chronological Summary</span>
                <span style="margin-left:auto;" class="badge b-teal">📅 {r.get("time_range","")}</span>
                <span class="badge b-blue">🤖 Nova Lite</span>
            </div>
            <div class="summary-text">{r.get("summary","–")}</div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# TAB 3 — MEDICATION SAFETY
# ─────────────────────────────────────────
elif tab == "💊   Medication Safety":

    st.markdown(f"""
    <div class="g-card">
        <div class="g-card-hdr">
            <span class="g-accent-bar"></span>
            <span class="g-card-hdr-text">💊 Medication Safety Check</span>
            <span style="margin-left:auto;" class="badge b-amber">⚠️ Clinical Review</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([3,1])
    with c1:
        med_mrn = st.text_input("🪪 Patient MRN",
            value=(st.session_state.current_patient or {}).get("mrn",""),
            placeholder="e.g. 010", key="m_mrn")
    with c2:
        st.markdown("<div style='height:29px'></div>", unsafe_allow_html=True)
        if st.button("🛡️ Run Safety Check", type="primary", use_container_width=True, key="med_btn"):
            if not med_mrn.strip():
                st.warning("⚠️ Please enter a MRN.")
            else:
                result, err = run_medication_loader(med_mrn.strip())
                if result:
                    st.session_state.med_result = result
                    st.rerun()
                else:
                    st.error(err)

    if st.session_state.med_result:
        r = st.session_state.med_result
        chunks_used = r.get("context_chunks_used", 0)
        interactions_raw = r.get("interactions_raw","")
        danger_keywords = ["high risk", "risk", "concern", "caution", "interaction", "contraindicated"] 
        has_interaction = any(k in interactions_raw.lower() for k in danger_keywords)
        int_badge = f'<span class="badge b-amber">⚠️ Review Required</span>' if has_interaction else f'<span class="badge b-green"> Clear</span>'

        c_med, c_int = st.columns(2)
        with c_med:
            st.markdown(f"""
            <div class="g-card">
                <div class="g-card-hdr">
                    <span class="g-accent-bar"></span>
                    <span class="g-card-hdr-text">💊 Medications Detected</span>
                    <span style="margin-left:auto;" class="badge b-muted">📦 {chunks_used} chunks</span>
                </div>
                <div class="med-text">{r.get("medications_raw","–")}</div>
            </div>
            """, unsafe_allow_html=True)
        with c_int:
            st.markdown(f"""
            <div class="g-card">
                <div class="g-card-hdr">
                    <span class="g-accent-bar"></span>
                    <span class="g-card-hdr-text"> Interaction Analysis</span>
                    <span style="margin-left:auto;">{int_badge}</span>
                </div>
                <div class="med-text">{interactions_raw or "–"}</div>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# TAB 4 — UPLOAD RECORDS
# ─────────────────────────────────────────
elif tab == "📤   Upload Records":

    st.markdown(f"""
    <div class="g-card">
        <div class="g-card-hdr">
            <span class="g-accent-bar"></span>
            <span class="g-card-hdr-text">📤 Upload Discharge Summary</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    upload_mrn = st.text_input("🪪 Patient MRN (required)",
        value=(st.session_state.current_patient or {}).get("mrn",""),
        placeholder="e.g. 010 or MRN-010", key="u_mrn")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader(" Drop a PDF discharge summary or clinical note here",
                                     type=["pdf"], label_visibility="visible")

    if uploaded_file:
        kb = uploaded_file.size / 1024
        st.markdown(f"""
        <div class="file-prev">
            <span style="font-size:16px;">📄</span>
            <span class="f-name">{uploaded_file.name}</span>
            <span class="f-size">💾 {kb:.1f} KB</span>
        </div>
        """, unsafe_allow_html=True)

    if st.button("📤 Upload & Index", type="primary", disabled=(uploaded_file is None), key="upload_btn"):
        if not upload_mrn.strip():
            st.warning("⚠️ Please enter a MRN.")
        elif uploaded_file is None:
            st.warning("⚠️ Please select a PDF file.")
        else:
            file_bytes = uploaded_file.read()
            result, err = run_upload_loader(upload_mrn.strip(), file_bytes, uploaded_file.name)
            if result:
                st.session_state.upload_result = result
                st.rerun()
            else:
                st.error(err)

    if st.session_state.upload_result:
        r = st.session_state.upload_result
        st.markdown(f"""
        <div class="g-card" style="border-color:rgba(52,211,153,0.3);">
            <div class="g-card-hdr" style="border-color:rgba(52,211,153,0.15);">
                <span style="width:3px;height:16px;background:{T['green']};border-radius:3px;flex-shrink:0;display:inline-block;"></span>
                <span class="g-card-hdr-text" style="color:{T['green']};">Upload Successful</span>
                <span style="margin-left:auto;" class="badge b-green">Indexed</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px;">
                <div class="info-cell">
                    <div class="cell-lbl">Filename</div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:11.5px;color:{T['text_primary']};font-weight:500;">{r.get("filename","–")}</div>
                </div>
                <div class="info-cell">
                    <div class="cell-lbl">MRN</div>
                    <div class="cell-mono">{r.get("mrn","–")}</div>
                </div>
                <div class="info-cell">
                    <div class="cell-lbl">Chunks Indexed</div>
                    <div class="cell-val">{r.get("total_chunks","✓")}</div>
                </div>
            </div>
            <div class="upload-ok">
                Record successfully chunked and stored in AstraDB. Patient is now queryable.
            </div>
        </div>
        """, unsafe_allow_html=True)