# modules/dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from modules.tutorial_helper import tutorial_button # Importando o tutorial

# --- Cached Data Computation Functions ---

@st.cache_data
def get_kpis(df, status_col, cliente_col, fechamento_col):
    """Calculates all KPIs from the dataframe in a single cached function."""
    total_os = len(df)
    
    agendadas = df[status_col].str.contains('Agendada', case=False, na=False).sum() if status_col else "N/A"
    
    clientes_unicos = df[cliente_col].nunique() if cliente_col else "N/A"
    
    improdutivas_total = df[df[fechamento_col].str.contains('improdutiva', case=False, na=False)].shape[0] if fechamento_col else "N/A"
    
    return total_os, agendadas, clientes_unicos, improdutivas_total

@st.cache_data
def get_os_by_status(df, status_col):
    """Computes value counts for OS by status."""
    if not status_col or status_col not in df.columns:
        return None
    return df[status_col].value_counts()

@st.cache_data
def get_os_by_city(df, cidade_col):
    """Computes value counts for OS by city (Top 10)."""
    if not cidade_col or cidade_col not in df.columns:
        return None
    return df[cidade_col].value_counts().head(10)

@st.cache_data
def get_improdutivas_by_cliente(df, fechamento_col, cliente_col):
    """Computes top 10 clients by unproductive visits."""
    if not fechamento_col or not cliente_col or fechamento_col not in df.columns or cliente_col not in df.columns:
        return None
    df_improdutiva = df[df[fechamento_col].str.contains('improdutiva', case=False, na=False)]
    if df_improdutiva.empty:
        return pd.Series(dtype='int64') # Return empty series
    return df_improdutiva.groupby(cliente_col).size().nlargest(10).rename("Visitas Improdutivas")

@st.cache_data
def get_nao_comparecimento_by_rep(df, fechamento_col, rep_col):
    """Computes top 10 reps by 'Não Comparecimento'."""
    if not fechamento_col or not rep_col or fechamento_col not in df.columns or rep_col not in df.columns:
        return None
    df_nao_compareceu = df[df[fechamento_col].str.contains('não comparecimento', case=False, na=False)]
    if df_nao_compareceu.empty:
        return pd.Series(dtype='int64')
    return df_nao_compareceu.groupby(rep_col).size().nlargest(10).rename("Não Comparecimento")

@st.cache_data
def get_indisponibilidade_by_rep(df, fechamento_col, rep_col):
    """Computes top 10 reps by 'Indisponibilidade Técnica'."""
    if not fechamento_col or not rep_col or fechamento_col not in df.columns or rep_col not in df.columns:
        return None
    df_indisponivel = df[df[fechamento_col].str.contains('indisponibilidade técnica', case=False, na=False)]
    if df_indisponivel.empty:
        return pd.Series(dtype='int64')
    return df_indisponivel.groupby(rep_col).size().nlargest(10).rename("Indisponibilidade Técnica")


@st.cache_data
def _generate_plotly_bar(data_series, category_col_name, title_suffix):
    """
    Generates a Plotly bar chart. This function is cached to prevent re-rendering.
    """
    if data_series is None or data_series.empty:
        return None

    df_chart = data_series.reset_index()
    df_chart.columns = [category_col_name, 'Contagem']

    fig = px.bar(
        df_chart, x='Contagem', y=category_col_name, orientation='h', text='Contagem',
        title=f"Contagem por {title_suffix}", template='plotly_dark'
    )
    fig.update_traces(
        textposition='outside', marker_color='#1f77b4',
        hovertemplate=f"<b>%{{y}}</b><br>Contagem: %{{x}}<extra></extra>"
    )
    fig.update_layout(
        plot_bgcolor='rgba(0, 0, 0, 0)', paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color='#FAFAFA'),
        xaxis=dict(showgrid=False, zerolinecolor='rgba(0, 0, 0, 0)'),
        yaxis=dict(showgrid=False, zerolinecolor='rgba(0, 0, 0, 0)', categoryorder='total ascending', tickangle=0, automargin=True),
        xaxis_title=f"Total de {title_suffix}", yaxis_title=category_col_name,
        margin=dict(l=10, r=10, t=40, b=10), height=400, title_text='', title_y=0
    )
    return fig


def exibir_dashboard(df_agendamentos):
    tutorial_button("Dashboard", "Dashboard - Visão Geral") 
    
    st.subheader("Visão Geral dos Agendamentos")
    
    if df_agendamentos.empty:
        st.info("Não há dados de agendamento para exibir.")
        return

    df = df_agendamentos.copy()
    
    # --- Flexible Column Identification ---
    status_col = next((c for c in df.columns if 'status' in c.lower()), None)
    cliente_col = next((c for c in df.columns if 'cliente' in c.lower() and 'id' not in c.lower()), None)
    cidade_col = next((c for c in df.columns if 'cidade' in c.lower()), None)
    rep_col = next((c for c in df.columns if 'representante' in c.lower() and 'id' not in c.lower()), None)
    fechamento_col = next((c for c in df.columns if 'tipo de fechamento' in c.lower() or 'motivo fechamento' in c.lower()), None)

    # Ensure columns are string type for `.str` accessor
    if status_col: df[status_col] = df[status_col].astype(str)
    if fechamento_col: df[fechamento_col] = df[fechamento_col].astype(str)

    # --- KPIs ---
    total_os, agendadas, clientes_unicos, improdutivas_total = get_kpis(df, status_col, cliente_col, fechamento_col)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de O.S. Carregadas", total_os)
    col2.metric("O.S. 'Agendadas'", agendadas)
    col3.metric("Clientes Únicos", clientes_unicos)
    col4.metric("Visitas Improdutivas", improdutivas_total)

    st.markdown("---") 
    
    # --- General Analysis Charts ---
    st.subheader("Análise Geral")
    colg1, colg2 = st.columns(2)
    
    with colg1:
        st.caption("Contagem por Status de O.S.")
        chart_data1 = get_os_by_status(df, status_col)
        fig1 = _generate_plotly_bar(chart_data1, 'Status', 'O.S.')
        if fig1:
            st.plotly_chart(fig1, use_container_width=True) 
        else:
            st.info("Coluna 'Status' não encontrada para gráfico.")

    with colg2:
        st.caption("Top 10 Cidades por Volume de O.S.")
        chart_data2 = get_os_by_city(df, cidade_col)
        fig2 = _generate_plotly_bar(chart_data2, 'Cidade', 'O.S.')
        if fig2:
            st.plotly_chart(fig2, use_container_width=True) 
        else:
            st.info("Coluna 'Cidade' não encontrada para gráfico.")

    st.markdown("---") 
    
    # --- Detailed Closure Analysis ---
    st.subheader("Análise Detalhada de Fechamento")
    
    if not fechamento_col:
        st.warning("Não foi possível gerar as análises de fechamento. Coluna 'Tipo de Fechamento' ou 'Motivo Fechamento' não encontrada.")
        return
        
    colf1, colf2 = st.columns(2)
    
    with colf1:
        st.caption("Visitas Improdutivas por Cliente (Top 10)")
        chart_data3 = get_improdutivas_by_cliente(df, fechamento_col, cliente_col)
        if chart_data3 is not None and not chart_data3.empty:
            fig3 = _generate_plotly_bar(chart_data3, 'Cliente', 'Visitas Improdutivas')
            st.plotly_chart(fig3, use_container_width=True) 
        elif chart_data3 is not None:
             st.info("Nenhuma 'Visita Improdutiva' encontrada.")
        else:
            st.info("Coluna 'Cliente' não encontrada.")

    with colf2:
        st.caption("Não Comparecimento (Técnico) por Representante (Top 10)")
        chart_data4 = get_nao_comparecimento_by_rep(df, fechamento_col, rep_col)
        if chart_data4 is not None and not chart_data4.empty:
            fig4 = _generate_plotly_bar(chart_data4, 'Representante', 'Não Comparecimentos')
            st.plotly_chart(fig4, use_container_width=True) 
        elif chart_data4 is not None:
            st.info("Nenhum 'Não Comparecimento' encontrado.")
        else:
            st.info("Coluna 'Representante' não encontrada.")

    st.caption("Indisponibilidade Técnica por Representante (Top 10)")
    chart_data5 = get_indisponibilidade_by_rep(df, fechamento_col, rep_col)
    if chart_data5 is not None and not chart_data5.empty:
        fig5 = _generate_plotly_bar(chart_data5, 'Representante', 'Indisponibilidades Técnicas')
        st.plotly_chart(fig5, use_container_width=True) 
    elif chart_data5 is not None:
        st.info("Nenhuma 'Indisponibilidade Técnica' encontrada.")
    else:
        st.info("Coluna 'Representante' não encontrada para este gráfico.")