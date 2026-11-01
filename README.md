# Multi-Downloader

Aplicativo desktop em Python para baixar mídia acessível publicamente a partir de links do YouTube, Instagram, X/Twitter e Facebook. A interface usa CustomTkinter; `yt-dlp` atende YouTube, X/Twitter e Facebook, e Instaloader atende posts de vídeo do Instagram.

> Use a aplicação somente para conteúdo que você tem autorização para baixar. Respeite direitos autorais, termos das plataformas e leis aplicáveis. A aplicação não contorna autenticação, DRM ou controles de acesso.

## Funcionalidades

- Baixa vídeos em MP4 e extrai áudio em MP3 nas plataformas compatíveis com `yt-dlp`.
- Baixa vídeos de posts/reels/IGTV públicos do Instagram em MP4. O Instagram não oferece opções de formato ou qualidade.
- Consulta título, duração e resoluções disponíveis antes do download, quando a plataforma fornece esses metadados.
- Mantém uma fila sequencial e aceita lotes de até 50 links, sem concorrência entre downloads.
- Permite pausar, retomar e cancelar operações de `yt-dlp`. O Instaloader não oferece pausa ou cancelamento seguro durante a transferência; nesse caso, é possível interromper a fila após a mídia atual.
- Seleciona o diretório de destino, mantém subpastas por plataforma e abre o local do arquivo concluído.
- Pede confirmação antes de substituir arquivos em plataformas atendidas por `yt-dlp`. No Instagram, arquivos existentes são ignorados porque o Instaloader não oferece substituição segura.
- Salva preferências e histórico persistente em SQLite. URLs de origem e fila pendente não são armazenadas; ao reiniciar, downloads em estados transitórios são marcados como interrompidos.
- Permite configurar qualidade, tentativas automáticas limitadas e consulta manual/de inicialização ao PyPI. Atualizações de dependências nunca são instaladas automaticamente.
- Exporta um relatório de diagnóstico revisável que exclui URLs, query strings, nomes de usuário e caminhos locais.
- Informa se o FFmpeg está disponível; FFmpeg é necessário para extrair MP3 e combinar faixas de áudio e vídeo quando necessário.
- Oferece colagem da área de transferência e atalhos: `Enter` para adicionar o link e `Ctrl+Enter` para iniciar a ação pelo campo de URL.

## Arquitetura

- `multi_downloader/service.py`: validação e roteamento de URLs, prévia, opções, retentativas e execução dos downloads.
- `multi_downloader/ui.py`: interface CustomTkinter, fila, preferências, histórico e diálogos. A rede e os downloads são executados em threads de trabalho; atualizações da interface passam por uma fila de eventos.
- `multi_downloader/persistence.py`: armazenamento local de preferências e histórico em SQLite.
- `multi_downloader/diagnostics.py`: sanitização e exportação voluntária de informações de diagnóstico.
- `downloader.py`: ponto de entrada para desenvolvimento e empacotamento.
- `executavel.spec`: configuração do PyInstaller.

## Requisitos

- Python 3.10 ou superior.
- Dependências Python de [`requirements.txt`](./requirements.txt).
- FFmpeg disponível no `PATH` para extração de MP3 e combinação de faixas quando necessário.
- Tkinter instalado com a distribuição Python. A instalação do Tkinter varia entre sistemas operacionais.

## Instalação e execução

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python downloader.py
```

No macOS/Linux, ative o ambiente virtual com `source .venv/bin/activate`.

## Dados locais e privacidade

O SQLite fica no diretório de dados da aplicação do usuário: `%LOCALAPPDATA%\MultiDownloader` no Windows, `~/Library/Application Support/MultiDownloader` no macOS ou `$XDG_STATE_HOME/multi-downloader` (por padrão `~/.local/state/multi-downloader`) no Linux. O histórico não tem expiração automática. Ele registra plataforma, título, formato, estado, caminho local do arquivo, tentativas e código de erro; não guarda a URL original. A fila não é restaurada depois de fechar o aplicativo.

Antes de exportar, o relatório de diagnóstico pode ser revisado na interface. O arquivo só é salvo após uma ação explícita do usuário.

## Testes

```powershell
python -m unittest discover -v
```

Os testes não acessam as plataformas: chamadas de rede e bibliotecas de download são isoladas com mocks e diretórios temporários.

## Gerar executável no Windows

Instale o PyInstaller no mesmo ambiente e execute:

```powershell
python -m pip install pyinstaller
pyinstaller executavel.spec
```

O executável é gerado em `dist`. O `.spec` aponta para `downloader.py`, usa `assets/images/icon.ico` no arquivo executável e inclui PNG/ICO no pacote. A janela usa `assets/images/icon.png`; no Windows, o `.ico` também é aplicado à janela e a aplicação define um AppUserModelID para a barra de tarefas.

## Revisão técnica e limitações conhecidas

Os pontos de entrada antigos foram consolidados no mesmo serviço, a validação de domínio rejeita hosts falsificados, e chamadas de rede não bloqueiam a thread da GUI. A disponibilidade e os formatos suportados dependem das plataformas e das bibliotecas externas e podem mudar. Consulte [`KNOWN_ISSUES.md`](./KNOWN_ISSUES.md) para limitações restantes e a investigação pendente sobre downloads MP3→MP4 subsequentes no X/Twitter.

## Licença

Distribuído sob a licença MIT. Consulte [`LICENSE.txt`](./LICENSE.txt).
