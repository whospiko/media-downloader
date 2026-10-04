import os
import re
import uuid
import threading
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file, abort
import yt_dlp

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DOWNLOAD_DIR = BASE_DIR / "downloads"
DEFAULT_DOWNLOAD_DIR.mkdir(exist_ok=True)

JOBS = {}
BULK_JOBS = {}

# Limit to 2 simultaneous downloads across ALL jobs to avoid CDN throttling
DOWNLOAD_SEMAPHORE = threading.Semaphore(2)

YT_REGEX = re.compile(
    r"^(https?://)?(www\.)?"
    r"(youtube\.com/(watch\?v=|shorts/|embed/)|youtu\.be/)"
    r"[\w\-]+"
)

# Valid audio quality targets (kbps)
VALID_QUALITIES = {"128", "192", "256", "320"}


def is_valid_youtube_url(url: str) -> bool:
    return bool(url and YT_REGEX.match(url.strip()))


def resolve_output_dir(user_path: str | None) -> Path:
    if not user_path or not user_path.strip():
        return DEFAULT_DOWNLOAD_DIR

    p = Path(user_path.strip()).expanduser()
    if not p.is_absolute():
        p = BASE_DIR / p

    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise ValueError(f"Cannot create/use folder '{p}': {e}")

    if not p.is_dir():
        raise ValueError(f"'{p}' is not a directory.")
    if not os.access(p, os.W_OK):
        raise ValueError(f"No write permission for '{p}'.")

    return p


def progress_hook(job_id):
    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            percent = (downloaded / total * 100) if total else 0
            JOBS[job_id].update(
                status="downloading",
                percent=round(percent, 1),
                speed=d.get("speed"),
                eta=d.get("eta"),
                downloaded_bytes=downloaded,
                total_bytes=total,
            )
        elif d["status"] == "finished":
            JOBS[job_id].update(status="processing", percent=100)
    return hook


def download_worker(job_id: str, url: str, fmt: str, output_dir: Path,
                    quality: str = "320"):
    with DOWNLOAD_SEMAPHORE:
        try:
            out_template = str(output_dir / f"{job_id}.%(ext)s")

            common_opts = {
                "outtmpl": out_template,
                "progress_hooks": [progress_hook(job_id)],
                "quiet": True,
                "noplaylist": True,

                # Retry & timeout — fixes googlevideo CDN timeouts
                "retries": 10,
                "fragment_retries": 10,
                "file_access_retries": 5,
                "extractor_retries": 5,
                "socket_timeout": 30,
                "http_chunk_size": 1048576,
                "source_address": "0.0.0.0",
                "retry_sleep_functions": {
                    "http": lambda n: min(2 ** n, 30),
                    "fragment": lambda n: min(2 ** n, 30),
                },
                "continuedl": True,
                "skip_unavailable_fragments": True,
                "geo_bypass": True,
                "ignoreerrors": False,
            }

            if fmt == "mp3":
                # Quality: pass target as preferredquality.
                # yt-dlp picks the best available audio source, then transcodes.
                # Note: If the source is only 128k AAC, you can't invent more bits —
                # but we always ask for the best source first.
                ydl_opts = {
                    **common_opts,
                    "format": "bestaudio/best",
                    "postprocessors": [
                        # First: extract audio using best available source
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": quality,
                        },
                        # Second: ensure embedded metadata (title/artist)
                        {"key": "FFmpegMetadata", "add_metadata": True},
                        # Third: attach thumbnail as cover art
                        {"key": "EmbedThumbnail", "already_have_thumbnail": False},
                    ],
                    "writethumbnail": True,
                    # Prefer m4a/webm audio sources with highest ABR
                    "format_sort": [
                        "abr",       # highest audio bitrate first
                        "asr",       # then sample rate
                        "channels",  # then channel count
                    ],
                }
            else:  # mp4
                ydl_opts = {
                    **common_opts,
                    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "merge_output_format": "mp4",
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "video")
                uploader = info.get("uploader", "")

            extension = "mp3" if fmt == "mp3" else "mp4"
            file_path = output_dir / f"{job_id}.{extension}"

            if not file_path.exists():
                raise FileNotFoundError("Output file was not created.")

            JOBS[job_id].update(
                status="done",
                percent=100,
                filename=file_path.name,
                filepath=str(file_path),
                saved_to=str(output_dir),
                title=title,
                uploader=uploader,
            )

        except Exception as e:
            JOBS[job_id].update(status="error", error=str(e))


@app.route("/")
def index():
    return render_template(
        "index.html",
        default_dir=str(DEFAULT_DOWNLOAD_DIR),
    )


# ============ SINGLE DOWNLOAD ============
@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    fmt = (data.get("format") or "mp4").lower()
    quality = str(data.get("quality") or "320")
    server_dir = (data.get("server_dir") or "").strip()

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL."}), 400
    if fmt not in ("mp3", "mp4"):
        return jsonify({"error": "Format must be mp3 or mp4."}), 400
    if quality not in VALID_QUALITIES:
        quality = "320"

    try:
        output_dir = resolve_output_dir(server_dir)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "status": "queued",
        "percent": 0,
        "saved_to": str(output_dir),
        "url": url,
    }

    threading.Thread(
        target=download_worker,
        args=(job_id, url, fmt, output_dir, quality),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id, "saved_to": str(output_dir)})


# ============ BULK DOWNLOAD ============
@app.route("/api/bulk-download", methods=["POST"])
def start_bulk_download():
    data = request.get_json(silent=True) or {}
    raw = (data.get("urls") or "").strip()
    fmt = (data.get("format") or "mp4").lower()
    quality = str(data.get("quality") or "320")
    server_dir = (data.get("server_dir") or "").strip()

    if fmt not in ("mp3", "mp4"):
        return jsonify({"error": "Format must be mp3 or mp4."}), 400
    if quality not in VALID_QUALITIES:
        quality = "320"

    lines = [l.strip() for l in raw.splitlines()]
    links = []
    seen = set()
    for l in lines:
        if not l or l in seen:
            continue
        seen.add(l)
        links.append(l)

    if not links:
        return jsonify({"error": "Please paste at least one link."}), 400

    valid_links = []
    invalid_links = []
    for l in links:
        if is_valid_youtube_url(l):
            valid_links.append(l)
        else:
            invalid_links.append(l)

    if not valid_links:
        return jsonify({
            "error": "No valid YouTube links found.",
            "invalid": invalid_links,
        }), 400

    try:
        output_dir = resolve_output_dir(server_dir)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    bulk_id = uuid.uuid4().hex
    job_ids = []

    for url in valid_links:
        jid = uuid.uuid4().hex
        JOBS[jid] = {
            "status": "queued",
            "percent": 0,
            "saved_to": str(output_dir),
            "url": url,
            "title": None,
            "error": None,
        }
        job_ids.append(jid)
        threading.Thread(
            target=download_worker,
            args=(jid, url, fmt, output_dir, quality),
            daemon=True,
        ).start()

    BULK_JOBS[bulk_id] = {
        "job_ids": job_ids,
        "total": len(job_ids),
        "invalid": invalid_links,
        "saved_to": str(output_dir),
    }

    return jsonify({
        "bulk_id": bulk_id,
        "job_ids": job_ids,
        "total": len(job_ids),
        "invalid": invalid_links,
        "saved_to": str(output_dir),
    })


@app.route("/api/bulk-status/<bulk_id>")
def bulk_status(bulk_id):
    bulk = BULK_JOBS.get(bulk_id)
    if not bulk:
        return jsonify({"error": "Unknown bulk job."}), 404

    items = []
    done_count = 0
    error_count = 0
    overall_percent_sum = 0.0

    for jid in bulk["job_ids"]:
        job = JOBS.get(jid, {})
        items.append({
            "job_id": jid,
            "url": job.get("url"),
            "title": job.get("title"),
            "uploader": job.get("uploader"),
            "status": job.get("status", "unknown"),
            "percent": job.get("percent", 0),
            "speed": job.get("speed"),
            "eta": job.get("eta"),
            "error": job.get("error"),
            "filename": job.get("filename"),
            "saved_to": job.get("saved_to"),
        })
        if job.get("status") == "done":
            done_count += 1
            overall_percent_sum += 100
        elif job.get("status") == "error":
            error_count += 1
            overall_percent_sum += 100
        else:
            overall_percent_sum += job.get("percent", 0)

    overall = overall_percent_sum / bulk["total"] if bulk["total"] else 0

    return jsonify({
        "total": bulk["total"],
        "done": done_count,
        "errors": error_count,
        "overall_percent": round(overall, 1),
        "items": items,
        "invalid": bulk.get("invalid", []),
        "saved_to": bulk.get("saved_to"),
    })


@app.route("/api/status/<job_id>")
def job_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job."}), 404
    return jsonify(job)


@app.route("/api/file/<job_id>")
def get_file(job_id):
    job = JOBS.get(job_id)
    if not job or job.get("status") != "done":
        abort(404)

    file_path = Path(job["filepath"])
    if not file_path.exists():
        abort(404)

    safe_title = re.sub(r"[^\w\-. ]+", "_", job.get("title", "media"))[:80]
    ext = file_path.suffix
    download_name = f"{safe_title}{ext}"

    return send_file(
        file_path,
        as_attachment=True,
        download_name=download_name,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)