FROM python:3.11

RUN apt update && apt install -y ffmpeg

WORKDIR /app
COPY . .

RUN pip install fastapi uvicorn yt-dlp jinja2 python-multipart

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]