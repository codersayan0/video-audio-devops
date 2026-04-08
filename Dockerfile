FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Always pull latest yt-dlp — old versions are the #1 cause of bot blocks
RUN pip install --no-cache-dir --upgrade yt-dlp

COPY app.py .
COPY templates/ templates/
COPY static/ static/

RUN mkdir -p /tmp/mediadrop /etc/secrets \
    && chown -R appuser:appuser /tmp/mediadrop /app

USER appuser

ENV PORT=10000
ENV YT_COOKIE_FILE=/etc/secrets/cookies.txt
# Optional: set YT_PROXY=socks5://user:pass@host:port in Render env vars
ENV YT_PROXY=""

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT} --workers 2"]