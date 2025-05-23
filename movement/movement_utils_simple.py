"""
Módulo simplificado de movimentação - Sem tratamento de obstáculos
"""
import time
import keyboard
import ctypes
from typing import Dict, List

# Importar módulos necessários
import sys
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

# Adicionar todos os caminhos necessários
sys.path.insert(0, os.path.join(project_root, 'config'))
sys.path.insert(0, os.path.join(project_root, 'utils'))
sys.path.insert(0, os.path.join(project_root, 'memory'))

from memory_manager import SimpleMemoryManager
from config_utils import get_config
from logging_utils import get_logger


def get_direction(cur: Dict[str, int], nxt: Dict[str, int]) -> List[str]:
    """
    Determina teclas de direção para mover de uma posição para outra.
    
    Args:
        cur: Posição atual {x, y}
        nxt: Próxima posição {x, y}
        
    Returns:
        Lista de teclas a pressionar (w, a, s, d)
    """
    dx, dy = nxt['x'] - cur['x'], nxt['y'] - cur['y']
    keys: List[str] = []
    if dy < 0: keys.append('w')  # Norte
    if dy > 0: keys.append('s')  # Sul
    if dx > 0: keys.append('d')  # Leste
    if dx < 0: keys.append('a')  # Oeste
    return keys


def break_into_single_steps(start: Dict[str, int], end: Dict[str, int]) -> List[Dict[str, int]]:
    """
    Quebra um movimento de múltiplos SQMs em passos de 1 SQM.
    
    Args:
        start: Posição inicial {x, y, [z]}
        end: Posição final {x, y, [z]}
        
    Returns:
        Lista de posições intermediárias de 1 SQM cada
    """
    steps = []
    current_x, current_y = start['x'], start['y']
    target_x, target_y = end['x'], end['y']
    
    # Incluir z se disponível
    z = start.get('z', end.get('z'))
    
    while current_x != target_x or current_y != target_y:
        # Mover primeiro na diagonal se possível
        next_x = current_x
        next_y = current_y
        
        if current_x < target_x and current_y < target_y:
            # Diagonal sudeste
            next_x += 1
            next_y += 1
        elif current_x < target_x and current_y > target_y:
            # Diagonal nordeste
            next_x += 1
            next_y -= 1
        elif current_x > target_x and current_y < target_y:
            # Diagonal sudoeste
            next_x -= 1
            next_y += 1
        elif current_x > target_x and current_y > target_y:
            # Diagonal noroeste
            next_x -= 1
            next_y -= 1
        elif current_x < target_x:
            # Apenas leste
            next_x += 1
        elif current_x > target_x:
            # Apenas oeste
            next_x -= 1
        elif current_y < target_y:
            # Apenas sul
            next_y += 1
        elif current_y > target_y:
            # Apenas norte
            next_y -= 1
        
        step = {'x': next_x, 'y': next_y}
        if z is not None:
            step['z'] = z
        
        steps.append(step)
        current_x, current_y = next_x, next_y
    
    return steps


def get_coordinates_from_memory(memory, config_path="config/config.json") -> Dict[str, int]:
    """
    Obtém as coordenadas atuais do personagem a partir da memória.
    Versão simplificada sem mapeamento de eixos.
    """
    config = get_config(config_path)
    include_z = config.get("include_z", True)
    
    # Resolver endereços para cada eixo
    pointer_chains = config.get_pointer_chains()
    
    # Usar endereços base diretamente (SimpleMemoryManager)
    addr_x = pointer_chains['x']['base_offset']
    addr_y = pointer_chains['y']['base_offset']
    addr_z = pointer_chains['z']['base_offset'] if include_z else None
    
    # Ler valores da memória diretamente
    try:
        x = memory.read_memory(addr_x, ctypes.c_int32)
        y = memory.read_memory(addr_y, ctypes.c_int32)
        
        pos = {'x': x, 'y': y}
        if include_z and addr_z:
            pos['z'] = memory.read_memory(addr_z, ctypes.c_int32)
            
        return pos
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Erro ao ler coordenadas: {e}")
        raise


class SimpleMovementManager:
    """
    Gerenciador de movimentos simplificado - movimento fiel ao caminho gravado.
    """
    def __init__(self, memory_manager, config_path="config/config.json"):
        """
        Inicializa o gerenciador de movimentos simples.
        """
        self.memory = memory_manager
        self.config = get_config(config_path)
        self.logger = get_logger(__name__)
        
        # Log de inicialização
        self.logger.info("SimpleMovementManager inicializado")
        
        # Obter configurações relevantes
        self.include_z = self.config.get("include_z", True)
        self.playback_timeout = self.config.get("playback_timeout", 1.0)
        self.playback_delay = self.config.get("playback_delay", 0.2)
        
        # Ajustar timeouts para movimento mais suave
        self.key_press_duration = 0.02  # Tempo que a tecla fica pressionada (20ms)
        self.movement_wait_time = 0.15  # Tempo para esperar o movimento (150ms)
        self.post_move_delay = 0.05    # Delay mínimo após movimento (50ms)
        
        self.logger.info(f"Configurações de movimento: press={self.key_press_duration}s, wait={self.movement_wait_time}s, delay={self.post_move_delay}s")
        
        # Resolver endereços para cada eixo
        pointer_chains = self.config.get_pointer_chains()
        self.raw_addrs = {
            axis: info['base_offset']
            for axis, info in pointer_chains.items()
        }
        
        # Estado da navegação
        self.current_pos = None
        self.movement_count = 0  # Contador de movimentos para log
    
    def update_position(self) -> Dict[str, int]:
        """
        Atualiza a posição atual lendo da memória.
        """
        try:
            pos = get_coordinates_from_memory(self.memory, self.config.config_path)
            self.current_pos = pos
            return pos
        except Exception as e:
            self.logger.error(f"Erro ao ler posição atual: {e}")
            raise
    
    def move_to_single_sqm(self, target: Dict[str, int], smooth_mode: bool = True) -> bool:
        """
        Move o personagem exatamente 1 SQM na direção do alvo.
        
        Args:
            target: Posição alvo {x, y, [z]} (deve estar a 1 SQM de distância)
            smooth_mode: Se True, usa movimento mais suave
            
        Returns:
            True se o movimento foi executado
        """
        # Não atualizar posição a cada movimento para economizar tempo
        if not hasattr(self, '_last_known_pos'):
            self.update_position()
            self._last_known_pos = self.current_pos
        
        current = self._last_known_pos
        
        # Verificar se já está no alvo
        if current['x'] == target['x'] and current['y'] == target['y']:
            return True
            
        # Determinar teclas
        keys = get_direction(current, target)
        if not keys:
            return True
            
        # Log simplificado
        self.movement_count += 1
        if self.movement_count % 10 == 1:  # Log ainda menos frequente
            self.logger.info(f"Progresso: {self.movement_count} movimentos...")
        
        # Executar movimento suave
        if smooth_mode:
            # Simular pressionamento mais natural
            for k in keys:
                keyboard.press(k)
                time.sleep(0.01)  # Micro delay entre teclas
            
            time.sleep(self.key_press_duration)
            
            for k in keys:
                keyboard.release(k)
                time.sleep(0.01)  # Micro delay entre teclas
        else:
            # Movimento rápido
            for k in keys:
                keyboard.press(k)
            time.sleep(self.key_press_duration)
            for k in keys:
                keyboard.release(k)
        
        # Aguardar movimento
        time.sleep(self.movement_wait_time)
        
        # Atualizar posição assumida
        self._last_known_pos = target
        
        return True
    
    def move_to(self, target: Dict[str, int]) -> bool:
        """
        Move o personagem para a posição alvo de forma suave.
        
        Args:
            target: Posição alvo {x, y, [z]}
            
        Returns:
            True se executou o movimento
        """
        # Usar posição conhecida ou atualizar
        if not hasattr(self, '_last_known_pos'):
            self.update_position()
            self._last_known_pos = self.current_pos
        
        current = self._last_known_pos
        
        # Verificar se já está na posição alvo
        if current['x'] == target['x'] and current['y'] == target['y']:
            return True
        
        # Calcular distância
        dx = abs(target['x'] - current['x'])
        dy = abs(target['y'] - current['y'])
        total_dist = max(dx, dy)
        
        # Para caminhos gravados, esperamos movimentos de 1 SQM
        if total_dist == 1:
            # Movimento simples de 1 SQM
            result = self.move_to_single_sqm(target, smooth_mode=True)
            
            # Pausa mínima entre movimentos
            time.sleep(self.post_move_delay)
            
            return result
            
        else:
            # Distância maior - precisa quebrar em passos
            if self.movement_count == 0:  # Log apenas primeira vez
                self.logger.info(f"Ajustando caminho: {total_dist} SQMs de distância")
            
            # Obter passos intermediários
            steps = break_into_single_steps(current, target)
            
            # Executar cada passo
            for step in steps:
                self.move_to_single_sqm(step, smooth_mode=True)
                # Micro pausa entre passos múltiplos
                time.sleep(0.02)
            
            return True
    
    def follow_path(self, path: List[Dict[str, int]], repeat: int = 1, interval: float = 2.0) -> bool:
        """
        Segue um caminho pré-definido - versão simplificada.
        
        Args:
            path: Lista de pontos a seguir
            repeat: Número de vezes para repetir o caminho
            interval: Intervalo entre repetições
            
        Returns:
            True sempre
        """
        if not path or len(path) < 2:
            self.logger.warning("Caminho vazio ou com apenas um ponto")
            return False
        
        # Atualizar posição atual
        self.update_position()
        
        # Loop de repetição
        iteration = 1
        
        while repeat < 0 or iteration <= repeat:
            if repeat != 1:
                self.logger.info(f"Executando caminho - Iteração {iteration}")
            
            # Executar caminho
            for i in range(len(path) - 1):
                target = path[i+1]
                self.move_to(target)
                
            # Aguardar antes da próxima repetição
            if repeat < 0 or iteration < repeat:
                self.logger.info(f"Aguardando {interval:.1f}s...")
                time.sleep(interval)
                
            iteration += 1
        
        self.logger.info("Execução do caminho concluída")
        return True


# Para compatibilidade, manter o nome original
MovementManager = SimpleMovementManager