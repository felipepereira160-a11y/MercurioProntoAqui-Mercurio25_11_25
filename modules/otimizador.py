# modules/otimizador.py (CÓDIGO CORRIGIDO PARA KEYERROR DE COORDENADAS)
import streamlit as st
import pandas as pd
from haversine import haversine, Unit
from modules.utils import convert_df_to_csv 
from modules.tutorial_helper import tutorial_button

# --- FUNÇÃO HELPER (DD/MM/AAAA) ---
def format_date_safe(t):
    """Converte para data e formata, retornando 'N/A' se for NaT."""
    dt = pd.to_datetime(t, errors='coerce')
    if pd.isna(dt):
        return 'N/A'
    return dt.strftime('%d/%m/%Y')
# --- FIM DA FUNÇÃO HELPER ---

@st.cache_data
def _calcular_distancias_e_custos(df_map, cidade_atendimento, ponto, map_rep_col, map_city_col, map_valor_km_col, 
                                  map_tel_col, map_abrang_col, map_km_col, map_rep_lat, map_rep_lon, map_rep_city_col, map_rep_uf_col, incluir_especiais):
    """
    Calcula distâncias (Haversine para ranking), custos (KM Fixo para regra) e RT sugerido para um único ponto (cidade).
    Retorna o dataframe de distâncias e o RT sugerido.
    """
    distancias = []
    
    try:
        ponto_lat = float(str(ponto[0]).replace(',', '.'))
        ponto_lon = float(str(ponto[1]).replace(',', '.'))
        ponto_limpo = (ponto_lat, ponto_lon)
    except (ValueError, TypeError, IndexError):
        # Este erro é crítico, mas não deve parar a aplicação
        return pd.DataFrame(), None # Retorna vazio

    # 🚨 CORREÇÃO CRÍTICA: Filtra os RTs especiais ANTES de qualquer cálculo
    df_map_filtrado = df_map.copy()
    if not incluir_especiais:
        termos_excluidos = ['STELLANTIS', 'CEABS', 'FCA CHRYSLER']
        mascara = ~df_map_filtrado[map_rep_col].str.contains('|'.join(termos_excluidos), case=False, na=False)
        df_map_filtrado = df_map_filtrado[mascara]

    # Pega a lista de RTs únicos para iterar
    rts_unicos = df_map_filtrado.drop_duplicates(subset=[map_rep_col])

    for _, rt_base in rts_unicos.iterrows():
        try:
            # 🚨 CORREÇÃO: Usando as variáveis flexíveis de Lat/Lon do RT
            lat_rt = float(str(rt_base[map_rep_lat]).replace(',', '.'))
            lon_rt = float(str(rt_base[map_rep_lon]).replace(',', '.'))
            # 1. Distância Haversine: Usada APENAS para ranking (Otimização)
            dist_haversine = haversine((lat_rt, lon_rt), ponto_limpo, unit=Unit.KILOMETERS)
        except (ValueError, TypeError):
            dist_haversine = float('inf') 
        
        # 2. KM Fixo: Usado para o CÁLCULO do custo (Regra de Negócio)
        # 🚨 CORREÇÃO: Garante que o fallback para Haversine seja usado se o KM fixo for inválido ou ausente.
        rt_nome = rt_base[map_rep_col]
        rota_especifica = df_map_filtrado[
            (df_map_filtrado[map_rep_col] == rt_nome) & 
            (df_map_filtrado[map_city_col].str.upper() == cidade_atendimento.upper())
        ]
        
        if not rota_especifica.empty:
            dados_rota = rota_especifica.iloc[0]
            km_fixo_custo = pd.to_numeric(dados_rota.get(map_km_col), errors='coerce')
            valor_km = pd.to_numeric(dados_rota.get(map_valor_km_col), errors='coerce')
            abrangencia = pd.to_numeric(dados_rota.get(map_abrang_col), errors='coerce')
        else: # Se a rota específica não existe, zera os custos fixos
            km_fixo_custo, valor_km, abrangencia = None, None, None

        # Se o KM Fixo não for um número válido, usa a distância Haversine como fallback
        if not (pd.notna(km_fixo_custo) and km_fixo_custo > 0):
            km_fixo_custo = dist_haversine
        
        distancias.append({
            'Representante': str(rt_nome), 
            'Distancia (km)': dist_haversine, # Para ranking de proximidade
            'KM_Fixo_Custo': km_fixo_custo, # Para o cálculo da regra
            'Valor_KM': valor_km if pd.notna(valor_km) else 0,
            'Abrangencia': abrangencia if pd.notna(abrangencia) else 0, 
            'Telefone': rt_base[map_tel_col] if map_tel_col else "N/A",
            'Cidade RT': rt_base[map_rep_city_col] if map_rep_city_col and map_rep_city_col in rt_base else "N/A",
            'UF RT': rt_base[map_rep_uf_col] if map_rep_uf_col and map_rep_uf_col in rt_base else "N/A"
        })
        
    df_dist = pd.DataFrame(distancias).drop_duplicates(subset=['Representante']).reset_index(drop=True)
    df_dist = df_dist[df_dist['Distancia (km)'] != float('inf')] 
    
    df_dist['Valor_KM'] = pd.to_numeric(df_dist['Valor_KM'], errors='coerce').fillna(0)
    df_dist['Abrangencia'] = pd.to_numeric(df_dist['Abrangencia'], errors='coerce').fillna(0)
    df_dist['KM_Fixo_Custo'] = pd.to_numeric(df_dist['KM_Fixo_Custo'], errors='coerce')
    
    # --- CÁLCULO DO VALOR CORRETO PARA O RT SUGERIDO (KM Fixo * 2 - Abrangencia) ---
    df_dist['KM_TOTAL_BASE'] = df_dist['KM_Fixo_Custo'] * 2
    df_dist['KM_A_PAGAR'] = df_dist['KM_TOTAL_BASE'] - df_dist['Abrangencia']
    df_dist['KM_A_PAGAR'] = df_dist['KM_A_PAGAR'].clip(lower=0) # Garante que o KM a pagar não seja negativo
    df_dist['Custo_Correto_R$'] = df_dist['KM_A_PAGAR'] * df_dist['Valor_KM']
    # --- FIM DO CÁLCULO ---
        
    rt_sugerido = None
    if not df_dist.empty:
        rt_sugerido = df_dist.sort_values(by='Distancia (km)').iloc[0]
        
    return df_dist, rt_sugerido

def _arredondar_relatorio(df_report):
    """ Arredonda as colunas de custo e km para 2 casas decimais antes de exportar. """
    df_report_export = df_report.copy()
    format_cols = {'Valor Agendado': 2, 'Valor Sugerido': 2, 'Economia Potencial (R$)': 2, 'Distancia Sugerida (km)': 1}
    format_cols = {'Valor Agendado': 2, 'Valor Sugerido': 2, 'Economia Potencial (R$)': 2, 'Distancia Sugerida (km)': 1, 'Distancia Agendada (km)': 1}
    for col, decimals in format_cols.items():
        if col in df_report_export.columns:
            df_report_export[col] = pd.to_numeric(df_report_export[col], errors='coerce').round(decimals)
    return df_report_export

def _analisar_proximidade_agendamentos(df, data_col, rep_col, city_col, id_col, cliente_col, valor_desloc_col, pedagio_col, tel_cliente_col):
    """
    Analisa o dataframe para encontrar RTs agendados para a mesma cidade
    em um intervalo de 6 a 7 dias.
    """
    if not all([data_col, rep_col, city_col, id_col, cliente_col]):
        st.warning("Não foi possível realizar a análise de proximidade por falta de colunas essenciais.")
        return pd.DataFrame()

    # Seleciona e copia as colunas necessárias para evitar SettingWithCopyWarning
    cols_to_use = [id_col, data_col, rep_col, city_col, cliente_col]
    if valor_desloc_col and valor_desloc_col in df.columns:
        cols_to_use.append(valor_desloc_col)
    if pedagio_col and pedagio_col in df.columns:
        cols_to_use.append(pedagio_col)
    if tel_cliente_col and tel_cliente_col in df.columns:
        cols_to_use.append(tel_cliente_col)
    
    df_analysis = df[cols_to_use].copy()
    
    # Converte colunas de custo para numérico e preenche NaNs
    if valor_desloc_col and valor_desloc_col in df_analysis.columns:
        df_analysis[valor_desloc_col] = pd.to_numeric(df_analysis[valor_desloc_col], errors='coerce').fillna(0)
    if pedagio_col and pedagio_col in df_analysis.columns:
        df_analysis[pedagio_col] = pd.to_numeric(df_analysis[pedagio_col], errors='coerce').fillna(0)

    df_analysis['DATA_DT'] = pd.to_datetime(df_analysis[data_col], errors='coerce')
    
    # Remove linhas onde informações cruciais são nulas
    df_analysis.dropna(subset=['DATA_DT', rep_col, city_col, id_col], inplace=True)
    df_analysis[id_col] = df_analysis[id_col].astype(str)

    # Ordena para garantir a lógica de comparação
    df_analysis = df_analysis.sort_values(by=[rep_col, city_col, 'DATA_DT'])

    pares_encontrados = []
    processed_os_ids = set()

    # Itera sobre o dataframe para formar pares
    for i in range(len(df_analysis)):
        # Pega a primeira OS do par potencial
        os1 = df_analysis.iloc[i]
        os1_id = os1[id_col]

        # Se esta OS já foi agrupada, pula para a próxima
        if os1_id in processed_os_ids:
            continue

        # Inicia um novo grupo com a OS atual
        current_group = [os1]

        # Compara com todas as OSs subsequentes
        for j in range(i + 1, len(df_analysis)):
            os2 = df_analysis.iloc[j]
            os2_id = os2[id_col]

            # Condições para formar um par: mesmo RT, mesma cidade
            if (os1[rep_col] == os2[rep_col]) and (os1[city_col] == os2[city_col]):
                # Calcula a diferença de dias
                delta = (os2['DATA_DT'] - os1['DATA_DT']).days

                # Se a diferença está no intervalo desejado e a OS ainda não foi processada
                if delta in [6, 7] and os2_id not in processed_os_ids:
                    current_group.append(os2)
            # Se a cidade ou RT mudou, podemos parar de procurar pares para os1
            elif (os1[rep_col] != os2[rep_col]) or (os1[city_col] != os2[city_col]):
                break
        
        # Se encontramos um grupo (mais de uma OS)
        if len(current_group) > 1:
            group_id = f"Grupo_{len(pares_encontrados) + 1}"
            for os_item in current_group:
                # Calcula o custo (colunas já foram limpas)
                custo_desloc = os_item.get(valor_desloc_col, 0)
                custo_pedagio = os_item.get(pedagio_col, 0)
                custo_total = custo_desloc + custo_pedagio

                pares_encontrados.append({
                    'Grupo': group_id,
                    'Representante': os_item[rep_col],
                    'Cidade': os_item[city_col],
                    'Numero OS': os_item[id_col],
                    'Cliente': os_item[cliente_col],
                    'Telefone Cliente': os_item.get(tel_cliente_col, "N/A"),
                    'Data Agendamento': os_item['DATA_DT'].strftime('%d/%m/%Y'),
                    'Custo Agendado (R$)': custo_total
                })
                # Marca a OS como processada para não ser incluída em outros grupos
                processed_os_ids.add(os_item[id_col])

    if not pares_encontrados:
        return pd.DataFrame()

    return pd.DataFrame(pares_encontrados)

# --- FUNÇÃO PRINCIPAL DO OTIMIZADOR ---
def otimizador(df_dados, df_map, df_ultimaposicao=None, df_ativos=None):
    
    tutorial_button("Otimizador", "Otimizador de Rotas")
    
    try:
        # --- 1. IDENTIFICAR COLUNAS (NOVO MÉTODO FLEXÍVEL PARA COORDENADAS) ---
        os_id_col = next((c for c in df_dados.columns if 'os' in c.lower() or 'número da o.s' in c.lower() or 'numeropedido' in c.lower()), None)
        os_cliente_col = next((c for c in df_dados.columns if 'cliente' in c.lower() and 'id' not in c.lower()), None)
        os_city_col = next((c for c in df_dados.columns if 'cidade agendamento' in c.lower() or 'cidade o.s.' in c.lower()), None)
        os_rep_col = next((c for c in df_dados.columns if 'representante' in c.lower() and 'id' not in c.lower()), None)
        os_status_col = next((c for c in df_dados.columns if 'status' in c.lower()), None)
        os_uf_col = next((c for c in df_dados.columns if 'uf agendamento' in c.lower() or 'estado agendamento' in c.lower() or 'uf os' in c.lower() or 'estado os' in c.lower() or c.lower() == 'uf' or c.lower() == 'estado'), None)
        os_data_col = next((c for c in df_dados.columns if 'data agendamento' in c.lower() or 'data da os' in c.lower() or 'data_agenda' in c.lower()), None)
        os_periodo_col = next((c for c in df_dados.columns if 'período agendamento' in c.lower()), None)
        os_tel_cliente_col = next((c for c in df_dados.columns if 'telefone' in c.lower() and ('cliente' in c.lower() or 'contato' in c.lower())), None)

        if os_id_col:
            df_dados[os_id_col] = df_dados[os_id_col].astype(str).str.replace(r'\.10000$', '', regex=True).str.strip()

        if os_data_col:
            df_dados['DATA_FORMATADA'] = df_dados[os_data_col].apply(format_date_safe)
        else:
            df_dados['DATA_FORMATADA'] = "N/A"
            
        if os_periodo_col:
            df_dados['PERIODO_FINAL'] = df_dados[os_periodo_col].fillna('N/A')
        else:
            df_dados['PERIODO_FINAL'] = "N/A"

        # --- Identificação FLEXÍVEL de Colunas do Mapeamento ---
        colunas_map_lower = {c.lower().strip(): c for c in df_map.columns}

        map_rep = colunas_map_lower.get('nm_representante', next((c for k, c in colunas_map_lower.items() if 'representante' in k and 'nome' in k), None))
        map_city_col = colunas_map_lower.get('nm_cidade_atendimento', next((c for k, c in colunas_map_lower.items() if 'cidade' in k), None))

        # 🚨 CORREÇÃO DE ERRO: Identificação flexível de Lat/Lon de ATENDIMENTO (o ponto da OS)
        map_lat = next((c for k, c in colunas_map_lower.items() if ('latitude' in k or 'lat' in k) and 'atendimento' in k), None)
        map_lon = next((c for k, c in colunas_map_lower.items() if ('longitude' in k or 'lon' in k) and 'atendimento' in k), None)
        
        # 🚨 CORREÇÃO CRÍTICA: Identificação flexível de Lat/Lon de REPRESENTANTE (o ponto de partida)
        map_rep_lat = next((c for k, c in colunas_map_lower.items() if ('latitude' in k or 'lat' in k) and ('representante' in k or 'rt' in k)), None)
        map_rep_lon = next((c for k, c in colunas_map_lower.items() if ('longitude' in k or 'lon' in k) and ('representante' in k or 'rt' in k)), None)

        # Identificação da cidade do RT (prioriza colunas com 'nome' ou 'nm')
        map_rep_city_col = next((c for k, c in colunas_map_lower.items() if ('cidade' in k and ('representante' in k or 'rt' in k)) and ('nome' in k or 'nm' in k)), None)
        # Fallback: se não encontrar com 'nome', pega a primeira que encontrar (comportamento anterior)
        if not map_rep_city_col:
            map_rep_city_col = next((c for k, c in colunas_map_lower.items() if 'cidade' in k and ('representante' in k or 'rt' in k)), None)

        map_rep_uf_col = next((c for k, c in colunas_map_lower.items() if ('uf' in k or 'estado' in k) and ('representante' in k or 'rt' in k)), None)

        
        map_tel_col = next((c for c in df_map.columns if 'telefone' in c.lower()), None)
        map_valor_km_col = next((c for c in df_map.columns if 'valor km' in c.lower() or 'valor_km' in c.lower() or 'valor deslocamento' in c.lower()), None)
        
        abrangencia_names = ['abrangência', 'abrangencia', 'v']
        map_abrang_col = next((c for c in df_map.columns if c.lower().strip() in abrangencia_names), None)
        km_fixo_names = ['qt_distancia_atendimento_km', 'distancia_km', 'distancia (km)', 'km']
        map_km_col = next((c for c in df_map.columns if c.lower().strip() in km_fixo_names), None)
        
        # --- FIM DA IDENTIFICAÇÃO FLEXÍVEL ---


        if map_rep: df_map[map_rep] = df_map[map_rep].astype(str).str.strip().str.upper()
        if os_rep_col: df_dados[os_rep_col] = df_dados[os_rep_col].astype(str).str.strip().str.upper()

        required = [os_id_col, os_cliente_col, os_city_col, os_rep_col, os_status_col, map_rep, map_lat, map_lon, map_rep_lat, map_rep_lon]
        if not all(required):
            st.warning("Planilhas de Agendamento ou Mapeamento com colunas obrigatórias ausentes.")
            
            missing_map = {
                os_id_col: 'ID da O.S.', map_rep: 'Nome Representante (Mapeamento)', 
                map_lat: 'Latitude Atendimento (Cidade)', map_lon: 'Longitude Atendimento (Cidade)', 
                map_rep_lat: 'Latitude Representante (Ponto Partida)', map_rep_lon: 'Longitude Representante (Ponto Partida)'
            }
            missing = [f"{name} (Não Encontrada)" for col, name in missing_map.items() if col is None]
            st.error(f"Colunas de Coordenada ou Chave não encontradas no Mapeamento: {', '.join(missing)}")
            return

        if not map_rep_city_col:
            st.warning("Coluna 'Cidade Representante' não encontrada no Mapeamento. O relatório será gerado sem essa informação.")
            
        if not map_valor_km_col:
            st.warning("Não foi possível encontrar a coluna 'Valor KM' ou 'Valor Deslocamento' no arquivo de Mapeamento. O cálculo de custo não estará disponível.")
        
        if not map_abrang_col:
             st.warning("Não foi possível encontrar a coluna 'Abrangência' ou 'V' no arquivo de Mapeamento. O cálculo do Custo Correto será feito sem subtração de abrangência.")
             
        if not map_km_col:
             st.warning("Não foi possível encontrar a coluna 'qt_distancia_atendimento_km' ou similar. O cálculo do Custo Correto será feito usando a distância Haversine * 2 em vez do KM Fixo.")

        # --- Identificação de Colunas para o "Valor Liberado" do Dashboard ---
        valor_deslocamento_dashboard_col = next((c for c in df_dados.columns if 'valor deslocamento' in c.lower()), None)
        pedagio_dashboard_col = next((c for c in df_dados.columns if 'pedágio' in c.lower() or 'pedagio' in c.lower()), None)

        if not valor_deslocamento_dashboard_col:
            st.warning("Coluna 'Valor Deslocamento' não encontrada na planilha de Agendamentos/Dashboard. O 'Valor Agendado' será considerado 0 para o cálculo de economia.")
        if not pedagio_dashboard_col:
            st.warning("Coluna 'Pedágio' não encontrada na planilha de Agendamentos/Dashboard. O 'Valor Agendado' será considerado 0 para o cálculo de economia.")

        # --- 2. FILTROS ---
        st.subheader("Filtros de Análise")
        
        col_f1, col_f2 = st.columns([3, 1])
        with col_f1:
            all_statuses = df_dados[os_status_col].dropna().unique().tolist()
            default_selection = [s for s in ['Agendada', 'Pendente', 'Aguardando Agendamento', 'Serviços realizados', 'Parcialmente realizado'] if s in all_statuses]
            status_selecionados = st.multiselect("1. Selecione os status para análise:", options=all_statuses, default=default_selection)
        with col_f2:
            incluir_especiais = st.toggle("Incluir RTs Especiais", value=False, help="Marca esta opção para incluir RTs de contratos especiais (Ceabs, Stellantis, etc.) na análise.")

        df_otim = df_dados[df_dados[os_status_col].isin(status_selecionados)].copy()
        if df_otim.empty:
            st.info(f"Nenhuma ordem encontrada com os status selecionados.")
            return

        # Filtro para excluir clientes específicos
        clientes_a_excluir = ['LIGHT SERVICOS DE ELETRICIDADE S/A', 'FCA CRHYSLER', 'FCA FIAT CHRYSLER AUTOMOVEIS BRASIL LTDA']
        if os_cliente_col:
            # Garante que a coluna do cliente seja string para usar o .str
            df_otim = df_otim[~df_otim[os_cliente_col].astype(str).str.contains('|'.join(clientes_a_excluir), case=False, na=False)]
        
        if df_otim.empty:
            st.info(f"Nenhuma ordem encontrada após a exclusão dos clientes '{', '.join(clientes_a_excluir)}'.")
            return

        col_f3, col_f4 = st.columns(2)
        uf_selecionado = None
        df_filtrado_uf = df_otim.copy() 
        
        if os_uf_col:
            with col_f3:
                lista_ufs = sorted(df_otim[os_uf_col].dropna().unique())
                uf_selecionado = st.selectbox("2. Filtrar por UF (Opcional):", options=["Todos"] + lista_ufs, index=0)
        
        if uf_selecionado and uf_selecionado != "Todos":
            df_filtrado_uf = df_otim[df_otim[os_uf_col] == uf_selecionado]

        with col_f4:
            lista_cidades = sorted(df_filtrado_uf[os_city_col].dropna().unique())
            cidade_selecionada_otim = st.selectbox("3. Selecione a Cidade de Atendimento:", options=lista_cidades, index=None, placeholder="Selecione...")

        os_pesquisada_num = st.text_input("Ou digite o Número da O.S. para análise direta (ignora filtros acima):")
        
        # --- LÓGICA DE FILTRAGEM (UF E CIDADE) ---
        ordens_para_analise = None
        titulo_analise = ""
        
        if os_pesquisada_num:
            resultado_busca = df_dados[df_dados[os_id_col].str.strip() == os_pesquisada_num.strip()]
            if not resultado_busca.empty:
                ordens_para_analise = resultado_busca
                titulo_analise = f"O.S. '{os_pesquisada_num}'"
            else:
                st.error(f"O.S. '{os_pesquisada_num}' não encontrada.")
                return
        
        elif cidade_selecionada_otim:
            ordens_para_analise = df_filtrado_uf[df_filtrado_uf[os_city_col] == cidade_selecionada_otim]
            titulo_analise = f"{cidade_selecionada_otim}"
        
        elif uf_selecionado and uf_selecionado != "Todos":
             ordens_para_analise = df_filtrado_uf.copy()
             titulo_analise = f"TODAS AS CIDADES DE {uf_selecionado}"

        if ordens_para_analise is None or ordens_para_analise.empty:
            st.info("Nenhuma ordem encontrada para a seleção feita. Selecione um UF, Cidade ou pesquise uma O.S.")
            return

        # --- 3. EXIBIÇÃO DA TABELA DE ORDENS ---
        st.subheader(f"Análise de RTs para {titulo_analise} ({len(ordens_para_analise)} ordens)")
        
        ordens_colunas = [os_id_col, 'DATA_FORMATADA', 'PERIODO_FINAL', os_cliente_col, os_city_col, os_rep_col, os_status_col]
        ordens_colunas_existentes = [col for col in ordens_colunas if col in ordens_para_analise.columns]
        
        df_display_ordens = ordens_para_analise[ordens_colunas_existentes].rename(columns={
            os_id_col: "Número da O.S.",
            'DATA_FORMATADA': 'Data Agendamento',
            'PERIODO_FINAL': 'Período',
            os_cliente_col: 'Cliente',
            os_city_col: 'Cidade',
            os_rep_col: 'Representante Técnico',
            os_status_col: 'Status'
        })
        altura_df = min(max(300, len(df_display_ordens) * 35 + 38), 600)
        st.dataframe(df_display_ordens, use_container_width=True, height=altura_df)

        # --- 4. EXIBIÇÃO E COLETA DE DADOS (EXPANDERS) ---
        st.markdown("---")
        st.subheader("Análise de Custo (RT Agendado vs. Sugerido)")
        
        cache_cidades = {} # Cache interno para esta execução
        report_data_selecao = []
        total_economia_selecao = 0.0

        # --- 🚨 LÓGICA DE ROLAGEM 🚨 ---
        num_ordens = len(ordens_para_analise)
        
        if num_ordens > 10:
            st.caption(f"Mostrando {num_ordens} ordens em uma lista com rolagem (600px).")
            container_de_custo = st.container(height=600)
        else:
            container_de_custo = st.container() # Container normal (sem rolagem)

        # Use o container (com ou sem rolagem) para desenhar os expanders
        with container_de_custo:
            for _, ordem in ordens_para_analise.iterrows():

                # --- Início do Bloco de Custo (por linha) ---
                cidade_da_ordem = ordem[os_city_col]

                # Calcular o "Valor Liberado" do Dashboard para esta OS
                valor_liberado_dashboard = 0.0
                if valor_deslocamento_dashboard_col and valor_deslocamento_dashboard_col in ordem and pd.notna(ordem[valor_deslocamento_dashboard_col]):
                    valor_desloc = pd.to_numeric(ordem[valor_deslocamento_dashboard_col], errors='coerce')
                    valor_liberado_dashboard += valor_desloc if pd.notna(valor_desloc) else 0
                if pedagio_dashboard_col and pedagio_dashboard_col in ordem and pd.notna(ordem[pedagio_dashboard_col]):
                    valor_pedagio = pd.to_numeric(ordem[pedagio_dashboard_col], errors='coerce')
                    valor_liberado_dashboard += valor_pedagio if pd.notna(valor_pedagio) else 0

                # Este é o valor que o sistema da empresa "liberou" para o RT agendado
                custo_agendado_para_comparacao = valor_liberado_dashboard
                
                # PULA A ANÁLISE SE O CUSTO AGENDADO FOR ZERO
                if custo_agendado_para_comparacao == 0:
                    continue

                if pd.isna(cidade_da_ordem):
                    continue
                    
                if cidade_da_ordem not in cache_cidades:
                    cidade_info = df_map[df_map[map_city_col].str.upper() == cidade_da_ordem.upper()] # Garante case-insensitivity
                    if cidade_info.empty:
                        cache_cidades[cidade_da_ordem] = (pd.DataFrame(), None) 
                        continue 

                    # Acessando as colunas de Latitude/Longitude com as variáveis flexíveis
                    ponto = (cidade_info.iloc[0][map_lat], cidade_info.iloc[0][map_lon])
                    
                    df_dist, rt_sugerido = _calcular_distancias_e_custos(df_map, cidade_da_ordem, ponto, map_rep, map_city_col, map_valor_km_col, 
                                                                         map_tel_col, map_abrang_col, map_km_col, map_rep_lat, map_rep_lon, map_rep_city_col, map_rep_uf_col, incluir_especiais)
                    cache_cidades[cidade_da_ordem] = (df_dist, rt_sugerido)
                else:
                    df_dist, rt_sugerido = cache_cidades[cidade_da_ordem]

                if df_dist.empty or rt_sugerido is None:
                    continue
                # --- Fim do Bloco de Custo ---

                rt_atual = ordem[os_rep_col] 
                status_atual = ordem[os_status_col]
                data_agendamento = ordem['DATA_FORMATADA']
                periodo = ordem['PERIODO_FINAL']
                
                expander_title = f"OS: {ordem[os_id_col]}"
                if periodo != "N/A":
                    expander_title += f" ({periodo})" 
                expander_title += f" | Data: {data_agendamento} | Cliente: {ordem[os_cliente_col]}"
                
                with st.expander(expander_title):
                    col1, col2 = st.columns(2) # Coluna para RT Agendado e Sugerido
                    dist_atual, custo_atual, economia_dist, economia_custo = float('inf'), 0.0, 0.0, 0.0
                    dist_atual, custo_atual, economia_dist, economia_custo, telefone_rt_agendado, cidade_rt_agendado, uf_rt_agendado = float('inf'), 0.0, 0.0, 0.0, "N/A", "N/A", "N/A"
                    dados_rt_atual = df_dist[df_dist['Representante'] == rt_atual]

                    with col1:
                        if pd.isna(rt_atual) or str(rt_atual).strip() == "" or str(rt_atual).strip() == "NAN" or dados_rt_atual.empty:
                            st.info(f"**RT Agendado:** (Nenhum ou Não Mapeado)")
                            st.metric("Distância (Haversine)", "N/A")
                            st.metric("Custo Estimado (RT Agendado)", "N/A")
                            custo_agendado_relatorio = custo_agendado_para_comparacao # Mesmo que seja 0, usa o valor do dashboard
                            dist_atual = float('inf')
                        else:
                            st.info(f"**RT Agendado:** {rt_atual}")
                            dados_rt_atual_series = dados_rt_atual.iloc[0]
                            dist_atual = dados_rt_atual_series['Distancia (km)']
                            custo_atual = custo_agendado_para_comparacao # O custo atual é o valor liberado do dashboard
                            st.metric("Distância (Haversine)", f"{dist_atual:.1f} km") # A distância ainda é a do RT agendado
                            st.metric("Custo Estimado (RT Agendado)", f"R$ {custo_atual:.2f}")
                            st.caption(f"KM Fixo Base: {dados_rt_atual_series['KM_Fixo_Custo']:.1f} km")
                            telefone_rt_agendado = dados_rt_atual_series['Telefone']
                            st.caption(f"Telefone: {dados_rt_atual_series['Telefone']}")
                            cidade_rt_agendado = dados_rt_atual_series['Cidade RT']
                            uf_rt_agendado = dados_rt_atual_series['UF RT']
                            custo_agendado_relatorio = custo_atual
                    
                    with col2:
                        st.success(f"**Sugestão (Mais Próximo):** {rt_sugerido['Representante']}")
                        dist_sugerida = rt_sugerido['Distancia (km)']
                        custo_sugerido = rt_sugerido['Custo_Correto_R$']
                        
                        if dist_atual != float('inf'):
                            economia_dist = dist_atual - dist_sugerida # Economia de distância (ainda baseada em Haversine)
                            economia_custo = custo_atual - custo_sugerido
                            total_economia_selecao += economia_custo
                        
                        st.metric("Distância (Haversine)", f"{dist_sugerida:.1f} km", delta=f"{-economia_dist:.1f} km")
                        st.metric("Custo Estimado (RT Sugerido)", f"R$ {custo_sugerido:.2f}", delta=f"R$ {-economia_custo:.2f}")
                        st.caption(f"KM Fixo Base: {rt_sugerido['KM_Fixo_Custo']:.1f} km")
                        st.caption(f"Telefone: {rt_sugerido['Telefone']}")

                        # --- LOG DE CÁLCULO E BOTÃO DE EXPORTAÇÃO ---
                        log_content = []
                        log_content.append(f"--- LOG DE CÁLCULO DE CUSTO (OTIMIZADOR) ---")
                        log_content.append(f"OS: {ordem[os_id_col]} | Cidade: {cidade_da_ordem}")
                        log_content.append("\n--- CUSTO RT AGENDADO (VALOR LIBERADO DASHBOARD) ---")
                        log_content.append(f"RT Agendado: {rt_atual}")
                        log_content.append(f"Valor Liberado (Deslocamento + Pedágio): R$ {custo_atual:,.2f}")
                        
                        log_content.append("\n--- CUSTO RT SUGERIDO (CÁLCULO MERCURIO) ---")
                        log_content.append(f"RT Sugerido: {rt_sugerido['Representante']}")
                        log_content.append(f"1. KM Fixo Base (Mapeamento ou Haversine): {rt_sugerido['KM_Fixo_Custo']:.2f} km")
                        log_content.append(f"2. Distância Total (Ida e Volta): {rt_sugerido['KM_Fixo_Custo']:.2f} * 2 = {rt_sugerido['KM_TOTAL_BASE']:.2f} km")
                        log_content.append(f"3. Abrangência do RT: {rt_sugerido['Abrangencia']:.2f} km")
                        log_content.append(f"4. Taxa por KM do RT: R$ {rt_sugerido['Valor_KM']:.2f}")
                        log_content.append(f"5. KM a Pagar (após franquia): max(0, {rt_sugerido['KM_TOTAL_BASE']:.2f} - {rt_sugerido['Abrangencia']:.2f}) = {rt_sugerido['KM_A_PAGAR']:.2f} km")
                        log_content.append(f"6. Custo Correto Final: {rt_sugerido['KM_A_PAGAR']:.2f} km * R$ {rt_sugerido['Valor_KM']:.2f} = R$ {custo_sugerido:,.2f}")
                        
                        # Exibe o cálculo simplificado na tela
                        st.caption(f"Cálculo: ({rt_sugerido['KM_Fixo_Custo']:.1f}km * 2 - {rt_sugerido['Abrangencia']:.0f}km) * R$ {rt_sugerido['Valor_KM']:.2f} = R$ {custo_sugerido:.2f}")

                        log_txt = "\n".join(log_content)
                        st.download_button("Exportar Log de Cálculo (.txt)", data=log_txt.encode('utf-8'), 
                                           file_name=f"log_otimizador_{ordem[os_id_col]}.txt", mime="text/plain",
                                           key=f"log_btn_{ordem[os_id_col]}")
                    
                report_data_selecao.append({
                    'Numero OS': ordem[os_id_col],
                    'UF O.S': ordem[os_uf_col] if os_uf_col in ordem and pd.notna(ordem[os_uf_col]) else "N/A",
                    'Cliente': ordem[os_cliente_col],
                    'Telefone Cliente': ordem.get(os_tel_cliente_col, "N/A"),
                    'data agendamento': data_agendamento,
                    'periodo': periodo,
                    'RT Agendado': rt_atual, 
                    'Cidade RT Agendado': cidade_rt_agendado,
                    'UF RT Agendado': uf_rt_agendado,
                    'Cidade O.S': ordem[os_city_col],
                    'Telefone RT Agendado': telefone_rt_agendado,
                    'Distancia Agendada (km)': dist_atual if dist_atual != float('inf') else None,
                    'Status': status_atual,
                    'Valor Agendado': custo_agendado_relatorio, # Este é o valor liberado do dashboard
                    'RT Sugerido': rt_sugerido['Representante'],
                    'Distancia Sugerida (km)': dist_sugerida,
                    'Cidade RT Sugerido': rt_sugerido['Cidade RT'],
                    'UF RT Sugerido': rt_sugerido['UF RT'],
                    'Telefone RT Sugerido': rt_sugerido['Telefone'],
                    'Valor Sugerido': custo_sugerido,
                    'Economia Potencial (R$)': economia_custo
                })
        # --- FIM DA LÓGICA DE ROLAGEM ---

        # A métrica de economia TOTAL deve ficar FORA do container de rolagem.
        st.metric("Economia Total Estimada (na seleção acima)", f"R$ {total_economia_selecao:.2f}")
        
        if report_data_selecao:
            st.markdown("---")
            st.subheader(f"Relatório de Exportação ({titulo_analise})")
            df_report_selecao = pd.DataFrame(report_data_selecao)
            df_report_selecao_export = _arredondar_relatorio(df_report_selecao)

            st.dataframe(df_report_selecao_export.style.format({
                'Valor Agendado': 'R$ {:,.2f}', 
                'Valor Sugerido': 'R$ {:,.2f}',
                'Economia Potencial (R$)': 'R$ {:,.2f}',
                'Distancia Sugerida (km)': '{:,.1f} km',
                'Distancia Agendada (km)': '{:,.1f} km'
            }), use_container_width=True)
            
            csv_selecao = convert_df_to_csv(df_report_selecao_export)
            st.download_button(
                label=f"📥 Exportar Seleção ({titulo_analise})",
                data=csv_selecao,
                file_name=f"relatorio_otimizacao_{titulo_analise.replace(' ', '_')}.csv", 
                mime="text/csv",
            )
            
        st.markdown("---")
        st.subheader(f"Relatório Completo (Todos os Status Selecionados: {len(df_otim)} ordens)")
        
        if st.button(f"Preparar Relatório Completo (pode demorar...)"):
            with st.spinner(f"Analisando TODAS as {len(df_otim)} ordens... Isso pode levar alguns minutos."):
                report_completo_data = []
                cache_cidades_completo = {} 
                progress_bar = st.progress(0, text="Analisando cidades...")
                
                cidades_unicas = df_otim[os_city_col].dropna().unique()
                for i, cidade in enumerate(cidades_unicas):
                    if cidade not in cache_cidades_completo:
                        cidade_info = df_map[df_map[map_city_col] == cidade]
                        if cidade_info.empty:
                            cache_cidades_completo[cidade] = (pd.DataFrame(), None) 
                            continue 

                        # Acessando as colunas de Latitude/Longitude com as variáveis flexíveis
                        ponto = (cidade_info.iloc[0][map_lat], cidade_info.iloc[0][map_lon])
                        
                        df_dist, rt_sugerido = _calcular_distancias_e_custos(df_map, cidade, ponto, map_rep, map_city_col, map_valor_km_col, 
                                                                             map_tel_col, map_abrang_col, map_km_col, map_rep_lat, map_rep_lon, map_rep_city_col, map_rep_uf_col, incluir_especiais)
                        cache_cidades_completo[cidade] = (df_dist, rt_sugerido)
                    progress_bar.progress((i + 1) / len(cidades_unicas), text=f"Analisando cidade: {cidade}")

                progress_bar.progress(1.0, text="Cidades analisadas! Gerando relatório de ordens...")

                for _, ordem in df_otim.iterrows():
                    cidade_ordem = ordem[os_city_col]
                    if pd.isna(cidade_ordem) or cidade_ordem not in cache_cidades_completo:
                        continue 

                    df_dist_ordem, rt_sugerido_ordem = cache_cidades_completo[cidade_ordem]
                    
                    if df_dist_ordem.empty or rt_sugerido_ordem is None:
                        continue 

                    rt_atual = ordem[os_rep_col] 
                    status_atual = ordem[os_status_col]
                    dados_rt_atual_df = df_dist_ordem[df_dist_ordem['Representante'] == rt_atual]
                    
                    # Calcular o "Valor Liberado" do Dashboard para esta OS no relatório completo
                    valor_liberado_dashboard_completo = 0.0
                    if valor_deslocamento_dashboard_col and valor_deslocamento_dashboard_col in ordem and pd.notna(ordem[valor_deslocamento_dashboard_col]):
                        valor_desloc_completo = pd.to_numeric(ordem[valor_deslocamento_dashboard_col], errors='coerce')
                        valor_liberado_dashboard_completo += valor_desloc_completo if pd.notna(valor_desloc_completo) else 0
                    if pedagio_dashboard_col and pedagio_dashboard_col in ordem and pd.notna(ordem[pedagio_dashboard_col]):
                        valor_pedagio_completo = pd.to_numeric(ordem[pedagio_dashboard_col], errors='coerce')
                        valor_liberado_dashboard_completo += valor_pedagio_completo if pd.notna(valor_pedagio_completo) else 0

                    custo_agendado_relatorio_completo = valor_liberado_dashboard_completo
                    
                    cidade_rt_agendado_val = "N/A"
                    uf_rt_agendado_val = "N/A"
                    telefone_rt_agendado_val = "N/A"
                    distancia_agendada_val = None

                    if not dados_rt_atual_df.empty:
                        dados_rt_atual_series = dados_rt_atual_df.iloc[0]
                        cidade_rt_agendado_val = dados_rt_atual_series['Cidade RT']
                        uf_rt_agendado_val = dados_rt_atual_series['UF RT']
                        telefone_rt_agendado_val = dados_rt_atual_series['Telefone']
                        distancia_agendada_val = dados_rt_atual_series['Distancia (km)']

                    custo_sugerido = rt_sugerido_ordem['Custo_Correto_R$']
                    
                    
                    # Calcula a economia para o relatório completo
                    economia_custo_completo = 0.0
                    if custo_agendado_relatorio_completo > 0:
                        economia_custo_completo = custo_agendado_relatorio_completo - custo_sugerido


                    data_agendamento_completo = ordem['DATA_FORMATADA']
                    periodo_completo = ordem['PERIODO_FINAL']

                    report_completo_data.append({
                        'Numero OS': ordem[os_id_col],
                        'UF O.S': ordem[os_uf_col] if os_uf_col in ordem and pd.notna(ordem[os_uf_col]) else "N/A",
                        'Cliente': ordem[os_cliente_col],
                        'Telefone Cliente': ordem.get(os_tel_cliente_col, "N/A"),
                        'data agendamento': data_agendamento_completo,
                        'periodo': periodo_completo,
                        'RT Agendado': rt_atual,
                        'Cidade RT Agendado': cidade_rt_agendado_val,
                        'UF RT Agendado': uf_rt_agendado_val,
                        'Cidade O.S': ordem[os_city_col],
                        'Telefone RT Agendado': telefone_rt_agendado_val,
                        'Distancia Agendada (km)': distancia_agendada_val,
                        'Status': status_atual,
                        'Valor Agendado': custo_agendado_relatorio_completo, # Este é o valor liberado do dashboard
                        'RT Sugerido': rt_sugerido_ordem['Representante'],
                        'Cidade RT Sugerido': rt_sugerido_ordem['Cidade RT'],
                        'UF RT Sugerido': rt_sugerido_ordem['UF RT'],
                        'Distancia Sugerida (km)': rt_sugerido_ordem['Distancia (km)'],
                        'Telefone RT Sugerido': rt_sugerido_ordem['Telefone'],
                        'Valor Sugerido': custo_sugerido,
                        'Economia Potencial (R$)': economia_custo_completo
                    })
                
                st.session_state.df_report_completo = pd.DataFrame(report_completo_data)
                progress_bar.empty()
                st.success(f"Relatório completo com {len(st.session_state.df_report_completo)} ordens está pronto para download!")

        if "df_report_completo" in st.session_state and st.session_state.df_report_completo is not None:
            df_report_completo_export = _arredondar_relatorio(st.session_state.df_report_completo)
            csv_completo = convert_df_to_csv(df_report_completo_export)
            st.download_button(
                label=f"📥 Baixar Relatório Completo ({len(df_report_completo_export)} ordens)",
                data=csv_completo,
                file_name="relatorio_otimizacao_COMPLETO.csv",
                mime="text/csv",
                key="download_completo"
            )

        st.markdown("---")
        st.subheader("Análise de Proximidade de Agendamentos (6-7 dias)")
        st.info("Esta análise identifica oportunidades para consolidar viagens. Ela mostra os técnicos que têm agendamentos para a mesma cidade em um intervalo de 6 a 7 dias.")

        if st.button("Analisar Agendamentos Próximos"):
            with st.spinner("Analisando agendamentos..."):
                # Passa o df_otim que já foi filtrado por status e clientes
                df_proximidade = _analisar_proximidade_agendamentos(
                    df=df_otim,
                    data_col=os_data_col,
                    rep_col=os_rep_col,
                    city_col=os_city_col,
                    id_col=os_id_col,
                    cliente_col=os_cliente_col,
                    valor_desloc_col=valor_deslocamento_dashboard_col,
                    pedagio_col=pedagio_dashboard_col,
                    tel_cliente_col=os_tel_cliente_col
                )

                if not df_proximidade.empty:
                    st.success(f"Encontrados {df_proximidade['Grupo'].nunique()} grupos de agendamentos que podem ser consolidados.")
                    st.dataframe(
                        df_proximidade,
                        use_container_width=True,
                        column_config={
                            "Custo Agendado (R$)": st.column_config.NumberColumn(
                                "Custo Agendado (R$)",
                                format="R$ %.2f"
                            )
                        }
                    )

                    csv_proximidade = convert_df_to_csv(df_proximidade)
                    st.download_button(
                        label="📥 Exportar Análise de Proximidade (.csv)",
                        data=csv_proximidade,
                        file_name="analise_proximidade_agendamentos.csv",
                        mime="text/csv",
                        key="download_proximidade"
                    )
                else:
                    st.info("Nenhuma oportunidade de consolidação encontrada para o período e filtros selecionados.")
        
        st.markdown("---")
        st.subheader("Análise de Ativos Sem Posição (>= 15 dias)")
        st.info("Esta análise identifica equipamentos que não registram posição há 15 dias ou mais, cruzando dados dos arquivos de 'Última Posição' e 'Ativos'.")

        if st.button("Analisar Ativos Sem Posição"):
            if df_ultimaposicao is None or df_ativos is None:
                st.warning("Para realizar esta análise, por favor, carregue os arquivos 'Relatório de Última Posição' (na aba Posição) e 'Base de Ativos' (na aba Ativos).")
            else:
                with st.spinner("Analisando ativos sem posição..."):
                    try:
                        # 1. Identificar colunas de forma flexível
                        pos_serial_col = next((c for c in df_ultimaposicao.columns if 'serial' in c.lower()), None)
                        pos_date_col = next((c for c in df_ultimaposicao.columns if 'data' in c.lower() and 'posição' in c.lower()), None)
                        
                        ativos_serial_col = next((c for c in df_ativos.columns if 'serial' in c.lower()), None)
                        ativos_model_col = next((c for c in df_ativos.columns if 'modelo' in c.lower()), None)

                        if not all([pos_serial_col, pos_date_col, ativos_serial_col, ativos_model_col]):
                            st.error("Não foi possível encontrar as colunas necessárias (serial, data da posição, modelo) nos arquivos carregados.")
                        else:
                            # 2. Preparar DataFrames
                            df_pos = df_ultimaposicao[[pos_serial_col, pos_date_col]].copy()
                            df_pos.rename(columns={pos_serial_col: 'Serial', pos_date_col: 'Data da Posição'}, inplace=True)
                            
                            df_at = df_ativos[[ativos_serial_col, ativos_model_col]].copy()
                            df_at.rename(columns={ativos_serial_col: 'Serial', ativos_model_col: 'Modelo'}, inplace=True)
                            
                            # Converter data e calcular dias sem posição
                            df_pos['Data da Posição'] = pd.to_datetime(df_pos['Data da Posição'], errors='coerce')
                            df_pos.dropna(subset=['Data da Posição'], inplace=True)
                            
                            hoje = pd.to_datetime("today")
                            df_pos['Dias Sem Posicionar'] = (hoje - df_pos['Data da Posição']).dt.days

                            # 3. Filtrar e juntar
                            df_sem_posicao = df_pos[df_pos['Dias Sem Posicionar'] >= 15]
                            
                            # Manter apenas a última posição registrada para cada serial
                            df_sem_posicao = df_sem_posicao.sort_values('Data da Posição', ascending=False).drop_duplicates('Serial')

                            df_final = pd.merge(df_sem_posicao, df_at, on='Serial', how='left')
                            
                            # Preencher modelo não encontrado
                            df_final['Modelo'].fillna('Modelo não encontrado na base de ativos', inplace=True)
                            
                            df_final = df_final[['Serial', 'Modelo', 'Dias Sem Posicionar', 'Data da Posição']]

                            st.session_state.df_sem_posicao_resultado = df_final

                            st.success(f"Análise concluída! Encontrados {len(df_final)} ativos sem posição há 15 dias ou mais.")
                            st.dataframe(df_final.style.format({'Data da Posição': '{:%d/%m/%Y}'}), use_container_width=True)
                            
                            csv_export = convert_df_to_csv(df_final)
                            st.download_button(
                                label="📥 Exportar Relatório de Ativos Sem Posição (.csv)",
                                data=csv_export,
                                file_name="relatorio_ativos_sem_posicao.csv",
                                mime="text/csv",
                                key="download_sem_posicao"
                            )

                    except Exception as e:
                        st.error(f"Ocorreu um erro na análise de ativos sem posição: {e}")

    except Exception as e:
        st.error(f"Ocorreu um erro inesperado no Otimizador. Detalhe: {e}")
        import traceback
        st.error(traceback.format_exc())