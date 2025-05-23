"""
Sistema V4: Reprodução Simples e Delegada
==========================================
Sistema focado APENAS em reprodução de caminhos.
TODAS as decisões de navegação são delegadas ao MovementManager.
Mantém simplicidade máxima e responsabilidade única.
"""
import json
import time
import threading
import keyboard
import mouse
import os
import sys
import glob
from datetime import datetime
from typing import Dict, List, Any

# Adicionar diretório principal ao PYTHONPATH
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

# Adicionar todos os caminhos necessários
sys.path.insert(0, os.path.join(project_root, 'config'))
sys.path.insert(0, os.path.join(project_root, 'utils'))
sys.path.insert(0, os.path.join(project_root, 'memory'))
sys.path.insert(0, os.path.join(project_root, 'movement'))

# Importar módulos utilitários centralizados
from config_utils import get_config
from logging_utils import get_logger
from memory_manager import get_memory_manager
from movement_utils_simple import SimpleMovementManager as MovementManager, get_coordinates_from_memory

# Definir tipos de ação (correspondendo aos do recorder)
ACTION_MOVE = "move"
ACTION_CLICK = "click"
ACTION_WAIT = "wait"

class PathPlayer:
    """
    Reproduz um caminho gravado, movendo o personagem automaticamente.
    Responsabilidade ÚNICA: reproduzir sequência de ações.
    TODAS as decisões de navegação são delegadas ao MovementManager.
    """
    def __init__(self, config_path: str = "config/config.json", path_data: List[Dict[str, Any]] = None, path_file: str = None):
        """
        Inicializa o reprodutor de caminho.
        
        Args:
            config_path: Caminho para o arquivo de configuração
            path_data: Lista de ações do caminho a seguir
            path_file: Caminho para o arquivo de origem (para referência)
        """
        self._stopped = False
        self._shutting_down = False

        # Configuração e logging
        self.config = get_config(config_path)
        self.logger = get_logger(__name__)
        
        # Sistema V4: Identificação
        self.logger.info("🎯 Sistema V4: Reprodução Simples e Delegada ativado")
        
        # Caminho a seguir
        self.path = path_data if path_data else []
        
        # Armazenar o arquivo de origem para referência
        self.path_file = path_file
        
        # Verificar se o caminho tem informações de tipo
        # Compatibilidade com caminhos antigos (somente movimentos)
        self._check_and_convert_path()
        
        # Inicializar gerenciador de memória
        self.mem = get_memory_manager(self.config.get_module_name(), simple=True)
        self.logger.info(f"Conectado ao processo {self.config.get_module_name()}")
        
        # Inicializar gerenciador de movimento
        # Versão simplificada não precisa de use_axis_mapping
        self.movement = MovementManager(self.mem, config_path)
        
        # Configurações de mouse
        self.mouse_click_delay = self.config.get("mouse_click_delay", 0.2)
        
        # Sistema de Pausa/Retomada
        self.paused = False
        self.pause_event = threading.Event()
        self.pause_event.set()  # Inicialmente não pausado
        self.pause_key = self.config.get_hotkey('pause_resume', 'F9')
        
        # Configurações de playback
        self.normal_playback_delay = self.config.get("playback_delay", 0.2)
        
    def _check_and_convert_path(self):
        """
        Verifica se o caminho está no formato novo (com tipos de ação)
        e converte se necessário para compatibilidade.
        """
        if not self.path:
            return
            
        # Verificar se já tem informações de tipo
        has_types = all('type' in action for action in self.path)
        
        # Se não tiver, converter para formato com tipo "move"
        if not has_types:
            self.logger.info("Convertendo caminho antigo para novo formato (adicionando tipos de ação)")
            converted_path = []
            
            for point in self.path:
                action = {'type': ACTION_MOVE}
                action.update(point)  # Copiar x, y, z
                converted_path.append(action)
                
            self.path = converted_path
            self.logger.info(f"Conversão concluída: {len(self.path)} ações de movimento")
        
    def start(self) -> None:
        """
        Inicia a reprodução do caminho.
        Segue cada ponto sequencialmente, delegando TODAS as decisões ao MovementManager.
        """
        if not self.path or len(self.path) < 1:
            self.logger.warning("Caminho vazio ou com apenas um ponto. Nada a fazer.")
            return
            
        # Contar tipos de ações para log
        moves = sum(1 for item in self.path if item.get('type') == ACTION_MOVE)
        clicks = sum(1 for item in self.path if item.get('type') == ACTION_CLICK)
        waits = sum(1 for item in self.path if item.get('type') == ACTION_WAIT)
        
        # Inicializar o índice de ação atual (pode ser atualizado se carregar um estado salvo)
        if not hasattr(self, 'current_action_index'):
            self.current_action_index = 0
        
        # Verificar se tem um estado salvo para carregar
        last_state = self._find_most_recent_state_file()
        try:
            if last_state:
                # Perguntar se quer carregar o estado salvo
                self.logger.info(f"Estado salvo encontrado: {last_state}")
                print(f"Estado salvo encontrado: {os.path.basename(last_state)}")
                print("Pressione 'S' para carregar este estado ou qualquer outra tecla para iniciar do zero.")
                
                # Esperar input por 5 segundos
                start_time = time.time()
                load_state = False
                
                while time.time() - start_time < 5:
                    if keyboard.is_pressed('s'):
                        load_state = True
                        break
                    time.sleep(0.1)
                
                if load_state:
                    self._load_state_from_file(last_state)
                    self.logger.info(f"Continuando do estado salvo, índice {self.current_action_index}")
                else:
                    self.logger.info("Iniciando novo percurso do zero.")
        except Exception as e:
            self.logger.error(f"Erro ao verificar estados salvos: {e}")
        
        # Resumo detalhado do caminho
        self.logger.info("="*60)
        self.logger.info("RESUMO DO CAMINHO")
        self.logger.info("="*60)
        self.logger.info(f"Arquivo: {self.path_file if self.path_file else 'Não especificado'}")
        self.logger.info(f"Total de ações: {len(self.path)}")
        self.logger.info(f"  - Movimentos: {moves}")
        self.logger.info(f"  - Cliques: {clicks}")
        self.logger.info(f"  - Esperas: {waits}")
        
        # Mostrar primeiros e últimos pontos se houver movimentos
        if moves > 0:
            first_move = next((a for a in self.path if a.get('type') == ACTION_MOVE), None)
            last_move = next((a for a in reversed(self.path) if a.get('type') == ACTION_MOVE), None)
            if first_move and last_move:
                self.logger.info(f"Primeiro ponto: ({first_move['x']}, {first_move['y']})")
                self.logger.info(f"Último ponto: ({last_move['x']}, {last_move['y']})")
                
            # Verificar se o caminho tem movimentos de 1 SQM
            self.logger.info("")
            self.logger.info("Verificando integridade do caminho...")
            large_jumps = 0
            move_actions = [a for a in self.path if a.get('type') == ACTION_MOVE]
            
            for i in range(1, len(move_actions)):
                prev = move_actions[i-1]
                curr = move_actions[i]
                dist = abs(curr['x'] - prev['x']) + abs(curr['y'] - prev['y'])
                if dist > 1:
                    large_jumps += 1
                    if large_jumps <= 3:  # Mostrar apenas os primeiros 3
                        self.logger.warning(f"  Salto de {dist} SQMs: ({prev['x']}, {prev['y']}) → ({curr['x']}, {curr['y']})")
            
            if large_jumps > 0:
                self.logger.warning(f"⚠️ ATENÇÃO: Caminho contém {large_jumps} saltos maiores que 1 SQM!")
                self.logger.warning("   Isso pode causar imprecisão na reprodução.")
            else:
                self.logger.info("✅ Caminho OK: todos os movimentos são de 1 SQM")
        
        self.logger.info("="*60)
        
        # Atualizar a posição atual
        try:
            # Obter coordenadas do personagem
            self.current_pos = get_coordinates_from_memory(self.mem, self.config.config_path)
            self.logger.info(f"Posição atual do personagem: ({self.current_pos['x']}, {self.current_pos['y']})")
        except Exception as e:
            self.logger.error(f"Falha ao ler posição inicial: {e}")
            self._shutdown()
            return
            
        # Configurar hotkey para parar
        keyboard.add_hotkey('esc', self.stop)
        self.logger.info("Pressione ESC para cancelar a reprodução.")
        
        # Configurar hotkey para pausar/retomar
        keyboard.add_hotkey(self.pause_key, self.toggle_pause)
        self.logger.info(f"Pressione {self.pause_key} para pausar/retomar a execução.")
        
        # Loop principal de reprodução
        self._execute_path()
            
        # Finalização
        self._shutdown()
        
    def toggle_pause(self) -> None:
        """
        Alterna entre pausar e retomar a execução do bot.
        """
        if self.paused:
            # Retomar execução
            self.paused = False
            self.pause_event.set()  # Liberar threads que estão aguardando
            self.logger.info("Bot retomado. Continuando execução...")
        else:
            # Pausar execução
            self.paused = True
            self.pause_event.clear()  # Sinaliza para threads aguardarem
            
            # Salvar o estado atual
            self._save_state_to_file()
            self.logger.info(f"Bot pausado. Estado salvo. Pressione {self.pause_key} novamente para retomar.")
            
    def _save_state_to_file(self) -> None:
        """
        Salva o estado atual do bot para um arquivo JSON na pasta 'saved_states'.
        """
        try:
            # Criar pasta para estados se não existir
            state_dir = "saved_states"
            if not os.path.exists(state_dir):
                try:
                    os.makedirs(state_dir)
                    self.logger.info(f"Pasta '{state_dir}' criada para armazenar estados")
                except Exception as e:
                    self.logger.error(f"Erro ao criar pasta '{state_dir}': {e}")
                    # Usar diretório atual como fallback
                    state_dir = "."
            
            # Gerar nome de arquivo com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(state_dir, f"state_{timestamp}.json")
            
            # Coletar estado atual
            current_state = {
                "timestamp": timestamp,
                "current_position": self.current_pos,
                "current_index": self.current_action_index if hasattr(self, 'current_action_index') else 0,
                "path_length": len(self.path),
                "config_path": self.config.config_path,
                "path_file": self.path_file
            }
            
            # Salvar estado para arquivo
            with open(filepath, 'w') as f:
                json.dump(current_state, f, indent=2)
                
            # Armazenar caminho do arquivo para referência
            self.saved_state_path = filepath
            
            self.logger.info(f"Estado salvo em {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar estado: {e}")
            return None
    
    def _load_state_from_file(self, filepath: str = None) -> bool:
        """
        Carrega o estado do bot de um arquivo JSON.
        
        Args:
            filepath: Caminho para o arquivo de estado. Se None, usa o último salvo.
            
        Returns:
            True se conseguiu carregar o estado, False caso contrário
        """
        try:
            # Se não foi especificado, usar o último estado salvo
            if not filepath and hasattr(self, 'saved_state_path'):
                filepath = self.saved_state_path
                
            # Se ainda não foi definido, procurar na pasta de estados
            if not filepath:
                filepath = self._find_most_recent_state_file()
                if filepath:
                    self.logger.info(f"Usando estado mais recente: {filepath}")
            
            if not filepath or not os.path.exists(filepath):
                self.logger.warning("Arquivo de estado não encontrado!")
                return False
                
            # Carregar estado do arquivo
            with open(filepath, 'r') as f:
                state = json.load(f)
                
            # Restaurar valores
            if 'current_index' in state and state['current_index'] < len(self.path):
                # Atualizar índice atual (começará a partir deste ponto)
                if not hasattr(self, 'current_action_index'):
                    self.current_action_index = state['current_index']
                else:
                    self.current_action_index = state['current_index']
                
            # Verificar se o caminho armazenado corresponde ao caminho atual
            if 'path_file' in state and state['path_file']:
                if self.path_file != state['path_file']:
                    self.logger.warning(f"O estado foi salvo para o caminho '{state['path_file']}' mas está sendo carregado para '{self.path_file}'")
            
            self.logger.info(f"Estado carregado de {filepath}")
            self.logger.info(f"Retomando execução do índice {self.current_action_index} de {len(self.path)} ações")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar estado: {e}")
            return False
    
    def _find_most_recent_state_file(self) -> str:
        """
        Busca o arquivo de estado mais recente na pasta saved_states.
        
        Returns:
            Caminho para o arquivo mais recente ou None se não encontrar
        """
        state_dir = "saved_states"
        if not os.path.exists(state_dir):
            return None
            
        state_files = glob.glob(os.path.join(state_dir, "state_*.json"))
        if not state_files:
            return None
            
        # Ordenar por data de modificação (mais recente primeiro)
        state_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return state_files[0]

    def _check_pause(self) -> None:
        """
        Verifica se o bot está pausado e aguarda retomada se necessário.
        """
        if self.paused:
            self.logger.debug("Execução pausada. Aguardando retomada...")
            self.pause_event.wait()  # Aguardar até que o evento seja setado
    
    def _execute_path(self) -> None:
        """
        Loop principal de execução do caminho.
        RESPONSABILIDADE ÚNICA: reproduzir sequência de ações.
        TODAS as decisões de navegação são delegadas ao MovementManager.
        """
        # Usar o current_action_index para retomar de onde parou
        i = self.current_action_index if hasattr(self, 'current_action_index') else 0
        self.logger.info(f"Iniciando execução do índice {i} de {len(self.path)}")
        
        while i < len(self.path) and not self._stopped and not self._shutting_down:
            # Verificar se está pausado
            self._check_pause()
            
            # Obter a ação atual
            action = self.path[i]
            action_type = action.get('type', ACTION_MOVE)  # Compatibilidade com caminhos antigos
            
            # Executar a ação baseada no tipo
            if action_type == ACTION_MOVE and not self._shutting_down:
                success = self._execute_move_action(action, i)
                if not success:
                    self.logger.warning(f"❌ Movimento para {action} falhou. Pulando para próximo ponto...")
                    # Continuar sem break - pular obstáculo
                    
            elif action_type == ACTION_CLICK and not self._shutting_down:
                self._execute_click_action(action)
                
            elif action_type == ACTION_WAIT and not self._shutting_down:
                self._execute_wait_action(action)
                
            else:
                # Tipo de ação desconhecido - logar e pular
                if not self._shutting_down:
                    self.logger.warning(f"Tipo de ação desconhecido: {action_type}. Pulando.")
            
            # Avançar para a próxima ação
            i += 1
            self.current_action_index = i  # Atualizar índice para persistência
    
    def _execute_move_action(self, action: Dict[str, Any], index: int) -> bool:
        """
        Executa uma ação de movimento DELEGANDO ao MovementManager.
        
        Args:
            action: Ação de movimento {x, y, [z], type}
            index: Índice da ação no caminho
            
        Returns:
            True se movimento foi bem-sucedido, False caso contrário
        """
        target = {'x': action['x'], 'y': action['y']}
        if 'z' in action:
            target['z'] = action['z']
        
        # Log reduzido para melhor performance
        if index % 10 == 0 or index == 0:  # Log a cada 10 ações
            total_actions = len(self.path)
            progress = (index / total_actions) * 100
            self.logger.info(f"[Progresso: {progress:.0f}%] Executando ações {index+1}-{min(index+10, total_actions)} de {total_actions}")
        
        # Delegar ao MovementManager
        success = self.movement.move_to(target)
        
        if success:
            # Não precisamos de pausa extra aqui pois o MovementManager já adiciona
            return True
        else:
            self.logger.error(f"Falha ao executar movimento para ({target['x']}, {target['y']})")
            return False
    
    def _execute_click_action(self, action: Dict[str, Any]) -> None:
        """
        Executa um clique de mouse nas coordenadas especificadas.
        
        Args:
            action: Dicionário com informações do clique (screen_x, screen_y, button)
        """
        if self._shutting_down:
            return
            
        screen_x = action.get('screen_x', 0)
        screen_y = action.get('screen_y', 0)
        button = action.get('button', 'left')
        
        self.logger.info(f"Executando clique: botão {button} na posição ({screen_x}, {screen_y})")
        
        try:
            # Mover o cursor para a posição
            mouse.move(screen_x, screen_y)
            
            # Pequena pausa para garantir que o cursor chegou
            time.sleep(0.1)
            
            # Executar o clique
            if button == 'left':
                mouse.click()
            elif button == 'right':
                mouse.right_click()
            elif button == 'middle':
                mouse.click(button='middle')
            else:
                self.logger.warning(f"Botão de mouse desconhecido: {button}. Usando clique esquerdo.")
                mouse.click()
                
        except Exception as e:
            if not self._shutting_down:
                self.logger.error(f"Erro ao executar clique de mouse: {e}")
        
        # Pausar após o clique para dar tempo de processamento ao jogo
        time.sleep(self.mouse_click_delay)
    
    def _execute_wait_action(self, action: Dict[str, Any]) -> None:
        """
        Executa uma ação de espera.
        
        Args:
            action: Dicionário com informações da espera (seconds)
        """
        wait_seconds = action.get('seconds', 1.0)
        self.logger.info(f"Executando espera de {wait_seconds:.1f} segundos")
        
        # Dividir a espera em intervalos menores para permitir interrupção
        wait_start = time.time()
        while time.time() - wait_start < wait_seconds and not self._stopped and not self._shutting_down:
            time.sleep(min(0.5, wait_seconds))  # Intervalo máximo de 0.5s
    
    def stop(self) -> None:
        """
        Para a reprodução em andamento.
        """
        self._stopped = True
        self._shutting_down = True
        self.logger.info("Parando reprodução...")
    
    def _shutdown(self) -> None:
        """
        Finaliza a reprodução e libera recursos.
        """
        # Flag para indicar que o processo de shutdown já iniciou
        if self._shutting_down:
            return
            
        self._shutting_down = True
        self._stopped = True
        
        try:
            # Dar um tempo para as threads perceberem as flags
            time.sleep(0.5)
            
            # Remover hotkeys
            keyboard.unhook_all()
            
            # Só fechar a conexão com o processo após todas as threads terem terminado
            if hasattr(self, 'mem'):
                self.mem.cleanup()
                
        except Exception as e:
            self.logger.warning(f"Erro ao finalizar: {e}")
            
        # Resumo final da execução
        self.logger.info("")
        self.logger.info("="*60)
        self.logger.info("RESUMO DA EXECUÇÃO")
        self.logger.info("="*60)
        
        # Estatísticas de movimento se disponível
        if hasattr(self, 'movement') and hasattr(self.movement, 'movement_count'):
            self.logger.info(f"Total de movimentos executados: {self.movement.movement_count}")
            
        # Posição final
        try:
            final_pos = get_coordinates_from_memory(self.mem, self.config.config_path)
            self.logger.info(f"Posição final: ({final_pos['x']}, {final_pos['y']})")
        except:
            pass
            
        # Status de conclusão
        if hasattr(self, 'current_action_index'):
            completion = (self.current_action_index / len(self.path)) * 100
            self.logger.info(f"Progresso: {self.current_action_index}/{len(self.path)} ações ({completion:.1f}%)")
            
        self.logger.info("="*60)
        self.logger.info("Reprodução finalizada.")


def main() -> None:
    """
    Função principal do reprodutor de caminhos.
    """
    import argparse
    
    # Configurar parser de argumentos
    parser = argparse.ArgumentParser(description="Reprodutor de caminhos para PokeTibia")
    parser.add_argument('path_file', help="Arquivo JSON gerado pelo gravador")
    parser.add_argument('-c', '--config', default='config/config.json', help="Arquivo de configuração")
    parser.add_argument('-d', '--debug', action='store_true', help="Ativar modo de debug")
    parser.add_argument('--no-mouse', action='store_true', help="Ignorar eventos de mouse no caminho")
    args = parser.parse_args()
    
    try:
        # Configurar modo de debug se necessário
        if args.debug:
            config = get_config(args.config)
            config.set("debug", True)
            config.save_config()
        
        # Configurar logging
        logger = get_logger(__name__)
        logger.info("Iniciando reprodutor de caminhos")
        
        # Verificar se o arquivo de caminho existe
        path_file = args.path_file
        if not os.path.exists(path_file):
            # Tentar procurar na pasta paths
            paths_dir = "paths"
            alternative_path = os.path.join(paths_dir, os.path.basename(path_file))
            if os.path.exists(alternative_path):
                path_file = alternative_path
                logger.info(f"Usando caminho de arquivo alternativo: {path_file}")
            else:
                logger.error(f"Arquivo de caminho não encontrado: {path_file}")
                return 1

        # Carregar arquivo de caminho
        try:
            with open(path_file, 'r') as f:
                path_data = json.load(f)
                logger.info(f"Carregado caminho com {len(path_data)} ações de {path_file}")
                
                # Remover eventos de mouse se solicitado
                if args.no_mouse:
                    path_data = [action for action in path_data if action.get('type') != ACTION_CLICK]
                    logger.info(f"Eventos de mouse ignorados. Caminho atualizado com {len(path_data)} ações.")
                    
                # DEBUG: Imprimir as primeiras ações do caminho para verificação
                if len(path_data) > 0:
                    logger.debug(f"Primeiras ações: {path_data[0:3]}")
        except Exception as e:
            logger.error(f"Erro ao carregar arquivo de caminho: {e}")
            return 1
            
        # Iniciar reprodução
        player = PathPlayer(args.config, path_data, path_file)
        player.start()
            
    except Exception as e:
        logger = get_logger(__name__)
        logger.critical(f"Erro fatal: {e}", exc_info=True)
        return 1
        
    return 0


if __name__ == '__main__':
    sys.exit(main())