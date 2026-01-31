# modules/mapeamento.py
import streamlit as st
import pandas as pd
from modules.tutorial_helper import tutorial_button # <-- NOVO IMPORT

def ferramenta_mapeamento(df):
    # 🚨 NOVO: Chamada do botão de tutorial
    tutorial_button("Mapeamento", "Mapeamento Geográfico")
    
    city_col, rep_col, lat_col, lon_col, km_col = 'nm_cidade_atendimento', 'nm_representante', 'cd_latitude_atendimento', 'cd_longitude_atendimento', 'qt_distancia_atendimento_km'
    if not all(c in df.columns for c in [city_col, rep_col, lat_col, lon_col, km_col]):
        st.error("ERRO: Planilha de mapeamento com colunas ausentes.")
        return

    col1, col2 = st.columns(2)
    cidade = col1.selectbox("Filtrar por Cidade:", sorted(df[city_col].dropna().unique()), index=None, placeholder="Selecione...")
    rep = col2.selectbox("Filtrar por Representante:", sorted(df[rep_col].dropna().unique()), index=None, placeholder="Selecione...")

    filtrado = df.copy()
    if cidade:
        filtrado = df[df[city_col] == cidade]
    elif rep:
        filtrado = df[df[rep_col] == rep]

    st.dataframe(filtrado[[rep_col, city_col, km_col] + [c for c in filtrado.columns if c not in [rep_col, city_col, km_col]]])

    map_data = filtrado.rename(columns={lat_col: 'lat', lon_col: 'lon'})
    st.map(map_data)