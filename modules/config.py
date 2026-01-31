# modules/config.py
import streamlit as st
import google.generativeai as genai
import os
import base64

# --- 1. NOVAS CONSTANTES DE TEMA ---
# Tema escuro, limpo e profissional
COR_FUNDO_APP = "#121212"    # Fundo principal (cinza bem escuro)
COR_FUNDO_CARD = "#1E1E1E"   # Fundo de todos os cards, inputs, etc.
COR_BORDA_CARD = "#444444"   # Borda sutil para os cards
COR_TEXTO = "#FAFAFA"        # Texto principal (branco)
COR_TEXTO_SEC = "#A0A0A0"    # Texto secundário (placeholders)
COR_DESTAQUE_1 = "#753BBD"   # Roxo (usado em títulos, abas)
COR_DESTAQUE_2 = "#00C896"   # Verde-água (usado em botões, destaques positivos)

def configurar_app():
    st.set_page_config(page_title="Mercúrio IA", page_icon="🧠", layout="wide")
    
    # --- 2. CSS NOVO E COMPLETO ---
    custom_css = f"""
    <style>
    /* --- FUNDO E TEXTO BASE --- */
    .stApp {{
        background-color: {COR_FUNDO_APP} !important;
        color: {COR_TEXTO} !important;
    }}
    h1, h2, h3, h4, h5, h6 {{
        color: {COR_TEXTO} !important;
    }}
    h1 {{ color: {COR_DESTAQUE_1} !important; }}
    
    /* --- BARRA LATERAL --- */
    [data-testid="stSidebar"] {{
        background-color: {COR_FUNDO_CARD};
        border-right: 1px solid {COR_BORDA_CARD};
    }}
    /* Reduz padding lateral da sidebar para a logo ocupar mais espaço */
    [data-testid="stSidebar"] .block-container {{
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }}
    
    /* --- ABAS --- */
    [data-testid="stTabs"] button[aria-selected="true"] {{
        color: {COR_DESTAQUE_1};
        border-bottom: 3px solid {COR_DESTAQUE_1};
    }}
    [data-testid="stTabs"] button {{
        color: {COR_TEXTO_SEC};
    }}
    
    /* --- ESTILO DE CARD UNIVERSAL --- */
    /* Aplica a todos os uploaders, métricas, e blocos de filtro */
    [data-testid="stFileUploader"], 
    [data-testid="stMetric"],
    [data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]),
    [data-testid="stHorizontalBlock"]:has([data-testid="stTextInput"]),
    [data-testid="stHorizontalBlock"]:has([data-testid="stMultiSelect"]),
    [data-testid="stHorizontalBlock"]:has([data-testid="stDateInput"]),
    div[style*="background-color: #3A3A3A;"], /* Captura o "Status: Pronto" antigo */
    div[style*="background-color: {COR_FUNDO_CARD};"] /* Captura os créditos antigos */
    {{
        background-color: {COR_FUNDO_CARD} !important;
        border: 1px solid {COR_BORDA_CARD} !important;
        border-radius: 8px;
        padding: 15px;
    }}
    [data-testid="stMetric"] label {{ color: {COR_TEXTO_SEC}; }}

    /* --- INPUTS E WIDGETS (CORREÇÃO DE INVERSÃO) --- */
    
    /* Inputs de Texto, Selects, Datas */
    [data-testid="stTextInput"] input,
    [data-testid="stDateInput"] input,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {{
        background-color: {COR_FUNDO_APP};
        color: {COR_TEXTO} !important;
        border: 1px solid {COR_BORDA_CARD} !important;
    }}
    /* Placeholders */
    ::placeholder {{
        color: {COR_TEXTO_SEC} !important;
    }}
    
    /* Pop-up do Calendário */
    div[data-baseweb="calendar"] {{
        background-color: {COR_FUNDO_CARD} !important;
        border: 1px solid {COR_BORDA_CARD} !important;
    }}
    div[data-baseweb="calendar"] input {{
        background-color: {COR_FUNDO_APP} !important;
        color: {COR_TEXTO} !important;
    }}
    div[data-baseweb="calendar"] abbr,
    div[data-baseweb="calendar"] div {{
        color: {COR_TEXTO} !important;
    }}
    div[data-baseweb="calendar"] button > svg {{
        fill: {COR_TEXTO} !important;
    }}
    div[role="option"][aria-selected="true"] {{
        background-color: {COR_DESTAQUE_1} !important;
    }}
    
    /* Expander (Acordeão) */
    [data-testid="stExpander"] {{
        background-color: {COR_FUNDO_CARD} !important;
        border: 1px solid {COR_BORDA_CARD} !important;
        border-radius: 8px !important;
    }}
    [data-testid="stExpander"] summary {{
        color: {COR_TEXTO} !important;
    }}
    [data-testid="stExpander"] summary:hover {{
        color: {COR_DESTAQUE_1} !important;
    }}
    
    /* Botões */
    [data-testid="stButton"] button {{
        background-color: {COR_DESTAQUE_2};
        color: {COR_FUNDO_APP};
        border: none;
    }}
    [data-testid="stButton"] button:hover {{
        background-color: {COR_DESTAQUE_1};
        color: {COR_TEXTO};
    }}
    /* Botão de Download */
    [data-testid="stDownloadButton"] button {{
        background-color: {COR_DESTAQUE_1};
        color: {COR_TEXTO};
        border: none;
    }}
    [data-testid="stDownloadButton"] button:hover {{
        background-color: {COR_DESTAQUE_2};
        color: {COR_FUNDO_APP};
    }}
    
    /* Tabelas e Dataframes */
    [data-testid="stDataFrame"] {{
         background-color: {COR_FUNDO_CARD} !important;
    }}
    [data-testid="stDataFrame"] div[data-testid="stTable"] {{
         background-color: {COR_FUNDO_CARD} !important;
         border: 1px solid {COR_BORDA_CARD} !important;
    }}
    [data-testid="stDataFrame"] th {{
        background-color: {COR_FUNDO_APP} !important;
        color: {COR_TEXTO_SEC} !important;
    }}
    [data-testid="stDataFrame"] td {{
        color: {COR_TEXTO} !important;
    }}

    /* Logo da sidebar */
    .sidebar-logo {{
        width: 100%;
        max-width: 100%;
        height: auto;
        display: block;
        margin: 0 auto;
    }}
    .sidebar-logo--large {{
        width: 100%;
        max-width: 100%;
        transform: scale(2.7);
        transform-origin: top center;
    }}
    .sidebar-logo-wrap {{
        width: 100%;
        padding: 0;
        margin: -40px auto 10px auto;
        display: block;
        overflow: visible;
    }}
    </style>
    """
    
    st.markdown(custom_css, unsafe_allow_html=True)

    wing_path = os.path.join("assets", "MercurioWing.png")
    wing_html = ""
    if os.path.exists(wing_path):
        with open(wing_path, "rb") as f:
            wing_b64 = base64.b64encode(f.read()).decode("ascii")
        wing_html = f"<img src='data:image/png;base64,{wing_b64}' style='height:48px; width:auto; margin-right:10px;' />"

    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:10px; margin: 0 0 4px 0;">
            {wing_html}
            <h1 style="margin:0; color:{COR_DESTAQUE_1}; font-size:2.1rem; line-height:1;">Mercúrio IA</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

def carregar_chave_api():
    logo_path = os.path.join("assets", "AAA.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("ascii")
        st.sidebar.markdown(
            f"""
            <div class="sidebar-logo-wrap">
                <img src="data:image/png;base64,{img_b64}" class="sidebar-logo sidebar-logo--large" style="background: transparent;" />
            </div>
            <div style="height: 170px;"></div>
            """,
            unsafe_allow_html=True,
        )

    api_key = None
    api_key_status = "Não configurada"
    try:
        api_key = st.secrets.get("GOOGLE_API_KEY")
        if api_key: api_key_status = "✔️ Carregada (Streamlit Secrets)"
    except Exception: pass
    if not api_key:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if api_key: api_key_status = "✔️ Carregada (Variável de Ambiente)"
        else: api_key_status = "❌ ERRO: Chave não encontrada."
    
    st.session_state.api_key_status = api_key_status

    if not api_key:
        st.error("A chave da API do Google não foi encontrada.")
        st.stop()
    try:
        genai.configure(api_key=api_key)
        modelo_padrao = "gemini-2.5-flash"
        model = genai.GenerativeModel(modelo_padrao)
        return model
    except Exception as e:
        st.error(f"Erro ao inicializar o modelo Gemini: {e}")
        st.stop()
