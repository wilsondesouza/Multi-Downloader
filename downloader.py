# Desenvolvido por @wilsonsouza https://github.com/wilsondesouza
# Se curtiu o trabalho ou se a aplicação lhe foi útil, favorite o repositório


# Importações nativas
import os
import threading
import time
from urllib.parse import urlparse, urlunparse

# Importações externas
import customtkinter as ctk
from tkinter import messagebox, StringVar
import yt_dlp
import instaloader

# Diretório base onde o arquivo .py se encontra
base_dir = os.path.dirname(os.path.abspath(__file__))

# Função para atualizar a barra de progresso
def update_progress_bar(progress, value):
    progress.set(value / 100)  # Atualiza a barra de progresso com o valor fornecido
    root.update_idletasks()  # Atualiza a interface gráfica

# Função para resetar a barra de progresso após um atraso
def reset_progress_bar(progress, delay=3):
    time.sleep(delay)  # Espera pelo tempo especificado
    progress.set(0)  # Reseta a barra de progresso para 0
    root.update_idletasks()  # Atualiza a interface gráfica

# Função para adicionar mensagens ao log
def log_message(message):
    log_area.configure(state='normal')  # Permite edição na área de log
    log_area.insert(ctk.END, message + '\n')  # Insere a mensagem no final do log
    log_area.configure(state='disabled')  # Desabilita edição na área de log
    log_area.see(ctk.END)  # Rola a área de log para a última linha
    
# Função para sanitizar a URL do Twitter
def sanitize_twitter_url(url):
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split('/')
    if len(path_parts) > 2 and path_parts[1] != 'i':
        path_parts[1] = 'i'
        sanitized_path = '/'.join(path_parts)
        sanitized_url = urlunparse(parsed_url._replace(path=sanitized_path))
        return sanitized_url
    return url
    
# Função para baixar vídeos do YouTube
def download_youtube(url, format_choice):
    try:
        youtube_dir = os.path.join(base_dir, 'downloads-Youtube')  # Define o diretório de download
        os.makedirs(youtube_dir, exist_ok=True)  # Cria o diretório se não existir
        
        start_time = time.time()  # Marca o tempo de início do download
        
        # Função de callback para atualizar a barra de progresso
        def progress_hook(d):
            if d['status'] == 'downloading':  # Verifica se o status é 'downloading'
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')  # Obtém o total de bytes
                if total_bytes:
                    percentage = d['downloaded_bytes'] / total_bytes * 100  # Calcula a porcentagem de download
                    update_progress_bar(progress, percentage)  # Atualiza a barra de progresso
        
        # Opções de configuração para o yt_dlp
        ydl_opts = {
            'outtmpl': os.path.join(youtube_dir, '%(title)s_' + format_choice + '.%(ext)s'), # Define o padrão de nome do arquivo de saída, incluindo o sufixo do formato escolhido (mp3 ou mp4)
            'format': 'bestaudio/best' if format_choice == 'mp3' else 'bestvideo+bestaudio/best', # Define o formato de download: 'bestaudio/best' para mp3, 'bestvideo+bestaudio/best' para mp4
            'progress_hooks': [progress_hook], # Adiciona a função de callback para atualizar a barra de progresso durante o download
            'postprocessors': [{ # Configurações para pós-processamento: extrai o áudio e converte para mp3 se o formato escolhido for mp3
                'key': 'FFmpegExtractAudio', # Utiliza o FFmpeg para extrair o áudio
                'preferredcodec': 'mp3', # Define o codec de áudio como mp3
                'preferredquality': '192', # Define a qualidade do áudio como 192 kbps
            }] if format_choice == 'mp3' else []
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)  # Extrai informações e baixa o vídeo
            video_title = info_dict.get('title', 'Vídeo')  # Obtém o título do vídeo
            
        end_time = time.time()  # Marca o tempo de término do download
        elapsed_time = end_time - start_time  # Calcula o tempo decorrido
        
        log_message(f"Vídeo '{video_title}' do Youtube baixado em {elapsed_time:.2f} segundos!")  # Adiciona mensagem ao log
        messagebox.showinfo("Sucesso", f"Download do vídeo '{video_title}' concluído com sucesso!")  # Mostra mensagem de sucesso
        threading.Thread(target=reset_progress_bar, args=(progress,)).start()  # Reseta a barra de progresso após alguns segundos
    
    except Exception as e:
        log_message(f"Erro ao baixar o vídeo do YouTube: {e}")  # Adiciona mensagem de erro ao log
        messagebox.showerror("Erro", f"Erro ao baixar o vídeo do YouTube: {e}")  # Mostra mensagem de erro

# Função para baixar posts do Instagram
def download_instagram(url):
    try:
        instagram_dir = os.path.join('downloads-Instagram')  # Define o diretório de download
        os.makedirs(instagram_dir, exist_ok=True)  # Cria o diretório se não existir
        
        start_time = time.time()  # Marca o tempo de início do download
        
        loader = instaloader.Instaloader(
            download_pictures=False,  # Não baixa imagens
            download_video_thumbnails=False,  # Não baixa miniaturas de vídeos
            save_metadata=False,  # Não salva metadados
            post_metadata_txt_pattern="",  # Não salva metadados em texto
            filename_pattern='{owner_username} - {mediaid}'  # Define o padrão de nome do arquivo
        )
        shortcode = url.strip('/').split('/')[-1]  # Obtém o shortcode do URL
        post = instaloader.Post.from_shortcode(loader.context, shortcode)  # Obtém o post a partir do shortcode
        username = post.owner_username  # Obtém o nome de usuário do dono do post
        
        # Baixar o post diretamente para o diretório de saída
        loader.download_post(post, target=instagram_dir)

        # Atualizar a barra de progresso para 100% quando o download estiver completo
        update_progress_bar(progress, 100)

        end_time = time.time()  # Marca o tempo de término do download
        elapsed_time = end_time - start_time  # Calcula o tempo decorrido
        
        log_message(f"Vídeo de '{username}' do Instagram baixado em {elapsed_time:.2f} segundos!")  # Adiciona mensagem ao log
        messagebox.showinfo("Sucesso", "Download do vídeo do Instagram concluído com sucesso!")  # Mostra mensagem de sucesso
        threading.Thread(target=reset_progress_bar, args=(progress,)).start()  # Reseta a barra de progresso após alguns segundos
    
    except Exception as e:
        log_message(f"Erro ao baixar o vídeo do Instagram: {e}")  # Adiciona mensagem de erro ao log
        messagebox.showerror("Erro", f"Erro ao baixar o vídeo do Instagram: {e}")  # Mostra mensagem de erro

# Função para baixar vídeos do Twitter
def download_twitter(url, format_choice):
    try:
        twitter_dir = os.path.join('downloads-Twitter')  # Define o diretório de download
        os.makedirs(twitter_dir, exist_ok=True)  # Cria o diretório se não existir

        
        start_time = time.time()  # Marca o tempo de início do download
        
        # Função de callback para atualizar a barra de progresso
        def progress_hook(d):
            if d['status'] == 'downloading':  # Verifica se o status é 'downloading'
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')  # Obtém o total de bytes
                if total_bytes:
                    percentage = d['downloaded_bytes'] / total_bytes * 100  # Calcula a porcentagem de download
                    update_progress_bar(progress, percentage)  # Atualiza a barra de progresso
        
        # Opções de configuração para o yt_dlp
        ydl_opts = {
            'outtmpl': os.path.join(twitter_dir, '%(title)s_' + format_choice + '.%(ext)s'), # Define o padrão de nome do arquivo de saída, incluindo o sufixo do formato escolhido (mp3 ou mp4)
            'format': 'bestaudio/best' if format_choice == 'mp3' else 'bestvideo+bestaudio/best', # Define o formato de download: 'bestaudio/best' para mp3, 'bestvideo+bestaudio/best' para mp4
            'merge_output_format': 'mp4' if format_choice == 'mp4' else None, # Define o formato de saída como mp4 se o formato escolhido for mp4
            'progress_hooks': [progress_hook], # Adiciona a função de callback para atualizar a barra de progresso durante o download
            'postprocessors': [{ # Configurações para pós-processamento: extrai o áudio e converte para mp3 se o formato escolhido for mp3
                'key': 'FFmpegExtractAudio', # Utiliza o FFmpeg para extrair o áudio
                'preferredcodec': 'mp3', # Define o codec de áudio como mp3
                'preferredquality': '192', # Define a qualidade do áudio como 192 kbps
            }] if format_choice == 'mp3' else [],
            'restrictfilenames': True,
            'trim_file_name': 50
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)  # Extrai informações e baixa o vídeo
            video_title = info_dict.get('title', 'Vídeo')  # Obtém o título do vídeo
            
        end_time = time.time()  # Marca o tempo de término do download
        elapsed_time = end_time - start_time  # Calcula o tempo decorrido
        
        log_message(f"Vídeo '{video_title}' do Twitter baixado em {elapsed_time:.2f} segundos!")  # Adiciona mensagem ao log
        messagebox.showinfo("Sucesso", f"Download do vídeo do Twitter '{video_title}' concluído com sucesso!")  # Mostra mensagem de sucesso
        threading.Thread(target=reset_progress_bar, args=(progress,)).start()  # Reseta a barra de progresso após alguns segundos
    
    except Exception as e:
        log_message(f"Erro ao baixar o vídeo do Twitter: {e}")  # Adiciona mensagem de erro ao log
        messagebox.showerror("Erro", f"Erro ao baixar o vídeo do Twitter: {e}")  # Mostra mensagem de erro

# Função para determinar qual método de download usar com base na URL
def download_file():
    url = url_var.get()  # Obtém a URL do campo de entrada
    parsed_url = urlparse(url)  # Faz o parsing da URL
    format_choice = format_var.get()

    # Reset progress bar
    progress.set(0)  # Reseta a barra de progresso para 0

    # Verifica a URL e chama a função de download correspondente
    if 'youtube.com' in parsed_url.netloc or 'youtu.be' in parsed_url.netloc:
        threading.Thread(target=download_youtube, args=(url, format_choice)).start()
    elif 'twitter.com' in parsed_url.netloc or 'x.com' in parsed_url.netloc:
        sanitized_url = sanitize_twitter_url(url)
        threading.Thread(target=download_twitter, args=(sanitized_url, format_choice)).start()
    elif 'instagram.com' in parsed_url.netloc:
        threading.Thread(target=download_instagram, args=(url,)).start()
    else:
        messagebox.showerror("Erro", "URL não suportada")  # Mostra mensagem de erro se a URL não for suportada

# Configuração da interface do usuário (UI) do CustomTkinter
ctk.set_appearance_mode("dark")  # Define o modo de aparência para escuro
ctk.set_default_color_theme("dark-blue")  # Define o tema de cores para azul escuro

root = ctk.CTk()  # Cria a janela principal
root.title("Multi Downloader")  # Define o título da janela

# Adicionar ícone
root.after(201, lambda :root.iconbitmap('assets/images/icon.ico'))

# Configurar cor de fundo
root.configure(bg='black')

# Armazena URL e formato
url_var = ctk.StringVar()
format_var = StringVar(value='mp4')  # Variável para armazenar a escolha do formato

# Adicionar título
title_label = ctk.CTkLabel(root, text="Multi Downloader", font=('Helvetica', 16, 'bold'), text_color='cyan')
title_label.grid(row=0, column=0, columnspan=3, padx=10, pady=10)

# Adicionar label para URL
url_label = ctk.CTkLabel(root, text="Adicione a URL no espaço abaixo e clique em 'Download'", text_color='white')
url_label.grid(row=1, column=0, columnspan=3, padx=10, pady=10)

# Campo de entrada para URL
ctk.CTkEntry(root, textvariable=url_var, width=400).grid(row=2, column=0, columnspan=2, padx=10, pady=10)

# Botão para iniciar o download
ctk.CTkButton(root, text="Download", command=download_file).grid(row=2, column=2, padx=10, pady=10)

# Adicionar opções de formato
format_label = ctk.CTkLabel(root, text="Formato:", text_color='white')
format_label.grid(row=3, column=0, padx=10, pady=10)

format_mp4 = ctk.CTkRadioButton(root, text="MP4", variable=format_var, value='mp4')
format_mp4.grid(row=3, column=1, padx=10, pady=10)

format_mp3 = ctk.CTkRadioButton(root, text="MP3", variable=format_var, value='mp3')
format_mp3.grid(row=3, column=2, padx=10, pady=10)

progress_label = ctk.CTkLabel(root, text="Progresso:", text_color='white')
progress_label.grid(row=4, column=0, columnspan=3, padx=10, pady=10)

# Adicionar barra de progresso
progress = ctk.CTkProgressBar(root, orientation='horizontal', width=400)
progress.grid(row=5, column=0, columnspan=3, padx=10, pady=10)
progress.set(0) # Iniciar a barra de progresso zerada

# Adicionar label para área de log
log_label = ctk.CTkLabel(root, text="Histórico de Downloads:", text_color='white')
log_label.grid(row=6, column=0, columnspan=3, padx=10, pady=10)

# Adicionar área de log
log_area = ctk.CTkTextbox(root, height=200, width=600, state='disabled', bg_color='black', text_color='white')
log_area.grid(row=7, column=0, columnspan=3, padx=10, pady=10)

# Adicionar scrollbar para a área de log
scrollbar = ctk.CTkScrollbar(root, orientation=ctk.VERTICAL, command=log_area.yview)
scrollbar.grid(row=7, column=3, sticky='ns')
log_area.configure(yscrollcommand=scrollbar.set)

# Iniciar a interface gráfica
root.mainloop()