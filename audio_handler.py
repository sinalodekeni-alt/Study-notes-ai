import yt_dlp
import whisper

def download_youtube_audio(url):
    ydl_opts = {'format': 'bestaudio/best', 'outtmpl': 'temp_audio.mp3'}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return "temp_audio.mp3"

def transcribe_audio(audio_path):
    # Runs locally on the student's machine for free
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    return result["text"]
