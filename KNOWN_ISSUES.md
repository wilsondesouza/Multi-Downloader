# Limitações conhecidas e melhorias

Este documento acompanha questões ainda abertas e registra melhorias implementadas. A disponibilidade e o comportamento das plataformas podem mudar sem aviso; testes automatizados não substituem validação com mídias públicas autorizadas.

## Questão em investigação

### Downloads MP3→MP4 subsequentes no X/Twitter

- **Impacto relatado:** um download MP3 pode impedir um download MP4 posterior da mesma origem.
- **Estado:** não reproduzido nem confirmado como corrigido.
- **Evidência atual:** os templates de saída diferenciam MP3 e MP4, e os testes verificam essa separação. Não há reprodução real com `yt-dlp`, FFmpeg e a plataforma.
- **Próximo passo:** reproduzir com links públicos autorizados, registrar as versões de `yt-dlp` e FFmpeg e inspecionar arquivos temporários, códigos de saída e logs antes de mudar a estratégia de nomes ou conversão.

## Melhorias implementadas

- Validação de esquema, host e credenciais embutidas na URL, incluindo rejeição de domínios falsificados.
- Prévia de metadados e consulta de resoluções em threads de trabalho, sem bloquear a interface.
- Fila sequencial e inclusão de lotes de até 50 links.
- Pausa, retomada, cancelamento e retentativas limitadas para downloads de `yt-dlp`.
- No Instagram, onde o Instaloader não oferece pausa ou cancelamento seguro durante a transferência, o usuário pode pedir para parar a fila depois da mídia atual. Arquivos existentes são ignorados em vez de substituídos.
- Seletor de pasta, preferências persistentes, confirmação de substituição onde suportada e proteção contra sobrescrita acidental.
- Histórico SQLite persistente e opção para mostrar o arquivo salvo. URLs originais não são armazenadas.
- Colagem da área de transferência, validação antecipada e atalhos de teclado.
- Verificação do FFmpeg, consulta manual/configurável de versões do PyPI e exportação voluntária de diagnóstico revisável. Não há instalação automática de dependências.
- Sanitização dos detalhes de erro exibidos e exclusão de URLs, query strings, nomes de usuário e caminhos locais do relatório de diagnóstico.

## Limitações restantes

- São aceitos somente links públicos compatíveis com os serviços externos e com as bibliotecas instaladas. Conteúdo privado, autenticação e controles de acesso não são contornados.
- A fila é sequencial; não é possível baixar itens em paralelo. A fila pendente e suas URLs não são salvas ou restauradas depois de fechar o aplicativo.
- O histórico não tem expiração automática e registra título e caminho local de saída, mas não a URL original. Registros transitórios são marcados como interrompidos ao iniciar novamente.
- O Instaloader não oferece substituição segura de arquivos; se a prévia identificar uma saída existente, o item é ignorado. Para baixá-lo novamente, remova o arquivo anterior manualmente.
- A pausa/cancelamento de `yt-dlp` ocorre nos callbacks de progresso, portanto a resposta pode aguardar o próximo callback. Arquivos parciais dependem do comportamento de retomada da biblioteca.
- Retentativas são limitadas e aplicadas somente a falhas classificadas como transitórias. Erros de mídia privada, removida ou requisições limitadas não são repetidos automaticamente.
- MP3 e combinação de faixas dependem do FFmpeg no `PATH`. O aplicativo verifica sua presença, mas não instala nem atualiza o FFmpeg.
- As atualizações de dependências são apenas consultadas no PyPI; a instalação é manual, usando as instruções do projeto.
- O diagnóstico é exportado somente após revisão e confirmação do usuário; ele é mínimo e não contém URLs, query strings, nomes de usuário ou caminhos locais.
- Não há garantia de disponibilidade permanente: alterações nas plataformas, limites de requisição e mudanças nas bibliotecas podem exigir manutenção.
