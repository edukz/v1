"""
Módulo de utilitários para gerenciamento de logs do PokeTibia Bot.
Centraliza a lógica de configuração e acesso aos logs.
"""
import logging
import os
from typing import Dict, Any, Optional

# Variável global para rastrear se o logging foi configurado
_logging_configured = False

def get_logger(name: str, level: int = None) -> logging.Logger:
    """
    Obtém um logger configurado.
    
    Args:
        name: Nome do logger (geralmente __name__)
        level: Nível de log opcional (DEBUG, INFO, etc.)
        
    Returns:
        Logger configurado
    """
    # Garantir que o logging básico esteja configurado
    global _logging_configured
    if not _logging_configured:
        setup_file_logging()
        _logging_configured = True
    
    logger = logging.getLogger(name)
    
    # Caso o nível de log seja fornecido, configurá-lo
    if level is not None:
        logger.setLevel(level)
    else:
        # Usar INFO como padrão
        logger.setLevel(logging.INFO)
    
    return logger

def setup_file_logging(log_file: str = "poketibia_bot.log") -> None:
    """
    Configura o logging para arquivo e console.
    
    Args:
        log_file: Caminho para o arquivo de log
    """
    global _logging_configured
    
    # Configurar o logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Limpar handlers existentes para evitar duplicação
    root_logger.handlers.clear()
    
    # Formato comum para todos os handlers
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para arquivo
    try:
        # Criar diretório de logs se não existir
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)  # Arquivo captura tudo
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Erro ao criar handler de arquivo: {e}")
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)  # Console mostra INFO e acima
    root_logger.addHandler(console_handler)
    
    _logging_configured = True

def set_log_level(level: int) -> None:
    """
    Define o nível de log para o logger raiz.
    
    Args:
        level: Nível de log (logging.DEBUG, logging.INFO, etc.)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Atualizar o nível em todos os handlers existentes
    for handler in root_logger.handlers:
        handler.setLevel(level)