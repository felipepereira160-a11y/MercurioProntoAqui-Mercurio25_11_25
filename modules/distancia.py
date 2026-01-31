# modules/distancia.py
import streamlit as st
import pandas as pd
from modules.utils import safe_to_numeric, convert_df_to_csv, convert_df_to_excel # Import convert_df_to_csv and convert_df_to_excel for download
from modules.tutorial_helper import tutorial_button
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import pydeck as pdk

# Helper function to find column names flexibly
def _find_column(df_columns, possible_names):
    for name in possible_names:
        # Check for exact match first
        if name in df_columns:
            return name
        # Then check for case-insensitive match
        for col in df_columns:
            if col.lower() == name.lower():
                return col
    return None

@st.cache_data
def geocode_addresses(addresses):
    """
    Converte uma lista de endereços em coordenadas (latitude, longitude)
    usando Nominatim e exibe uma barra de progresso.
    """
    geolocator = Nominatim(user_agent="mercurio_app")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
    
    coords = {}
    
    progress_bar = st.progress(0, text="Geocodificando endereços...")
    total = len(addresses)
    
    for i, address in enumerate(addresses):
        try:
            location = geocode(address)
            if location:
                coords[address] = {'lat': location.latitude, 'lon': location.longitude}
            else:
                coords[address] = {'lat': None, 'lon': None}
        except Exception as e:
            # st.warning(f"Não foi possível geocodificar o endereço '{address}': {e}") # Suppress warning for each failure
            coords[address] = {'lat': None, 'lon': None}
        
        progress_bar.progress((i + 1) / total)
    progress_bar.empty() # Clear the progress bar after completion
    return coords

def analisar_distancia_percorrida():
    """
    Seção para analisar e consolidar relatórios de distância percorrida.
    """
    tutorial_button("Viagens", "Análise de Viagens e Distância Percorrida")
    st.info("Carregue um ou mais relatórios de 'Distância Percorrida' em formato .xlsx. O cabeçalho é esperado na linha 8.")

    uploaded_files = st.file_uploader(
        "Selecione os relatórios de distância",
        type=['xlsx'],
        accept_multiple_files=True,
        key="distancia_uploader"
    )

    if uploaded_files:
        if st.button("Analisar Distância Percorrida", use_container_width=True):
            all_dfs = []
            
            # Define a mapping of logical column names to possible actual column names
            column_name_map = {
                'Placa / Identificação': ['Placa / Identificação', 'Placa', 'Identificação'],
                'Proprietário': ['Proprietário', 'Proprietario'],
                # 'Data': ['Data', 'Data da Viagem'], # Removed: 'Data' is not mandatory, 'Início' serves this purpose
                'Percorrido (Km)': ['Percorrido (Km)', 'Distância (Km)', 'Distancia Km'],
                'Tempo Viagem': ['Tempo', 'Tempo Viagem', 'Tempo de Viagem'],
                'Início': ['Início', 'Inicio', 'Data/Hora Início'],
                'Fim': ['Fim', 'Data/Hora Fim'],
                'Média (km/h)': ['Média (km/h)', 'Media (km/h)', 'Velocidade Média'],
                'Máxima (km/h)': ['Máxima (km/h)', 'Maxima (km/h)', 'Velocidade Máxima'],
                'Frota': ['Frota'], # New column from user request
                'Identificador': ['Identificador'], # New column from user request
                'Motorista': ['Motorista', 'Nome do Motorista'],
                'Localização Inicial': ['Localização Inicial', 'Localizacao Inicial', 'Endereço Inicial'],
                'Localização Final': ['Localização Final', 'Localizacao Final', 'Endereço Final']
            }

            # Standardized column names for later use
            col_placa_id = 'Placa / Identificação'
            col_proprietario = 'Proprietário'
            col_distancia = 'Percorrido (Km)'
            col_tempo_viagem = 'Tempo Viagem'
            col_inicio = 'Início'
            col_fim = 'Fim'
            col_media = 'Média (km/h)'
            col_maxima = 'Máxima (km/h)'
            col_frota = 'Frota'
            col_identificador = 'Identificador'
            col_marca_modelo = 'Marca / Modelo' # New column from user request

            progress_bar = st.progress(0, text="Iniciando processamento...")



            total_files = len(uploaded_files)

            with st.spinner("Processando arquivos... Isso pode levar alguns minutos dependendo do volume de dados."):
                for i, file in enumerate(uploaded_files):
                    progress_bar.progress((i + 1) / total_files, text=f"Analisando {file.name}")
                    try:
                        # --- Dynamic Header Detection ---
                        # Read a small chunk of the file without a header to detect the best header row
                        # Read enough rows to cover potential headers (e.g., up to line 8, which is index 7)
                        temp_df_for_header_detection = pd.read_excel(file, header=None, nrows=8) 
                        
                        best_header_row = -1
                        max_matches = 0
                        
                        # Check potential header rows (0-indexed)
                        # Line 7 is index 6, Line 8 is index 7
                        potential_header_rows = [6, 7] 

                        for row_idx in potential_header_rows: # Iterate through potential header rows
                            if row_idx < len(temp_df_for_header_detection):
                                # Use the row as potential column names
                                potential_cols = temp_df_for_header_detection.iloc[row_idx].astype(str).tolist()
                                
                                current_matches = 0
                                # Count how many of the *logical* column names can be found in this potential header
                                for logical_name in column_name_map.keys():
                                    if _find_column(potential_cols, column_name_map[logical_name]):
                                        current_matches += 1
                                
                                if current_matches > max_matches:
                                    max_matches = current_matches
                                    best_header_row = row_idx
                        
                        if best_header_row == -1: # If no good header was detected
                            st.warning(f"Não foi possível detectar o cabeçalho no arquivo '{file.name}' (linhas 7 ou 8). Tentando com a linha 8 (padrão).")
                            # Fallback to line 8 (index 7) as header
                            df = pd.read_excel(file, header=7)
                        else:
                            # Re-read the file with the detected header
                            df = pd.read_excel(file, header=best_header_row)
                        # --- End Dynamic Header Detection ---
                        
                        # Dynamically find actual column names and store them
                        found_cols_for_df = {}
                        missing_cols_for_file = []
                        for logical_name, possible_names in column_name_map.items():
                            actual_name = _find_column(df.columns, possible_names)
                            if actual_name:
                                found_cols_for_df[logical_name] = actual_name
                            else:
                                missing_cols_for_file.append(logical_name)

                        if missing_cols_for_file:
                            st.warning(f"O arquivo '{file.name}' não contém as seguintes colunas necessárias e será ignorado: {', '.join(missing_cols_for_file)}. Colunas esperadas (exemplos): {', '.join(column_name_map.keys())}.")
                            continue
                        
                        # --- Limpeza e Preparação dos Dados ---
                        # All required columns are found, now select and rename them to standardized names
                        df_filtered = df[list(found_cols_for_df.values())].copy()
                        df_filtered.rename(columns={v: k for k, v in found_cols_for_df.items()}, inplace=True)

                        # Ensure critical columns are present after renaming
                        df_filtered.dropna(subset=[col_placa_id, col_inicio], inplace=True)

                        # Converter colunas para o tipo correto
                        if df_filtered['Percorrido (Km)'].dtype == 'object':
                            df_filtered['Percorrido (Km)'] = df_filtered['Percorrido (Km)'].astype(str).str.replace(',', '.', regex=False)
                        df_filtered['Percorrido (Km)'] = pd.to_numeric(df_filtered['Percorrido (Km)'], errors='coerce').fillna(0)

                        # Converter as colunas de média e máxima para numérico
                        df_filtered['Média (km/h)'] = safe_to_numeric(df_filtered['Média (km/h)'])
                        df_filtered['Máxima (km/h)'] = safe_to_numeric(df_filtered['Máxima (km/h)'])

                        # Converter as colunas de data de início e fim para datetime
                        df_filtered['Início'] = pd.to_datetime(df_filtered['Início'], errors='coerce')
                        df_filtered['Fim'] = pd.to_datetime(df_filtered['Fim'], errors='coerce')

                        # Remover linhas com valores NaT (Not a Time) nas colunas de data
                        df_filtered = df_filtered.dropna(subset=['Início', 'Fim'])

                        # Formatar as colunas de data para exibição
                        df_filtered['Inicio_Formatado'] = df_filtered['Início'].dt.strftime('%d/%m/%Y %H:%M')
                        df_filtered['Fim_Formatado'] = df_filtered['Fim'].dt.strftime('%d/%m/%Y %H:%M')

                        # Ensure 'Tempo Viagem' is timedelta, handle potential string formats like 'HH:MM:SS'
                        def parse_time_string(time_str):
                            if pd.isna(time_str):
                                return pd.Timedelta(seconds=0)
                            try:
                                # Try parsing as HH:MM:SS
                                return pd.to_timedelta(time_str)
                            except ValueError:
                                # If that fails, try parsing as a generic string (e.g., '00:54:52')
                                parts = str(time_str).split(':')
                                if len(parts) == 3:
                                    return pd.Timedelta(hours=int(parts[0]), minutes=int(parts[1]), seconds=int(parts[2]))
                                return pd.Timedelta(seconds=0) # Fallback

                        df_filtered['Tempo Viagem'] = df_filtered['Tempo Viagem'].apply(parse_time_string)
                        
                        all_dfs.append(df_filtered)

                        # Store geocoded data for mapping
                        st.session_state.df_viagens_geocoded = pd.DataFrame() # Initialize
                        st.session_state.df_viagens_geocoded_start = pd.DataFrame()
                        st.session_state.df_viagens_geocoded_end = pd.DataFrame()
                    except Exception as e:
                        st.error(f"Erro ao processar o arquivo '{file.name}': {e}")
            
            progress_bar.empty()
            if not all_dfs:
                st.warning("Nenhum dado válido foi processado. Verifique o formato e o conteúdo dos arquivos.")
                st.session_state.pop('df_distancia_agregada', None)
                st.session_state.pop('df_distancia_detalhada', None)
                return

            # --- Consolidação e Agregação ---
            df_final = pd.concat(all_dfs, ignore_index=True)
            st.session_state.df_distancia_detalhada = df_final.copy() # Store detailed trips
            
            # Agrupar por placa e proprietário para somar a distância e o tempo totais de todo o período.
            df_agregado = df_final.groupby([col_placa_id, col_proprietario]).agg(
                Distancia_Total_Km=(col_distancia, 'sum'),
                Tempo_Total_Viagem=(col_tempo_viagem, 'sum'),
                Media_Km_h=(col_media, 'mean'), # Mean of individual trip averages
                Maxima_Km_h=(col_maxima, 'max') # Max of individual trip maximums
            ).reset_index()

            # Ordenar os resultados pela maior distância percorrida.
            df_agregado = df_agregado.sort_values(by='Distancia_Total_Km', ascending=False)            
            st.session_state.df_distancia_agregada = df_agregado.copy()

            # --- Geocodificação para Mapas ---
            st.markdown("---")
            st.subheader("Geocodificação de Localizações para Mapas")
            st.info("As localizações inicial e final serão geocodificadas para exibição no mapa. Este processo pode levar alguns minutos.")
            
            if st.button("Geocodificar Localizações e Gerar Mapas", use_container_width=True):
                with st.spinner("Geocodificando endereços..."):
                    all_locations = pd.concat([df_final['Localização Inicial'].dropna(), df_final['Localização Final'].dropna()]).unique()
                    
                    if len(all_locations) > 0:
                        address_coords = geocode_addresses(tuple(all_locations))
                        
                        df_final['lat_inicio'] = df_final['Localização Inicial'].map(lambda x: address_coords.get(x, {}).get('lat'))
                        df_final['lon_inicio'] = df_final['Localização Inicial'].map(lambda x: address_coords.get(x, {}).get('lon'))
                        df_final['lat_fim'] = df_final['Localização Final'].map(lambda x: address_coords.get(x, {}).get('lat'))
                        df_final['lon_fim'] = df_final['Localização Final'].map(lambda x: address_coords.get(x, {}).get('lon'))

                        st.session_state.df_viagens_geocoded = df_final.copy()
                        
                        # Prepare data for start and end point maps
                        df_start_points = df_final.dropna(subset=['lat_inicio', 'lon_inicio']).rename(columns={'lat_inicio': 'lat', 'lon_inicio': 'lon'})
                        df_end_points = df_final.dropna(subset=['lat_fim', 'lon_fim']).rename(columns={'lat_fim': 'lat', 'lon_fim': 'lon'})
                        
                        # Add tooltips for pydeck
                        df_start_points['tooltip'] = df_start_points.apply(lambda row: f"Início: {row['Localização Inicial']}<br>Placa: {row[col_placa_id]}<br>Motorista: {row['Motorista']}", axis=1)
                        df_end_points['tooltip'] = df_end_points.apply(lambda row: f"Fim: {row['Localização Final']}<br>Placa: {row[col_placa_id]}<br>Motorista: {row['Motorista']}", axis=1)

                        st.session_state.df_viagens_geocoded_start = df_start_points
                        st.session_state.df_viagens_geocoded_end = df_end_points
                        st.success("Geocodificação concluída e dados de mapa preparados!")
                    else:
                        st.info("Nenhuma localização para geocodificar.")
            else:
                st.info("Clique no botão acima para geocodificar as localizações e visualizar os mapas.")

    # --- Display Results ---
    if 'df_distancia_agregada' in st.session_state and st.session_state.df_distancia_agregada is not None:
        # --- Helper functions for formatting ---
        df_agregado = st.session_state.df_distancia_agregada.copy()

    # --- Display Results ---
    if 'df_distancia_agregada' in st.session_state and st.session_state.df_distancia_agregada is not None:
        # --- Helper functions for formatting ---
        df_agregado = st.session_state.df_distancia_agregada.copy()

        
        # --- Preparação para Exibição ---
        df_display = df_agregado.copy()

        # 1. Adicionar coluna com o total de horas em formato decimal
        df_display['Tempo_Total_Horas'] = df_display['Tempo_Total_Viagem'].dt.total_seconds() / 3600

        # 2. Função para formatar o timedelta no formato "dias, HH:MM:SS"
        def format_timedelta_with_days(td):
            if pd.isnull(td):
                return "0 dias, 00:00:00"
            days = td.days
            hours, remainder = divmod(td.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{days} dias, {hours:02}:{minutes:02}:{seconds:02}"

        def format_brazilian_number(n, decimals=2):
            try:
                if pd.isna(n):
                    return "N/A"
                s = f"{{:,.{decimals}f}}".format(n)
                s = s.replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.')
                return s
            except (ValueError, TypeError):
                return n
                return str(n)

        # --- Aggregated Summary ---
        st.subheader("Resultado Consolidado por Veículo")
        df_display_agregado = df_agregado.copy()
        df_display_agregado['Tempo_Total_Horas'] = df_display_agregado['Tempo_Total_Viagem'].dt.total_seconds() / 3600
        df_display_agregado['Tempo Total (Dias, H:M:S)'] = df_display_agregado['Tempo_Total_Viagem'].apply(format_timedelta_with_days)
        df_display_agregado['Distancia_Total_Km'] = df_display_agregado['Distancia_Total_Km'].apply(lambda x: format_brazilian_number(x, 2))
        df_display_agregado['Tempo_Total_Horas'] = df_display_agregado['Tempo_Total_Horas'].apply(lambda x: format_brazilian_number(x, 2))
        df_display_agregado['Média (km/h)'] = df_display_agregado['Media_Km_h'].apply(lambda x: format_brazilian_number(x, 2))
        df_display_agregado['Máxima (km/h)'] = df_display_agregado['Maxima_Km_h'].apply(lambda x: format_brazilian_number(x, 2))

        df_display_agregado = df_display_agregado.rename(columns={
            'Tempo_Total_Viagem_Formatado': 'Tempo Total (Dias, H:M:S)',
            'Tempo_Total_Horas': 'Tempo Total (Horas)'
        })

        display_order_agregado = [
            'Placa / Identificação', 
            'Proprietário',
            'Média (km/h)',
            'Máxima (km/h)',
            'Frota', # New column
            'Marca / Modelo', # New column
            'Distancia_Total_Km',
            'Tempo Total (Dias, H:M:S)', 
            'Tempo Total (Horas)'
        ]
        # Filtra para garantir que apenas colunas existentes sejam usadas
        existing_display_order_agregado = [col for col in display_order_agregado if col in df_display_agregado.columns]
        st.dataframe(df_display_agregado[existing_display_order_agregado], use_container_width=True)

        # Download for aggregated data
        df_download_agregado = df_agregado.copy()
        df_download_agregado = df_agregado.copy() # Use the aggregated DF for download
        df_download_agregado['Tempo_Total_Horas'] = df_download_agregado['Tempo_Total_Viagem'].dt.total_seconds() / 3600
        df_download_agregado['Tempo_Total_Viagem'] = df_download_agregado['Tempo_Total_Viagem'].apply(format_timedelta_with_days)
        st.download_button(
            label="📥 Baixar Resumo Consolidado (CSV)",
            data=convert_df_to_csv(df_download_agregado),
            file_name='distancia_consolidada_resumo.csv',
            mime='text/csv',
            key='download_consolidado'
        )

        st.markdown("---")
        st.subheader("Detalhes de Todas as Viagens")
        # Display detailed trips
        df_detalhada = st.session_state.df_distancia_detalhada.copy()
        df_display_detalhada = df_detalhada.copy()
        df_display_detalhada['Percorrido (Km)'] = df_display_detalhada['Percorrido (Km)'].apply(lambda x: format_brazilian_number(x, 2))
        df_display_detalhada['Média (km/h)'] = df_display_detalhada['Média (km/h)'].apply(lambda x: format_brazilian_number(x, 2))
        df_display_detalhada['Máxima (km/h)'] = df_display_detalhada['Máxima (km/h)'].apply(lambda x: format_brazilian_number(x, 2))
        df_display_detalhada['Tempo Viagem'] = df_display_detalhada['Tempo Viagem'].apply(format_timedelta_with_days)


        display_order_detalhada = [
            'Placa / Identificação',
            'Proprietário',
            'Frota', # New column
            'Motorista',
            'Identificador', # New column
            'Marca / Modelo', # New column
            'Inicio_Formatado',
            'Fim_Formatado',
            'Tempo Viagem',
            'Percorrido (Km)',
            'Média (km/h)', # This was already there
            'Máxima (km/h)',
            'Localização Inicial',
            'Localização Final'
        ]
        existing_display_order_detalhada = [col for col in display_order_detalhada if col in df_display_detalhada.columns]
        st.dataframe(df_display_detalhada[existing_display_order_detalhada], use_container_width=True)

        # Download for detailed trips
        df_download_detalhada = df_detalhada.copy() # Re-added this line
        df_download_detalhada['Tempo Viagem'] = df_download_detalhada['Tempo Viagem'].apply(format_timedelta_with_days)
        st.download_button(
            label="📥 Baixar Detalhes das Viagens (XLSX)",
            data=convert_df_to_excel(df_download_detalhada),
            file_name='distancia_consolidada_detalhes.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            key='download_detalhes'
        )

    # --- Map Display Section ---
    if 'df_viagens_geocoded' in st.session_state and not st.session_state.df_viagens_geocoded.empty:
        st.markdown("---")
        st.subheader("Mapas de Localizações de Viagem")
        
        df_start_points = st.session_state.df_viagens_geocoded_start
        df_end_points = st.session_state.df_viagens_geocoded_end

        if not df_start_points.empty:
            st.markdown("#### Localizações Iniciais das Viagens")
            # Filter out invalid coordinates (e.g., 0,0 or outside typical ranges)
            df_start_points_valid = df_start_points[
                (df_start_points['lat'].between(-90, 90)) &
                (df_start_points['lon'].between(-180, 180)) &
                ((df_start_points['lat'] != 0) | (df_start_points['lon'] != 0))
            ]
            if not df_start_points_valid.empty:
                view_state_start = pdk.ViewState(
                    latitude=df_start_points_valid['lat'].mean(),
                    longitude=df_start_points_valid['lon'].mean(),
                    zoom=8,
                    pitch=0
                )
                layer_start = pdk.Layer(
                    "ScatterplotLayer",
                    data=df_start_points_valid,
                    get_position=['lon', 'lat'],
                    get_color=[0, 128, 255, 160], # Blue
                    get_radius=100,
                    pickable=True,
                    tooltip={"html": "{tooltip}"}
                )
                st.pydeck_chart(pdk.Deck(
                    map_style='mapbox://styles/mapbox/light-v9',
                    initial_view_state=view_state_start,
                    layers=[layer_start]
                ))
            else:
                st.info("Nenhuma localização inicial válida para exibir no mapa.")

        if not df_end_points.empty:
            st.markdown("#### Localizações Finais das Viagens")
            # Filter out invalid coordinates
            df_end_points_valid = df_end_points[
                (df_end_points['lat'].between(-90, 90)) &
                (df_end_points['lon'].between(-180, 180)) &
                ((df_end_points['lat'] != 0) | (df_end_points['lon'] != 0))
            ]
            if not df_end_points_valid.empty:
                view_state_end = pdk.ViewState(
                    latitude=df_end_points_valid['lat'].mean(),
                    longitude=df_end_points_valid['lon'].mean(),
                    zoom=8,
                    pitch=0
                )
                layer_end = pdk.Layer(
                    "ScatterplotLayer",
                    data=df_end_points_valid,
                    get_position=['lon', 'lat'],
                    get_color=[255, 0, 0, 160], # Red
                    get_radius=100,
                    pickable=True,
                    tooltip={"html": "{tooltip}"}
                )
                st.pydeck_chart(pdk.Deck(
                    map_style='mapbox://styles/mapbox/light-v9',
                    initial_view_state=view_state_end,
                    layers=[layer_end]
                ))
            else:
                st.info("Nenhuma localização final válida para exibir no mapa.")
