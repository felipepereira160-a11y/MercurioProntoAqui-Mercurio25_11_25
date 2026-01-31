# modules/roteirizacao.py

import pandas as pd

def carregar_planilhas(path_mapeamento, path_custos,
                       sheet_mapeamento='Mapeamento', sheet_custos='Custos'):
    """Carrega as planilhas em DataFrames."""
    df_map = pd.read_excel(path_mapeamento, sheet_name=sheet_mapeamento, dtype=str)
    df_cus = pd.read_excel(path_custos, sheet_name=sheet_custos, dtype=str)
    return df_map, df_cus

def verificar_colunas(df_map, df_cus,
                      col_rt_map='RT',
                      col_cidade_atend_map='Cidade Atendimento',
                      col_dist_atend_map='Distância Ida',
                      col_rt_cus='RT',
                      col_cidade_cus='Cidade',
                      col_abrang_cus='Abrangência',
                      col_valorkm_cus='Valor KM RT'):
    """Verifica se todas as colunas necessárias existem."""
    missing = []
    for df, cols, name in [
        (df_map, [col_rt_map, col_cidade_atend_map, col_dist_atend_map], 'Mapeamento'),
        (df_cus, [col_rt_cus, col_cidade_cus, col_abrang_cus, col_valorkm_cus], 'Custos')
    ]:
        for c in cols:
            if c not in df.columns:
                missing.append(f"{name}: falta coluna '{c}'")
    if missing:
        raise ValueError("Colunas obrigatórias ausentes:\n" + "\n".join(missing))

def tratar_tipo_distancia(df_map, col_dist='Distância Ida'):
    """Transforma coluna de distância em número (km), removendo ' km' e convertendo para float/int."""
    def parse_dist(x):
        try:
            if isinstance(x, str):
                return float(x.replace('km','').strip())
            return float(x)
        except:
            return None
    df_map[col_dist] = df_map[col_dist].apply(parse_dist)
    return df_map

def calcular_custo(df_map, df_cus,
                   col_rt_map='RT',
                   col_cidade_atend_map='Cidade Atendimento',
                   col_dist_atend_map='Distância Ida',
                   col_rt_cus='RT',
                   col_cidade_cus='Cidade',
                   col_abrang_cus='Abrangência',
                   col_valorkm_cus='Valor KM RT',
                   col_custo='Custo Calculado'):
    """Faz o merge e aplica a fórmula de custo."""
    # Trata tipos
    df_map = tratar_tipo_distancia(df_map, col_dist=col_dist_atend_map)
    df_cus[col_abrang_cus] = pd.to_numeric(df_cus[col_abrang_cus], errors='coerce')
    df_cus[col_valorkm_cus] = pd.to_numeric(df_cus[col_valorkm_cus], errors='coerce')

    # Merge usando RT + Cidade Atendimento = RT + Cidade (Custos)
    df_merge = pd.merge(
        df_map,
        df_cus,
        how='left',
        left_on=[col_rt_map, col_cidade_atend_map],
        right_on=[col_rt_cus, col_cidade_cus],
        suffixes=('_map', '_cus')
    )

    # Aviso registros sem correspondência
    sem_custo = df_merge[df_merge[col_valorkm_cus].isna()]
    if len(sem_custo) > 0:
        print("⚠️ Não foi possível encontrar custos para os seguintes registros:")
        print(sem_custo[[col_rt_map, col_cidade_atend_map]].drop_duplicates())

    # Aplica fórmula: (Distância * 2 – Abrangência) * Valor KM
    df_merge[col_custo] = (df_merge[col_dist_atend_map] * 2 - df_merge[col_abrang_cus]) * df_merge[col_valorkm_cus]

    # Valores negativos → zero
    df_merge[col_custo] = df_merge[col_custo].apply(lambda x: x if x > 0 else 0)

    return df_merge

def salvar_resultado(df, path_saida, sheet_name='Resultado'):
    """Salva o DataFrame resultante em Excel."""
    with pd.ExcelWriter(path_saida, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)

def executar(path_mapeamento, path_custos, path_saida,
            sheet_mapeamento='Mapeamento', sheet_custos='Custos'):
    """Fluxo completo."""
    df_map, df_cus = carregar_planilhas(path_mapeamento, path_custos,
                                         sheet_mapeamento, sheet_custos)
    verificar_colunas(df_map, df_cus)
    df_result = calcular_custo(df_map, df_cus)
    salvar_resultado(df_result, path_saida)
    print(f"✅ Arquivo de resultado salvo em: {path_saida}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Calcula custo de roteirização')
    parser.add_argument('--map', required=True, help='Caminho para planilha Mapeamento')
    parser.add_argument('--cus', required=True, help='Caminho para planilha Custos')
    parser.add_argument('--out', required=True, help='Caminho de saída Excel')
    args = parser.parse_args()
    executar(args.map, args.cus, args.out)
