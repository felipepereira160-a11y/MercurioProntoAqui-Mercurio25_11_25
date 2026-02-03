# modules/utils.py
import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import shutil
from datetime import datetime, date

@st.cache_data
def convert_df_to_csv(df):
    # --- CORREÇÃO DE FORMATAÇÃO CSV ---
    # Adicionado decimal=',' para que o Excel (BRL) leia os números corretamente
    # E sep=';' (ponto e vírgula)
    return df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
    # --- FIM DA CORREÇÃO ---

@st.cache_data
def convert_df_to_excel(df):
    """
    Converte um DataFrame para um arquivo Excel (.xlsx) em memória.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()
def safe_to_numeric(series):
    # Esta função já converte R$ 1.234,56 para 1234.56
    if series.dtype == 'object':
        series = series.astype(str).str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
    return pd.to_numeric(series, errors='coerce').fillna(0)

def processar_os_raiz(os_str):
    """Função crucial para tratar os sufixos .1, .2 etc."""
    os_str = str(os_str).strip()
    if '.' in os_str:
        return os_str.split('.')[0]
    return os_str

# --- FUNÇÃO DE ANÁLISE (Agente de 2 Passos) ---
@st.cache_data(ttl=3600)
def executar_analise_segura(_df_hash, pergunta, df_type):
    df = None
    nome_df = ""
    
    if df_type == 'agendamentos' and "df_agendamentos" in st.session_state and st.session_state.df_agendamentos is not None:
        df = st.session_state.df_agendamentos
        nome_df = "Agendamentos de O.S."
    elif df_type == 'mapeamento' and "df_mapeamento" in st.session_state and st.session_state.df_mapeamento is not None:
        df = st.session_state.df_mapeamento
        nome_df = "Mapeamento de RTs"
    elif df_type == 'ativos' and "df_ativos" in st.session_state and st.session_state.df_ativos is not None:
        df = st.session_state.df_ativos
        nome_df = "Base de Ativos"
    elif df_type == 'custos' and "df_pagamento" in st.session_state and st.session_state.df_pagamento is not None:
        df = st.session_state.df_pagamento
        nome_df = "Base de Pagamento (Custos)"
    elif df_type == 'devolucao' and "df_devolucao" in st.session_state and st.session_state.df_devolucao is not None:
        df = st.session_state.df_devolucao
    elif df_type == 'viagens' and "df_distancia_detalhada" in st.session_state and st.session_state.df_distancia_detalhada is not None:
        df = st.session_state.df_distancia_detalhada
        nome_df = "Base de Devolução"
    
    if df is None:
        if df_type == 'agendamentos': return "Para responder isso, por favor, carregue a 'Pesquisa de O.S.' na aba 'Dashboard'.", None
        elif df_type == 'mapeamento': return "Para responder isso, por favor, carregue o 'Mapeamento de RT' na aba 'Otimizador'.", None
        elif df_type == 'ativos': return "Para responder isso, por favor, carregue a 'Base de Ativos' na aba 'Ativos'.", None
        elif df_type == 'custos': return "Para responder isso, por favor, carregue a 'Base de Pagamento' na aba 'Custos'.", None
        elif df_type == 'devolucao': return "Para responder isso, por favor, carregue a 'Base de Devolução' na aba 'Devolução'.", None
        elif df_type == 'viagens': return "Para responder isso, por favor, carregue o 'Relatório de Distância Percorrida' na aba 'Viagens'.", None
        else: return "Não encontrei os dados necessários. Por favor, carregue o arquivo correspondente.", None

    prompt_gerar_codigo = f"""
    Você é um especialista em Pandas. A partir da pergunta do usuário, gere UMA ÚNICA LINHA de código Python (sem 'print()') que possa ser executada para obter a resposta.
    Use o dataframe 'df'.
    As colunas disponíveis no dataframe '{nome_df}' são: {', '.join(df.columns)}.

    Exemplos:
    Pergunta: "quantas ordens tem?" -> Resposta: len(df)
    Pergunta: "qual o deslocamento total?" -> Resposta: df['Deslocamento'].sum()
    Pergunta: "quais clientes tem mais ordens?" -> Resposta: df['Cliente'].value_counts().head(5)
    Pergunta: "Total de ordens agendadas" -> Resposta: len(df[df['Status'] == 'Agendada'])

    INSTRUÇÕES:
    1. Se a pergunta for genérica (ex: "quem descobriu o Brasil?"), responda APENAS com: "PERGUNTA_INVALIDA".
    2. Retorne APENAS a linha de código.

    Pergunta do Usuário: "{pergunta}"
    Sua linha de código:
    """
    
    try:
        response_codigo = st.session_state.model.generate_content(prompt_gerar_codigo)
        codigo_pandas = response_codigo.text.strip().replace('`', '').replace('python', '')

        if "PERGUNTA_INVALIDA" in codigo_pandas:
            return None, "PERGUNTA_INVALIDA"

        resultado_bruto = eval(codigo_pandas, {'df': df, 'pd': pd, 'np': np})

        prompt_formatar_resposta = f"""
        **Sua Personalidade:** Você é Mercúrio, um assistente de IA amigável, prestativo e brasileiro.
        **Tarefa:** Responda à pergunta do usuário de forma amigável e direta, com base no resultado da análise.
        **Pergunta do Usuário:** "{pergunta}"
        **Resultado da Análise:** "{str(resultado_bruto)}"
        **Instruções para a Resposta:**
        - Fale como Mercúrio, em primeira pessoa.
        - Não mencione o "resultado da análise" ou o código.
        - Apenas dê a resposta final.
        **Sua Resposta (como Mercúrio):**
        """
        
        response_final = st.session_state.model.generate_content(prompt_formatar_resposta)
        resposta_formatada = response_final.text.strip()
        
        return resposta_formatada, None

    except Exception as e:
        return f"Não consegui analisar essa pergunta. Detalhes do erro: {e}", None

def gerar_contexto_dados(filtro_chave=None):
    """Gera uma string de contexto com o resumo dos DataFrames carregados na sessão.

    Se filtro_chave for informado, retorna apenas o contexto daquele DataFrame.
    """
    contexto = []
    
    # Mapeia as chaves do session_state para nomes amigáveis
    df_map = {
        "df_agendamentos": "Agendamentos de O.S.",
        "df_mapeamento": "Mapeamento de RTs",
        "df_ativos": "Base de Ativos",
        "df_pagamento": "Base de Pagamento (Custos)",
        "df_devolucao": "Base de Devolução",
        "df_distancia_detalhada": "Relatório de Viagens/Distância",
        "df_backlog": "Backlog de O.S.",
        "df_ultimaposicao": "Última Posição dos Ativos",
        "df_cps": "Relatório CPS",
        "df_ordens_pendentes": "Ordens Pendentes"
    }
    
    contexto.append("Resumo dos dados atualmente carregados na sessão:")
    
    for key, name in df_map.items():
        if filtro_chave and key != filtro_chave:
            continue
        if key in st.session_state and st.session_state[key] is not None:
            df = st.session_state[key]
            colunas = ", ".join(df.columns)
            contexto.append(f"- **DataFrame `{key}` ('{name}')**: Contém {len(df)} linhas. Colunas: `{colunas}`.")
            
    if len(contexto) == 1: # Apenas o título foi adicionado
        if filtro_chave:
            return "Nenhum dado foi carregado para esse tópico ainda."
        return "Nenhum dado foi carregado na aplicação ainda."
        
    return "\n".join(contexto)

# --- FUNÇÃO DE DETECÇÃO DE TIPO (Atualizada) ---
def detectar_tipo_pergunta(texto):
    if not texto:
        return "geral"
    texto = str(texto).lower()
    
    custos_keys = ["custos", "pagamento", "conciliar", "zerar", "roteirização"]
    if any(k in texto for k in custos_keys) and "df_pagamento" in st.session_state and st.session_state.df_pagamento is not None:
        return "custos"
    
    ativos_keys = ["ativos", "veículo", "veiculo", "placa", "chassi", "numero de serie"]
    if any(k in texto for k in ativos_keys) and "df_ativos" in st.session_state and st.session_state.df_ativos is not None:
        return "ativos"
        
    devol_keys = ["devolução", "devolucao", "itens a instalar", "vencidas"]
    if any(k in texto for k in devol_keys) and "df_devolucao" in st.session_state and st.session_state.df_devolucao is not None:
        return "devolucao"

    viagens_keys = ["viagens", "distancia", "percorrido", "tempo viagem", "placa", "motorista", "localizacao"]
    if any(k in texto for k in viagens_keys) and "df_distancia_detalhada" in st.session_state and st.session_state.df_distancia_detalhada is not None:
        return "viagens"

    map_keys = ["mapeamento", "quem atende", "rt para", "cidade x"]
    if any(k in texto for k in map_keys) and "df_mapeamento" in st.session_state and st.session_state.df_mapeamento is not None:
        return "mapeamento"
    
    agenda_keys = [
        "quantos", "qual o total", "agendada", "realizada", "status", 
        "cliente", "os", "ordem", "agendamento", "visita", "deslocamento",
        "cidades", "rt"
    ]
    if any(k in texto for k in agenda_keys) and "df_agendamentos" in st.session_state and st.session_state.df_agendamentos is not None:
        return "agendamentos"
    
    return "geral"


def adicionar_mensagem_assistente(mensagem):
    if isinstance(mensagem, str):
        mensagem = mensagem.replace("\r\n", "\n").replace("\r", "\n").strip()
    if "display_history" not in st.session_state:
        st.session_state.display_history = []
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    st.session_state.display_history.append({"role": "assistant", "content": mensagem})
    st.session_state.chat_history.append({"role": "assistant", "content": mensagem})

def inicializar_metricas_chat():
    if "chat_metrics" not in st.session_state:
        st.session_state.chat_metrics = {
            "total": 0,
            "por_topico": {},
            "duracoes": [],
            "perguntas": {},
            "modo": {"geral": 0, "especialista": 0, "local": 0},
            "ultima_resposta_s": None,
        }

def _limitar_tamanho_lista(lista, max_itens=300):
    if len(lista) > max_itens:
        del lista[:-max_itens]

def _limitar_tamanho_dict_por_valor(dados, max_itens=200):
    if len(dados) <= max_itens:
        return
    itens = sorted(dados.items(), key=lambda x: x[1], reverse=True)[:max_itens]
    dados.clear()
    dados.update(itens)

def registrar_metricas_chat(prompt, topico, duracao_s, modo, usuario=None):
    inicializar_metricas_chat()
    metrics = st.session_state.chat_metrics

    metrics["total"] += 1
    if topico:
        metrics["por_topico"][topico] = metrics["por_topico"].get(topico, 0) + 1
    if usuario:
        if "por_usuario" not in metrics:
            metrics["por_usuario"] = {}
        metrics["por_usuario"][usuario] = metrics["por_usuario"].get(usuario, 0) + 1

    if duracao_s is not None:
        metrics["duracoes"].append(float(duracao_s))
        metrics["ultima_resposta_s"] = float(duracao_s)
        _limitar_tamanho_lista(metrics["duracoes"], max_itens=300)

    if modo:
        if modo not in metrics["modo"]:
            metrics["modo"][modo] = 0
        metrics["modo"][modo] += 1

    if prompt:
        chave = str(prompt).strip().lower()
        if chave:
            metrics["perguntas"][chave] = metrics["perguntas"].get(chave, 0) + 1
            _limitar_tamanho_dict_por_valor(metrics["perguntas"], max_itens=200)

    if usuario and prompt:
        if "perguntas_por_usuario" not in metrics:
            metrics["perguntas_por_usuario"] = {}
        lista = metrics["perguntas_por_usuario"].setdefault(usuario, [])
        lista.append(str(prompt).strip())
        _limitar_tamanho_lista(lista, max_itens=50)

def backup_automatico_diario(arquivos, base_dir=".", backup_dir="backups", max_backups=10):
    if not arquivos:
        return
    base_dir = os.path.abspath(base_dir)
    backup_root = os.path.join(base_dir, backup_dir)
    os.makedirs(backup_root, exist_ok=True)

    marcador = os.path.join(backup_root, "last_backup.txt")
    hoje = date.today().isoformat()
    if os.path.exists(marcador):
        try:
            with open(marcador, "r", encoding="utf-8") as f:
                if f.read().strip() == hoje:
                    return
        except Exception:
            pass

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(backup_root, f"backup_{timestamp}")
    os.makedirs(destino, exist_ok=True)

    for rel_path in arquivos:
        origem = os.path.join(base_dir, rel_path)
        if not os.path.exists(origem):
            continue
        if os.path.isdir(origem):
            shutil.copytree(origem, os.path.join(destino, rel_path))
        else:
            os.makedirs(os.path.dirname(os.path.join(destino, rel_path)), exist_ok=True)
            shutil.copy2(origem, os.path.join(destino, rel_path))

    with open(marcador, "w", encoding="utf-8") as f:
        f.write(hoje)

    backups = sorted(
        [d for d in os.listdir(backup_root) if d.startswith("backup_")],
        reverse=True,
    )
    for old in backups[max_backups:]:
        try:
            shutil.rmtree(os.path.join(backup_root, old))
        except Exception:
            pass
