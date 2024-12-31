import unittest
from unittest.mock import patch, MagicMock
from downloader import download_youtube, download_instagram, download_twitter, download_facebook, sanitize_twitter_url

class TestDownloader(unittest.TestCase):

    @patch('downloader.yt_dlp.YoutubeDL')
    @patch('downloader.update_progress_bar')
    @patch('downloader.log_message')
    @patch('downloader.messagebox.showinfo')
    def test_download_youtube(self, mock_showinfo, mock_log_message, mock_update_progress_bar, mock_youtube_dl):
        mock_instance = mock_youtube_dl.return_value.__enter__.return_value
        mock_instance.extract_info.return_value = {'title': 'Test Video'}
        
        download_youtube('http://youtube.com/watch?v=12345', 'mp4')
        
        mock_youtube_dl.assert_called_once()
        mock_instance.extract_info.assert_called_once_with('http://youtube.com/watch?v=12345', download=True)
        mock_log_message.assert_called_with("Vídeo 'Test Video' do Youtube baixado em 0.00 segundos!")
        mock_showinfo.assert_called_with("Sucesso", "Download do vídeo 'Test Video' concluído com sucesso!")

    @patch('downloader.instaloader.Instaloader')
    @patch('downloader.update_progress_bar')
    @patch('downloader.log_message')
    @patch('downloader.messagebox.showinfo')
    def test_download_instagram(self, mock_showinfo, mock_log_message, mock_update_progress_bar, mock_instaloader):
        mock_loader = mock_instaloader.return_value
        mock_post = MagicMock()
        mock_post.owner_username = 'testuser'
        mock_loader.context = MagicMock()
        mock_loader.download_post = MagicMock()
        mock_instaloader.Post.from_shortcode.return_value = mock_post
        
        download_instagram('http://instagram.com/p/12345')
        
        mock_instaloader.Post.from_shortcode.assert_called_once_with(mock_loader.context, '12345')
        mock_loader.download_post.assert_called_once_with(mock_post, target='downloads-Instagram')
        mock_log_message.assert_called_with("Vídeo de 'testuser' do Instagram baixado em 0.00 segundos!")
        mock_showinfo.assert_called_with("Sucesso", "Download do vídeo do Instagram concluído com sucesso!")

    @patch('downloader.yt_dlp.YoutubeDL')
    @patch('downloader.update_progress_bar')
    @patch('downloader.log_message')
    @patch('downloader.messagebox.showinfo')
    def test_download_twitter(self, mock_showinfo, mock_log_message, mock_update_progress_bar, mock_youtube_dl):
        mock_instance = mock_youtube_dl.return_value.__enter__.return_value
        mock_instance.extract_info.return_value = {'title': 'Test Video'}
        
        download_twitter('http://twitter.com/user/status/12345', 'mp4')
        
        mock_youtube_dl.assert_called_once()
        mock_instance.extract_info.assert_called_once_with('http://twitter.com/user/status/12345', download=True)
        mock_log_message.assert_called_with("Vídeo 'Test Video' do Twitter baixado em 0.00 segundos!")
        mock_showinfo.assert_called_with("Sucesso", "Download do vídeo do Twitter 'Test Video' concluído com sucesso!")

    @patch('downloader.yt_dlp.YoutubeDL')
    @patch('downloader.update_progress_bar')
    @patch('downloader.log_message')
    @patch('downloader.messagebox.showinfo')
    def test_download_facebook(self, mock_showinfo, mock_log_message, mock_update_progress_bar, mock_youtube_dl):
        mock_instance = mock_youtube_dl.return_value.__enter__.return_value
        mock_instance.extract_info.return_value = {'title': 'Test Video'}
        
        download_facebook('http://facebook.com/video/12345', 'mp4')
        
        mock_youtube_dl.assert_called_once()
        mock_instance.extract_info.assert_called_once_with('http://facebook.com/video/12345', download=True)
        mock_log_message.assert_called_with("Vídeo 'Test Video' do Facebook baixado em 0.00 segundos!")
        mock_showinfo.assert_called_with("Sucesso", "Download do vídeo 'Test Video' concluído com sucesso!")

    def test_sanitize_twitter_url(self):
        url = "https://twitter.com/user/status/12345"
        sanitized_url = sanitize_twitter_url(url)
        self.assertEqual(sanitized_url, "https://twitter.com/i/status/12345")

if __name__ == '__main__':
    unittest.main()