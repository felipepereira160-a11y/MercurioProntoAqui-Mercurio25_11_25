# modules/ativos.py
import streamlit as st
import pandas as pd
from modules.utils import convert_df_to_csv
from modules.tutorial_helper import tutorial_button # <-- NOVO IMPORT

def ferramenta_ativos(df):
    # 🚨 NOVO: Chamada do botão de tutorial
    tutorial_button("Base Ativos", "Base Completa de Ativos")
    
    try:
        col_cliente, col_modelo, col_serial = None, None, None
        colunas_encontradas = {c.lower().strip(): c for c in df.columns}

        if 'cliente' in colunas_encontradas:
            col_cliente = colunas_encontradas['cliente']
        elif 'nome fantasia' in colunas_encontradas:
            col_cliente = colunas_encontradas['nome fantasia']
        
        if 'modelo' in colunas_encontradas:
            col_modelo = colunas_encontradas['modelo']
        elif 'veiculomodelo' in colunas_encontradas:
            col_modelo = colunas_encontradas['veiculomodelo']

        if 'numero de serie' in colunas_encontradas:
            col_serial = colunas_encontradas['numero de serie']
        elif 'serial' in colunas_encontradas:
            col_serial = colunas_encontradas['serial']
        elif 'rastreador numero serie' in colunas_encontradas:
            col_serial = colunas_encontradas['rastreador numero serie']

        if not all([col_cliente, col_modelo, col_serial]):
            st.error(f"ERRO: Não foi possível encontrar as colunas 'Cliente', 'Modelo' e 'Numero de Serie' na sua planilha de Ativos.")
            st.info(f"Colunas encontradas: {list(df.columns)}")
            return

        st.info("Devido ao tamanho do arquivo, digite o nome do cliente para pesquisar.")
        cliente_digitado = st.text_input(
            "Digite o nome (ou parte do nome) do Cliente para analisar:",
            placeholder="Ex: 'TRANSPORTADORA XYZ'"
        )

        if not cliente_digitado:
            # st.info("Digite o nome de um cliente para ver os detalhes.") # Removido
            return

        try:
            mask = df[col_cliente].str.contains(cliente_digitado, case=False, na=False)
            df_filtrado = df[mask]
        except Exception as e:
            st.error(f"Erro na busca: {e}. Tentando busca exata.")
            mask = df[col_cliente].astype(str).str.upper() == cliente_digitado.upper()
            df_filtrado = df[mask]

        if df_filtrado.empty:
            st.warning(f"Nenhum dado encontrado para o cliente: '{cliente_digitado}'")
            return
        
        clientes_encontrados = df_filtrado[col_cliente].unique()
        if len(clientes_encontrados) > 1:
            st.warning(f"Sua busca retornou {len(clientes_encontrados)} clientes. Refine sua busca.")
            st.dataframe(pd.DataFrame(clientes_encontrados, columns=["Clientes Encontrados"]))
            return
            
        df_cliente = df_filtrado.copy()
        cliente_selecionado = clientes_encontrados[0]

        st.subheader(f"Resumo para: {cliente_selecionado}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total de Ativos (Veículos)", len(df_cliente))
        with col2:
            st.dataframe(df_cliente[col_modelo].value_counts().rename("Qtd. por Modelo").head(10))

        st.subheader("Seriais para Copiar")
        
        seriais_lista = df_cliente[col_serial].dropna().astype(str).tolist()
        seriais_texto = "\n".join(seriais_lista)
        
        st.text_area(
            "Copie os seriais abaixo (um por linha):",
            value=seriais_texto,
            height=200
        )
        st.caption(f"Total de seriais: {len(seriais_lista)}")

        st.subheader("Exportar Dados do Cliente")
        
        csv = convert_df_to_csv(df_cliente)
        st.download_button(
            label="📥 Baixar dados deste cliente (.csv)",
            data=csv,
            file_name=f"ativos_{cliente_selecionado}.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"Ocorreu um erro inesperado na ferramenta de Ativos: {e}")
        import traceback
        st.error(traceback.format_exc())