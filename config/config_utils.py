"""
Módulo de utilitários para gerenciamento de configuração do PokeTibia Bot.
Centraliza a lógica de carregamento, validação e acesso às configurações.
"""
import json
import logging
import os
import shutil
from typing import Dict, Any, Union, List

# Valores padrão para configurações
DEFAULT_CONFIG = {
    "module_name": "PokeAlliance_dx.exe",
    "record_interval": 0.1,
    "playback_delay": 0.2,
    "playback_timeout": 1.0,
    "wait_poll_interval": 0.005,
    "include_z": True,
    "hotkeys": {"start_stop": "F8"},
    "debug": False,
    "log_level": "INFO",
}

class ConfigManager:
    """
    Classe centralizada para gerenciamento de configurações.
    Fornece acesso uniforme aos parâmetros de configuração com validação.
    """
    def __init__(self, config_path: str = "config/config.json"):
        """
        Inicializa o gerenciador de configuração a partir de um arquivo JSON.
        
        Args:
            config_path: Caminho para o arquivo de configuração
        """
        # Migração automática de config.json da raiz para config/
        self.config_path = self._migrate_config_if_needed(config_path)
        self.config = self._load_config()
        self.logger = logging.getLogger(__name__)
        
    def _migrate_config_if_needed(self, config_path: str) -> str:
        """
        Migra automaticamente config.json da raiz para config/ se necessário.
        
        Args:
            config_path: Caminho desejado para o config
            
        Returns:
            Caminho final do arquivo de configuração
        """
        old_path = "config.json"
        new_path = config_path
        
        # Se o arquivo já está no local correto, não fazer nada
        if os.path.exists(new_path):
            return new_path
            
        # Se existe config.json na raiz, migrar
        if os.path.exists(old_path):
            try:
                # Criar diretório config se não existir
                config_dir = os.path.dirname(new_path)
                if config_dir:
                    os.makedirs(config_dir, exist_ok=True)
                
                # Mover arquivo
                shutil.move(old_path, new_path)
                print(f"✅ Configuração migrada: {old_path} → {new_path}")
                
                # Migrar backup se existir
                old_backup = f"{old_path}.bak"
                if os.path.exists(old_backup):
                    new_backup = f"{new_path}.bak"
                    shutil.move(old_backup, new_backup)
                    print(f"✅ Backup migrado: {old_backup} → {new_backup}")
                    
            except Exception as e:
                print(f"⚠️ Erro ao migrar configuração: {e}")
                print(f"   Por favor, mova manualmente {old_path} para {new_path}")
                # Continuar usando o arquivo da raiz se a migração falhar
                return old_path
                
        return new_path
        
    def _load_config(self) -> Dict[str, Any]:
        """
        Carrega o arquivo de configuração com valores padrão para campos ausentes.
        
        Returns:
            Dicionário com as configurações carregadas
        """
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Mesclar com valores padrão para garantir que todos os campos existam
            merged_config = DEFAULT_CONFIG.copy()
            merged_config.update(config)
            
            # Garantir que estruturas aninhadas também tenham valores padrão
            if "hotkeys" in config:
                merged_hotkeys = DEFAULT_CONFIG["hotkeys"].copy()
                merged_hotkeys.update(config["hotkeys"])
                merged_config["hotkeys"] = merged_hotkeys
                
            return merged_config
            
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.warning(f"Erro ao carregar configuração de '{self.config_path}': {e}")
            logging.info("Usando valores padrão para configuração.")
            return DEFAULT_CONFIG.copy()
            
    def save_config(self) -> bool:
        """
        Salva as configurações atuais no arquivo JSON.
        
        Returns:
            True se salvou com sucesso, False caso contrário
        """
        try:
            # Fazer backup da configuração anterior
            try:
                import os
                if os.path.exists(self.config_path):
                    backup_path = f"{self.config_path}.bak"
                    with open(self.config_path, 'r') as source:
                        with open(backup_path, 'w') as target:
                            target.write(source.read())
                    self.logger.debug(f"Backup da configuração criado em {backup_path}")
            except Exception as e:
                self.logger.warning(f"Erro ao criar backup da configuração: {e}")
            
            # Salvar configuração atual
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
                
            self.logger.info(f"Configuração salva com sucesso em {self.config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar configuração: {e}")
            return False
    
    def reload_config(self) -> bool:
        """
        Recarrega as configurações do arquivo para atualizar após modificações externas.
        
        Returns:
            True se recarregou com sucesso, False caso contrário
        """
        try:
            self.config = self._load_config()
            self.logger.debug("Configuração recarregada com sucesso")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao recarregar configuração: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtém um valor de configuração com fallback para valor padrão.
        
        Args:
            key: Chave da configuração a obter
            default: Valor padrão caso a chave não exista
            
        Returns:
            Valor da configuração ou o default
        """
        if "." in key:  # Acesso a configurações aninhadas
            parts = key.split(".")
            current = self.config
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            return current
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Define um valor de configuração.
        
        Args:
            key: Chave da configuração a definir
            value: Valor a atribuir
        """
        if "." in key:  # Acesso a configurações aninhadas
            parts = key.split(".")
            current = self.config
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value
        else:
            self.config[key] = value
    
    def update(self, updates: Dict[str, Any]) -> None:
        """
        Atualiza múltiplos valores de configuração de uma vez.
        
        Args:
            updates: Dicionário com as atualizações
        """
        for key, value in updates.items():
            self.set(key, value)
    
    def get_log_level(self) -> int:
        """
        Obtém o nível de log configurado convertido para constante do logging.
        
        Returns:
            Constante do logging (DEBUG, INFO, etc.)
        """
        level_str = self.get("log_level", "INFO").upper()
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        return levels.get(level_str, logging.INFO)
    
    def get_pointer_chains(self) -> Dict[str, Dict[str, Union[int, List[int]]]]:
        """
        Obtém as definições de cadeias de ponteiros para acesso à memória.
        
        Returns:
            Dicionário com as cadeias de ponteiros por eixo
        """
        return self.get("pointer_chains", {})
    
    
    def get_module_name(self) -> str:
        """
        Obtém o nome do módulo/processo do jogo.
        
        Returns:
            Nome do processo
        """
        return self.get("module_name", "PokeAlliance_dx.exe")
    
    def get_hotkey(self, key: str, default: str = None) -> str:
        """
        Obtém uma tecla de atalho configurada.
        
        Args:
            key: Nome da tecla de atalho
            default: Valor padrão caso não esteja configurada
            
        Returns:
            Tecla de atalho configurada
        """
        hotkeys = self.get("hotkeys", {})
        return hotkeys.get(key, default)


# Instância global para uso em todo o projeto
config_manager = ConfigManager()


def get_config(config_path: str = "config/config.json") -> ConfigManager:
    """
    Função auxiliar para obter instância do gerenciador de configuração.
    
    Args:
        config_path: Caminho para o arquivo de configuração
        
    Returns:
        Instância do ConfigManager
    """
    global config_manager
    
    if config_manager.config_path != config_path:
        config_manager = ConfigManager(config_path)
        
    return config_manager