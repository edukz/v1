"""
Módulo de gravação de caminhos no jogo - Versão refatorada e aprimorada.
Registra a sequência de posições do personagem e cliques de mouse para uso posterior.
"""
import json
import time
import threading
import keyboard
import os
import sys
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set, Any, Union

# Adicionar diretório principal ao PYTHONPATH
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

# Adicionar todos os caminhos necessários
sys.path.insert(0, os.path.join(project_root, 'config'))
sys.path.insert(0, os.path.join(project_root, 'utils'))
sys.path.insert(0, os.path.join(project_root, 'memory'))
sys.path.insert(0, os.path.join(project_root, 'movement'))

# Importar módulos necessários
from config_utils import get_config
from logging_utils import get_logger
from memory_manager import get_memory_manager
from movement_utils_simple import get_coordinates_from_memory

# Definir novos tipos de evento
ACTION_MOVE = "move"
ACTION_CLICK = "click"

# Configurar hotkeys para simular cliques do mouse
# Como mouse.on_click() não está funcionando corretamente, usamos essa abordagem alternativa
LEFT_CLICK_KEY = "ctrl+alt+1"   # Combinação para simular clique esquerdo
RIGHT_CLICK_KEY = "ctrl+alt+2"  # Combinação para simular clique direito
MIDDLE_CLICK_KEY = "ctrl+alt+3" # Combinação para simular clique do meio

class PathRecorder:
    """
    Grava o caminho percorrido pelo personagem no jogo e eventos de mouse.
    Implementação refatorada e aprimorada para suportar múltiplos tipos de eventos.
    """
    def __init__(self, config_path: str = "config/config.json"):
        """
        Inicializa o gravador de caminho.
        
        Args:
            config_path: Caminho para o arquivo de configuração
        """
        # Configuração e logging
        self.config = get_config(config_path)
        self.logger = get_logger(__name__)
        
        # Conectar ao processo
        self.memory = get_memory_manager(self.config.get_module_name(), simple=True)
        self.logger.info(f"Conectado ao processo {self.config.get_module_name()}")
        
        # Obter endereços diretos
        pointer_chains = self.config.get_pointer_chains()
        self.addr_x = pointer_chains['x']['base_offset']
        self.addr_y = pointer_chains['y']['base_offset']
        self.addr_z = pointer_chains['z']['base_offset']
        
        self.logger.info(f"Usando endereços: X={hex(self.addr_x)}, Y={hex(self.addr_y)}, Z={hex(self.addr_z)}")
        
        # Estado da gravação
        self.recording = False
        self.path = []
        self.last_pos = None
        self.exit_flag = False
        self.visited = set()
        
        # Novo: Estado para gravação de mouse
        self.record_mouse = self.config.get("record_mouse", True)
        self.mouse_listener_active = False
        self.min_mouse_interval = self.config.get("min_mouse_interval", 0.3)  # Mínimo intervalo entre cliques em segundos
        self.last_mouse_time = 0
        
        # Intervalo de gravação
        self.record_interval = self.config.get("record_interval", 0.1)
    
    def start(self):
        """
        Inicia o gravador em uma thread separada e configura hotkeys.
        """
        # Iniciar thread de monitoramento
        threading.Thread(target=self._reader_loop, daemon=True).start()
        
        # Configurar teclas de atalho
        start_stop_key = self.config.get_hotkey('start_stop', 'F8')
        toggle_mouse_key = self.config.get_hotkey('toggle_mouse', 'F10')  # Nova hotkey
        keyboard.add_hotkey(start_stop_key, self.toggle)
        keyboard.add_hotkey(toggle_mouse_key, self.toggle_mouse_recording)
        keyboard.add_hotkey('esc', self.stop)
        
        # Mensagem informativa atualizada para incluir mouse
        self.logger.info(f"Pressione {start_stop_key} para iniciar/parar gravação, "
                        f"{toggle_mouse_key} para ativar/desativar gravação de mouse, "
                        f"ESC para sair.")
        
        # Loop principal
        try:
            while not self.exit_flag:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.logger.info("Interrupção recebida, finalizando...")
            self.stop()
        finally:
            self._cleanup()

    def toggle(self):
        """
        Alterna entre iniciar e parar a gravação do caminho.
        """
        if not self.recording:
            # Iniciar gravação
            self.path.clear()
            self.last_pos = None
            self.visited.clear()
            self.recording = True
            
            # Iniciar monitoramento de mouse se ativado
            if self.record_mouse:
                self._start_mouse_monitoring()
                self.logger.info("Gravação iniciada (com captura de mouse).")
                print("\n[GRAVAÇÃO INICIADA] Movimentos e cliques de mouse serão registrados!\n")
                print("Pressione F8 para parar a gravação quando terminar.")
            else:
                self.logger.info("Gravação iniciada (sem captura de mouse).")
                print("\n[GRAVAÇÃO INICIADA] Apenas movimentos serão registrados!\n")
                print("Pressione F8 para parar a gravação quando terminar.")
        else:
            # Parar gravação
            self.recording = False
            
            # Parar monitoramento de mouse
            self._stop_mouse_monitoring()
            
            # Salvar caminho
            filename = self._save_path()
            moves = sum(1 for item in self.path if item.get('type') == ACTION_MOVE)
            clicks = sum(1 for item in self.path if item.get('type') == ACTION_CLICK)
            
            print(f"\n[GRAVAÇÃO FINALIZADA] {len(self.path)} ações gravadas:")
            print(f"- {moves} movimentos")
            print(f"- {clicks} cliques")
            print(f"- {len(self.visited)} SQMs únicos visitados")
            if filename:
                print(f"Caminho salvo em: {filename}")
            print()
            
            self.logger.info(f"Gravação finalizada. {len(self.path)} ações no total: "
                           f"{moves} movimentos, {clicks} cliques, {len(self.visited)} SQMs únicos.")

    def toggle_mouse_recording(self):
        """
        Alterna entre ativar e desativar a gravação de eventos de mouse.
        """
        self.record_mouse = not self.record_mouse
        
        if self.recording:
            if self.record_mouse:
                self._start_mouse_monitoring()
                self.logger.info("Gravação de mouse ATIVADA.")
                print("\n[ATENÇÃO] Gravação de mouse ATIVADA.")
                print("Use Ctrl+Alt+1 (botão esquerdo), Ctrl+Alt+2 (botão direito) ou Ctrl+Alt+3 (botão meio)")
            else:
                self._stop_mouse_monitoring()
                self.logger.info("Gravação de mouse DESATIVADA.")
                print("\n[ATENÇÃO] Gravação de mouse DESATIVADA. Apenas movimentos serão registrados.")
        else:
            msg = "ATIVADA" if self.record_mouse else "DESATIVADA"
            self.logger.info(f"Gravação de mouse {msg} (será aplicada quando a gravação iniciar).")
            print(f"\n[CONFIGURAÇÃO] Gravação de mouse {msg}.")
            print("Esta configuração será aplicada quando você iniciar a gravação.")
            
        # Atualizar configuração
        self.config.set("record_mouse", self.record_mouse)
        self.config.save_config()

    def stop(self):
        """
        Para a gravação e finaliza o programa.
        """
        if self.recording:
            self.toggle()  # Para a gravação se estiver em andamento
        self.exit_flag = True
        self.logger.info("Finalizando programa.")

    def _cleanup(self):
        """
        Libera recursos ao finalizar o programa.
        """
        # Remover hotkeys
        try:
            keyboard.unhook_all()
        except Exception as e:
            self.logger.warning(f"Erro ao remover hotkeys: {e}")
            
        # Parar monitoramento de mouse
        self._stop_mouse_monitoring()
            
        # Fechar conexão com o processo
        if hasattr(self, 'memory'):
            self.memory.cleanup()
            
        # Cleanup concluído

    def _save_path(self):
        """
        Salva o caminho gravado em um arquivo JSON na pasta 'paths'.
        
        Returns:
            str: Nome do arquivo salvo, ou None se falhou
        """
        if not self.path:
            self.logger.warning("Nenhum ponto gravado para salvar.")
            return None
            
        # Garantir que a pasta 'paths' existe
        paths_dir = "paths"
        if not os.path.exists(paths_dir):
            try:
                os.makedirs(paths_dir)
                self.logger.info(f"Pasta '{paths_dir}' criada para armazenar caminhos")
            except Exception as e:
                self.logger.error(f"Erro ao criar pasta '{paths_dir}': {e}")
                # Continuar e tentar salvar no diretório atual como fallback
        
        # Perguntar pelo nome personalizado
        print("\n" + "="*60)
        print("SALVAR CAMINHO GRAVADO")
        print("="*60)
        print("Pressione ENTER para nome automático ou digite um nome personalizado:")
        
        try:
            custom_name = input("Nome do arquivo (sem extensão): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperação cancelada.")
            return None
        
        # Gerar nome do arquivo
        if custom_name:
            # Limpar nome personalizado (remover caracteres inválidos)
            custom_name = re.sub(r'[<>:"/\\|?*]', '_', custom_name)
            filename = f"{custom_name}.json"
        else:
            # Nome automático com timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            filename = f"path_{timestamp}.json"
        
        filepath = os.path.join(paths_dir, filename)
        
        # Verificar se arquivo já existe
        if os.path.exists(filepath):
            print(f"\nArquivo '{filename}' já existe!")
            try:
                overwrite = input("Deseja sobrescrever? (s/N): ").strip().lower()
                if not overwrite.startswith('s'):
                    print("Salvamento cancelado.")
                    return None
            except (KeyboardInterrupt, EOFError):
                print("\nOperação cancelada.")
                return None
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.path, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Caminho salvo em {filepath}")
            print(f"[OK] Caminho salvo como: {filename}")
            return filepath
        except Exception as e:
            self.logger.error(f"Erro ao salvar caminho: {e}")
            print(f"[ERRO] Falha ao salvar em paths/: {e}")
            return None

    def _start_mouse_monitoring(self):
        """
        Inicia o monitoramento de eventos de mouse usando teclas do teclado.
        """
        if not self.mouse_listener_active:
            try:
                # Configurar hotkeys para simular cliques
                keyboard.add_hotkey(LEFT_CLICK_KEY, lambda: self._simulate_mouse_click("left"))
                keyboard.add_hotkey(RIGHT_CLICK_KEY, lambda: self._simulate_mouse_click("right"))
                keyboard.add_hotkey(MIDDLE_CLICK_KEY, lambda: self._simulate_mouse_click("middle"))
                
                self.mouse_listener_active = True
                self.logger.debug("Monitoramento de mouse iniciado via hotkeys.")
                
                # Mostrar instruções
                print("\nComo usar cliques de mouse:")
                print(f"  {LEFT_CLICK_KEY} - Registrar clique esquerdo")
                print(f"  {RIGHT_CLICK_KEY} - Registrar clique direito")
                print(f"  {MIDDLE_CLICK_KEY} - Registrar clique do meio")
                print("Posicione o cursor onde deseja registrar o clique e pressione a combinação correspondente.")
                
            except Exception as e:
                self.logger.error(f"Erro ao iniciar monitoramento de mouse: {e}")
                self.mouse_listener_active = False

    def _stop_mouse_monitoring(self):
        """
        Para o monitoramento de eventos de mouse.
        """
        if self.mouse_listener_active:
            try:
                # Remover hotkeys específicas para mouse
                keyboard.remove_hotkey(LEFT_CLICK_KEY)
                keyboard.remove_hotkey(RIGHT_CLICK_KEY)
                keyboard.remove_hotkey(MIDDLE_CLICK_KEY)
            except Exception as e:
                self.logger.warning(f"Erro ao remover hotkeys de mouse: {e}")
            
            self.mouse_listener_active = False
            self.logger.debug("Monitoramento de mouse finalizado.")

    def _simulate_mouse_click(self, button: str):
        """
        Simula um clique de mouse usando a posição atual do cursor.
        
        Args:
            button: Tipo de botão ('left', 'right', 'middle')
        """
        if not self.recording or not self.record_mouse:
            return
            
        try:
            # Obter a posição atual do cursor
            import pyautogui
            x, y = pyautogui.position()
            
            # Registrar o clique
            self._on_mouse_click(x, y, button)
        except Exception as e:
            self.logger.error(f"Erro ao simular clique de mouse: {e}")
            # Fallback para coordenadas fixas se pyautogui falhar
            self._on_mouse_click(100, 100, button)

    def _on_mouse_click(self, x: int, y: int, button: str):
        """
        Processa um evento de clique do mouse e o adiciona ao caminho.
        
        Args:
            x: Coordenada X do cursor
            y: Coordenada Y do cursor
            button: Botão pressionado ('left', 'right', 'middle')
        """
        # Verificar intervalo mínimo entre cliques para evitar duplicação
        current_time = time.time()
        if current_time - self.last_mouse_time < self.min_mouse_interval:
            return
            
        self.last_mouse_time = current_time
        
        # Criar entrada para o caminho
        click_entry = {
            'type': ACTION_CLICK,
            'screen_x': x,
            'screen_y': y,
            'button': button,
            'timestamp': datetime.now().isoformat()
        }
        
        # Adicionar ao caminho e registrar
        self.path.append(click_entry)
        # Feedback visual para o usuário
        print(f"\n[GRAVANDO] Clique {button} em ({x}, {y}) | Total: {len(self.path)} ações")
        self.logger.info(f"Gravado clique: {button} em ({x}, {y})")

    def _reader_loop(self):
        """
        Loop principal que monitora a posição do personagem.
        Usa get_coordinates_from_memory para obter posição atual
        para ler coordenadas sem aplicar o mapeamento de eixos.
        Agora adiciona tipo de ação 'move' para diferenciar de cliques.
        """
        while not self.exit_flag:
            try:
                if self.recording:
                    # Ler coordenadas usando a função centralizada
                    try:
                        # Obter coordenadas da memória
                        position = get_coordinates_from_memory(self.memory, self.config.config_path)
                        
                        # Extrair valores
                        x = position['x']
                        y = position['y']
                        z = position.get('z')  # Pode ser None se include_z for False
                        
                        # Se temos coordenadas válidas e a posição mudou
                        include_z = self.config.get("include_z", True)
                        pos_tuple = (x, y, z) if include_z else (x, y, None)
                        pos_xy = (x, y)  # para o set de visitados
                        
                        if pos_tuple != self.last_pos:
                            # Criar entrada para o caminho
                            # Formato atualizado com tipo "move"
                            entry = {'type': ACTION_MOVE, 'x': x, 'y': y}
                            if include_z and z is not None:
                                entry['z'] = z
                                
                            # Adicionar ao caminho e registrar
                            self.path.append(entry)
                            self.visited.add(pos_xy)
                            self.last_pos = pos_tuple
                            
                            # Feedback visual para o usuário
                            print(f"\r[GRAVANDO] Posição: x={x}, y={y}" + (f", z={z}" if z is not None else "") + f" | Total: {len(self.path)} ações", end="")
                            
                            self.logger.info(f"Gravado movimento: {entry} (Total: {len(self.path)})")
                    except Exception as e:
                        self.logger.error(f"Erro ao ler posição: {e}")
            except Exception as e:
                self.logger.error(f"Erro no loop de leitura: {e}")
                
            # Aguardar próxima leitura
            time.sleep(self.record_interval)


def main():
    """Função principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Gravador de caminhos refatorado para PokeTibia")
    parser.add_argument('-c', '--config', default='config/config.json', help="Arquivo de configuração")
    parser.add_argument('-d', '--debug', action='store_true', help="Ativar modo de debug")
    parser.add_argument('--no-mouse', action='store_true', help="Desativar gravação de mouse")
    args = parser.parse_args()
    
    try:
        # Ajustar configuração de debug se solicitado
        if args.debug:
            config = get_config(args.config)
            config.set("debug", True)
            config.save_config()
            
        # Ajustar configuração de mouse se solicitado
        if args.no_mouse:
            config = get_config(args.config)
            config.set("record_mouse", False)
            config.save_config()
        
        # Iniciar gravador
        recorder = PathRecorder(args.config)
        recorder.start()
    except Exception as e:
        logger = get_logger(__name__)
        logger.critical(f"Erro fatal: {e}", exc_info=True)
        return 1
        
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())