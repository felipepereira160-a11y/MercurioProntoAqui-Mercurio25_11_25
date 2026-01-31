# modules/custos.py (AJUSTADO PARA A CHAVE DE MERGE E LÓGICA DO ROTEIRO)
import streamlit as st
import numpy as np
import pandas as pd
from modules.utils import safe_to_numeric, convert_df_to_csv
from modules.tutorial_helper import tutorial_button
import datetime 
from haversine import haversine, Unit
 

try:
    from geopy.distance import geodesic
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False
# Variáveis chave padronizadas para o merge
MAP_REP_KEY = 'MERGE_REP_KEY'
MAP_CITY_KEY = 'MERGE_CITY_KEY'

def analisar_custos(df_pagamento, df_agendamentos=None, df_mapeamento=None):
    
    tutorial_button("Custos", "Análise de Custos")
    
    # --- Função helper (para o bug NaTType) ---
    def format_date_safe(t):
        """Converte para data e formata, retornando 'N/A' se for NaT."""
        dt = pd.to_datetime(t, errors='coerce')
        if pd.isna(dt):
            return 'N/A'
        return dt.strftime('%d/%m/%Y')
    
    df_custos = df_pagamento.copy()
    
    # --- 1. Identificação de Colunas de Pagamento (df_custos) ---
    os_col_p = next((c for c in df_custos.columns if 'os' in c.lower()), None)
    data_col_p = next((c for c in df_custos.columns if 'data de fechamento' in c.lower()), None)
    cidade_os_p = next((c for c in df_custos.columns if 'cidade o.s.' in c.lower()), None)
    cidade_rt_p = next((c for c in df_custos.columns if 'cidade rt' in c.lower()), None)
    rep_col_p = next((c for c in df_custos.columns if 'representante' in c.lower() and 'nome fantasia' not in c.lower()), None)
    tec_col_p = next((c for c in df_custos.columns if 'técnico' in c.lower()), None)
    
    # VALOR EXTRA / VALOR PAGO TOTAL
    valor_extra_p = next((c for c in df_custos.columns if 'valor extra' in c.lower()), None)
    # Valor Deslocamento (se existir)
    valor_desl_p = next((c for c in df_custos.columns if 'valor deslocamento' in c.lower() or 'valor deslocamento' in c.lower()), None) 

    # Valor do KM dentro da planilha custos (ex: "VALOR KM RT")
    valor_km_p = next((c for c in df_custos.columns if 'valor km' in c.lower() or 'valor km rt' in c.lower()), None)
    # Abrangência vindo da planilha custos (ex: "ABRANGÊNCIA RT")
    abrang_custos_p = next((c for c in df_custos.columns if 'abrang' in c.lower()), None)
    
    cliente_col_p_orig = next((c for c in df_custos.columns if 'cliente' in c.lower() and c.lower() not in ['cd_cliente', 'documento do cliente']), None)
    data_ag_col_p_orig = next((c for c in df_custos.columns if 'data de agendamento' in c.lower() and c.lower() not in ['data_analise']), None)

    # Verificação das colunas do PAGAMENTO (df_custos)
    required_p = [os_col_p, data_col_p, cidade_os_p, cidade_rt_p, rep_col_p, tec_col_p, valor_extra_p, valor_desl_p]
    
    if not all(required_p):
        st.error("Planilha de pagamento (LotesPagoRT) sem colunas obrigatórias.")
        missing_map = {
            os_col_p: 'OS', data_col_p: 'Data de Fechamento', cidade_os_p: 'Cidade O.S.',
            cidade_rt_p: 'Cidade RT', rep_col_p: 'Representante', tec_col_p: 'Técnico',
            valor_extra_p: 'Valor Extra', valor_desl_p: 'Valor Deslocamento'
        }
        missing = [name for col, name in missing_map.items() if col is None]
        st.error(f"Colunas não encontradas na Planilha de Pagamento: {', '.join(missing)}")
        return

    # Limpeza de valor e data
    df_custos['VALOR_PAGO_R$'] = safe_to_numeric(df_custos[valor_desl_p]) # Deslocamento/Valor Pago (Para duplicidade)
    df_custos['VALOR_EXTRA_R$'] = safe_to_numeric(df_custos[valor_extra_p]) # Novo campo para o total pago (Para rotas)
    df_custos['DATA_ANALISE'] = pd.to_datetime(df_custos[data_col_p], dayfirst=True, errors='coerce').dt.date
    
    # Normaliza as colunas de CHAVE 
    df_custos[rep_col_p] = df_custos[rep_col_p].astype(str).str.strip().str.upper()
    df_custos[cidade_os_p] = df_custos[cidade_os_p].astype(str).str.strip().str.upper()
    
    # Filtrar VALOR_EXTRA_R$ > 0 (Valor Pago Total)
    df_custos = df_custos[df_custos['VALOR_EXTRA_R$'] > 0].copy()
    if df_custos.empty:
        st.info("Nenhum dado com 'Valor Extra' > 0 encontrado.")
        return

    # Extração de Lat/Lon (LAT/LONG AGENDAMENTO)
    lat_long_os_p = next((c for c in df_custos.columns if 'lat/long agendamento' in c.lower()), None)
    if lat_long_os_p:
        try:
            df_custos['COORD_SPLIT'] = df_custos[lat_long_os_p].astype(str).str.strip().str.replace('"', '').str.split(',', expand=True)
            df_custos['lat_os_pag'] = pd.to_numeric(df_custos['COORD_SPLIT'].iloc[:, 0], errors='coerce')
            df_custos['lon_os_pag'] = pd.to_numeric(df_custos['COORD_SPLIT'].iloc[:, 1], errors='coerce')
            df_custos.drop(columns=['COORD_SPLIT'], inplace=True, errors='ignore')
        except Exception:
            df_custos['lat_os_pag'] = np.nan
            df_custos['lon_os_pag'] = np.nan
    else:
        df_custos['lat_os_pag'] = np.nan
        df_custos['lon_os_pag'] = np.nan

    # Extração de Lat/Lon (LAT/LONG RT)
    lat_long_rt_p = next((c for c in df_custos.columns if 'lat/long rt' in c.lower()), None)
    if lat_long_rt_p:
        try:
            df_custos['COORD_RT_SPLIT'] = df_custos[lat_long_rt_p].astype(str).str.strip().str.replace('"', '').str.split(',', expand=True)
            df_custos['lat_rt_pag'] = pd.to_numeric(df_custos['COORD_RT_SPLIT'].iloc[:, 0], errors='coerce')
            df_custos['lon_rt_pag'] = pd.to_numeric(df_custos['COORD_RT_SPLIT'].iloc[:, 1], errors='coerce')
            df_custos.drop(columns=['COORD_RT_SPLIT'], inplace=True, errors='ignore')
        except Exception:
            df_custos['lat_rt_pag'] = np.nan
            df_custos['lon_rt_pag'] = np.nan
    else:
        df_custos['lat_rt_pag'] = np.nan
        df_custos['lon_rt_pag'] = np.nan

    # --- Filtros de Data e Representante (Geral) ---
    col1, col2 = st.columns(2)
    datas = df_custos['DATA_ANALISE'].dropna()
    df_filtrado = df_custos.copy()
    
    if not datas.empty:
        min_d, max_d = datas.min(), datas.max()
        d_sel = col1.date_input("Filtrar por Data (Geral):", 
                                value=(min_d, max_d), 
                                min_value=min_d, 
                                max_value=max_d)
        if len(d_sel) == 2:
            start, end = d_sel
            df_filtrado = df_filtrado[(df_filtrado['DATA_ANALISE'] >= start) & (df_filtrado['DATA_ANALISE'] <= end)]
    else:
        col1.date_input("Filtrar por Data (Geral):", value=datetime.date.today(), disabled=True)
        st.info("Filtro de Data indisponível: Nenhum dado de 'Data de Fechamento' encontrado.")

    reps = sorted(df_filtrado[rep_col_p].dropna().unique())
    reps_sel = col2.multiselect("Filtrar por Representante (Geral):", options=reps)
    if reps_sel:
        df_filtrado = df_filtrado[df_filtrado[rep_col_p].isin(reps_sel)]

    # --- Correção de Merge (Agendamentos) ---
    df_merged = df_filtrado.copy()
    
    if df_agendamentos is not None and os_col_p:
        os_col_a = next((c for c in df_agendamentos.columns if 'os' in c.lower() or 'numero os' in c.lower()), None)
        os_cliente_col_a = next((c for c in df_agendamentos.columns if 'cliente' in c.lower() or 'nome fantasia' in c.lower()), None)
        os_data_ag_col_a = next((c for c in df_agendamentos.columns if 'data agendamento' in c.lower() or 'data agenda' in c.lower()), None)

        if os_col_a and os_cliente_col_a and os_data_ag_col_a:
            df_agendamentos[os_col_a] = df_agendamentos[os_col_a].astype(str).str.strip()
            df_merged[os_col_p] = df_merged[os_col_p].astype(str).str.strip()
            cols_to_merge = [os_col_a, os_cliente_col_a, os_data_ag_col_a]
            df_agendamentos_slim = df_agendamentos[cols_to_merge].rename(columns={os_cliente_col_a: 'CLIENTE_AGEND', os_data_ag_col_a: 'DATA_AGENDAMENTO_AGEND'}).drop_duplicates(subset=[os_col_a])
            df_merged = pd.merge(df_merged, df_agendamentos_slim, left_on=os_col_p, right_on=os_col_a, how='left', suffixes=('_PAG', '_AGEND'))
            df_merged.drop(columns=[os_col_a], inplace=True, errors='ignore')
            
            if 'CLIENTE_AGEND' in df_merged.columns and cliente_col_p_orig in df_merged.columns:
                df_merged['CLIENTE_FINAL'] = df_merged['CLIENTE_AGEND'].fillna(df_merged[cliente_col_p_orig])
                df_merged = df_merged.drop(columns=[cliente_col_p_orig, 'CLIENTE_AGEND'], errors='ignore')
            elif 'CLIENTE_AGEND' in df_merged.columns:
                df_merged['CLIENTE_FINAL'] = df_merged['CLIENTE_AGEND']
                df_merged = df_merged.drop(columns=['CLIENTE_AGEND'], errors='ignore')
            elif cliente_col_p_orig in df_merged.columns:
                df_merged['CLIENTE_FINAL'] = df_merged[cliente_col_p_orig]
                df_merged = df_merged.drop(columns=[cliente_col_p_orig], errors='ignore')
            else:
                df_merged['CLIENTE_FINAL'] = 'N/A'
            
            if 'DATA_AGENDAMENTO_AGEND' in df_merged.columns and data_ag_col_p_orig in df_merged.columns:
                df_merged['DATA_AGENDAMENTO_FINAL'] = df_merged['DATA_AGENDAMENTO_AGEND'].fillna(df_merged[data_ag_col_p_orig])
                df_merged = df_merged.drop(columns=[data_ag_col_p_orig, 'DATA_AGENDAMENTO_AGEND'], errors='ignore')
            elif 'DATA_AGENDAMENTO_AGEND' in df_merged.columns:
                df_merged['DATA_AGENDAMENTO_FINAL'] = df_merged['DATA_AGENDAMENTO_AGEND']
                df_merged = df_merged.drop(columns=['DATA_AGENDAMENTO_AGEND'], errors='ignore')
            elif data_ag_col_p_orig in df_merged.columns:
                df_merged['DATA_AGENDAMENTO_FINAL'] = df_merged[data_ag_col_p_orig]
                df_merged = df_merged.drop(columns=[data_ag_col_p_orig], errors='ignore')
            else:
                df_merged['DATA_AGENDAMENTO_FINAL'] = pd.NaT
        else:
            if cliente_col_p_orig in df_merged.columns:
                df_merged['CLIENTE_FINAL'] = df_merged[cliente_col_p_orig]
                df_merged = df_merged.drop(columns=[cliente_col_p_orig], errors='ignore')
            if data_ag_col_p_orig in df_merged.columns:
                df_merged['DATA_AGENDAMENTO_FINAL'] = df_merged[data_ag_col_p_orig]
                df_merged = df_merged.drop(columns=[data_ag_col_p_orig], errors='ignore')
    else:
        if cliente_col_p_orig in df_merged.columns:
            df_merged['CLIENTE_FINAL'] = df_merged[cliente_col_p_orig]
            df_merged = df_merged.drop(columns=[cliente_col_p_orig], errors='ignore')
        if data_ag_col_p_orig in df_merged.columns:
            df_merged['DATA_AGENDAMENTO_FINAL'] = df_merged[data_ag_col_p_orig]
            df_merged = df_merged.drop(columns=[data_ag_col_p_orig], errors='ignore')

    if 'CLIENTE_FINAL' not in df_merged.columns:
        df_merged['CLIENTE_FINAL'] = 'N/A'
    if 'DATA_AGENDAMENTO_FINAL' not in df_merged.columns:
        df_merged['DATA_AGENDAMENTO_FINAL'] = pd.NaT
        
    cliente_col_final = 'CLIENTE_FINAL'
    data_agendamento_col_final = 'DATA_AGENDAMENTO_FINAL'
    # --- Fim da Correção de Merge ---


    # --- PREPARAÇÃO PARA ANÁLISES (KM CALCULADO E VALOR CORRETO) ---
    df_analise = df_merged.copy() 
    
    if df_mapeamento is None:
        st.warning("Para as análises de Roterização e Auditoria, carregue o 'Mapeamento de RT' na aba 'Otimizador'.")
        df_analise['VALOR_CORRETO_R$'] = np.nan
    else:
        # 1. Identificar colunas no Mapeamento
        map_rep_col = next((c for c in df_mapeamento.columns if 'nm_representante' in c.lower()), None)
        map_city_col = next((c for c in df_mapeamento.columns if 'nm_cidade_atendimento' in c.lower()), None)
        
        # Colunas para o cálculo do Valor Correto
        km_fixo_names = ['qt_distancia_atendimento_km', 'distancia_km', 'distancia (km)', 'km']
        map_km_col = next((c for c in df_mapeamento.columns if c.lower().strip() in km_fixo_names), None)

        abrangencia_names = ['abrangência', 'abrangencia', 'v']
        map_abrang_col = next((c for c in df_mapeamento.columns if c.lower().strip() in abrangencia_names), None)
        map_taxa_col = next((c for c in df_mapeamento.columns if 'valor deslocamento' in c.lower() or 'valor km' in c.lower()), None)

        # Coordenadas do Atendimento no Mapeamento (para fallback no Mapa)
        map_lat_atendimento_col = next((c for c in df_mapeamento.columns if 'cd_latitude_atendimento' in c.lower()), None)
        map_lon_atendimento_col = next((c for c in df_mapeamento.columns if 'cd_longitude_atendimento' in c.lower()), None)
        
        required_map_cols = [map_rep_col, map_city_col, map_km_col, map_abrang_col, map_taxa_col, map_lat_atendimento_col, map_lon_atendimento_col]

        if all(required_map_cols):
            
            # --- FUNÇÃO DE CÁLCULO DE DISTÂNCIA (KM_IDA) (MANTIDA APENAS PARA A ORDENAÇÃO DO MAPA) ---
            def calcular_distancia_os_rt(row):
                """Calcula a distância Haversine entre a O.S. (lat/lon_os_pag) e o RT (lat/lon_rt_pag)."""
                lat_os, lon_os = row.get('lat_os_pag'), row.get('lon_os_pag')
                lat_rt, lon_rt = row.get('lat_rt_pag'), row.get('lon_rt_pag')
                
                if pd.isna(lat_os) or pd.isna(lon_os) or pd.isna(lat_rt) or pd.isna(lon_rt):
                    return np.nan
                
                try:
                    # Seção 3 (Roterização) usará este KM_IDA_CALCULADO para ranking
                    return haversine((lat_os, lon_os), (lat_rt, lon_rt), unit=Unit.KILOMETERS)
                except Exception:
                    return np.nan

            # O KM CALCULADO É MANTIDO PARA A LÓGICA DE ROTERIZAÇÃO (SEÇÃO 3)
            df_analise['KM_IDA_CALCULADO'] = df_analise.apply(calcular_distancia_os_rt, axis=1)

            # --- PREPARAÇÃO DO DATAFRAME DE MERGE DO MAPA ---
            
            # 1. Renomeia e Normaliza as colunas de chave no df_map_norm
            df_map_norm = df_mapeamento.copy()
            df_map_norm[MAP_REP_KEY] = df_map_norm[map_rep_col].astype(str).str.strip().str.upper()
            df_map_norm[MAP_CITY_KEY] = df_map_norm[map_city_col].astype(str).str.strip().str.upper() 
            
            df_map_norm.rename(columns={
                map_km_col: 'KM_IDA_MAP',
                map_abrang_col: 'ABRANGENCIA_MAP',
                map_taxa_col: 'TAXA_MAP',
                map_lat_atendimento_col: 'LAT_MAP_ATEND',
                map_lon_atendimento_col: 'LON_MAP_ATEND'
            }, inplace=True)
            
            df_map_norm['KM_IDA_MAP'] = safe_to_numeric(df_map_norm['KM_IDA_MAP'])
            df_map_norm['ABRANGENCIA_MAP'] = safe_to_numeric(df_map_norm['ABRANGENCIA_MAP'])
            df_map_norm['TAXA_MAP'] = safe_to_numeric(df_map_norm['TAXA_MAP'])

            cols_merge_map = [MAP_REP_KEY, MAP_CITY_KEY, 'KM_IDA_MAP', 'ABRANGENCIA_MAP', 'TAXA_MAP', 'LAT_MAP_ATEND', 'LON_MAP_ATEND']
            df_map_taxa = df_map_norm[[col for col in cols_merge_map if col in df_map_norm.columns]].drop_duplicates(subset=[MAP_REP_KEY, MAP_CITY_KEY])
            
            # 2. Renomeia e Normaliza as colunas de chave no df_analise (Custos)
            df_analise[MAP_REP_KEY] = df_analise[rep_col_p].astype(str).str.strip().str.upper()
            df_analise[MAP_CITY_KEY] = df_analise[cidade_os_p].astype(str).str.strip().str.upper()
            
            # 3. Faz o merge usando as chaves padronizadas (MAP_REP_KEY, MAP_CITY_KEY)
            df_analise = pd.merge(df_analise, df_map_taxa, on=[MAP_REP_KEY, MAP_CITY_KEY], how='left', indicator=True)

            # Log de linhas que não encontraram correspondência no mapeamento
            nao_mapeados = df_analise[df_analise['_merge'] == 'left_only']
            if not nao_mapeados.empty:
                st.warning("Aviso: Algumas rotas não foram encontradas no arquivo de Mapeamento e não terão o 'Valor Correto' calculado.")

                st.markdown("---")
                st.subheader("Análise de Capilaridade")
                st.info("A tabela abaixo mostra os atendimentos realizados em cidades que não constam no arquivo de Mapeamento para o representante correspondente. Isso ajuda a identificar novas áreas de atuação ou a necessidade de atualizar o mapeamento.")
                
                # Agrupar para contar as visitas por RT, cidade e dia
                capilaridade_df = nao_mapeados.groupby([rep_col_p, cidade_os_p, 'DATA_ANALISE']).agg(
                    NUM_VISITAS=(os_col_p, 'count')
                ).reset_index()

                # Renomear colunas para exibição
                capilaridade_df.rename(columns={
                    rep_col_p: 'Representante',
                    cidade_os_p: 'Cidade não Mapeada',
                    'DATA_ANALISE': 'Data da Visita',
                    'NUM_VISITAS': 'Nº de Visitas no Dia'
                }, inplace=True)

                # Formatar a data para exibição
                capilaridade_df['Data da Visita'] = pd.to_datetime(capilaridade_df['Data da Visita']).dt.strftime('%d/%m/%Y')
                
                # Ordenar para melhor visualização
                capilaridade_df = capilaridade_df.sort_values(by=['Representante', 'Cidade não Mapeada', 'Data da Visita'])

                st.dataframe(capilaridade_df, use_container_width=True)

                # Botão de download
                csv_capilaridade = convert_df_to_csv(capilaridade_df)
                st.download_button(
                    label="📥 Exportar Análise de Capilaridade (.csv)",
                    data=csv_capilaridade,
                    file_name="analise_capilaridade.csv",
                    mime="text/csv",
                    key="download_capilaridade"
                )

            # Remove colunas de merge e o indicador
            df_analise.drop(columns=[MAP_REP_KEY, MAP_CITY_KEY, '_merge'], inplace=True, errors='ignore')

            # --- NOVA LÓGICA: pegar abrangência e valor_km preferencialmente da planilha custos ---
            # Cria colunas normalizadas a partir das colunas originais (se existirem)
            if abrang_custos_p and abrang_custos_p in df_analise.columns:
                df_analise['ABRANGENCIA_CUSTOS'] = safe_to_numeric(df_analise[abrang_custos_p])
            else:
                df_analise['ABRANGENCIA_CUSTOS'] = np.nan

            if valor_km_p and valor_km_p in df_analise.columns:
                df_analise['VALOR_KM_CUSTOS'] = safe_to_numeric(df_analise[valor_km_p])
            else:
                df_analise['VALOR_KM_CUSTOS'] = np.nan

            # 🚨 CÁLCULO FINAL DO VALOR CORRETO (USANDO KM_IDA_MAP * 2) 🚨
            # Garante que as colunas do mapeamento existam após o merge, preenchendo com 0 se não existirem
            df_analise['KM_IDA_MAP'] = df_analise.get('KM_IDA_MAP', 0).fillna(0)
            df_analise['ABRANGENCIA_MAP'] = df_analise.get('ABRANGENCIA_MAP', 0).fillna(0)
            df_analise['TAXA_MAP'] = df_analise.get('TAXA_MAP', 0).fillna(0)

            df_analise['KM_TOTAL_CORRETO'] = df_analise['KM_IDA_MAP'] * 2

            # Escolhe abrangência final: se houver ABRANGENCIA_CUSTOS > 0 usa ela, senão usa ABRANGENCIA_MAP
            df_analise['ABRANGENCIA_FINAL'] = np.where(
                df_analise.get('ABRANGENCIA_CUSTOS', 0) > 0,
                df_analise['ABRANGENCIA_CUSTOS'],
                df_analise['ABRANGENCIA_MAP']
            )
            df_analise['KM_A_PAGAR'] = (df_analise['KM_TOTAL_CORRETO'] - df_analise['ABRANGENCIA_FINAL']).clip(lower=0)

            # Escolhe valor por km final: se existir VALOR_KM_CUSTOS usa ela, senão usa TAXA_MAP (do mapeamento)
            df_analise['VALOR_KM_FINAL'] = np.where(
                df_analise.get('VALOR_KM_CUSTOS', 0) > 0,
                df_analise['VALOR_KM_CUSTOS'],
                df_analise['TAXA_MAP']
            )

            # Calcula o valor correto
            df_analise['VALOR_CORRETO_R$'] = df_analise['KM_A_PAGAR'] * df_analise['VALOR_KM_FINAL']

            # 🚨 CORREÇÃO DO BUG DO MAPA: Prioriza Lat/Lon do Pagamento, senão usa Lat/Lon do Mapeamento 🚨
            df_analise['lat'] = df_analise['lat_os_pag'].fillna(df_analise.get('LAT_MAP_ATEND'))
            df_analise['lon'] = df_analise['lon_os_pag'].fillna(df_analise.get('LON_MAP_ATEND'))
            
        else:
            missing_cols = [
                ('nm_representante', map_rep_col), ('nm_cidade_atendimento', map_city_col), 
                ('qt_distancia_atendimento_km', map_km_col), 
                ('Abrangência ou V', map_abrang_col),
                ('Valor Deslocamento', map_taxa_col),
                ('cd_latitude_atendimento', map_lat_atendimento_col),
                ('cd_longitude_atendimento', map_lon_atendimento_col)
            ]
            missing = [desc for desc, col in missing_cols if col is None]
            st.error(f"Mapeamento incompleto. As análises de valor e roteirização serão limitadas. Colunas não encontradas no Mapeamento: {', '.join(missing)}")
            df_analise['VALOR_CORRETO_R$'] = np.nan
    
    # --- Seção 1: Custo Zerado (Mesma Cidade) ---
    try:
        st.subheader("Resultados: Custo Zerado (Mesma Cidade)")
        mesma_cidade = df_analise[cidade_rt_p] == df_analise[cidade_os_p]
        df_zero = df_analise[mesma_cidade]
        if not df_zero.empty:
            st.dataframe(df_zero[[os_col_p, cidade_os_p, cidade_rt_p, rep_col_p, tec_col_p, 'VALOR_EXTRA_R$']])
        else:
            st.info("Nenhuma ordem com Cidade RT = Cidade O.S. encontrada.")
    except Exception as e:
        st.error(f"Erro ao processar Custo Zerado: {e}")

    st.markdown("---") 

    # --- Seção 2: Duplicidade (Pagamentos Excedentes) ---
    try:
        st.subheader("Seção 2: Detecção de Duplicidade (Pagamentos Excedentes)")
        group_keys = ['DATA_ANALISE', cidade_os_p, rep_col_p, tec_col_p] 
        duplicadas = df_analise[df_analise.duplicated(subset=group_keys, keep='first')].copy()
        
        if duplicadas.empty:
            st.success("✅ Nenhuma duplicidade (pagamentos excedentes) encontrada no filtro.")
        else:
            duplicadas = df_analise[df_analise.duplicated(subset=group_keys, keep=False)].copy()
            duplicadas['AÇÃO_RECOMENDADA'] = np.where(duplicadas.duplicated(subset=group_keys, keep='first'), 'ZERAR CUSTO', 'MANTER VALOR')
            duplicadas = duplicadas.sort_values(by=group_keys + [os_col_p])
            st.warning(f"Encontradas {len(duplicadas)} ordens com duplicidade. Verifique a coluna 'AÇÃO_RECOMENDADA'.")
            
            cols_to_display = [os_col_p, data_agendamento_col_final, 'DATA_ANALISE', cliente_col_final, cidade_os_p, rep_col_p, tec_col_p, valor_extra_p, 'AÇÃO_RECOMENDADA']
            cols_final = [col for col in cols_to_display if col in duplicadas.columns] 
            col_map = {os_col_p: 'NUMERO O.S.', data_agendamento_col_final: 'DATA AGENDAMENTO', 'DATA_ANALISE': 'DATA FECHAMENTO', cliente_col_final: 'CLIENTE', cidade_os_p: 'CIDADE O.S. (ATENDIMENTO)', rep_col_p: 'REPRESENTANTE', tec_col_p: 'TÉCNICO', valor_extra_p: 'VALOR PAGO (EXTRA)', 'AÇÃO_RECOMENDADA': 'AÇÃO RECOMENDADA'}
            df_display = duplicadas.copy()
            df_display = df_display[cols_final].rename(columns=col_map)
            
            format_dict = {
                'VALOR PAGO (EXTRA)': 'R$ {:,.2f}',
                'DATA AGENDAMENTO': format_date_safe,
                'DATA FECHAMENTO': format_date_safe
            }
            
            st.dataframe(df_display.style.applymap(lambda x: 'background-color: #791616' if isinstance(x, str) and 'ZERAR CUSTO' in x else '', subset=['AÇÃO RECOMENDADA']).format(format_dict), use_container_width=True)
            csv = convert_df_to_csv(duplicadas)
            st.download_button("📥 Exportar Duplicidades (.csv)", csv, "duplicidades.csv", "text/csv", key="download_duplicadas")
    except Exception as e:
        st.error(f"Erro ao processar Duplicidade: {e}")

    st.markdown("---")
    
    # --- FUNÇÃO HELPER PARA A SEÇÃO 3 ---
    def calcular_roteiro_diario(df_roterizado_clean, cidade_base_rt, os_col, cidade_os_col):
        """
        Calcula o valor correto de um roteiro diário, considerando apenas um deslocamento por cidade.
        Agrupa O.S. por cidade na exibição.
        Retorna um dicionário com os resultados e o log.
        """
        resultado = {
            'valor_correto': 0,
            'distancia_total': 0,
            'km_a_pagar': 0,
            'metodo_usado': 'KM Fixo / Estrela (1 Desloc. por Cidade)',
            'display_roteiro': '', # Alterado para string
            'log': []
        }
    
        if df_roterizado_clean.empty:
            resultado['log'].append("DataFrame vazio, cálculo não realizado.")
            return resultado
    
        abrangencia_dia = df_roterizado_clean['ABRANGENCIA_FINAL'].iloc[0]
        taxa_km_dia = df_roterizado_clean['VALOR_KM_FINAL'].iloc[0]
    
        if taxa_km_dia == 0:
            st.error(f"A 'Taxa por KM' para este roteiro é R$ 0,00. Verifique as colunas 'Valor KM RT' (Pagamento) ou 'Valor Deslocamento' (Mapeamento). O cálculo do valor correto será zerado.")

        # --- LÓGICA DE CÁLCULO (REQUEST 2) ---
        # Considera a distância de ida para cada cidade visitada apenas UMA VEZ
        df_cidades_unicas = df_roterizado_clean.drop_duplicates(subset=[cidade_os_col])
        km_total_ida_dia = df_cidades_unicas['KM_IDA_MAP'].sum()
        
        resultado['distancia_total'] = km_total_ida_dia * 2
        resultado['km_a_pagar'] = max(0, resultado['distancia_total'] - abrangencia_dia)
        resultado['valor_correto'] = resultado['km_a_pagar'] * taxa_km_dia

        # --- LÓGICA DE EXIBIÇÃO (REQUEST 3 e 1) ---
        roteiro_parts = []
        # Agrupa por cidade de destino para montar a string de exibição
        for cidade, group in df_roterizado_clean.groupby(cidade_os_col):
            os_nums = ', '.join(group[os_col].astype(str))
            # Pega a distância da primeira O.S. do grupo (será a mesma para todas na mesma cidade)
            dist_km = group['KM_IDA_MAP'].iloc[0]
            roteiro_parts.append(f"**{cidade}** (OS: {os_nums}, {dist_km:.0f}km)")
        
        display_str = ' → '.join(roteiro_parts)
        # Monta a string final com cidade de origem/destino do RT
        resultado['display_roteiro'] = f"**{cidade_base_rt}** → {display_str} → **{cidade_base_rt}**"
    
        # --- GERAÇÃO DO LOG ---
        resultado['log'].append(f"--- CÁLCULO USADO: {resultado['metodo_usado']} ---")
        resultado['log'].append("REGRA: A distância de deslocamento é contada apenas uma vez por cidade de destino.")
        resultado['log'].append(f"1. Soma dos KM de Ida (distâncias únicas por cidade): {km_total_ida_dia:.2f} km")
        resultado['log'].append(f"2. Distância Total (Ida e Volta): {km_total_ida_dia:.2f} * 2 = {resultado['distancia_total']:.2f} km")
        resultado['log'].append(f"3. Abrangência (Franquia) do Dia: {abrangencia_dia:.2f} km")
        resultado['log'].append(f"4. Taxa por KM do Dia: R$ {taxa_km_dia:,.2f}")
        resultado['log'].append(f"5. KM a Pagar (após franquia): max(0, {resultado['distancia_total']:.2f} - {abrangencia_dia:.2f}) = {resultado['km_a_pagar']:.2f} km")
        resultado['log'].append(f"6. Valor Correto Final: {resultado['km_a_pagar']:.2f} km * R$ {taxa_km_dia:,.2f} = R$ {resultado['valor_correto']:,.2f}")
    
        return resultado

    # --- Seção 3: Roterização (ITINERÁRIO DIÁRIO) ---
    try:
        st.subheader("Seção 3: Análise de Roterização (Itinerário Diário)")
        
        if df_mapeamento is None:
            st.info("Carregue o 'Mapeamento de RT' (com KM/Taxa) para habilitar esta análise de roteiro.")
            st.markdown("---")
        else:
            col_rot1, col_rot2 = st.columns(2)
            datas_rot = df_analise['DATA_ANALISE'].dropna().unique()
            options_data = sorted(list(datas_rot)) if len(datas_rot) > 0 else []
            data_roteiro = col_rot1.selectbox("Selecione a Data do Roteiro:", options=[None] + options_data, index=0, format_func=lambda x: x.strftime('%d/%m/%Y') if x and hasattr(x, 'strftime') else 'Selecione a Data...')

            if data_roteiro is None:
                st.info("Selecione uma data acima para visualizar os roteiros daquele dia.")
            else:
                df_diario = df_analise[df_analise['DATA_ANALISE'] == data_roteiro].copy().dropna(subset=[rep_col_p, tec_col_p])
                grupos_rot = df_diario.groupby([rep_col_p, tec_col_p]).size().reset_index(name='count')
                grupos_rot['RT_TECNICO'] = grupos_rot[rep_col_p] + ' / ' + grupos_rot[tec_col_p]
                rt_selecionado = col_rot2.selectbox("Selecione o RT/Técnico:", options=[None] + grupos_rot['RT_TECNICO'].tolist(), index=0)

                if rt_selecionado is None:
                    st.info("Selecione um RT/Técnico para ver o roteiro e o custo.")
                else:
                    rep_sel, tec_sel = rt_selecionado.split(' / ')
                    df_roterizado = df_diario[(df_diario[rep_col_p] == rep_sel) & (df_diario[tec_col_p] == tec_sel)].copy()
                    
                    if df_roterizado.empty:
                        st.warning("Nenhum pagamento encontrado para esta seleção.")
                        return
                    
                    df_roterizado['VALOR_CORRETO_R$'] = df_roterizado['VALOR_CORRETO_R$'].fillna(0)

                    # Cria um DF de limpeza para o MAPA. Se não houver lat/lon, usa o DF completo.
                    df_roterizado_clean = df_roterizado.copy()
                    map_clean_subset = ['lat', 'lon'] # Colunas para o mapa
                    
                    # Filtra para o mapa apenas se as colunas de coordenadas existirem
                    if all(col in df_roterizado_clean.columns for col in map_clean_subset):
                        df_roterizado_clean = df_roterizado_clean.dropna(subset=map_clean_subset).copy()

                    # Para exibição do Roteiro, a ordenação é feita pelo KM Haversine (se disponível) ou KM Fixo
                    km_ordenacao_col = 'KM_IDA_CALCULADO' if 'KM_IDA_CALCULADO' in df_roterizado_clean.columns else 'KM_IDA_MAP'
                    df_roterizado_clean = df_roterizado_clean.sort_values(by=[km_ordenacao_col])

                    total_pago_dia = df_roterizado_clean['VALOR_EXTRA_R$'].sum()
                    cidade_base_rt = df_roterizado_clean[cidade_rt_p].iloc[0] if not df_roterizado_clean.empty else "N/A"
                    
                    st.subheader(f"Itinerário para {rt_selecionado} ({data_roteiro.strftime('%d/%m/%Y')})")

                    # Chama a nova função de cálculo
                    calculo = calcular_roteiro_diario(df_roterizado_clean, cidade_base_rt, os_col_p, cidade_os_p)
                    valor_correto_roteiro = calculo['valor_correto']

                    # Exibe o roteiro na tela
                    st.markdown(f"**Roteiro (Baseado em KM Fixo):** {calculo['display_roteiro']}")
                    
                    cols_metric = st.columns(3)
                    cols_metric[0].metric("Valor Pago Total (Dia)", f"R$ {total_pago_dia:,.2f}")
                    cols_metric[1].metric("Valor Correto Roteiro (Soma)", f"R$ {valor_correto_roteiro:,.2f}")
                    cols_metric[2].metric("Diferença / Economia", f"R$ {total_pago_dia - valor_correto_roteiro:,.2f}", delta=f"R$ {valor_correto_roteiro - total_pago_dia:,.2f}")
                    st.caption("A 'Diferença' mostra o valor que foi pago a mais que o ideal (Valor Pago Total - Valor Correto Roteiro).")

                    # --- GERAÇÃO DO LOG DE CÁLCULO (AGORA VINDO DA FUNÇÃO) ---
                    log_content = []
                    log_content.append("--- LOG DE CÁLCULO DO ROTEIRO ---")
                    log_content.append(f"Data do Roteiro: {data_roteiro.strftime('%d/%m/%Y')}")
                    log_content.append(f"RT/Técnico: {rt_selecionado}")
                    
                    log_content.append("\n--- Cidades no Roteiro ---")
                    for _, row in df_roterizado_clean.iterrows():
                        log_content.append(f"- Cidade: {row[cidade_os_p]}, OS: {row[os_col_p]}, KM Ida (Fixo): {row.get('KM_IDA_MAP', 0):.2f} km")

                    log_content.append("\n" + "\n".join(calculo['log']))

                    log_content.append("\n--- Comparação ---")
                    log_content.append(f"Valor Pago Total no Dia: R$ {total_pago_dia:,.2f}")
                    log_content.append(f"Valor Correto Calculado: R$ {valor_correto_roteiro:,.2f}")

                    log_txt = "\n".join(log_content)
                    st.download_button("📥 Exportar Log de Cálculo (.txt)", data=log_txt.encode('utf-8'), file_name=f"log_calculo_{rep_sel.replace(' ','_')}_{data_roteiro.strftime('%Y%m%d')}.txt", mime="text/plain")
                    
                    st.markdown("#### Mapa do Roteiro")
                    # O Mapa usa a coluna 'lat' e 'lon' que agora tem o fallback do Mapeamento
                    map_data = df_roterizado_clean.rename(columns={'lat': 'lat', 'lon': 'lon'})
                    map_data = df_roterizado_clean.rename(columns={'lat': 'lat', 'lon': 'lon'}).dropna(subset=['lat', 'lon'])
                    
                    if not map_data.empty:
                        st.map(map_data)
                    else:
                        st.info("Coordenadas de Lat/Lon não foram encontradas para este roteiro (Verifique as colunas de coordenadas no Mapeamento ou Pagamento).")
                    
                    st.markdown("---")
                    st.subheader("Detalhe de Custos por O.S. na Rota")
                    
                    cols_display_rota = [os_col_p, 'DATA_ANALISE', cidade_os_p, 'KM_IDA_MAP', 'VALOR_EXTRA_R$', 'VALOR_CORRETO_R$']
                    cols_rota_final = [col for col in cols_display_rota if col in df_roterizado_clean.columns]
                    df_display_rota = df_roterizado_clean[cols_rota_final].rename(columns={os_col_p: 'NUMERO O.S.', 'DATA_ANALISE': 'DATA FECHAMENTO', cidade_os_p: 'CIDADE O.S.', 'KM_IDA_MAP': 'KM IDA (FIXO)', 'VALOR_EXTRA_R$': 'VALOR PAGO (EXTRA)', 'VALOR_CORRETO_R$': 'VALOR CORRETO'})
                    
                    if 'VALOR PAGO (EXTRA)' in df_display_rota.columns and 'VALOR CORRETO' in df_display_rota.columns:
                        df_display_rota['DIFERENCA'] = df_display_rota['VALOR PAGO (EXTRA)'] - df_display_rota['VALOR CORRETO']
                    
                    st.dataframe(df_display_rota.style.format({
                        'DATA FECHAMENTO': format_date_safe, 
                        'KM IDA (FIXO)': '{:.0f} km',
                        'VALOR PAGO (EXTRA)': 'R$ {:,.2f}',
                        'VALOR CORRETO': 'R$ {:,.2f}',
                        'DIFERENCA': 'R$ {:,.2f}',
                    }), use_container_width=True)
                    
                    csv_rota = convert_df_to_csv(df_roterizado_clean)
                    st.download_button("📥 Exportar Detalhe do Roteiro (.csv)", csv_rota, "detalhe_roteiro.csv", "text/csv", key="download_roteiro_detalhe")
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado no Otimizador (Seção 3): {e}")
        import traceback
        st.error(traceback.format_exc())

    st.markdown("---")
