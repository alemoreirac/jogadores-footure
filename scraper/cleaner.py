import json
import os
import glob
from pathlib import Path

class JsonCleaner:
    """
    Uma classe para limpar campos desnecessários de arquivos JSON do SofaScore.
    """

    def __init__(self, keys_to_remove):
        """
        Inicializa o limpador com um conjunto de chaves a serem removidas.
        """
        if not isinstance(keys_to_remove, set):
            raise TypeError("keys_to_remove deve ser um conjunto (set).")
        self.keys_to_remove = keys_to_remove

    def clean_data(self, data):
        """
        Percorre recursivamente um objeto (dicionário ou lista) e remove as chaves especificadas.
        """
        if isinstance(data, dict):
            # Cria uma cópia das chaves para iterar, permitindo a modificação do dicionário original
            for key in list(data.keys()):
                if key in self.keys_to_remove:
                    del data[key]
                else:
                    # Continua a limpeza recursiva para o valor associado à chave
                    self.clean_data(data[key])
        elif isinstance(data, list):
            # Se for uma lista, aplica a limpeza a cada item da lista
            for item in data:
                self.clean_data(item)
        return data

    def process_directory(self, base_path, output_path):
        """
        Processa todos os arquivos .json em uma estrutura de diretórios,
        limpa-os e os salva em um novo diretório de saída.
        """
        print(f"Iniciando o processo no diretório base: {base_path}")
        print(f"Os arquivos limpos serão salvos em: {output_path}")

        # Itera pelas pastas de temporada de 2021 a 2025
        for year in range(2025, 2026):
            season_folder = f"brasileirao_{year}"
            search_path = os.path.join(base_path, season_folder)

            if not os.path.exists(search_path):
                print(f"Diretório da temporada não encontrado, pulando: {search_path}")
                continue

            # Usa glob para encontrar todos os arquivos .json recursivamente
            json_files = glob.glob(os.path.join(search_path, '**', '*.json'), recursive=True)

            if not json_files:
                print(f"Nenhum arquivo JSON encontrado para a temporada {year}")
                continue

            print(f"Encontrados {len(json_files)} arquivos para a temporada {year}.")

            for file_path in json_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        data = json.loads(content)

                    # Calcula os tokens antes da limpeza
                    tokens_before = len(content.split())
                    
                    # Limpa os dados
                    cleaned_data = self.clean_data(data)
                    
                    # Converte os dados limpos de volta para uma string JSON
                    cleaned_content = json.dumps(cleaned_data, indent=2)
                    
                    # Calcula os tokens após a limpeza
                    tokens_after = len(cleaned_content.split())

                    print(f"\nProcessando arquivo: {file_path}")
                    print(f"Tokens antes: {tokens_before} -> Tokens depois: {tokens_after}")

                    # Cria o caminho de saída preservando a estrutura de pastas
                    relative_path = os.path.relpath(file_path, base_path)
                    output_file_path = os.path.join(output_path, relative_path)
                    
                    # Garante que o diretório de destino exista
                    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
                    
                    # Salva o novo arquivo JSON
                    with open(output_file_path, 'w', encoding='utf-8') as f:
                        f.write(cleaned_content)
                    
                    print(f"Arquivo salvo em: {output_file_path}")

                except json.JSONDecodeError:
                    print(f"Erro ao decodificar JSON no arquivo: {file_path}")
                except Exception as e:
                    print(f"Ocorreu um erro ao processar o arquivo {file_path}: {e}")

        print("\nProcesso de limpeza concluído.")


if __name__ == '__main__':
    # Defina aqui o caminho base onde as pastas 'brasileirao_202x' estão localizadas
    # Exemplo: /Users/ale/Desktop/projetos/GitHub/Sofa Scraper/data
    base_data_path = '/Users/ale/Desktop/projetos/GitHub/Sofa Scraper/data'

    # Defina o nome da pasta de saída que será criada dentro do caminho base
    output_folder_name = 'data-output'
    output_data_path = os.path.join(base_data_path, output_folder_name)

    # Conjunto de chaves a serem removidas dos arquivos JSON.
    # Usar um 'set' é mais eficiente para verificações de pertinência.
    keys_to_remove = {
        "fieldTranslations",
        "nameTranslation",
        "shortNameTranslation",
        "ar",
        "alpha2",
        "alpha3",
        "slug"
    }

    # Instancia e executa o limpador
    cleaner = JsonCleaner(keys_to_remove)
    cleaner.process_directory(base_data_path, output_data_path)