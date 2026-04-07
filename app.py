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


# 🔹 Download YouTube / Instagram / Facebook
@app.post("/download")
def download(url: str = Form(...), format_type: str = Form(...)):
    try:
        os.makedirs("/tmp", exist_ok=True)

        unique_id = str(uuid.uuid4())
        output_template = f"/tmp/{unique_id}.%(ext)s"

        # 🎵 AUDIO DOWNLOAD
        if format_type == "audio":
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": output_template,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            file_path = f"/tmp/{unique_id}.mp3"

        # 🎬 VIDEO DOWNLOAD
        elif format_type == "video":
            ydl_opts = {
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "outtmpl": output_template,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            file_path = f"/tmp/{unique_id}.mp4"

        # 🔍 Check file exists
        if not os.path.exists(file_path):
            return {"error": "File not generated. Check ffmpeg or yt-dlp."}

        return FileResponse(
            file_path,
            media_type="application/octet-stream",
            filename=os.path.basename(file_path)
        )

    except Exception as e:
        print("ERROR:", str(e))
        return {"error": str(e)}


# 🔹 Upload video → convert to MP3
@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    try:
        os.makedirs("/tmp", exist_ok=True)

        unique_id = str(uuid.uuid4())
        input_path = f"/tmp/{unique_id}_{file.filename}"
        output_path = f"/tmp/{unique_id}.mp3"

        # Save uploaded file
        with open(input_path, "wb") as buffer:
            buffer.write(await file.read())

        # Convert using ffmpeg
        subprocess.run([
            "ffmpeg",
            "-i", input_path,
            "-vn",
            "-ab", "192k",
            output_path
        ], check=True)

        # Check output
        if not os.path.exists(output_path):
            return {"error": "Conversion failed"}

        return FileResponse(
            output_path,
            media_type="audio/mpeg",
            filename="converted_audio.mp3"
        )

    except Exception as e:
        print("ERROR:", str(e))
        return {"error": str(e)}