# 🎮 PokeTibia Bot v1

Um bot automatizado para PokeTibia que grava e reproduz caminhos com precisão, desenvolvido em Python.

## ✨ Características

- **🎯 Gravação de Caminhos**: Grave seus percursos com precisão de 1 SQM
- **🔄 Reprodução Fiel**: Reproduza caminhos gravados com movimento suave e natural
- **🖱️ Suporte a Mouse**: Grave e reproduza cliques do mouse
- **⏸️ Sistema de Pausa**: Pause e retome a execução a qualquer momento (F9)
- **💾 Salvamento de Estado**: Continue de onde parou após pausar
- **📊 Logs Detalhados**: Sistema completo de logging em arquivo e console
- **⚡ Performance Otimizada**: Movimento fluido sem travadas

## 📋 Requisitos

- Python 3.8 ou superior
- Windows (testado no Windows 10/11)
- PokeTibia client (PokeAlliance_dx.exe)

## 🚀 Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/Poke_bot_v1.git
cd Poke_bot_v1
```

2. Crie um ambiente virtual (recomendado):
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

## ⚙️ Configuração

### Primeira Execução

1. Execute o bot:
```bash
python start_bot.py
```

2. No menu principal, escolha a opção **4 - Configuração de Coordenadas**

3. Siga as instruções para configurar os endereços de memória do jogo:
   - Use o Cheat Engine para encontrar os endereços X, Y e Z
   - Cole os valores quando solicitado

### Estrutura de Pastas

```
Poke_bot_v1/
├── config/              # Arquivos de configuração
│   └── config.json      # Configuração principal
├── paths/               # Caminhos gravados
├── saved_states/        # Estados salvos (pausas)
├── utils/               # Módulos utilitários
├── movement/            # Sistema de movimento
├── memory/              # Gerenciamento de memória
└── poketibia_bot.log    # Arquivo de log
```

## 📖 Como Usar

### 1. Gravando um Caminho

1. No menu principal, escolha **1 - Iniciar Gravação de Caminho**
2. Posicione seu personagem no ponto inicial
3. Pressione **F8** para iniciar a gravação
4. Mova-se pelo caminho desejado (1 SQM por vez para melhor precisão)
5. Use **Ctrl+Alt+1/2/3** para registrar cliques do mouse
6. Pressione **F8** novamente para parar e salvar

### 2. Reproduzindo um Caminho

1. No menu principal, escolha **2 - Reproduzir Caminho Gravado**
2. Selecione o caminho desejado da lista
3. O bot iniciará a reprodução automaticamente
4. Use **F9** para pausar/retomar
5. Use **ESC** para parar

### 3. Teclas de Atalho

| Tecla | Função |
|-------|---------|
| F8 | Iniciar/Parar gravação |
| F9 | Pausar/Retomar reprodução |
| F10 | Ativar/Desativar captura de mouse |
| ESC | Parar execução |
| Ctrl+Alt+1 | Registrar clique esquerdo |
| Ctrl+Alt+2 | Registrar clique direito |
| Ctrl+Alt+3 | Registrar clique do meio |

## 🎯 Dicas para Melhor Desempenho

1. **Grave com movimentos de 1 SQM**: O bot funciona melhor com movimentos precisos
2. **Evite correr durante a gravação**: Mantenha velocidade normal
3. **Grave em áreas sem obstáculos móveis**: Pokémons podem interferir
4. **Use o intervalo padrão**: 0.1s entre gravações funciona bem

## 🛠️ Configurações Avançadas

### config.json

```json
{
  "module_name": "PokeAlliance_dx.exe",
  "record_interval": 0.1,        // Intervalo entre gravações
  "playback_delay": 0.2,         // Delay entre ações
  "playback_timeout": 2.5,       // Timeout para movimentos
  "include_z": true,             // Incluir coordenada Z
  "hotkeys": {
    "start_stop": "F8",
    "pause_resume": "F9",
    "toggle_mouse": "F10"
  }
}
```

### Ajustes de Performance

O bot usa configurações otimizadas para movimento suave:
- Pressionar tecla: 20ms
- Aguardar movimento: 150ms
- Delay entre movimentos: 50ms

## 🔧 Solução de Problemas

### Bot não detecta o jogo
- Verifique se o PokeTibia está rodando
- Execute o bot como administrador
- Reconfigure os endereços de memória

### Movimentos imprecisos
- Grave novamente com movimentos de 1 SQM
- Verifique se há lag no jogo
- Ajuste os tempos no código se necessário

### Erro de memória no final
- Normal ao finalizar - não afeta o funcionamento
- Ocorre quando o bot tenta ler a posição final

## 📝 Logs

Os logs são salvos em `poketibia_bot.log` e mostram:
- Início e fim de gravações
- Progresso da reprodução
- Erros e avisos
- Estatísticas de execução

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para:
- Reportar bugs
- Sugerir melhorias
- Enviar pull requests

## ⚠️ Aviso Legal

Este bot é apenas para fins educacionais. O uso de bots pode violar os termos de serviço do jogo. Use por sua conta e risco.

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.

---

**Desenvolvido com ❤️ para a comunidade PokeTibia**