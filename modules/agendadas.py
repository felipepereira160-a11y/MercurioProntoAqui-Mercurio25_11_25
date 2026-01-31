# modules/agendadas.py
import streamlit as st
import pandas as pd
import io

def exibir_ordens_agendadas(df: pd.DataFrame):
    """
    Exibe a interface para análise das Ordens de Serviço Agendadas.
    
    Argumentos:
        df (pd.DataFrame): O DataFrame contendo os dados das ordens agendadas.
    """
    if df is None:
        st.info("👆 Por favor, carregue o arquivo 'Ordens Pendentes.xlsx' para começar.")
        return

    st.header("Análise de Ordens Agendadas")

    with st.expander("Análise Exploratória dos Dados (Temporário)"):
        st.write("Amostra dos dados:")
        st.write(df.head())
        
        st.write("Informações das colunas:")
        buffer = io.StringIO()
        df.info(buf=buffer)
        s = buffer.getvalue()
        st.text(s)
    
    try:
        # Tenta encontrar colunas relevantes de forma flexível
        col_os = next((col for col in df.columns if 'os' in col.lower() or 'ordem' in col.lower()), None)
        col_data = next((col for col in df.columns if 'data' in col.lower()), None)
        col_tecnico = next((col for col in df.columns if 'téc' in col.lower() or 'tecnico' in col.lower()), None)
        col_cidade = next((col for col in df.columns if 'cidade' in col.lower()), None)

        st.metric("Total de Ordens Agendadas", len(df))

        # Filtros
        st.subheader("Filtros")
        col1, col2 = st.columns(2)
        
        df_filtrado = df.copy()

        if col_tecnico:
            tecnicos = sorted(df_filtrado[col_tecnico].dropna().unique())
            tecnico_selecionado = col1.multiselect(f"Filtrar por {col_tecnico}:", options=tecnicos)
            if tecnico_selecionado:
                df_filtrado = df_filtrado[df_filtrado[col_tecnico].isin(tecnico_selecionado)]

        if col_cidade:
            cidades = sorted(df_filtrado[col_cidade].dropna().unique())
            cidade_selecionada = col2.multiselect(f"Filtrar por {col_cidade}:", options=cidades)
            if cidade_selecionada:
                df_filtrado = df_filtrado[df_filtrado[col_cidade].isin(cidade_selecionada)]

        st.dataframe(df_filtrado, use_container_width=True)

        if df_filtrado.empty:
            st.warning("Nenhum dado corresponde aos filtros selecionados.")
        else:
            st.success(f"Exibindo {len(df_filtrado)} ordens agendadas.")

    except Exception as e:
        st.error(f"Ocorreu um erro ao processar os dados das ordens agendadas: {e}")
        st.exception(e)
