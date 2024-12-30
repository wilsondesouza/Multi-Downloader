# Known Issues

Este documento documenta as anomalias conhecidas e comportamentos inesperados identificados no aplicativo. Caso você encontre uma inconsistência que não esteja listada aqui, recomendamos abrir uma **Issue** no repositório para análise e tratamento.

---

## Problemas Atuais

### 1. [Erro ao realizar download subsequente]
- **Impacto:** Não é possível efetuar o download de arquivos no formato `.mp4` após realizar o download de arquivos no formato `.mp3` provenientes da mesma fonte, especificamente o Twitter.
- **Status:** Em análise.
- **Solução Alternativa:** Execute os downloads em ordem inversa, iniciando pelo formato `.mp4`.

---

## Problemas Resolvidos

### 1. [Erro no salvamento de arquivos com nomes extensos]
- **Descrição:** Arquivos de vídeo extraídos do Twitter apresentavam nomes que ultrapassam os limites suportados pelo S.O, resultando em falha no salvamento no diretório correto. Os arquivos eram armazenados em diretórios superiores ao especificado.
- **Solução:** 
  - Limitação do nome do arquivo para utilizar exclusivamente caracteres ASCII.
  - Redução do tamanho máximo para 50 caracteres.
  - Definição de um diretório de saída padrão, localizado em uma subpasta específica do diretório raiz da aplicação.

### 2. [Substituição de mídia ao realizar downloads subsequentes]
- **Descrição:** Arquivos no formato `.mp4` eram deletados quando o download subsequente de um arquivo no formato `.mp3` era realizado a partir da mesma fonte.
- **Solução:** Implementação de uma nomenclatura diferenciada para os arquivos de saída, adicionando o formato do arquivo ao nome final para evitar conflitos.
