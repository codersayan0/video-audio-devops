from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import yt_dlp
import os, uuid, subprocess, re

app = FastAPI(title="MediaDrop API", version="3.0.0")

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
if os.path.exists("templates"):
    templates = Jinja2Templates(directory="templates")
else:
    templates = None

COOKIE_FILE = os.environ.get("YT_COOKIE_FILE", "/etc/secrets/cookies.txt")
PROXY       = os.environ.get("YT_PROXY", "")   # e.g. "socks5://user:pass@host:port"


# ─────────────────────────────────────────────────────────────
# URL normalisation
# Convert Shorts / mobile / tracking URLs → clean watch URL
# ─────────────────────────────────────────────────────────────
def normalise_url(url: str) -> str:
    url = url.strip()

    # youtube.com/shorts/VIDEO_ID  →  youtube.com/watch?v=VIDEO_ID
    shorts = re.match(r"https?://(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]+)", url)
    if shorts:
        vid = shorts.group(1)
        clean = f"https://www.youtube.com/watch?v={vid}"
        print(f"[normalise] Shorts → {clean}")
        return clean

    # youtu.be/VIDEO_ID  →  youtube.com/watch?v=VIDEO_ID
    short_link = re.match(r"https?://youtu\.be/([A-Za-z0-9_-]+)", url)
    if short_link:
        vid = short_link.group(1)
        clean = f"https://www.youtube.com/watch?v={vid}"
        print(f"[normalise] youtu.be → {clean}")
        return clean

    # Strip tracking params (?si=...) but keep ?v=
    if "youtube.com/watch" in url:
        vid_match = re.search(r"[?&]v=([A-Za-z0-9_-]+)", url)
        if vid_match:
            clean = f"https://www.youtube.com/watch?v={vid_match.group(1)}"
            print(f"[normalise] Stripped tracking → {clean}")
            return clean

    return url


# ─────────────────────────────────────────────────────────────
# Build yt-dlp option sets — tried in order until one works
# ─────────────────────────────────────────────────────────────
def _common(tmpl: str) -> dict:
    opts: dict = {
        "outtmpl":          tmpl,
        "quiet":            False,
        "no_warnings":      False,
        "retries":          3,
        "fragment_retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    if os.path.exists(COOKIE_FILE):
        opts["cookiefile"] = COOKIE_FILE
        print(f"[yt-dlp] cookie file: {COOKIE_FILE}")
    if PROXY:
        opts["proxy"] = PROXY
        print(f"[yt-dlp] proxy: {PROXY}")
    return opts


def _strategies(tmpl: str) -> list[dict]:
    """
    Return a list of yt-dlp option dicts to try in sequence.
    Each strategy targets a different YouTube internal API client.
    """
    base = _common(tmpl)

    # Strategy 1 — tv_embedded: no sign-in required for most public videos
    s1 = {**base, "extractor_args": {"youtube": {
        "player_client": ["tv_embedded"],
        "skip": ["translated_subs"],
    }}}

    # Strategy 2 — mweb (mobile web): different bot-check path
    s2 = {**base, "extractor_args": {"youtube": {
        "player_client": ["mweb"],
        "skip": ["translated_subs"],
    }}}

    # Strategy 3 — android_vr: often skips IP-based checks
    s3 = {**base, "extractor_args": {"youtube": {
        "player_client": ["android_vr"],
        "skip": ["translated_subs"],
    }}}

    # Strategy 4 — web_creator: creator studio client
    s4 = {**base, "extractor_args": {"youtube": {
        "player_client": ["web_creator"],
        "skip": ["translated_subs"],
    }}}

    # Strategy 5 — ios: Apple client, different signing
    s5 = {**base, "extractor_args": {"youtube": {
        "player_client": ["ios"],
        "skip": ["translated_subs"],
    }}}

    return [s1, s2, s3, s4, s5]


def _is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


def _try_download(url: str, extra_opts: dict, tmpl: str) -> dict:
    """
    Try each strategy in turn. Returns yt-dlp info dict on success.
    Raises the last exception if all strategies fail.
    """
    if not _is_youtube(url):
        # Non-YouTube: single attempt with common opts
        opts = {**_common(tmpl), **extra_opts}
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url)

    last_err = None
    for i, strategy in enumerate(_strategies(tmpl), 1):
        opts = {**strategy, **extra_opts}
        try:
            print(f"[yt-dlp] Trying strategy {i}/5 for {url}")
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url)
            print(f"[yt-dlp] Strategy {i} succeeded ✓")
            return info
        except yt_dlp.utils.DownloadError as e:
            last_err = e
            msg = str(e).lower()
            # Only retry on bot/sign-in errors — fail fast on others
            if not any(k in msg for k in ["sign in", "bot", "confirm", "unavailable", "blocked"]):
                raise
            print(f"[yt-dlp] Strategy {i} failed: {str(e)[:120]}")

    raise last_err


def _try_info(url: str, tmpl: str) -> dict:
    """Same as _try_download but skip_download=True."""
    extra = {"skip_download": True}
    if not _is_youtube(url):
        opts = {**_common(tmpl), **extra}
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    last_err = None
    for i, strategy in enumerate(_strategies(tmpl), 1):
        opts = {**strategy, **extra}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as e:
            last_err = e
            msg = str(e).lower()
            if not any(k in msg for k in ["sign in", "bot", "confirm", "unavailable", "blocked"]):
                raise
    raise last_err


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────
@app.get("/")
def home(request: Request):
    if templates:
        return templates.TemplateResponse("index.html", {"request": request})
    return {"message": "Templates not found"}


@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0"}


@app.post("/info")
def get_info(url: str = Form(...)):
    try:
        url = normalise_url(url)
        os.makedirs("/tmp/mediadrop", exist_ok=True)
        info = _try_info(url, "/tmp/mediadrop/%(id)s.%(ext)s")
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
        url = normalise_url(url)
        os.makedirs("/tmp/mediadrop", exist_ok=True)
        uid  = str(uuid.uuid4())
        tmpl = f"/tmp/mediadrop/{uid}.%(ext)s"

        if format_type == "audio":
            extra = {
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key":             "FFmpegExtractAudio",
                    "preferredcodec":  "mp3",
                    "preferredquality":"192",
                }],
            }
            info      = _try_download(url, extra, tmpl)
            file_path = f"/tmp/mediadrop/{uid}.mp3"
            media_type= "audio/mpeg"
            ext       = "mp3"

        elif format_type == "video":
            extra = {
                "format":               "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "merge_output_format":  "mp4",
            }
            info      = _try_download(url, extra, tmpl)
            file_path = f"/tmp/mediadrop/{uid}.mp4"
            media_type= "video/mp4"
            ext       = "mp4"

        else:
            return JSONResponse({"error": "Invalid format type"}, status_code=400)

        # Fallback file search if yt-dlp wrote a different extension
        if not os.path.exists(file_path):
            matches = sorted(
                [f for f in os.listdir("/tmp/mediadrop") if f.startswith(uid)],
                key=lambda f: os.path.getsize(f"/tmp/mediadrop/{f}"),
                reverse=True
            )
            if matches:
                file_path = f"/tmp/mediadrop/{matches[0]}"
            else:
                return JSONResponse({"error": "File not generated."}, status_code=500)

        title      = (info.get("title") or uid)[:80]
        safe_title = re.sub(r'[^\w\s\-()]', '', title).strip() or uid
        filename   = f"{safe_title}.{ext}"

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
        uid      = str(uuid.uuid4())
        in_path  = f"/tmp/mediadrop/{uid}_{file.filename}"
        out_path = f"/tmp/mediadrop/{uid}.mp3"

        with open(in_path, "wb") as buf:
            buf.write(await file.read())

        r = subprocess.run(
            ["ffmpeg", "-i", in_path, "-vn", "-ab", "192k", "-ar", "44100", "-y", out_path],
            capture_output=True, text=True
        )
        if r.returncode != 0 or not os.path.exists(out_path):
            return JSONResponse({"error": f"FFmpeg error: {r.stderr[-300:]}"}, status_code=500)

        base     = os.path.splitext(file.filename)[0]
        safe     = re.sub(r'[^\w\s\-]', '', base).strip() or "audio"
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


# ─────────────────────────────────────────────────────────────
# Error messages
# ─────────────────────────────────────────────────────────────
def friendly_error(msg: str) -> str:
    m = msg.lower()
    if any(k in m for k in ["sign in", "login", "bot", "confirm your age", "jsinterp"]):
        if os.path.exists(COOKIE_FILE):
            return "YouTube blocked even with cookies — cookies may be expired. Re-export from your browser."
        return (
            "YouTube is blocking this server's IP. "
            "To fix permanently: export cookies.txt from your browser and add it as a "
            "Render Secret File at /etc/secrets/cookies.txt (see README)."
        )
    if "private"  in m: return "This video is private."
    if "geo"      in m or "your country" in m: return "This video is geo-restricted."
    if "copyright"in m: return "Removed due to copyright."
    if "age"      in m: return "Age-restricted — add cookies.txt to unlock."
    if "404"      in m or "not found" in m: return "Video not found. Check the URL."
    return msg