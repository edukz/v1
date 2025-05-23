import re
import sys
import json
import ctypes
import psutil
import os

# Adicionar diretório principal ao PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Constantes
PROCESS_ALL_ACCESS = 0x1F0FFF
CONFIG_FILE = "config/config.json"
GAME_PROCESS = "PokeAlliance_dx.exe"

def extract_address(addr_str):
    """
    Extrai o endereço hexadecimal de strings no formato do Cheat Engine como "P->010B249C".
    """
    # Remover espaços
    addr_str = addr_str.strip()
    
    # Procurar por padrão P->XXXXXXXX ou semelhante
    match = re.search(r'P->([0-9A-Fa-f]+)', addr_str)
    if match:
        hex_addr = match.group(1)
        # Adicionar prefixo 0x se não existir
        if not hex_addr.startswith('0x'):
            hex_addr = '0x' + hex_addr
        return hex_addr
    
    # Verificar se já é um endereço hex com 0x
    if addr_str.lower().startswith('0x'):
        return addr_str
    
    # Verificar se é um número hexadecimal sem 0x
    if all(c in '0123456789ABCDEFabcdef' for c in addr_str):
        return '0x' + addr_str
    
    # Não conseguiu extrair
    return None

def parse_address(addr_str):
    """
    Converte uma string de endereço para inteiro, suportando formatos hex e decimal.
    """
    addr_str = addr_str.strip()
    
    # Primeiro tentar extrair o formato do Cheat Engine
    extracted = extract_address(addr_str)
    if extracted:
        addr_str = extracted
    
    try:
        # Se começa com 0x, é hexadecimal
        if addr_str.lower().startswith("0x"):
            return int(addr_str, 16)
        # Se começa com qualquer outra coisa, tenta interpretar como decimal
        else:
            return int(addr_str)
    except ValueError:
        raise ValueError(f"Formato de endereço inválido: {addr_str}")

def update_poketibia_config():
    print(f"Atualizador de configuração para PokeTibia Bot")
    print(f"Detectando endereços para o processo: {GAME_PROCESS}")
    
    # Encontrar PID do jogo
    pid = None
    for proc in psutil.process_iter(['name', 'pid']):
        if proc.info['name'] == GAME_PROCESS:
            pid = proc.info['pid']
            break

    if not pid:
        print(f"ERRO: Jogo {GAME_PROCESS} não está rodando!")
        return False

    print(f"Jogo encontrado! PID: {pid}")
    
    # Abrir processo
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    
    if not handle:
        error_code = ctypes.get_last_error()
        print(f"ERRO: Não foi possível abrir o processo (Erro {error_code})")
        return False
    
    print("Processo aberto com sucesso!")
    
    # Carregar config atual
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            print(f"Arquivo de configuração carregado: {CONFIG_FILE}")
    except Exception as e:
        print(f"AVISO: Erro ao carregar {CONFIG_FILE}: {e}")
        print("Será criado um novo arquivo de configuração.")
        config = {"module_name": GAME_PROCESS}
    
    # Mostrar coordenadas atuais se existirem
    if "pointer_chains" in config:
        try:
            # Tentar ler as coordenadas atuais
            kernel32 = ctypes.windll.kernel32
            
            # Ler coordenada X
            x_value = ctypes.c_int32()
            x_read = ctypes.c_size_t()
            x_result = kernel32.ReadProcessMemory(
                handle, 
                ctypes.c_void_p(config["pointer_chains"]["x"]["base_offset"]), 
                ctypes.byref(x_value), 
                ctypes.sizeof(x_value), 
                ctypes.byref(x_read)
            )
            
            # Ler coordenada Y
            y_value = ctypes.c_int32()
            y_read = ctypes.c_size_t()
            y_result = kernel32.ReadProcessMemory(
                handle, 
                ctypes.c_void_p(config["pointer_chains"]["y"]["base_offset"]), 
                ctypes.byref(y_value), 
                ctypes.sizeof(y_value), 
                ctypes.byref(y_read)
            )
            
            # Ler coordenada Z
            z_value = ctypes.c_int32()
            z_read = ctypes.c_size_t()
            z_result = kernel32.ReadProcessMemory(
                handle, 
                ctypes.c_void_p(config["pointer_chains"]["z"]["base_offset"]), 
                ctypes.byref(z_value), 
                ctypes.sizeof(z_value), 
                ctypes.byref(z_read)
            )
            
            if x_result and y_result and z_result:
                x_coord = x_value.value
                y_coord = y_value.value
                z_coord = z_value.value
                
                print("\n" + "=" * 54)
                print("        COORDENADAS ATUAIS:")
                print("=" * 54)
                print(f"Eixo X: {x_coord}")
                print(f"Eixo Y: {y_coord}")
                print(f"Eixo Z: {z_coord}")
                print("=" * 54)
            else:
                print("\n" + "=" * 54)
                print("        COORDENADAS ATUAIS:")
                print("=" * 54)
                print("Falha ao ler coordenadas")
                print("(Endereços podem estar incorretos)")
                print("=" * 54)
        except Exception as e:
            print("\n" + "=" * 54)
            print("        COORDENADAS ATUAIS:")
            print("=" * 54)
            print("Erro ao ler coordenadas atuais")
            print("(Configuração pode estar incompleta)")
            print("=" * 54)
    else:
        print("\n" + "=" * 54)
        print("        COORDENADAS ATUAIS:")
        print("=" * 54)
        print("Nenhuma configuração de coordenadas encontrada")
        print("=" * 54)
    
    # Solicitar os endereços do Cheat Engine
    print("                 INSERÇÃO DE ENDEREÇOS")
    print("=" * 54)
    print("Por favor, cole os endereços diretamente do Cheat Engine")
    print("Formatos aceitos:")
    print("  - P->010B249C (formato exato do Cheat Engine)")
    print("  - 0x010B249C (formato hexadecimal)")
    print("  - 010B249C (hex sem prefixo)")
    print("  - 17507484 (decimal)")
    print("\nOpções de saída:")
    print("  - Digite 'menu' ou deixe em branco para voltar ao menu")
    print("  - Pressione Ctrl+C para cancelar")
    
    try:
        try:
            print()
            x_addr_str = input("Endereço para coordenada X (ou 'menu' para voltar): ").strip()
            
            # Verificar se quer voltar ao menu
            if not x_addr_str or x_addr_str.lower() == 'menu':
                print("Retornando ao menu principal...")
                kernel32.CloseHandle(handle)
                return True
            x_hex = extract_address(x_addr_str)
            x_addr = parse_address(x_addr_str)
            
            y_addr_str = input("Endereço para coordenada Y (ou 'menu' para voltar): ").strip()
            
            # Verificar se quer voltar ao menu
            if not y_addr_str or y_addr_str.lower() == 'menu':
                print("Retornando ao menu principal...")
                kernel32.CloseHandle(handle)
                return True
                
            y_hex = extract_address(y_addr_str)
            y_addr = parse_address(y_addr_str)
            
            z_addr_str = input("Endereço para coordenada Z (ou 'menu' para voltar): ").strip()
            
            # Verificar se quer voltar ao menu
            if not z_addr_str or z_addr_str.lower() == 'menu':
                print("Retornando ao menu principal...")
                kernel32.CloseHandle(handle)
                return True
            z_hex = extract_address(z_addr_str)
            z_addr = parse_address(z_addr_str)
        except (KeyboardInterrupt, EOFError):
            print("\nOperação cancelada pelo usuário.")
            kernel32.CloseHandle(handle)
            return False
        
    except ValueError as e:
        print(f"ERRO: {e}")
        kernel32.CloseHandle(handle)
        return False
    
    print(f"\nEndereços extraídos e convertidos:")
    print(f"X: {x_hex} ({x_addr})")
    print(f"Y: {y_hex} ({y_addr})")
    print(f"Z: {z_hex} ({z_addr})")
    
    # Testar leitura dos endereços
    print("\nTestando leitura dos endereços...")
    
    success = True
    coords = {}
    
    for name, addr, hex_str in [("X", x_addr, x_hex), ("Y", y_addr, y_hex), ("Z", z_addr, z_hex)]:
        value = ctypes.c_int32()
        read = ctypes.c_size_t()
        
        result = kernel32.ReadProcessMemory(
            handle, 
            ctypes.c_void_p(addr), 
            ctypes.byref(value), 
            ctypes.sizeof(value), 
            ctypes.byref(read)
        )
        
        if result:
            print(f"Coordenada {name} ({hex_str}): {value.value}")
            coords[name.lower()] = value.value
        else:
            error_code = ctypes.get_last_error()
            print(f"ERRO ao ler coordenada {name}: Erro {error_code}")
            success = False
    
    if not success:
        print("\nATENÇÃO: Alguns endereços não puderam ser lidos!")
        try:
            proceed = input("Deseja continuar mesmo assim? (S/N): ").strip().upper()
            if proceed != 'S':
                kernel32.CloseHandle(handle)
                return False
        except (KeyboardInterrupt, EOFError):
            print("\nOperação cancelada pelo usuário.")
            kernel32.CloseHandle(handle)
            return False
    
    # Atualizar configuração
    config["pointer_chains"] = {
        "x": {
            "base_offset": x_addr,
            "offsets": []
        },
        "y": {
            "base_offset": y_addr,
            "offsets": []
        },
        "z": {
            "base_offset": z_addr,
            "offsets": []
        }
    }
    
    # Fazer backup da configuração anterior
    if "config.json.bak" not in sys.argv[0]:  # Evitar sobrescrever o script
        backup_file = f"{CONFIG_FILE}.bak"
        try:
            with open(backup_file, 'w') as f:
                json.dump(config, f, indent=2)
                print(f"Backup criado: {backup_file}")
        except Exception as e:
            print(f"AVISO: Não foi possível criar backup: {e}")
    
    # Salvar nova configuração
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
            print(f"\nConfiguração atualizada com sucesso em {CONFIG_FILE}!")
    except Exception as e:
        print(f"ERRO ao salvar configuração: {e}")
        kernel32.CloseHandle(handle)
        return False
    
    # Fechar handle
    kernel32.CloseHandle(handle)
    
    print("\n===== INSTRUÇÕES =====")
    print("1. A configuração foi atualizada para usar os endereços diretos")
    print("2. Execute seu bot com o script direct_recorder.py")
    print("3. Se o jogo atualizar novamente, execute este script para atualizar os endereços")
    
    return True

if __name__ == "__main__":
    try:
        if update_poketibia_config():
            print("\nTudo pronto! Seu bot deve funcionar agora.")
        else:
            print("\nOcorreram erros durante a atualização da configuração.")
        
        try:
            input("\nPressione ENTER para sair (ou Ctrl+C)...")
        except (KeyboardInterrupt, EOFError):
            print("\nFinalizando...")
    except KeyboardInterrupt:
        print("\nOperação interrompida pelo usuário.")
        sys.exit(0)
    except EOFError:
        print("\nOperação interrompida pelo usuário (EOF).")
        sys.exit(0)
    except Exception as e:
        print(f"\nERRO inesperado: {e}")
        try:
            input("\nPressione ENTER para sair (ou Ctrl+C)...")
        except (KeyboardInterrupt, EOFError):
            print("\nFinalizando...")