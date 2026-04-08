from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import yt_dlp
import os
import uuid
import subprocess

app = FastAPI(title="MediaDrop API", version="2.1.0")

print("CWD:", os.getcwd())
print("Files:", os.listdir())

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
else:
    print("WARNING: static/ not found")

if os.path.exists("templates"):
    templates = Jinja2Templates(directory="templates")
else:
    templates = None
    print("WARNING: templates/ not found")


# ── Shared yt-dlp options that help bypass bot detection ──
def base_ydl_opts(output_template: str) -> dict:
    return {
        "outtmpl": output_template,
        "quiet": False,
        "no_warnings": False,
        # Use the android client — bypasses most sign-in/bot checks
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
        # Spoof a real browser user-agent
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 11; Pixel 5) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/90.0.4430.91 Mobile Safari/537.36"
            )
        },
    }


@app.get("/")
def home(request: Request):
    if templates:
        return templates.TemplateResponse("index.html", {"request": request})
    return {"message": "Templates not found, API working"}


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.1.0"}


@app.post("/info")
def get_info(url: str = Form(...)):
    """Fetch video metadata without downloading."""
    try:
        ydl_opts = {
            **base_ydl_opts("/tmp/mediadrop/%(id)s.%(ext)s"),
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return JSONResponse({
                "title":     info.get("title", "Unknown"),
                "duration":  info.get("duration", 0),
                "thumbnail": info.get("thumbnail", ""),
                "uploader":  info.get("uploader", "Unknown"),
                "platform":  info.get("extractor_key", "Unknown"),
            })
    except yt_dlp.utils.DownloadError as e:
        return JSONResponse({"error": friendly_error(str(e))}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/download")
def download(url: str = Form(...), format_type: str = Form(...)):
    try:
        os.makedirs("/tmp/mediadrop", exist_ok=True)
        uid = str(uuid.uuid4())
        tmpl = f"/tmp/mediadrop/{uid}.%(ext)s"

        if format_type == "audio":
            ydl_opts = {
                **base_ydl_opts(tmpl),
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url)

            file_path = f"/tmp/mediadrop/{uid}.mp3"
            media_type = "audio/mpeg"
            ext = "mp3"

        elif format_type == "video":
            ydl_opts = {
                **base_ydl_opts(tmpl),
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "merge_output_format": "mp4",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url)

            file_path = f"/tmp/mediadrop/{uid}.mp4"
            media_type = "video/mp4"
            ext = "mp4"

        else:
            return JSONResponse({"error": "Invalid format type"}, status_code=400)

        # Fallback: scan /tmp/mediadrop for file matching uid
        if not os.path.exists(file_path):
            matches = [f for f in os.listdir("/tmp/mediadrop") if f.startswith(uid)]
            if matches:
                file_path = f"/tmp/mediadrop/{matches[0]}"
            else:
                return JSONResponse(
                    {"error": "File not generated. The URL may be unsupported, geo-restricted, or age-restricted."},
                    status_code=500
                )

        title = (info.get("title") or uid)[:80]
        # Sanitise filename for Content-Disposition header
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_()").strip() or uid
        filename = f"{safe_title}.{ext}"

        return FileResponse(
            file_path,
            media_type=media_type,
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except yt_dlp.utils.DownloadError as e:
        return JSONResponse({"error": friendly_error(str(e))}, status_code=422)
    except Exception as e:
        print("DOWNLOAD ERROR:", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    try:
        os.makedirs("/tmp/mediadrop", exist_ok=True)
        uid = str(uuid.uuid4())
        in_path  = f"/tmp/mediadrop/{uid}_{file.filename}"
        out_path = f"/tmp/mediadrop/{uid}.mp3"

        with open(in_path, "wb") as buf:
            buf.write(await file.read())

        result = subprocess.run(
            ["ffmpeg", "-i", in_path, "-vn", "-ab", "192k", "-ar", "44100", "-y", out_path],
            capture_output=True, text=True
        )
        if result.returncode != 0 or not os.path.exists(out_path):
            return JSONResponse(
                {"error": f"FFmpeg conversion failed: {result.stderr[-300:]}"},
                status_code=500
            )

        base = os.path.splitext(file.filename)[0]
        safe = "".join(c for c in base if c.isalnum() or c in " -_").strip() or "audio"
        filename = f"{safe}.mp3"

        return FileResponse(
            out_path,
            media_type="audio/mpeg",
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        print("UPLOAD ERROR:", e)
        return JSONResponse({"error": str(e)}, status_code=500)


def friendly_error(msg: str) -> str:
    """Turn yt-dlp's raw error into a human-readable message."""
    m = msg.lower()
    if "sign in" in m or "login" in m:
        return (
            "YouTube blocked this download (bot/sign-in check). "
            "Try a different video, or use the 'Upload file' option instead."
        )
    if "private" in m:
        return "This video is private and cannot be downloaded."
    if "geo" in m or "available in your country" in m:
        return "This video is geo-restricted and not available from this server's location."
    if "copyright" in m:
        return "This video has been removed due to a copyright claim."
    if "age" in m:
        return "This video is age-restricted. Age-restricted videos cannot be downloaded without authentication."
    if "404" in m or "not found" in m:
        return "Video not found. Check the URL and try again."
    return msg