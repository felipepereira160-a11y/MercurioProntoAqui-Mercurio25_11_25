
import pandas as pd
import glob
import os
from modules.processar_relatorio import processar_dataframe_posicao

try:
    # 1. Find the latest position report file
    list_of_files = glob.glob('*ultimaposicao*.xlsx')
    if not list_of_files:
        print("Nenhum arquivo de relatório de última posição encontrado.")
    else:
        latest_file = max(list_of_files, key=os.path.getctime)
        print(f"Analisando o arquivo: {latest_file}...")

        # 2. Load the file
        df_bruto = pd.read_excel(latest_file)
        total_equipamentos = len(df_bruto)

        # 3. Process the dataframe using the project's own logic
        df_processado = processar_dataframe_posicao(df_bruto)

        # 4. Perform the analysis
        if 'dias_sem_posicao' in df_processado.columns:
            # Garante que a coluna não tenha valores nulos para a comparação
            df_processado.dropna(subset=['dias_sem_posicao'], inplace=True)
            necessitam_manutencao = len(df_processado[df_processado['dias_sem_posicao'] >= 15])
            posicionando_hoje = len(df_processado[df_processado['dias_sem_posicao'] <= 1])
            
            # 5. Print the summary
            print("\n--- Resumo da Situação (Aba Posição) ---")
            print(f"Total de equipamentos analisados: {total_equipamentos}")
            print(f"Equipamentos que necessitam de manutenção (>= 15 dias sem comunicar): {necessitam_manutencao}")
            print(f"Equipamentos posicionando hoje (<= 1 dia): {posicionando_hoje}")
        else:
            print("A coluna 'dias_sem_posicao' não foi encontrada após o processamento.")

except Exception as e:
    print(f"Ocorreu um erro durante a análise: {e}")
