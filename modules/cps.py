import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import numpy as np
from modules.processar_relatorio import extrair_odometros

@st.cache_data
def geocode_addresses(addresses):
    """
    Converte uma lista de endereços em coordenadas (latitude, longitude)
    usando Nominatim e exibe uma barra de progresso.
    """
    geolocator = Nominatim(user_agent="mercurio_app")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
    
    coords = {}
    
    progress_bar = st.progress(0)
    total = len(addresses)
    
    for i, address in enumerate(addresses):
        try:
            location = geocode(address)
            if location:
                coords[address] = {'lat': location.latitude, 'lon': location.longitude}
            else:
                coords[address] = {'lat': None, 'lon': None}
        except Exception as e:
            st.warning(f"Não foi possível geocodificar o endereço '{address}': {e}")
            coords[address] = {'lat': None, 'lon': None}
        
        progress_bar.progress((i + 1) / total)
        
    return coords

def analisar_cps(df_cps):
    """
    Analisa e exibe os dados do relatório CPS, com geocodificação e mapas.
    """
    if df_cps is None or df_cps.empty:
        st.warning("Nenhum dado do CPS para analisar. Por favor, carregue um relatório.")
        return

    st.subheader("Dados do Relatório CPS")
    
    # 1. Verificar a coluna combinada correta
    required_columns = ['Localização', 'Evento / Ignição']
    if not all(col in df_cps.columns for col in required_columns):
        st.error(f"O arquivo carregado não contém as colunas necessárias: {', '.join(required_columns)}. Verifique o arquivo e tente novamente.")
        st.info(f"Colunas encontradas: {', '.join(df_cps.columns)}")
        st.dataframe(df_cps.head())
        return

    # 2. Dividir a coluna 'Evento / Ignição' em duas
    try:
        split_cols = df_cps['Evento / Ignição'].str.split('/', n=1, expand=True)
        df_cps['Evento'] = split_cols[0].str.strip()
        df_cps['Ignição'] = split_cols[1].str.strip()
    except Exception as e:
        st.error(f"Falha ao tentar dividir a coluna 'Evento / Ignição'. Verifique o formato dos dados. Erro: {e}")
        return

    # 3. Extrair odômetros direto do texto (quando existir)
    try:
        odometro_cols = df_cps['Evento / Ignição'].apply(lambda txt: pd.Series(extrair_odometros(txt), index=['odometro', 'odometro_can']))
        df_cps = pd.concat([df_cps, odometro_cols], axis=1)
    except Exception:
        df_cps['odometro'] = None
        df_cps['odometro_can'] = None

    st.dataframe(df_cps)

    st.markdown("---")
    st.subheader("Gerar Mapas de Geolocalização")
    st.info("Como o relatório não possui coordenadas, usaremos a coluna 'Localização' para geocodificar os endereços. Este processo pode ser lento.")

    if st.button("Gerar Coordenadas e Mapas"):
        with st.spinner("Geocodificando endereços... Isso pode levar vários minutos."):
            unique_addresses = df_cps['Localização'].dropna().unique()
            
            # Chama a função de geocodificação
            address_coords = geocode_addresses(tuple(unique_addresses))
            
            # Mapeia as coordenadas de volta para o dataframe
            df_cps['lat'] = df_cps['Localização'].map(lambda x: address_coords.get(x, {}).get('lat'))
            df_cps['lon'] = df_cps['Localização'].map(lambda x: address_coords.get(x, {}).get('lon'))

            st.session_state.df_cps_geocoded = df_cps.copy()

    if 'df_cps_geocoded' in st.session_state:
        df_geocoded = st.session_state.df_cps_geocoded.copy()
        
        # Remove linhas que não puderam ser geocodificadas
        df_mapa = df_geocoded.dropna(subset=['lat', 'lon'])
        
        # Garante que as coordenadas são numéricas
        df_mapa['lat'] = pd.to_numeric(df_mapa['lat'])
        df_mapa['lon'] = pd.to_numeric(df_mapa['lon'])

        num_geocoded = len(df_mapa)
        num_total = len(df_geocoded)
        st.success(f"{num_geocoded} de {num_total} endereços foram geocodificados com sucesso.")

        if num_geocoded > 0:
            # MAPA 1: Evento Posição (ON/OFF)
            st.markdown("---")
            st.subheader("Mapa de Dispositivos por Posição (ON/OFF)")

            df_mapa['Ignição'] = df_mapa['Ignição'].str.lower()
            
            # Adicionando uma coluna de cor para a legenda do mapa
            def get_color(status):
                if status == 'on':
                    return [0, 255, 0]  # Green
                elif status == 'off':
                    return [255, 0, 0]  # Red
                else:
                    return [128, 128, 128] # Gray

            df_mapa['color'] = df_mapa['Ignição'].apply(get_color)

            # O evento "Posição" parece ser o evento principal para ON/OFF
            df_on = df_mapa[df_mapa['Evento'].str.contains("Posição", case=False, na=False) & (df_mapa['Ignição'] == 'on')]
            df_off = df_mapa[df_mapa['Evento'].str.contains("Posição", case=False, na=False) & (df_mapa['Ignição'] == 'off')]

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Dispositivos com Posição e Ignição ON", len(df_on))
                if not df_on.empty:
                    st.map(df_on, latitude='lat', longitude='lon', color='color')
                else:
                    st.info("Nenhum dispositivo com 'Posição' e ignição 'ON' encontrado.")
            
            with col2:
                st.metric("Dispositivos com Posição e Ignição OFF", len(df_off))
                if not df_off.empty:
                    st.map(df_off, latitude='lat', longitude='lon', color='color')
                else:
                    st.info("Nenhum dispositivo com 'Posição' e ignição 'OFF' encontrado.")

            # MAPA 2: Status de Evento
            st.markdown("---")
            st.subheader("Mapa de Dispositivos por Status de Evento")
            
            # Criar colunas para os filtros
            col1_filter, col2_filter = st.columns(2)

            with col1_filter:
                # Filtro de Eventos
                eventos = df_mapa['Evento'].dropna().unique()
                # Remove 'on' e 'off' se estiverem na lista de eventos, para evitar redundância
                eventos_filtrados = [e for e in eventos if str(e).lower() not in ['on', 'off']]
                evento_selecionado = st.selectbox("Selecione um Evento:", options=['Todos'] + sorted(eventos_filtrados))

            with col2_filter:
                # Filtro de Ignição
                ignicao_selecionada = st.selectbox("Selecione a Ignição:", options=['Ambas', 'On', 'Off'])

            # Aplicar filtros
            df_filtrado = df_mapa.copy()

            # Filtro por evento selecionado
            if evento_selecionado != 'Todos':
                df_filtrado = df_filtrado[df_filtrado['Evento'] == evento_selecionado]

            # Filtro por ignição selecionada
            if ignicao_selecionada != 'Ambas':
                df_filtrado = df_filtrado[df_filtrado['Ignição'].str.lower() == ignicao_selecionada.lower()]

            st.metric(f"Dispositivos Encontrados", len(df_filtrado))

            if not df_filtrado.empty:
                # 'Placa / Identificação' e 'Data/Hora Evento' foram fornecidas pelo usuário
                display_cols = [col for col in ['Placa / Identificação', 'Data/Hora Evento', 'Evento', 'Ignição', 'Localização', 'odometro', 'odometro_can'] if col in df_filtrado.columns]
                
                st.map(df_filtrado, latitude='lat', longitude='lon', color='color')
                st.dataframe(df_filtrado[display_cols])
            else:
                st.info("Nenhum dispositivo encontrado para os filtros selecionados.")
        else:
            st.warning("Nenhum endereço pôde ser exibido no mapa.")
