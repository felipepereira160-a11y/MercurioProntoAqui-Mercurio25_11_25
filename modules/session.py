import streamlit as st
from modules.utils import inicializar_metricas_chat

def inicializar_sessao(model):
    if "model" not in st.session_state:
        st.session_state.model = model
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "display_history" not in st.session_state:
        st.session_state.display_history = []
    if "app_log" not in st.session_state:
        st.session_state.app_log = []
    inicializar_metricas_chat()

    for df_key in ['df_dados', 'df_mapeamento', 'df_devolucao', 'df_pagamento']:
        if df_key not in st.session_state:
            st.session_state[df_key] = None
