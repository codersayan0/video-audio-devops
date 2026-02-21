from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import yt_dlp
import os
import uuid
import subprocess

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 🔹 Download YouTube, Instagram, Facebook Video/Audio → Convert to MP3/MP4

@app.post("/download")
def download(url: str = Form(...), format_type: str = Form(...)):
    os.makedirs("downloads", exist_ok=True)

    unique_id = str(uuid.uuid4())
    output_template = f"downloads/{unique_id}.%(ext)s"

    if format_type == "audio":
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            mp3_file = f"downloads/{unique_id}.mp3"

        return FileResponse(
            mp3_file,
            media_type="audio/mpeg",
            filename="audio.mp3"
        )

    elif format_type == "video":
        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": output_template,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        return FileResponse(
            filename,
            media_type="video/mp4",
            filename="video.mp4"
        )


# 🔹 Upload Video From Computer → Convert to MP3
@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    os.makedirs("downloads", exist_ok=True)

    unique_id = str(uuid.uuid4())
    input_path = f"downloads/{unique_id}_{file.filename}"
    output_path = f"downloads/{unique_id}.mp3"

    # Save uploaded file
    with open(input_path, "wb") as buffer:
        buffer.write(await file.read())

    # Convert to MP3 using ffmpeg
    subprocess.run([
        "ffmpeg",
        "-i", input_path,
        "-vn",
        "-ab", "192k",
        output_path
    ])

    return FileResponse(output_path,
                        media_type="audio/mpeg",
                        filename="converted_audio.mp3")