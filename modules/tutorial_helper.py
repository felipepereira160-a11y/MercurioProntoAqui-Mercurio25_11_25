# modules/tutorial_helper.py
import streamlit as st

# Mapeamento do conteúdo do tutorial para cada aba
TUTORIAL_CONTENTS = {
    "Dashboard": {
        "title": "Guia Rápido do Dashboard 📊",
        "content": "Use o dashboard para ter uma visão geral dos KPIs. Utilize as ferramentas de zoom nos gráficos (Plotly) para detalhar regiões específicas de contagem de O.S. e cidades.",
    },
    "Custos": {
        "title": "Guia de Análise de Custos 💰",
        "content": "Nesta seção, analise a eficiência de custo por representante e a distribuição de despesas. Filtre por período ou tipo de serviço para otimizar os gastos.",
    },
    "Otimizador": {
        "title": "Guia do Otimizador de Rotas 🧭",
        "content": "Utilize o Otimzador para recalcular rotas de agendamento, minimizando tempo de deslocamento ou quilometragem. Insira os novos pontos e clique em 'Otimizar'.",
    },
    "Mapeamento": {
        "title": "Guia de Mapeamento Geográfico 🗺️",
        "content": "Visualize a distribuição geográfica de O.S. e clientes. O mapeamento auxilia na identificação de clusters e na estratégia de expansão territorial.",
    },
    "Devolução": {
        "title": "Guia de Análise de Devoluções 🔄",
        "content": "Acompanhe as métricas de devolução. Revise os motivos mais comuns e a performance dos representantes para reduzir as taxas de retrabalho.",
    },
    "Viagens": {
        "title": "Guia de Análise de Viagens ✈️",
        "content": "Nesta seção, você pode carregar relatórios de distância percorrida para analisar viagens de veículos. Visualize rotas, distâncias e tempos de viagem, e identifique padrões de deslocamento. As localizações inicial e final são geocodificadas e exibidas no mapa.",
    },
    "Base Ativos": {
        "title": "Guia da Base de Ativos 🗄️",
        "content": "Explore a base de dados completa de ativos. Use os filtros avançados para localizar informações específicas sobre equipamentos, peças ou estoque.",
    },
    "Chat/IA": {
        "title": "Guia do Assistente IA (Mercúrio) 🤖",
        "content": "O Mercúrio pode te ajudar a responder perguntas complexas sobre os dados e até gerar códigos SQL/Python. Digite sua pergunta sobre o dataset ou sobre a aplicação!",
    },
}

def tutorial_button(page_name: str, page_title: str):
    """
    Exibe o título da página e um botão de tutorial st.popover no mesmo nível.
    """
    
    with st.container():
        col_btn, col_title = st.columns([1, 10]) 

        with col_btn:
            with st.popover("❔", use_container_width=False):
                if page_name in TUTORIAL_CONTENTS:
                    tutorial_info = TUTORIAL_CONTENTS[page_name]
                    st.subheader(tutorial_info["title"])
                    st.markdown(tutorial_info["content"])
                else:
                    st.info(f"Nenhum tutorial disponível para a aba '{page_name}'.")
                
        with col_title:
            st.header(page_title)