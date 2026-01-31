# modules/footer.py
import streamlit as st

def rodape():
    # Estilo CSS para o rodapé
    footer_style = """
    <style>
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #262730; /* Cor de fundo escura */
        color: #FAFAFA; /* Cor do texto */
        text-align: center;
        padding: 10px;
        font-size: 14px;
        border-top: 1px solid #707070; /* Linha superior sutil */
        z-index: 9999; /* Garante que fique sobre a maioria dos elementos */
    }
    .footer a {
        color: #1E88E5; /* Cor para links */
        text-decoration: none;
    }
    .footer a:hover {
        text-decoration: underline;
    }
    /* Adiciona um 'padding-bottom' ao corpo principal para não sobrepor o conteúdo */
    body {
        margin-bottom: 50px; 
    }
    </style>
    """
    
    st.markdown(footer_style, unsafe_allow_html=True)

    # Conteúdo do rodapé
    st.markdown(
        '<div class="footer">Desenvolvido com ❤️ por Felipão Castrão o brabo da Ceabs.</div>',
        unsafe_allow_html=True
    )