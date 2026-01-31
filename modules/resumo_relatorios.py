import pandas as pd

from modules.processar_relatorio import processar_dataframe_posicao
from modules.utils import safe_to_numeric


def _format_int(valor):
    try:
        return f"{int(valor):,}".replace(",", ".")
    except Exception:
        return str(valor)


def _format_money(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(valor)


def _infer_date_range(df):
    if df is None or df.empty:
        return None
    date_cols = [c for c in df.columns if isinstance(c, str) and "data" in c.lower()]
    for col in date_cols:
        serie = pd.to_datetime(df[col], errors="coerce")
        if serie.notna().any():
            data_min = serie.min()
            data_max = serie.max()
            if pd.notna(data_min) and pd.notna(data_max):
                return col, data_min, data_max
    return None


def _sum_money_columns(df):
    if df is None or df.empty:
        return []
    cols = [
        c for c in df.columns
        if isinstance(c, str) and any(k in c.lower() for k in ["valor", "custo", "pagamento", "total"])
    ]
    resultados = []
    for col in cols:
        serie = pd.to_numeric(df[col], errors="coerce")
        if serie.notna().any():
            resultados.append((col, serie.sum()))
    return resultados


def gerar_resumo_ultima_posicao(df_bruto, nome_arquivo=None):
    if df_bruto is None or df_bruto.empty:
        return "Resumo Geral — Última Posição\nNenhum dado válido encontrado no relatório."

    df_processado = processar_dataframe_posicao(df_bruto)
    if df_processado is None or df_processado.empty:
        return "Resumo Geral — Última Posição\nNenhum dado válido encontrado após o processamento."

    total = len(df_processado)
    dias = df_processado.get("dias_sem_posicao")
    if dias is None:
        return "Resumo Geral — Última Posição\nA coluna 'dias_sem_posicao' não foi encontrada no relatório."

    sem_posicao = dias.isna().sum()
    fora_prazo = (dias >= 15).sum()
    alerta = dias.between(12, 14, inclusive="both").sum()
    ok = dias.between(1, 11, inclusive="both").sum()
    recente = (dias == 0).sum()
    criticos = sem_posicao + fora_prazo

    titulo = f"**Resumo Geral — Base de Equipamentos ({_format_int(total)})**"
    arquivo = f"Arquivo: {nome_arquivo}" if nome_arquivo else None

    resumo = "\n".join(
        [titulo]
        + ([arquivo] if arquivo else [])
        + [
            "",
            f"- **Equipamentos sem posição (nunca posicionaram):** {_format_int(sem_posicao)}",
            "  - Indicam possível falha de instalação, ativação ou ausência total de cobertura.",
            "",
            f"- **Equipamentos fora do prazo (≥ 15 dias sem posição):** {_format_int(fora_prazo)}",
            "  - Necessitam manutenção imediata.",
            "",
            f"- **Equipamentos em alerta (12 a 14 dias sem posição):** {_format_int(alerta)}",
            "  - Devem ser monitorados preventivamente.",
            "",
            f"- **⚠️ Total de equipamentos críticos:** {_format_int(criticos)}",
            "  - Representam os casos que exigem ação e acompanhamento.",
            "",
            f"- **🟡 Equipamentos operando dentro do prazo (1–11 dias):** {_format_int(ok)}",
            "  - Situação normal.",
            "",
            f"- **✅ Equipamentos com posição muito recente (0 dias):** {_format_int(recente)}",
            "",
            f"**Total da base:** {_format_int(total)}",
        ]
    )

    return resumo


def gerar_resumo_generico(df, nome, nome_arquivo=None):
    if df is None or df.empty:
        return f"Resumo Geral — {nome}\nNenhum dado válido encontrado no arquivo."

    total = len(df)
    total_cols = len(df.columns)
    colunas = [c for c in df.columns if isinstance(c, str)]
    colunas_preview = ", ".join(colunas[:8])
    if len(colunas) > 8:
        colunas_preview += ", ..."

    titulo = f"**Resumo Geral — {nome}**"
    arquivo = f"Arquivo: {nome_arquivo}" if nome_arquivo else None

    resumo = "\n".join(
        [titulo]
        + ([arquivo] if arquivo else [])
        + [
            "",
            f"- **Total de registros:** {_format_int(total)}",
            f"- **Total de colunas:** {_format_int(total_cols)}",
            f"- **Principais colunas:** {colunas_preview}",
        ]
    )

    return resumo


def gerar_resumo_agendamentos(df, nome_arquivo=None):
    if df is None or df.empty:
        return "Resumo Geral — Agendamentos de O.S.\nNenhum dado válido encontrado no arquivo."

    df_ag = df.copy()
    total = len(df_ag)

    status_col = next((c for c in df_ag.columns if isinstance(c, str) and "status" in c.lower()), None)
    cliente_col = next((c for c in df_ag.columns if isinstance(c, str) and "cliente" in c.lower() and "id" not in c.lower()), None)
    cidade_col = next((c for c in df_ag.columns if isinstance(c, str) and "cidade" in c.lower()), None)
    rep_col = next((c for c in df_ag.columns if isinstance(c, str) and "representante" in c.lower() and "id" not in c.lower()), None)
    fechamento_col = next((c for c in df_ag.columns if isinstance(c, str) and ("tipo de fechamento" in c.lower() or "motivo fechamento" in c.lower())), None)

    data_fech_col = next((c for c in df_ag.columns if isinstance(c, str) and "data de fechamento" in c.lower()), None)
    data_ref_col = next((c for c in df_ag.columns if isinstance(c, str) and "data de referencia" in c.lower()), None)
    data_abert_col = next((c for c in df_ag.columns if isinstance(c, str) and "data de abertura" in c.lower()), None)
    data_col = data_fech_col or data_ref_col or data_abert_col

    valor_extra_col = next((c for c in df_ag.columns if isinstance(c, str) and "valor extra" in c.lower()), None)
    valor_desl_col = next((c for c in df_ag.columns if isinstance(c, str) and "valor deslocamento" in c.lower()), None)

    if status_col:
        df_ag[status_col] = df_ag[status_col].astype(str)
    if fechamento_col:
        df_ag[fechamento_col] = df_ag[fechamento_col].astype(str)

    agendadas = df_ag[status_col].str.contains("agendada", case=False, na=False).sum() if status_col else None
    realizadas = df_ag[status_col].str.contains("realizada", case=False, na=False).sum() if status_col else None
    clientes_unicos = df_ag[cliente_col].nunique() if cliente_col else None

    improdutivas = df_ag[df_ag[fechamento_col].str.contains("improdutiva", case=False, na=False)].shape[0] if fechamento_col else None
    nao_comparecimento = df_ag[df_ag[fechamento_col].str.contains("não comparecimento|nao comparecimento", case=False, na=False)].shape[0] if fechamento_col else None
    indisponibilidade = df_ag[df_ag[fechamento_col].str.contains("indisponibilidade técnica|indisponibilidade tecnica", case=False, na=False)].shape[0] if fechamento_col else None

    titulo = "**Resumo Geral — Agendamentos de O.S.**"
    arquivo = f"Arquivo: {nome_arquivo}" if nome_arquivo else None

    linhas = [titulo] + ([arquivo] if arquivo else []) + [""]
    linhas.append(f"- **Total de O.S.:** {_format_int(total)}")
    if agendadas is not None:
        linhas.append(f"- **O.S. agendadas:** {_format_int(agendadas)}")
    if realizadas is not None:
        linhas.append(f"- **O.S. realizadas:** {_format_int(realizadas)}")
    if clientes_unicos is not None:
        linhas.append(f"- **Clientes únicos:** {_format_int(clientes_unicos)}")
    if improdutivas is not None:
        linhas.append(f"- **Visitas improdutivas:** {_format_int(improdutivas)}")
    if nao_comparecimento is not None:
        linhas.append(f"- **Não comparecimento:** {_format_int(nao_comparecimento)}")
    if indisponibilidade is not None:
        linhas.append(f"- **Indisponibilidade técnica:** {_format_int(indisponibilidade)}")

    if cidade_col:
        top_cidades = df_ag[cidade_col].value_counts().head(3)
        if not top_cidades.empty:
            linhas.append("")
            linhas.append("- **Top 3 cidades por volume:**")
            for cidade, qtd in top_cidades.items():
                linhas.append(f"  - {cidade}: {_format_int(qtd)}")

    # Custos extras/deslocamento por representante e cidade (por mês)
    custo_cols = [c for c in [valor_extra_col, valor_desl_col] if c]
    if custo_cols and rep_col and cidade_col and data_col:
        df_custos = df_ag.copy()
        total_custo = 0
        for col in custo_cols:
            df_custos[col] = safe_to_numeric(df_custos[col])
            total_custo += df_custos[col]
        df_custos["CUSTO_TOTAL_R$"] = total_custo
        df_custos = df_custos[df_custos["CUSTO_TOTAL_R$"] > 0].copy()
        df_custos["_DATA"] = pd.to_datetime(df_custos[data_col], dayfirst=True, errors="coerce")
        df_custos = df_custos[df_custos["_DATA"].notna()].copy()
        if not df_custos.empty:
            df_custos["MES"] = df_custos["_DATA"].dt.to_period("M").astype(str)
            resumo_custos = (
                df_custos.groupby([rep_col, cidade_col, "MES"])["CUSTO_TOTAL_R$"]
                .agg(["sum", "count"])
                .sort_values(by="sum", ascending=False)
                .head(5)
            )
            if not resumo_custos.empty:
                linhas.append("")
                linhas.append("- **Custos extras/deslocamento (Top 5):**")
                for (rep, cidade, mes), row in resumo_custos.iterrows():
                    linhas.append(
                        f"  - {rep} · {cidade} · {mes}: {_format_money(row['sum'])} | {int(row['count'])} visitas"
                    )
    else:
        if custo_cols:
            linhas.append("")
            linhas.append("- **Custos extras/deslocamento:** colunas de representante/cidade/data não encontradas para detalhamento.")

    return "\n".join(linhas)


def gerar_resumo_backlog(df, nome_arquivo=None):
    if df is None or df.empty:
        return "Resumo Geral — Backlog\nNenhum dado válido encontrado no arquivo."

    total = len(df)
    os_col = next((c for c in df.columns if isinstance(c, str) and c.lower() in ["os", "numero os", "ordem de servico", "ordem"]), None)
    cidade_col = next((c for c in df.columns if isinstance(c, str) and "cidade" in c.lower()), None)
    uf_col = next((c for c in df.columns if isinstance(c, str) and c.lower() == "uf"), None)

    total_os = df[os_col].nunique() if os_col else None
    total_cidades = df[cidade_col].nunique() if cidade_col else None
    total_ufs = df[uf_col].nunique() if uf_col else None

    titulo = "**Resumo Geral — Backlog (Base Itens Instalar)**"
    arquivo = f"Arquivo: {nome_arquivo}" if nome_arquivo else None

    linhas = [titulo] + ([arquivo] if arquivo else []) + ["", f"- **Total de registros:** {_format_int(total)}"]
    if total_os is not None:
        linhas.append(f"- **Ordens de serviço únicas:** {_format_int(total_os)}")
    if total_cidades is not None:
        linhas.append(f"- **Cidades diferentes:** {_format_int(total_cidades)}")
    if total_ufs is not None:
        linhas.append(f"- **UFs diferentes:** {_format_int(total_ufs)}")

    return "\n".join(linhas)


def gerar_resumo_custos(df, nome_arquivo=None):
    if df is None or df.empty:
        return "Resumo Geral — Custos\nNenhum dado válido encontrado no arquivo."

    df_custos = df.copy()
    total = len(df_custos)

    os_col = next((c for c in df_custos.columns if isinstance(c, str) and "os" in c.lower()), None)
    data_col = next((c for c in df_custos.columns if isinstance(c, str) and "data de fechamento" in c.lower()), None)
    cidade_os_col = next((c for c in df_custos.columns if isinstance(c, str) and "cidade o.s." in c.lower()), None)
    rep_col = next((c for c in df_custos.columns if isinstance(c, str) and "representante" in c.lower() and "nome fantasia" not in c.lower()), None)
    tec_col = next((c for c in df_custos.columns if isinstance(c, str) and ("técnico" in c.lower() or "tecnico" in c.lower())), None)
    valor_extra_col = next((c for c in df_custos.columns if isinstance(c, str) and "valor extra" in c.lower()), None)
    if valor_extra_col is None:
        valor_extra_col = next((c for c in df_custos.columns if isinstance(c, str) and "valor deslocamento" in c.lower()), None)
    valor_correto_col = next((c for c in df_custos.columns if isinstance(c, str) and "valor correto" in c.lower()), None)

    valor_extra_total = None
    if valor_extra_col:
        df_custos["VALOR_EXTRA_R$"] = safe_to_numeric(df_custos[valor_extra_col])
        valor_extra_total = df_custos["VALOR_EXTRA_R$"].sum()

    valor_correto_total = None
    if valor_correto_col:
        df_custos["VALOR_CORRETO_R$"] = safe_to_numeric(df_custos[valor_correto_col])
        valor_correto_total = df_custos["VALOR_CORRETO_R$"].sum()

    duplicidade_qtd = None
    duplicidade_total = None
    if data_col and cidade_os_col and rep_col and tec_col:
        df_custos["DATA_ANALISE"] = pd.to_datetime(df_custos[data_col], dayfirst=True, errors="coerce").dt.date
        group_keys = ["DATA_ANALISE", cidade_os_col, rep_col, tec_col]
        duplicadas = df_custos[df_custos.duplicated(subset=group_keys, keep=False)].copy()
        if not duplicadas.empty:
            duplicadas["EXCEDENTE"] = duplicadas.duplicated(subset=group_keys, keep="first")
            excedentes = duplicadas[duplicadas["EXCEDENTE"]]
            duplicidade_qtd = len(excedentes)
            if "VALOR_EXTRA_R$" in duplicadas.columns:
                duplicidade_total = excedentes["VALOR_EXTRA_R$"].sum()

    titulo = "**Resumo Geral — Base de Pagamento (Custos)**"
    arquivo = f"Arquivo: {nome_arquivo}" if nome_arquivo else None

    linhas = [titulo] + ([arquivo] if arquivo else []) + [""]

    if valor_extra_total is not None:
        linhas.append(f"- **Custo extra atual:** {_format_money(valor_extra_total)}")
    else:
        linhas.append("- **Custo extra atual:** coluna 'Valor Extra' não encontrada.")

    if valor_correto_total is not None:
        linhas.append(f"- **Custo extra correto (aprox.):** {_format_money(valor_correto_total)}")
    else:
        linhas.append("- **Custo extra correto:** não calculado (requer mapeamento/valor correto).")

    if duplicidade_qtd is not None:
        if duplicidade_total is not None:
            linhas.append(
                f"- **Duplicidades (excedentes):** {_format_int(duplicidade_qtd)} ordens | **Total:** {_format_money(duplicidade_total)}"
            )
        else:
            linhas.append(f"- **Duplicidades (excedentes):** {_format_int(duplicidade_qtd)} ordens")
    else:
        linhas.append("- **Duplicidades:** colunas necessárias não encontradas.")

    return "\n".join(linhas)


def gerar_resumo_cps(df, nome_arquivo=None):
    if df is None or df.empty:
        return "Resumo Geral — CPS\nNenhum dado válido encontrado no arquivo."

    total = len(df)
    status_col = next((c for c in df.columns if isinstance(c, str) and "status" in c.lower()), None)
    date_range = _infer_date_range(df)

    titulo = "**Resumo Geral — Relatório CPS**"
    arquivo = f"Arquivo: {nome_arquivo}" if nome_arquivo else None

    linhas = [titulo] + ([arquivo] if arquivo else []) + ["", f"- **Total de registros:** {_format_int(total)}"]

    if status_col:
        top_status = df[status_col].value_counts().head(3)
        for status, qtd in top_status.items():
            linhas.append(f"- **Status {status}:** {_format_int(qtd)}")

    if date_range:
        col, data_min, data_max = date_range
        linhas.append(f"- **Período ({col}):** {data_min:%d/%m/%Y} a {data_max:%d/%m/%Y}")

    return "\n".join(linhas)
