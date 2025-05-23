#!/usr/bin/env python3
"""
PokeTibia Bot - Menu Principal
Sistema Otimizado com Priorização Diagonal
"""
import os
import sys
import time
import json
import subprocess
import re
from datetime import datetime
from typing import List, Dict

# Garantir que o diretório atual é o diretório do script
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Configurar sistema de logging ANTES de tudo
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'utils'))
from logging_utils import setup_file_logging, get_logger
setup_file_logging()  # Configura arquivo de log
logger = get_logger(__name__)
logger.info("="*60)
logger.info("PokeTibia Bot iniciado")
logger.info("="*60)

def clear_screen():
    """Limpa a tela do terminal."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """Exibe o cabeçalho do bot."""
    clear_screen()
    print("\n")
    print("=" * 60)
    print("                     POKETIBIA BOT")
    print("              Assistente Automatizado para PokeTibia")
    print("=" * 60)
    print("\n")

def print_menu():
    """Exibe o menu principal."""
    print_header()
    print("Menu Principal:\n")
    print("1. Iniciar Gravação de Caminho")
    print("2. Reproduzir Caminho Gravado")
    print("3. Ver Caminhos Gravados")
    print("4. Configuração de Coordenadas")
    print("5. Sair")
    print("\n")

def start_recording():
    """Inicia o módulo de gravação."""
    try:
        print_header()
        print("Iniciando Módulo de Gravação de Caminhos...\n")
        print("Teclas de atalho:")
        print("- F8: Iniciar/parar gravação")
        print("- F10: Ativar/desativar captura de mouse")
        print("- ESC: Sair do gravador")
        print("\nPressione ENTER para continuar ou Ctrl+C para voltar ao menu...")
        input()
        
        python_exe = sys.executable
        cmd = [python_exe, "utils/direct_recorder.py"]
        
        try:
            # Executar mostrando a saída em tempo real
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                     universal_newlines=True, bufsize=1)
            
            # Mostrar saída linha por linha
            for line in process.stdout:
                print(line, end='')
                
            process.wait()
            print("\n🔄 Gravação finalizada, retornando ao menu...")
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Gravação interrompida pelo usuário.")
            print("🔄 Retornando ao menu...")
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nGravação interrompida pelo usuário.")
    
    # Retorna automaticamente ao menu principal

def list_recorded_paths() -> List[str]:
    """Lista os caminhos gravados disponíveis."""
    paths = []
    
    # Verificar na pasta 'paths' primeiro
    paths_dir = "paths"
    if os.path.exists(paths_dir) and os.path.isdir(paths_dir):
        for file in os.listdir(paths_dir):
            if file.endswith(".json"):
                paths.append(os.path.join(paths_dir, file))
    
    # Verificar também no diretório atual para compatibilidade
    for file in os.listdir():
        if file.endswith(".json") and (file.startswith("path_") or not os.path.exists(os.path.join("paths", file))):
            full_path = os.path.abspath(file)
            if full_path not in [os.path.abspath(p) for p in paths]:
                paths.append(file)
    
    # Ordenar por data de modificação (mais recente primeiro)
    paths.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return paths

def play_path():
    """Reproduz um caminho gravado."""
    try:
        print_header()
        print("🎯 REPRODUÇÃO DE CAMINHOS")
        print("=" * 60)
        print()
        
        paths = list_recorded_paths()
        
        if not paths:
            print("Nenhum caminho gravado encontrado.")
            try:
                print("\n🔄 Retornando ao menu principal...")
                time.sleep(1)
            except (KeyboardInterrupt, EOFError):
                print()
            return
        
        print("Selecione um caminho para reproduzir:\n")
        
        for i, path_file in enumerate(paths, 1):
            print(f"{i}. {os.path.basename(path_file)}")
        
        print("\nDigite o número do caminho ou 0 para voltar: ", end="")
        try:
            choice = int(input().strip())
            if choice == 0 or choice > len(paths):
                return
                
            selected_path = paths[choice - 1]
            
            cmd = ["python", "utils/direct_player.py", selected_path]
            
            display_name = os.path.basename(selected_path)
            print(f"\n🎯 Iniciando reprodução de '{display_name}'...")
            print("Pressione ESC durante a execução para parar, ou Ctrl+C aqui para voltar ao menu.\n")
            time.sleep(1)
            
            # Use o Python da mesma instalação
            python_exe = sys.executable
            cmd[0] = python_exe
            try:
                # Executar mostrando a saída em tempo real
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                         universal_newlines=True, bufsize=1)
                
                # Mostrar saída linha por linha
                for line in process.stdout:
                    print(line, end='')
                    
                process.wait()
                print("\n🔄 Reprodução finalizada, retornando ao menu...")
                time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Reprodução interrompida pelo usuário.")
                print("🔄 Retornando ao menu...")
                time.sleep(1)
            
        except ValueError:
            print("\nOpção inválida!")
        
    except KeyboardInterrupt:
        print("\nSeleção interrompida pelo usuário.")
    
    try:
        print("\n🔄 Retornando ao menu principal...")
        time.sleep(1)
    except (KeyboardInterrupt, EOFError):
        print("\nRetornando ao menu principal...")
        time.sleep(0.5)

def rename_path_file(current_path: str):
    """Renomeia um arquivo de caminho."""
    try:
        current_name = os.path.basename(current_path)
        
        print(f"\nRenomear arquivo:")
        print(f"Nome atual: {current_name}")
        
        try:
            new_name = input("Novo nome (sem extensão): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperação cancelada.")
            return
        
        if not new_name:
            print("Nome não pode estar vazio!")
            return
        
        # Limpar nome (remover caracteres inválidos)
        new_name = re.sub(r'[<>:"/\\|?*]', '_', new_name)
        new_filename = f"{new_name}.json"
        
        # Determinar novo caminho completo
        current_dir = os.path.dirname(current_path)
        new_path = os.path.join(current_dir, new_filename)
        
        # Verificar se arquivo de destino já existe
        if os.path.exists(new_path):
            print(f"\nArquivo '{new_filename}' já existe!")
            try:
                overwrite = input("Deseja sobrescrever? (s/N): ").strip().lower()
                if not overwrite.startswith('s'):
                    print("Renomeação cancelada.")
                    return
            except (KeyboardInterrupt, EOFError):
                print("\nOperação cancelada.")
                return
        
        # Renomear arquivo
        try:
            os.rename(current_path, new_path)
            print(f"✅ Arquivo renomeado para: {new_filename}")
            time.sleep(1.5)
        except Exception as e:
            print(f"❌ Erro ao renomear arquivo: {e}")
            time.sleep(2)
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        time.sleep(2)

def display_paths():
    """Exibe informações detalhadas sobre os caminhos gravados."""
    try:
        print_header()
        print("Caminhos Gravados:\n")
        
        paths = list_recorded_paths()
        
        if not paths:
            print("Nenhum caminho gravado encontrado.")
        else:
            for i, path_file in enumerate(paths, 1):
                print(f"{i}. {os.path.basename(path_file)}")
                
                try:
                    with open(path_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    moves = len([a for a in data if a.get('type') == 'move'])
                    clicks = len([a for a in data if a.get('type') == 'click'])
                    waits = len([a for a in data if a.get('type') == 'wait'])
                    
                    file_size = round(os.path.getsize(path_file) / 1024, 2)
                    mod_time = datetime.fromtimestamp(os.path.getmtime(path_file))
                    
                    print(f"   - Tamanho: {file_size} KB")
                    print(f"   - Modificado: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"   - Ações: {len(data)} total ({moves} movimentos, {clicks} cliques, {waits} esperas)")
                    print()
                except Exception as e:
                    print(f"   (Erro ao ler: {e})")
                    print()
        
        # Opções de interação
        if paths:
            print("Digite 'R' + número para RENOMEAR (ex: R1) ou ENTER para voltar:")
            try:
                choice = input().strip()
                
                if choice.upper().startswith('R') and len(choice) > 1:
                    try:
                        file_num = int(choice[1:]) - 1
                        if 0 <= file_num < len(paths):
                            rename_path_file(paths[file_num])
                        else:
                            print("Número inválido!")
                            time.sleep(1)
                    except ValueError:
                        print("Formato inválido! Use 'R' + número (ex: R1)")
                        time.sleep(1)
                
            except (KeyboardInterrupt, EOFError):
                print("\nRetornando ao menu principal...")
        else:
            try:
                print("\n🔄 Retornando ao menu principal...")
                time.sleep(1)
            except (KeyboardInterrupt, EOFError):
                print("\nRetornando ao menu principal...")
                
    except KeyboardInterrupt:
        print("\nListagem interrompida. Retornando ao menu principal...")
        time.sleep(0.5)

def configure_coordinates():
    """Configuração de coordenadas."""
    try:
        print_header()
        print("Configuração de Coordenadas...\n")
        print("Iniciando configurador de coordenadas...")
        
        python_exe = sys.executable
        cmd = [python_exe, "coordinates/conversor_de_eixos.py"]
        
        try:
            # Executar mostrando a saída em tempo real
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                     universal_newlines=True, bufsize=1)
            
            # Mostrar saída linha por linha
            for line in process.stdout:
                print(line, end='')
                
            process.wait()
            print("\n🔄 Configuração finalizada, retornando ao menu...")
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Configuração interrompida pelo usuário.")
            print("🔄 Retornando ao menu...")
            time.sleep(1)
        except FileNotFoundError:
            print("❌ Arquivo de configuração não encontrado.")
            print("🔄 Retornando ao menu...")
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nConfiguração interrompida pelo usuário.")
    
    try:
        print("\n🔄 Retornando ao menu principal...")
        time.sleep(1)
    except (KeyboardInterrupt, EOFError):
        pass  # Silenciosamente voltar ao menu


def main():
    """Função principal do menu."""
    while True:
        try:
            print_menu()
            
            try:
                choice = input("Digite sua escolha (1-5): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nFinalizando o programa...")
                break
            
            if choice == '1':
                start_recording()
            elif choice == '2':
                play_path()
            elif choice == '3':
                display_paths()
            elif choice == '4':
                configure_coordinates()
            elif choice == '5':
                print_header()
                print("Obrigado por usar o PokeTibia Bot!\n")
                break
            else:
                print("\nOpção inválida! Pressione ENTER para continuar...")
                try:
                    input()
                except (KeyboardInterrupt, EOFError):
                    print("\n\nFinalizando o programa...")
                    break
        
        except KeyboardInterrupt:
            print("\n\nFinalizando o programa...")
            break
        except Exception as e:
            print(f"\nErro inesperado: {e}")
            print("Retornando ao menu principal...")
            time.sleep(2)
    
    # Cleanup final
    try:
        time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    sys.exit(0)

if __name__ == "__main__":
    main()