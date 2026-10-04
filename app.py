import os
import re
import uuid
import threading
from pathlib import Path
import imageio_ffmpeg
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

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

PLAYLIST_REGEX = re.compile(
    r"^(https?://)?(www\.)?"
    r"(youtube\.com/playlist\?list=|"
    r"youtube\.com/.*[?&]list=|"
    r"music\.youtube\.com/playlist\?list=)"
    r"[\w\-]+"
)

# TikTok URL patterns
TIKTOK_REGEX = re.compile(
    r"^(https?://)?(www\.|m\.)?"
    r"(tiktok\.com/(@[\w.\-]+/video/\d+|t/\w+|vm\.tiktok\.com/\w+)|"
    r"vt\.tiktok\.com/\w+)"
)

# Facebook URL patterns — covers videos, watch pages, reels, share links
FACEBOOK_REGEX = re.compile(
    r"^(https?://)?(www\.|m\.|web\.|mbasic\.)?"
    r"(facebook\.com/|fb\.watch/|fb\.me/)"
    r".*"
)

VALID_QUALITIES = {"128", "192", "256", "320"}
VALID_PLATFORMS = {"youtube", "tiktok", "facebook"}


def is_valid_youtube_url(url: str) -> bool:
    return bool(url and YT_REGEX.match(url.strip()))


def is_valid_playlist_url(url: str) -> bool:
    if not url:
        return False
    u = url.strip()
    return bool(PLAYLIST_REGEX.match(u)) or ("list=" in u and "youtube.com" in u)


def is_valid_tiktok_url(url: str) -> bool:
    return bool(url and TIKTOK_REGEX.match(url.strip()))


def is_valid_facebook_url(url: str) -> bool:
    """Facebook has many URL shapes; accept broad facebook.com / fb.watch patterns."""
    if not url:
        return False
    u = url.strip()
    if not FACEBOOK_REGEX.match(u):
        return False
    # Must contain something that looks like a video / reel / watch / share path
    return any(k in u for k in (
        "/video", "/videos", "/watch", "/reel", "/reels",
        "fb.watch/", "fb.me/", "/share/", "/story",
    ))


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


def build_ydl_opts(job_id, fmt, quality, output_dir, platform, remove_watermark):
    """
    Build the yt-dlp options dict. Shared by all platforms.
    Returns (ydl_opts, expected_extension).
    """
    out_template = str(output_dir / f"{job_id}.%(ext)s")

    common_opts = {
        "outtmpl": out_template,
        "progress_hooks": [progress_hook(job_id)],
        "quiet": True,
        "noplaylist": True,

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
        return {
            **common_opts,
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": quality,
                },
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail", "already_have_thumbnail": False},
            ],
            "writethumbnail": True,
            "format_sort": ["abr", "asr", "channels"],
        }, "mp3"

    # TikTok MP4 (single-file, no merge needed)
    if platform == "tiktok":
        return {
            **common_opts,
            "format": "best[ext=mp4]/best",
            "merge_output_format": "mp4",
        }, "mp4"

    # Facebook MP4 (usually single progressive mp4, sometimes HLS)
    if platform == "facebook":
        return {
            **common_opts,
            "format": "best[ext=mp4]/best",
            "merge_output_format": "mp4",
        }, "mp4"

    # YouTube MP4 (existing logic)
    return {
        **common_opts,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
    }, "mp4"


def download_worker(job_id: str, url: str, fmt: str, output_dir: Path,
                    quality: str = "320",
                    platform: str = "youtube",
                    remove_watermark: bool = False):
    with DOWNLOAD_SEMAPHORE:
        try:
            ydl_opts, extension = build_ydl_opts(
                job_id, fmt, quality, output_dir, platform, remove_watermark
            )

            # TikTok extractor options
            if platform == "tiktok":
                ydl_opts["extractor_args"] = {
                    "tiktok": {
                        # Force the mobile API hostname so the no-watermark
                        # URL is returned (when available).
                        "api_hostname": ["api22-normal-c-useast2a.tiktokv.com"],
                    }
                }

            # Facebook extractor options
            if platform == "facebook":
                # Try to grab the highest quality. Facebook often needs
                # a modern User-Agent — yt-dlp's extractor handles this.
                ydl_opts.setdefault("extractor_args", {})
                ydl_opts["extractor_args"].setdefault("facebook", {})

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "video") or info.get("id", "video")
                uploader = info.get("uploader") or info.get("creator") or ""

            file_path = output_dir / f"{job_id}.{extension}"

            if not file_path.exists():
                # Fallback: scan for any file matching the job id
                matches = list(output_dir.glob(f"{job_id}.*"))
                if matches:
                    file_path = matches[0]
                    extension = file_path.suffix.lstrip(".")
                else:
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
    platform = (data.get("platform") or "youtube").lower()
    remove_watermark = bool(data.get("remove_watermark"))

    # Validate platform
    if platform not in VALID_PLATFORMS:
        return jsonify({"error": "Platform must be 'youtube', 'tiktok', or 'facebook'."}), 400

    # Validate URL by platform
    if platform == "youtube":
        if not is_valid_youtube_url(url):
            return jsonify({"error": "Invalid YouTube URL."}), 400
    elif platform == "tiktok":
        if not is_valid_tiktok_url(url):
            return jsonify({"error": "Invalid TikTok URL."}), 400
    else:  # facebook
        if not is_valid_facebook_url(url):
            return jsonify({"error": "Invalid Facebook video URL."}), 400

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
        "platform": platform,
    }

    threading.Thread(
        target=download_worker,
        args=(job_id, url, fmt, output_dir, quality, platform, remove_watermark),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id, "saved_to": str(output_dir), "platform": platform})


# ============ BULK DOWNLOAD (YouTube only) ============
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
            "platform": "youtube",
        }
        job_ids.append(jid)
        threading.Thread(
            target=download_worker,
            args=(jid, url, fmt, output_dir, quality, "youtube", False),
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


# ============ PLAYLIST DOWNLOAD (YouTube only) ============
@app.route("/api/playlist-download", methods=["POST"])
def start_playlist_download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    fmt = (data.get("format") or "mp4").lower()
    quality = str(data.get("quality") or "320")
    server_dir = (data.get("server_dir") or "").strip()
    max_items = data.get("max_items")

    if not is_valid_playlist_url(url):
        return jsonify({"error": "Invalid YouTube playlist URL."}), 400
    if fmt not in ("mp3", "mp4"):
        return jsonify({"error": "Format must be mp3 or mp4."}), 400
    if quality not in VALID_QUALITIES:
        quality = "320"

    try:
        output_dir = resolve_output_dir(server_dir)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    extract_opts = {
        "quiet": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "ignoreerrors": True,
        "socket_timeout": 30,
        "retries": 5,
        "noplaylist": False,
    }

    try:
        with yt_dlp.YoutubeDL(extract_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return jsonify({"error": f"Could not read playlist: {e}"}), 400

    if not info:
        return jsonify({"error": "Playlist info could not be fetched."}), 400

    entries = info.get("entries") or []
    playlist_title = info.get("title") or "Playlist"

    if max_items:
        try:
            max_items = int(max_items)
            entries = entries[:max_items]
        except (TypeError, ValueError):
            pass

    if not entries:
        return jsonify({"error": "Playlist is empty."}), 400

    video_items = []
    for e in entries:
        if not e:
            continue
        vid = e.get("id")
        vurl = e.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else None)
        if vurl:
            video_items.append({
                "url": vurl,
                "title": e.get("title") or vid or "video",
            })

    if not video_items:
        return jsonify({"error": "No usable videos found in playlist."}), 400

    bulk_id = uuid.uuid4().hex
    job_ids = []
    for item in video_items:
        jid = uuid.uuid4().hex
        JOBS[jid] = {
            "status": "queued",
            "percent": 0,
            "saved_to": str(output_dir),
            "url": item["url"],
            "title": item["title"],
            "error": None,
            "platform": "youtube",
        }
        job_ids.append(jid)
        threading.Thread(
            target=download_worker,
            args=(jid, item["url"], fmt, output_dir, quality, "youtube", False),
            daemon=True,
        ).start()

    BULK_JOBS[bulk_id] = {
        "job_ids": job_ids,
        "total": len(job_ids),
        "invalid": [],
        "saved_to": str(output_dir),
        "playlist_title": playlist_title,
    }

    return jsonify({
        "bulk_id": bulk_id,
        "job_ids": job_ids,
        "total": len(job_ids),
        "playlist_title": playlist_title,
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
        "playlist_title": bulk.get("playlist_title"),
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
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)