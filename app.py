from fastapi import FastAPI, Request, Form
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
import yt_dlp
import os
import uuid

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/download")
def download_audio(url: str = Form(...)):
    os.makedirs("downloads", exist_ok=True)

    unique_id = str(uuid.uuid4())
    output_template = f"downloads/{unique_id}.%(ext)s"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return FileResponse(
        f"downloads/{unique_id}.mp3",
        media_type="audio/mpeg",
        filename="audio.mp3"
    )