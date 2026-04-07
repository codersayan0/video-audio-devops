from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import yt_dlp
import os
import uuid
import subprocess

app = FastAPI()

# 🔍 Debug logs (VERY IMPORTANT)
print("Current working directory:", os.getcwd())
print("Files in root:", os.listdir())

# ✅ Safe static mount
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
else:
    print("WARNING: static folder not found")

# ✅ Safe template setup
if os.path.exists("templates"):
    templates = Jinja2Templates(directory="templates")
else:
    templates = None
    print("WARNING: templates folder not found")


# 🔹 Home route (safe)
@app.get("/")
def home(request: Request):
    try:
        if templates:
            return templates.TemplateResponse("index.html", {"request": request})
        else:
            return {"message": "Templates not found, API working"}
    except Exception as e:
        print("ERROR in home:", str(e))
        return {"error": str(e)}


# 🔹 Download API
@app.post("/download")
def download(url: str = Form(...), format_type: str = Form(...)):
    try:
        os.makedirs("/tmp", exist_ok=True)

        unique_id = str(uuid.uuid4())
        output_template = f"/tmp/{unique_id}.%(ext)s"

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

        elif format_type == "video":
            ydl_opts = {
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "outtmpl": output_template,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            file_path = f"/tmp/{unique_id}.mp4"

        else:
            return {"error": "Invalid format type"}

        if not os.path.exists(file_path):
            return {"error": "File not generated"}

        return FileResponse(
            file_path,
            media_type="application/octet-stream",
            filename=os.path.basename(file_path)
        )

    except Exception as e:
        print("DOWNLOAD ERROR:", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)


# 🔹 Upload API
@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    try:
        os.makedirs("/tmp", exist_ok=True)

        unique_id = str(uuid.uuid4())
        input_path = f"/tmp/{unique_id}_{file.filename}"
        output_path = f"/tmp/{unique_id}.mp3"

        with open(input_path, "wb") as buffer:
            buffer.write(await file.read())

        subprocess.run([
            "ffmpeg",
            "-i", input_path,
            "-vn",
            "-ab", "192k",
            output_path
        ], check=True)

        if not os.path.exists(output_path):
            return {"error": "Conversion failed"}

        return FileResponse(
            output_path,
            media_type="audio/mpeg",
            filename="converted_audio.mp3"
        )

    except Exception as e:
        print("UPLOAD ERROR:", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)