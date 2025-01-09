# Multi Downloader 📥

<div align="center">

![Badge em Desenvolvimento](http://img.shields.io/static/v1?label=STATUS&message=FINALIZADO&color=GREEN&style=for-the-badge) [![](http://img.shields.io/static/v1?label=BAIXAR&message=EXECUTÁVEL&color=blue&style=for-the-badge)](https://www.mediafire.com/file/np5zvv0hqqjdmgh/Multi-Downloader.rar/file)

</div>

Bem-vindo ao **Multi Downloader**! Este projeto é uma aplicação gráfica que permite baixar vídeos de várias plataformas populares, como YouTube, Instagram, Twitter e Facebook, utilizando a biblioteca `customtkinter` para a interface gráfica.

---

## Funcionalidades 🚀

- **Download de vídeos do YouTube** 🎥
- **Download de posts do Instagram** 📸
- **Download de vídeos do Twitter** 🐦
- **Download de vídeos do Facebook** 📘
- **Todos (exceto Instagram) em formato de áudio ou vídeo com as qualidades disponíveis para cada vídeo**

---

## Como Usar 🛠️

1. **Clone o repositório**:
    ```sh
    git clone https://github.com/wilsondesouza/Multi-Downloader.git
    cd Multi-Downloader
    ```

2. **Instale as dependências**:
    ```sh
    pip install -r requirements.txt
    ```

3. **Instale o `ffmpeg`**:
    [Acesse](https://www.ffmpeg.org/download.html) o site e baixe a versão estável mais recente condizente com seu sistema operacional e adicione-o ao path nas variáves de ambiente.
    *Abra o CMD e digite o comando `ffmpeg -version` para conferir se ele foi reconhecido*

4. **Execute a aplicação**:
    ```sh
    python downloader.py
    ```

**Observações:** Ao executar o programa, inserir a URL e fazer o download do vídeo, será criada automaticamente uma subpasta no diretório raiz onde se encontra o aplicativo, de acordo com a origem: `downloads-Youtube` para vídeos do Youtube, `downloads-Instagram` para vídeos do Instagram, `downloads-Twitter` para vídeos do Twitter e `downloads-Facebook` para vídeos do Facebook.

---

## Interface Gráfica 🖥️

A interface gráfica é construída utilizando [customtkinter](https://customtkinter.tomschimansky.com/) e possui os seguintes componentes:

- **Campo de entrada para URL**: Insira a URL do vídeo que deseja baixar.
- **Botão de Download**: Inicia o download do vídeo/post.
- **Barra de Progresso**: Mostra o progresso do download.
- **Área de Log**: Exibe o histórico de downloads e mensagens de erro/sucesso.

---

## Dependências 📦

- [customtkinter](https://customtkinter.tomschimansky.com/): Biblioteca para criar interfaces gráficas modernas.
- [yt_dlp](https://github.com/yt-dlp/yt-dlp): Biblioteca para download de vídeos do YouTube.
- [instaloader](https://instaloader.github.io/): Biblioteca para download de posts do Instagram.
- [tkinter](https://docs.python.org/pt-br/3.13/library/tkinter.html): Biblioteca padrão do Python para interfaces gráficas.

---

## Funções Principais 🔍

### `download_youtube(url)`
Baixa vídeos do YouTube.

### `download_instagram(url)`
Baixa posts do Instagram.

### `download_twitter(url)`
Baixa vídeos do Twitter.

### `download_file(url)`
Determina qual método de download usar com base na URL fornecida.

---

## Contribuição 🤝

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues e pull requests.

---

## Licença 📄

Este projeto está licenciado sob a MIT License.

---

Feito na madrugada por [Wilson Souza](https://github.com/wilsondesouza)
