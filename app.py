from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import yt_dlp
import os
import uuid
import subprocess
import asyncio

app = FastAPI(title="MediaDrop API", version="2.0.0")

print("Current working directory:", os.getcwd())
print("Files in root:", os.listdir())

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
else:
    print("WARNING: static folder not found")

if os.path.exists("templates"):
    templates = Jinja2Templates(directory="templates")
else:
    templates = None
    print("WARNING: templates folder not found")


@app.get("/")
def home(request: Request):
    try:
        if templates:
            return templates.TemplateResponse("index.html", {"request": request})
        return {"message": "Templates not found, API working"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/info")
def get_info(url: str = Form(...)):
    """Get video metadata before downloading."""
    try:
        ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return JSONResponse({
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "thumbnail": info.get("thumbnail", ""),
                "uploader": info.get("uploader", "Unknown"),
                "platform": info.get("extractor_key", "Unknown"),
            })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/download")
def download(url: str = Form(...), format_type: str = Form(...)):
    try:
        os.makedirs("/tmp/mediadrop", exist_ok=True)
        unique_id = str(uuid.uuid4())
        output_template = f"/tmp/mediadrop/{unique_id}.%(ext)s"

        common_opts = {
            "outtmpl": output_template,
            "quiet": False,
            "no_warnings": False,
            # Use cookies workaround for age-restricted / bot-check videos
            "extractor_args": {"youtube": {"skip": ["dash", "hls"]}},
        }

        if format_type == "audio":
            ydl_opts = {
                **common_opts,
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url)
                title = info.get("title", unique_id)
            file_path = f"/tmp/mediadrop/{unique_id}.mp3"
            media_type = "audio/mpeg"
            filename = f"{title[:60]}.mp3"

        elif format_type == "video":
            ydl_opts = {
                **common_opts,
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "merge_output_format": "mp4",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url)
                title = info.get("title", unique_id)
            file_path = f"/tmp/mediadrop/{unique_id}.mp4"
            media_type = "video/mp4"
            filename = f"{title[:60]}.mp4"

        else:
            return JSONResponse({"error": "Invalid format type"}, status_code=400)

        if not os.path.exists(file_path):
            # Try finding any file with the unique_id prefix
            tmp_files = [f for f in os.listdir("/tmp/mediadrop") if unique_id in f]
            if tmp_files:
                file_path = f"/tmp/mediadrop/{tmp_files[0]}"
            else:
                return JSONResponse({"error": "File not generated. The URL may be unsupported or geo-restricted."}, status_code=500)

        return FileResponse(
            file_path,
            media_type=media_type,
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "Sign in" in msg or "bot" in msg.lower():
            msg = "This video requires sign-in or is bot-protected. Try a different URL."
        return JSONResponse({"error": msg}, status_code=422)
    except Exception as e:
        print("DOWNLOAD ERROR:", str(e))
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    try:
        os.makedirs("/tmp/mediadrop", exist_ok=True)
        unique_id = str(uuid.uuid4())
        input_path = f"/tmp/mediadrop/{unique_id}_{file.filename}"
        output_path = f"/tmp/mediadrop/{unique_id}.mp3"

        with open(input_path, "wb") as buffer:
            buffer.write(await file.read())

        result = subprocess.run([
            "ffmpeg", "-i", input_path,
            "-vn", "-ab", "192k",
            "-ar", "44100",
            "-y", output_path
        ], capture_output=True, text=True)

        if result.returncode != 0:
            return JSONResponse({"error": f"FFmpeg error: {result.stderr[-300:]}"}, status_code=500)

        if not os.path.exists(output_path):
            return JSONResponse({"error": "Conversion failed"}, status_code=500)

        base_name = os.path.splitext(file.filename)[0]
        return FileResponse(
            output_path,
            media_type="audio/mpeg",
            filename=f"{base_name}.mp3",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.mp3"'}
        )

    except Exception as e:
        print("UPLOAD ERROR:", str(e))
        return JSONResponse({"error": str(e)}, status_code=500)