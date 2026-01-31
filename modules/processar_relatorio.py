import pandas as pd
import re
from urllib.parse import unquote
import os
import glob
def extrair_odometros(texto):
    """
    Extrai os valores do odômetro Normal e CAN de um bloco de texto.
    """
    if not isinstance(texto, str):
        return None, None

    texto_limpo = texto.replace('\n', ' ').replace('\r', ' ')
    
    odometro_normal = None
    odometro_can = None

    # Padrão para "Odometro CAN", agora mais flexível (H opcional, espaço ou underscore, : opcional)
    padrao_can = r"(H?odometro[\s_]*CAN)\s*:?\s*(-?\d+\.?\d*)"
    match_can = re.search(padrao_can, texto_limpo, re.IGNORECASE)
    if match_can:
        odometro_can = float(match_can.group(2))

    # Padrão para "Odometro" normal.
    padrao_normal = r"(H?odometro)\s*:?\s*(-?\d+\.?\d*)"
    matches_normal = re.finditer(padrao_normal, texto_limpo, re.IGNORECASE)
    for match in matches_normal:
        start_substring = match.start(1) + len(match.group(1))
        end_substring = match.start(2)
        # The substring is what's between "H?odometro" and the number
        substring = texto_limpo[start_substring:end_substring]
        
        if "can" not in substring.lower():
            odometro_normal = float(match.group(2))
            break 
            
    return odometro_normal, odometro_can

def extrair_valor(texto, campo):
    """Usa Regex para encontrar um valor em um bloco de texto."""
    if not isinstance(texto, str):
        return None

    # Limpeza: Transforma o texto de múltiplas linhas em uma única linha.
    texto_limpo = texto.replace('\n', ' ').replace('\r', ' ')

    # Padrão para valores numéricos (latitude, longitude, velocidade, tensao)
    # Odometro é tratado separadamente agora
    if campo in ['latitude', 'longitude', 'velocidade', 'tensao']:
        padrao = rf"{campo}\s*:\s*(-?\d+\.?\d*)"
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None

    # Padrão para o município (texto entre aspas)
    if campo == 'municipio':
        padrao = r'municipio\s*:\s*""([^""]+)""'
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            texto_codificado = match.group(1)
            return unquote(texto_codificado).replace('+', ' ')
        return None
    
    return None

def processar_dataframe_posicao(df_bruto):
    """
    Recebe um DataFrame bruto de última posição e retorna um DataFrame processado
    com as colunas de lat, long, etc., extraídas.
    """
    if df_bruto is None:
        return None

    df = df_bruto.copy()

    if 'Dados GSM' not in df.columns: df['Dados GSM'] = None
    if 'Dados P2P' not in df.columns: df['Dados P2P'] = None

    campos_para_extrair = ['latitude', 'longitude', 'velocidade', 'tensao', 'municipio']
    
    for campo in campos_para_extrair:
        # Tenta extrair do GSM primeiro
        if 'Dados GSM' in df.columns:
            df[campo] = df['Dados GSM'].apply(lambda texto: extrair_valor(texto, campo))
        
        # Onde não encontrou, tenta no P2P
        if 'Dados P2P' in df.columns:
            coluna_p2p = df['Dados P2P'].apply(lambda texto: extrair_valor(texto, campo))
            df[campo] = df.get(campo, pd.Series(index=df.index)).fillna(coluna_p2p)

    # --- EXTRAÇÃO DO ODÔMETRO (Normal e CAN) ---
    def assign_odometers(row):
        # Prioriza GSM
        gsm_text = row.get('Dados GSM', None)
        normal_gsm, can_gsm = extrair_odometros(gsm_text) if isinstance(gsm_text, str) else (None, None)

        # Fallback para P2P
        p2p_text = row.get('Dados P2P', None)
        normal_p2p, can_p2p = extrair_odometros(p2p_text) if isinstance(p2p_text, str) else (None, None)
        
        # Consolida os resultados: usa o valor do GSM se existir, senão usa o do P2P.
        final_normal = normal_gsm if normal_gsm is not None else normal_p2p
        final_can = can_gsm if can_gsm is not None else can_p2p
        
        return (final_normal, final_can)

    # Aplica a função para obter os dois valores de odômetro
    odometer_data = df.apply(assign_odometers, axis=1, result_type='expand')
    odometer_data.columns = ['odometro', 'odometro_can']

    # Atribui as novas colunas ao DataFrame principal
    df['odometro'] = odometer_data['odometro']
    df['odometro_can'] = odometer_data['odometro_can']

    df.rename(columns={
        'latitude': 'lat', 'longitude': 'long',
        'tensao': 'tensao bateria', 'municipio': 'cidade'
    }, inplace=True)

    # --- CÁLCULO DE DIAS SEM POSIÇÃO E TECNOLOGIA (MAIS ROBUSTO) ---
    df['tecnologia_posicao'] = None
    df['data_evento'] = pd.NaT # Inicializa a coluna

    # Identificação flexível das colunas de data
    gsm_date_col = next((c for c in df.columns if 'data' in c.lower() and 'gsm' in c.lower()), None)
    p2p_date_col = next((c for c in df.columns if 'data' in c.lower() and 'p2p' in c.lower()), None)

    # Tenta usar GSM como primário
    if gsm_date_col:
        data_gsm = pd.to_datetime(df[gsm_date_col], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        mask_gsm_valid = data_gsm.notna()
        # Aplica data e tecnologia onde o GSM é válido
        df.loc[mask_gsm_valid, 'data_evento'] = data_gsm[mask_gsm_valid]
        df.loc[mask_gsm_valid, 'tecnologia_posicao'] = 'GSM'

    # Tenta usar P2P como secundário (fallback)
    if p2p_date_col:
        data_p2p = pd.to_datetime(df[p2p_date_col], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        # Máscara para as datas que AINDA estão vazias (seja porque GSM não existe ou era inválido)
        mask_needs_fallback = df['data_evento'].isna()
        mask_p2p_valid = data_p2p.notna()
        
        fill_mask = mask_needs_fallback & mask_p2p_valid
        df.loc[fill_mask, 'data_evento'] = data_p2p[fill_mask]
        df.loc[fill_mask, 'tecnologia_posicao'] = 'P2P'

    # Calcula a diferença em dias de hoje até a data do evento
    if 'data_evento' in df.columns:
        df['dias_sem_posicao'] = (pd.Timestamp.now() - df['data_evento']).dt.days
    else:
        df['dias_sem_posicao'] = None # Garante que a coluna exista

    return df
