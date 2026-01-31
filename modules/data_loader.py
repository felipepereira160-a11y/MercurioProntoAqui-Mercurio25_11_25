# modules/data_loader.py
import streamlit as st
import pandas as pd
import io
from modules.utils import convert_df_to_csv, adicionar_mensagem_assistente
from modules.resumo_relatorios import (
    gerar_resumo_ultima_posicao,
    gerar_resumo_generico,
    gerar_resumo_backlog,
    gerar_resumo_custos,
    gerar_resumo_cps,
    gerar_resumo_agendamentos,
)

@st.cache_data
def _carregar_dataframe_from_bytes(file_content, file_name, separador_padrao=',', forcar_cabecalho_relatorio=False):
    """
    Reads file content from bytes and returns a DataFrame. This function is cached.
    """
    arquivo_memoria = io.BytesIO(file_content)
    nome_arquivo_lower = file_name.lower()

    if nome_arquivo_lower.endswith('.xlsx'):
        if forcar_cabecalho_relatorio or any(keyword in nome_arquivo_lower for keyword in ["estoque", "relatorio", "posicao"]):
            return pd.read_excel(arquivo_memoria, engine='openpyxl', header=6)
        else:
            return pd.read_excel(arquivo_memoria, engine='openpyxl')
    elif nome_arquivo_lower.endswith('.xls'):
        return pd.read_excel(arquivo_memoria, engine='xlrd')
    elif nome_arquivo_lower.endswith('.csv'):
        try:
            arquivo_memoria.seek(0)
            df = pd.read_csv(arquivo_memoria, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
            if len(df.columns) > 1:
                return df
        except Exception:
            pass # Tenta o próximo separador
        
        arquivo_memoria.seek(0)
        outro_sep = ',' if separador_padrao == ';' else ';'
        return pd.read_csv(arquivo_memoria, encoding='latin-1', sep=outro_sep, on_bad_lines='skip')
    
    return None

def carregar_dataframe(arquivo, separador_padrao=',', forcar_cabecalho_relatorio=False):
    """
    Wrapper function that calls the cached internal function with file bytes.
    """
    if arquivo is None:
        return None
    return _carregar_dataframe_from_bytes(
        arquivo.getvalue(), 
        arquivo.name, 
        separador_padrao=separador_padrao, 
        forcar_cabecalho_relatorio=forcar_cabecalho_relatorio
    )

def _post_resumo_no_chat(resumo_texto, file_obj, resumo_key):
    if not resumo_texto or file_obj is None:
        return
    file_id = f"{file_obj.name}:{getattr(file_obj, 'size', 'na')}"
    sent_key = f"resumo_enviado_{resumo_key}"
    if st.session_state.get(sent_key) == file_id:
        return
    adicionar_mensagem_assistente(resumo_texto)
    st.session_state[sent_key] = file_id

def _render_botao_resumo(resumo_texto, button_key):
    if resumo_texto and st.button("Gerar resumo no chat", key=button_key, use_container_width=True):
        adicionar_mensagem_assistente(resumo_texto)

# --- COMPONENTES DE UPLOAD (ATUALIZADOS) ---
def uploader_agendamentos(key=None):
    data_file = st.file_uploader("1. 📊 O.S (Agendamentos)", type=["csv", "xlsx", "xls"], key=key)
    if data_file:
        try:
            st.session_state.df_agendamentos = carregar_dataframe(data_file, separador_padrao=';')
            st.success("O.S. carregadas!")
            resumo = gerar_resumo_agendamentos(st.session_state.df_agendamentos, data_file.name)
            st.session_state.resumo_agendamentos = resumo
            _post_resumo_no_chat(resumo, data_file, "agendamentos")
            _render_botao_resumo(resumo, f"btn_resumo_agendamentos_{key or 'default'}")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")

def uploader_mapeamento(key=None):
    map_file = st.file_uploader("2. 🌍 Mapeamento RT", type=["csv", "xlsx", "xls"], key=key)
    if map_file:
        try:
            st.session_state.df_mapeamento = carregar_dataframe(map_file, separador_padrao=',')
            st.success("Mapeamento carregado!")
            resumo = gerar_resumo_generico(st.session_state.df_mapeamento, "Mapeamento de RTs", map_file.name)
            st.session_state.resumo_mapeamento = resumo
            _post_resumo_no_chat(resumo, map_file, "mapeamento")
            _render_botao_resumo(resumo, f"btn_resumo_mapeamento_{key or 'default'}")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")

def uploader_devolucao(key=None):
    devolucao_file = st.file_uploader("3. 📥 Devolução (Itens)", type=["csv", "xlsx", "xls"], key=key)
    if devolucao_file:
        try:
            st.session_state.df_devolucao = carregar_dataframe(devolucao_file, separador_padrao=';')
            st.success("Devolução carregada!")
            resumo = gerar_resumo_generico(st.session_state.df_devolucao, "Base de Devolução", devolucao_file.name)
            st.session_state.resumo_devolucao = resumo
            _post_resumo_no_chat(resumo, devolucao_file, "devolucao")
            _render_botao_resumo(resumo, f"btn_resumo_devolucao_{key or 'default'}")
        except Exception as e:
            st.error(f"Erro na base de devolução: {e}")

def uploader_pagamento(key=None):
    pagamento_file = st.file_uploader("4. 💵 Pagamento (Custos)", type=["csv", "xlsx", "xls"], key=key)
    if pagamento_file:
        try:
            st.session_state.df_pagamento = carregar_dataframe(pagamento_file, separador_padrao=';')
            st.success("Pagamento carregado!")
            resumo = gerar_resumo_custos(st.session_state.df_pagamento, pagamento_file.name)
            st.session_state.resumo_pagamento = resumo
            _post_resumo_no_chat(resumo, pagamento_file, "pagamento")
            _render_botao_resumo(resumo, f"btn_resumo_pagamento_{key or 'default'}")
        except Exception as e:
            st.error(f"Erro na base de pagamento: {e}")

def uploader_ativos(key=None):
    ativos_file = st.file_uploader("5. 🚗 Base de Ativos (Clientes)", type=["csv", "xlsx", "xls"], key=key)
    if ativos_file:
        st.info("Carregando arquivo de Ativos... Isso pode levar um minuto.")
        try:
            st.session_state.df_ativos = carregar_dataframe(ativos_file)
            st.success("Base de Ativos (Clientes) carregada!")
            resumo = gerar_resumo_generico(st.session_state.df_ativos, "Base de Ativos (Clientes)", ativos_file.name)
            st.session_state.resumo_ativos = resumo
            _post_resumo_no_chat(resumo, ativos_file, "ativos")
            _render_botao_resumo(resumo, f"btn_resumo_ativos_{key or 'default'}")
        except Exception as e:
            st.error(f"Erro na base de Ativos: {e}")

def uploader_backlog(key=None):
    backlog_file = st.file_uploader("6. 📦 Backlog (BaseItensInstalar)", type=["csv", "xlsx", "xls"], key=key)
    if backlog_file:
        try:
            st.session_state.df_backlog = carregar_dataframe(backlog_file, separador_padrao=';')
            st.success("Backlog carregado!")
            resumo = gerar_resumo_backlog(st.session_state.df_backlog, backlog_file.name)
            st.session_state.resumo_backlog = resumo
            _post_resumo_no_chat(resumo, backlog_file, "backlog")
            _render_botao_resumo(resumo, f"btn_resumo_backlog_{key or 'default'}")
        except Exception as e:
            st.error(f"Erro na base de backlog: {e}")

def uploader_ultimaposicao(key=None):
    posicao_file = st.file_uploader("7. 🛰️ Última Posição (Ativos)", type=["xlsx", "xls", "csv"], key=key)
    if posicao_file:
        try:
            st.session_state.df_ultimaposicao = carregar_dataframe(posicao_file, forcar_cabecalho_relatorio=True)
            st.success("Relatório de Última Posição carregado!")
            resumo = gerar_resumo_ultima_posicao(st.session_state.df_ultimaposicao, posicao_file.name)
            st.session_state.resumo_ultimaposicao = resumo
            _post_resumo_no_chat(resumo, posicao_file, "ultimaposicao")
            _render_botao_resumo(resumo, f"btn_resumo_ultimaposicao_{key or 'default'}")
        except Exception as e:
            st.error(f"Erro na base de última posição: {e}")

def uploader_cps(key=None):
    cps_file = st.file_uploader("8. 📋 CPS (Relatórios)", type=["xlsx", "xls", "csv"], key=key)
    if cps_file:
        try:
            st.session_state.df_cps = carregar_dataframe(cps_file, forcar_cabecalho_relatorio=True)
            st.success("Relatório CPS carregado!")
            resumo = gerar_resumo_cps(st.session_state.df_cps, cps_file.name)
            st.session_state.resumo_cps = resumo
            _post_resumo_no_chat(resumo, cps_file, "cps")
            _render_botao_resumo(resumo, f"btn_resumo_cps_{key or 'default'}")
        except Exception as e:
            st.error(f"Erro na base do CPS: {e}")

def uploader_ordens_pendentes(key=None):
    pendentes_file = st.file_uploader("🗓️ Ordens Pendentes", type=["xlsx", "xls"], key=key)
    if pendentes_file:
        try:
            st.session_state.df_ordens_pendentes = carregar_dataframe(pendentes_file)
            st.success("Arquivo de Ordens Pendentes carregado!")
            resumo = gerar_resumo_generico(st.session_state.df_ordens_pendentes, "Ordens Pendentes", pendentes_file.name)
            st.session_state.resumo_ordens_pendentes = resumo
            _post_resumo_no_chat(resumo, pendentes_file, "ordens_pendentes")
            _render_botao_resumo(resumo, f"btn_resumo_ordens_pendentes_{key or 'default'}")
        except Exception as e:
            st.error(f"Erro ao carregar o arquivo de ordens pendentes: {e}")

# --- FUNÇÃO DE LIMPEZA (Atualizada para limpar o chat) ---
def limpar_tudo():
    st.cache_data.clear()
    chaves_para_limpar = [
        "df_agendamentos", "df_mapeamento", "df_devolucao", 
        "df_pagamento", "df_ativos", "df_backlog", "df_ultimaposicao", "df_cps",
        "df_ordens_pendentes", # Adicionado para limpar o novo dataframe
        "display_history", "chat_history", # Limpa o chat tamb?m
        "resumo_agendamentos", "resumo_mapeamento", "resumo_devolucao", "resumo_pagamento",
        "resumo_ativos", "resumo_backlog", "resumo_ultimaposicao", "resumo_cps",
        "resumo_ordens_pendentes",
        "resumo_enviado_agendamentos", "resumo_enviado_mapeamento", "resumo_enviado_devolucao",
        "resumo_enviado_pagamento", "resumo_enviado_ativos", "resumo_enviado_backlog",
        "resumo_enviado_ultimaposicao", "resumo_enviado_cps", "resumo_enviado_ordens_pendentes"
    ]
    for key in chaves_para_limpar:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()
