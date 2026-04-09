<div align="center">

```
███╗   ███╗███████╗██████╗ ██╗ █████╗ ██████╗ ██████╗  ██████╗ ██████╗
████╗ ████║██╔════╝██╔══██╗██║██╔══██╗██╔══██╗██╔══██╗██╔═══██╗██╔══██╗
██╔████╔██║█████╗  ██║  ██║██║███████║██║  ██║██████╔╝██║   ██║██████╔╝
██║╚██╔╝██║██╔══╝  ██║  ██║██║██╔══██║██║  ██║██╔══██╗██║   ██║██╔═══╝
██║ ╚═╝ ██║███████╗██████╔╝██║██║  ██║██████╔╝██║  ██║╚██████╔╝██║
╚═╝     ╚═╝╚══════╝╚═════╝ ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝
```

**Download anything. Instantly. From anywhere.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Render](https://img.shields.io/badge/Render-Deployed-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://render.com)
[![License](https://img.shields.io/badge/License-MIT-F7DF1E?style=for-the-badge)](LICENSE)

</div>

---

## 👁️ What Is This?

**MediaDrop** is a cloud-native, Dockerized video/audio downloader built as a **real-world DevOps project** — not just a tutorial clone. It downloads from 1000+ platforms, converts video to MP3 using FFmpeg, and ships through a fully automated CI/CD pipeline to Render.

> *"Built to learn DevOps by doing DevOps."* — Sayan Mandal

---

## 🗺️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                            │
│              Paste URL  ──or──  Upload File                     │
└─────────────────────────┬───────────────────────────────────────┘
                          │  HTTP POST
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI  BACKEND                              │
│                                                                  │
│   /info     ──► yt-dlp (metadata only)                          │
│   /download ──► yt-dlp ──► FFmpeg (if audio) ──► FileResponse  │
│   /upload   ──► FFmpeg (mp4 → mp3) ──► FileResponse            │
│   /health   ──► {"status": "ok"}  ← Render health check        │
└──────────────┬──────────────────────────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
  yt-dlp 🔗         FFmpeg 🎬
  (fetch media)   (transcode)
       │                │
       └───────┬────────┘
               │
        /tmp/mediadrop/
        (temp storage)
               │
               ▼
        📥 File streamed to user
```

---

## ⚙️ DevOps Pipeline

```
  You write code
       │
       ▼
  git push ──► GitHub
       │
       ▼
  GitHub Actions triggers
  ┌────────────────────────────────────────┐
  │  Step 1 ─ 🧪  Lint + smoke test       │
  │  Step 2 ─ 🐳  Docker build & push     │
  │               (→ GitHub Container      │
  │                  Registry / GHCR)      │
  │  Step 3 ─ 🚀  Trigger Render deploy   │
  └────────────────────────────────────────┘
       │
       ▼
  Render pulls image
  and serves live app
       │
       ▼
  🌐 Your URL is live
```

Every single `git push` to `main` goes through this loop automatically.

---

## 🛠️ Tech Stack

| Layer | Tool | Why |
|---|---|---|
| 🖥️ Backend | FastAPI | Async, fast, auto-docs at `/docs` |
| 🎨 Frontend | HTML + CSS (inline) | Zero build step, always loads |
| 📥 Downloader | yt-dlp | 1000+ sites, active maintenance |
| 🎬 Processor | FFmpeg | Industry-standard audio/video |
| 📦 Container | Docker | Same behaviour everywhere |
| ☁️ Hosting | Render | Free tier, auto-deploy from GitHub |
| 🔄 CI/CD | GitHub Actions | Lint → Build → Deploy on every push |
| 🗂️ Registry | GHCR | Docker image storage |

---

## 🚀 Quick Start

### Run with Docker (recommended)

```bash
# Clone the repo
git clone https://github.com/codersayan0/video-audio-devops.git
cd video-audio-devops

# Build and run
docker build -t mediadrop .
docker run -p 10000:10000 mediadrop

# Open in browser
open http://localhost:10000
```

### Run without Docker

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 10000
```

---

## 📡 API Reference

> Interactive docs available at `/docs` when running locally.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web UI |
| `GET` | `/health` | Health check — returns `{"status":"ok"}` |
| `POST` | `/info` | Fetch video title, thumbnail, duration |
| `POST` | `/download` | Download as `mp3` or `mp4` |
| `POST` | `/upload` | Convert uploaded video file to MP3 |

**Example `/download` request:**
```bash
curl -X POST http://localhost:10000/download \
  -F "url=https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  -F "format_type=audio" \
  --output audio.mp3
```

---

## 🌍 Supported Platforms

```
YouTube    Instagram    Facebook    TikTok    Twitter/X
Vimeo      Twitch       Reddit      SoundCloud  Dailymotion
                    + 1000 more via yt-dlp
```

Full list → [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

---

## 🏗️ Project Structure

```
video-audio-devops/
│
├── app.py                    ← FastAPI backend (all routes)
├── requirements.txt          ← Python dependencies
├── Dockerfile                ← Container definition
├── render.yaml               ← Render deployment config (IaC)
│
├── templates/
│   └── index.html            ← Frontend (dark UI, inline CSS)
│
├── static/
│   └── style.css             ← Styles
│
├── .github/
│   └── workflows/
│       └── docker.yml        ← CI/CD pipeline
│
└── README.md                 ← You are here
```

---

## ☁️ Deploy to Render

**Option A — One click with render.yaml**

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New → Blueprint**
3. Connect your repo → **Apply**

**Option B — Manual**

1. Render → **New → Web Service** → connect repo
2. Runtime: `Docker` | Port: `10000`
3. Deploy

**For GitHub Actions auto-deploy**, add this secret in your repo settings:

| Secret Name | Where to get it |
|---|---|
| `RENDER_DEPLOY_HOOK_URL` | Render → Service → Settings → Deploy Hook |

---

## ⚠️ Known Limitations

- YouTube may block datacenter IPs — fix: add `cookies.txt` as a Render Secret File at `/etc/secrets/cookies.txt`
- Private / age-restricted videos require authenticated cookies
- Free Render tier sleeps after 15 min of inactivity (first request is slow)
- Large files (500MB+) may time out on free tier

---

## 🗺️ Roadmap

- [ ] Real-time download progress bar via WebSocket
- [ ] Queue system for concurrent downloads
- [ ] Auto-delete temp files after delivery
- [ ] Kubernetes deployment config
- [ ] Nginx reverse proxy for production
- [ ] Authentication system

---

## 👨‍💻 Author

<div align="center">

**Sayan Mandal**

B.Tech Computer Science & Engineering

Aspiring DevOps & Software Engineer

[![GitHub](https://img.shields.io/badge/GitHub-codersayan0-181717?style=for-the-badge&logo=github)](https://github.com/codersayan0)

</div>

---

<div align="center">

Built with ❤️, Docker, and a lot of `git push`

*If this project helped you, drop a ⭐ on GitHub!*

</div>