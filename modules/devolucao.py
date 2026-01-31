# modules/devolucao.py
import streamlit as st
import pandas as pd
from modules.utils import convert_df_to_csv
from modules.tutorial_helper import tutorial_button # <-- NOVO IMPORT

def ferramenta_devolucao(df):
    # 🚨 NOVO: Chamada do botão de tutorial
    tutorial_button("Devolução", "Análise de Devoluções")
    
    date_col = next((c for c in df.columns if 'prazoinstalacao' in c.lower().replace(' ', '')), None)
    cliente_col = next((c for c in df.columns if 'clientenome' in c.lower().replace(' ', '')), None)
    if not date_col or not cliente_col:
        st.error("ERRO: Planilha sem colunas 'PrazoInstalacao' e 'ClienteNome'.")
        return

    df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
    df.dropna(subset=[date_col], inplace=True)
    hoje = pd.Timestamp.now().normalize()
    vencidas = df[df[date_col] < hoje]
    if vencidas.empty:
        st.info("Nenhuma ordem vencida encontrada.")
        return

    st.warning(f"Foram encontradas {len(vencidas)} ordens vencidas.")
    
    clientes = sorted(vencidas[cliente_col].dropna().unique())
    cliente = st.selectbox("Selecione o cliente:", options=clientes, index=None, placeholder="Pesquisar cliente...")
    
    if cliente:
        filtrado = vencidas[vencidas[cliente_col] == cliente]
        st.dataframe(filtrado)
        csv = convert_df_to_csv(filtrado)
        st.download_button(f"📥 Exportar {len(filtrado)} ordens de {cliente}", csv, f"vencidas_{cliente}.csv", "text/csv")