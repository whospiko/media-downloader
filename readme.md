# 🎵 YouTube Downloader

> A modern, self-hosted web app to download YouTube videos as **MP4** or **high-quality MP3 (up to 320 kbps)** — with Single, Bulk, and Playlist modes, folder picking, and a clean dark UI.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)
![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-red)
![License](https://img.shields.io/badge/License-MIT-green)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

---

## 📖 Table of Contents

- [Features](#-features)
- [Screenshots](#-screenshots)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Usage](#-usage)
  - [Single Download](#single-download)
  - [Bulk Download](#bulk-download)
  - [Playlist Download](#playlist-download)
- [Access from Your Phone (LAN)](#-access-from-your-phone-lan)
- [Configuration](#-configuration)
- [Troubleshooting](#-troubleshooting)
- [Tech Stack](#-tech-stack)
- [Legal Notice](#️-legal-notice)
- [FAQ](#-faq)
- [Contributing](#-contributing)
- [License](#-license)
- [Acknowledgments](#-acknowledgments)

---

## ✨ Features

### 🎯 Three Download Modes
- **Single** — paste one YouTube link, download instantly
- **Bulk** — paste many links (one per line), each queued as its own job
- **Playlist** — paste a YouTube playlist URL and grab every video in it

### 🔊 Audio Quality
- Choose **128 / 192 / 256 / 320 kbps** MP3
- Automatically picks the **highest-bitrate source** YouTube offers
- **Cover art + metadata** (title, artist) embedded into every MP3
- Matches Spotify Premium's "Very High" tier output bitrate

### 💾 Flexible Save Options
- **My computer** — browser download, or pick a folder directly via Chrome/Edge File System Access API
- **Server's default folder** — `./downloads/` next to `app.py`
- **Custom folder on server** — any absolute or relative path
- **💚 Save All** button — one click, one folder picker, all files saved (Chrome/Edge); sequential fallback for Firefox

### 📊 Real-Time Feedback
- Live percent, speed (MB/s), ETA for active downloads
- Per-item status badges: `queued` · `downloading` · `processing` · `done` · `error`
- Animated shimmer progress bars, pulsing indicators on active items
- Overall bulk/playlist progress bar

### 🛡 Reliability
- **Smart concurrency** — max 2 simultaneous downloads to avoid YouTube CDN throttling
- **Auto-retry** — 10 retries per HTTP request & per fragment, with exponential backoff
- **Resumable downloads** — 1 MiB chunks so a dropped connection resumes, not restarts
- **IPv4 forced** — fixes common `googlevideo.com` timeouts on Windows

### 🎨 Experience
- Modern dark UI with gradient accents
- Fully responsive — works great on mobile
- **LAN access** — use it from your phone over Wi-Fi
- No build step, no frontend dependencies — just vanilla JS + CSS

---

## 📸 Screenshots

> _Add your screenshots to a `docs/` folder and update the paths below. If you don't want screenshots, delete this section._

| Single Tab | Bulk Tab | Playlist Tab |
| :-: | :-: | :-: |
| ![Single Tab](docs/single.png) | ![Bulk Tab](docs/bulk.png) | ![Playlist Tab](docs/playlist.png) |

| Mobile View |
| :-: |
| ![Mobile](docs/mobile.png) |

---

## 🚀 Quick Start

### Prerequisites

You'll need three tools installed:

| Tool | Why | Minimum |
|---|---|---|
| **Python** | Runs the app | 3.10+ |
| **FFmpeg** | Merges video/audio & converts to MP3 | Any recent version |
| **Deno** | JS runtime required by yt-dlp for YouTube | Any recent version |

#### Install Python

- **Windows:** [python.org/downloads](https://www.python.org/downloads/) — tick "Add Python to PATH"
- **macOS:** `brew install python@3.12`
- **Linux:** `sudo apt install python3 python3-venv python3-pip`

Verify: `python --version` (should show 3.10+)

#### Install FFmpeg

- **Windows:** `winget install Gyan.FFmpeg`
- **macOS:** `brew install ffmpeg`
- **Linux (Debian/Ubuntu):** `sudo apt install ffmpeg`

Verify: `ffmpeg -version`

#### Install Deno

- **Windows:** `winget install DenoLand.Deno`
- **macOS:** `brew install deno`
- **Linux:** `curl -fsSL https://deno.land/install.sh | sh`

Verify: `deno --version`

> ⚠️ **Restart your terminal** after installing FFmpeg and Deno so PATH updates take effect.

### Clone & Run

```bash
# 1. Clone the repository
git clone https://github.com/whospiko/youtube-downloader.git
cd youtube-downloader

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\activate
                                 # Windows CMD:        .venv\Scripts\activate.bat

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Then open **http://localhost:5001** in your browser.

The terminal will print something like:

```
=======================================================
  📱  Open on your phone:  http://192.168.100.162:5001
  💻  On this computer:    http://127.0.0.1:5001
=======================================================
```

---

## 📁 Project Structure

```
youtube-downloader/
├── app.py                  # Flask backend + yt-dlp logic
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html          # Single-page UI (Single + Bulk + Playlist tabs)
├── downloads/              # Default output folder (auto-created on first run)
├── docs/                   # Screenshots for README (optional)
│   ├── single.png
│   ├── bulk.png
│   ├── playlist.png
│   └── mobile.png
└── README.md
```

---

## 📖 Usage

### Single Download

1. Open the **Single** tab.
2. Paste a YouTube URL.
3. Pick **MP4** (video) or **MP3** (audio only).
4. If **MP3**, pick a bitrate — default **320 kbps** is best.
5. Choose where to save:
   - **Save to my computer** — browser downloads it (or pick a folder directly in Chrome/Edge)
   - **Server's default folder** — saves to `./downloads/`
   - **Custom folder on the server** — type a path like `D:\Music` or `/home/user/Music`
6. Click **⬇ Download**.
7. Watch the progress bar; when done, click **Save** or use the folder picker.

### Bulk Download

1. Open the **Bulk** tab.
2. Paste YouTube links, **one per line**.
   - Duplicates are removed automatically.
   - Invalid links show in a red warning box and are skipped.
3. Pick format and quality.
4. Choose save location.
5. Click **⬇ Download All**.
6. Each link gets its own progress card with a status badge.
7. When items finish, click **💾 Save All N Files**:
   - **Chrome/Edge** — pick one folder, all files save silently
   - **Firefox** — browser triggers sequential downloads (accept the "multiple downloads" prompt once)

### Playlist Download

1. Open the **Playlist** tab.
2. Paste a YouTube playlist URL:
   - `https://www.youtube.com/playlist?list=PLxxxx`
   - Or any watch URL that contains `&list=PLxxxx`
3. Pick format and quality.
4. **Optional: Max videos** — cap the download (All / 5 / 10 / 25 / 50). Useful for huge playlists.
5. Choose save location.
6. Click **⬇ Download Playlist**.
7. The app:
   - Reads the playlist metadata (fast — no per-video resolution yet)
   - Queues every video as its own job (goes through the same 2-at-a-time limit)
   - Shows one progress card per video
8. When items finish, click **💾 Save All N Files**.

**Notes:**
- Private playlists require cookies (see [Troubleshooting](#-troubleshooting)).
- The playlist title appears in the status line.
- Each video is downloaded individually — you can retry only the failed ones by re-pasting the specific video URLs in the Bulk tab.

---

## 📱 Access from Your Phone (LAN)

Run the app on your PC, use it from your phone's browser over Wi-Fi.

### Steps

1. Make sure your **phone and PC are on the same Wi-Fi network**.
2. Start the app on your PC: `python app.py`
3. Note the phone URL printed on startup (e.g., `http://192.168.100.162:5001`).
4. Open that URL on your phone's browser.

> ⚠️ Type **`http://`** — not `https://`. Flask's dev server is HTTP-only.

### If it doesn't load

**99% of the time it's the firewall.** Allow Python through it:

**GUI method:**
1. Windows Security → Firewall & network protection
2. Allow an app through firewall → Change settings → Allow another app
3. Browse to `.venv\Scripts\python.exe` in your project
4. Tick **Private** and **Public** → Add

**PowerShell method** (run as Administrator):

```powershell
New-NetFirewallRule -DisplayName "Flask YouTube Downloader" -Direction Inbound -LocalPort 5001 -Protocol TCP -Action Allow
```

### Common LAN gotchas

| Problem | Fix |
|---|---|
| Phone on mobile data | Switch to Wi-Fi |
| Guest network isolated | Connect both to the main SSID |
| IP changed after reboot | Run `ipconfig` and use the new IP |
| Debug reloader drops connection | Set `debug=False` in `app.py` while testing |
| VPN running on PC | Pause VPN — it may block LAN |

### Auto-print the phone URL on startup

Replace the `if __name__ == "__main__":` block in `app.py` with:

```python
import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    ip = get_local_ip()
    print("\n" + "=" * 55)
    print(f"  📱  Open on your phone:  http://{ip}:5001")
    print(f"  💻  On this computer:    http://127.0.0.1:5001")
    print("=" * 55 + "\n")
    app.run(host="0.0.0.0", port=5001, debug=True)
```

---

## 🔧 Configuration

### Change the port

In `app.py`, edit the last line:

```python
app.run(host="0.0.0.0", port=5001, debug=True)
```

Common alternative ports: `5002`, `8000`, `8080`.

> Port **5000** is often reserved by Windows (Hyper-V/WSL2) or macOS (AirPlay Receiver). Use 5001 or higher.

### Change concurrency limit

Downloads are throttled to avoid YouTube CDN timeouts. Edit `app.py`:

```python
DOWNLOAD_SEMAPHORE = threading.Semaphore(2)   # change 2 to N
```

Higher values = faster bulk/playlist jobs, but more chance of hitting CDN errors.

### Change default download folder

```python
DEFAULT_DOWNLOAD_DIR = BASE_DIR / "downloads"   # change to any path
```

---

## 🩺 Troubleshooting

| Symptom | Fix |
|---|---|
| **Port already in use / socket error** | Change port (`5001` → `5002`) |
| **`ffmpeg is not installed`** | Install FFmpeg and restart terminal |
| **`No supported JavaScript runtime`** | Install Deno and restart terminal |
| **`Please sign in` / `Precondition check failed`** | Update yt-dlp: `pip install -U yt-dlp` |
| **`Connection to googlevideo.com timed out`** | Auto-retries 10×; if persistent, disable VPN or antivirus HTTPS scanning |
| **Phone can't reach the app** | Windows Firewall — see [LAN section](#-access-from-your-phone-lan) |
| **Audio sounds same at all bitrates** | YouTube's source is often only 128–256 kbps; higher output preserves that better but can't add detail |
| **Playlist says "Could not read playlist"** | Private/age-restricted playlist → add cookies (below) |
| **Playlist downloads only some videos** | Some videos may be region-locked or deleted; the rest still succeed |
| **`Unable to download API page`** | Update yt-dlp: `pip install -U yt-dlp` |

### Keep yt-dlp updated

YouTube changes its API often. Keep yt-dlp fresh:

```bash
pip install -U yt-dlp
```

The `requirements.txt` intentionally does **not** pin yt-dlp — this ensures `pip install -r requirements.txt` always grabs a working version.

### Adding cookies (for age-restricted, private, or sign-in-required content)

**Option A — live browser cookies:**

In `app.py`, add to `common_opts` inside `download_worker`:

```python
"cookiesfrombrowser": ("firefox",),   # or "chrome", "edge", "brave"
```

> Firefox is the most reliable on Windows.

**Option B — exported cookie file:**

1. Install a "Get cookies.txt LOCALLY" browser extension
2. Log in to YouTube, export cookies to `cookies.txt` in the project root
3. Add to `common_opts`:

```python
"cookiefile": "cookies.txt",
```

You'll also want to add the same cookie option to the **playlist extraction** block in `start_playlist_download` (the `extract_opts` dict) for private playlists.

> ⚠️ Never commit `cookies.txt` — it contains session credentials.

---

## 🛠 Tech Stack

- **[Flask](https://flask.palletsprojects.com/)** — lightweight web framework
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — the actual download engine
- **[FFmpeg](https://ffmpeg.org/)** — audio extraction, A/V merging, metadata embedding
- **[Deno](https://deno.land/)** — JavaScript runtime for YouTube challenge solving
- **Vanilla JS + CSS** — no build step, no frontend dependencies

---

## ⚖️ Legal Notice

This project is intended for **personal and educational use only**.

- Downloading copyrighted content without permission may violate YouTube's [Terms of Service](https://www.youtube.com/t/terms) and copyright law in your country.
- Use this tool only for:
  - Content you own
  - Content in the public domain
  - Content with a permissive license (e.g., Creative Commons)
  - Content you have explicit permission to download
- The authors are **not responsible** for how you use this tool.

> Spotify is mentioned for **bitrate comparison only**. This tool cannot and does not access Spotify — see the [FAQ](#-faq).

---

## ❓ FAQ

**Q: Can I download from Spotify?**
No. Spotify streams are DRM-protected and their ToS forbids downloading. Any tool claiming otherwise either downloads from YouTube and mislabels it, or circumvents DRM (illegal in most countries).

**Q: What's the highest MP3 quality I can get?**
The app outputs up to **320 kbps MP3**, matching Spotify Premium's "Very High" tier. However, YouTube's source is typically 128–256 kbps AAC, so the effective ceiling is bounded by the source.

**Q: Will this work on a public server?**
Yes, but the **server-folder save options** let users write to arbitrary paths. Before exposing publicly, either:
- Remove those options, OR
- Restrict them to an allowlist of subfolders under `downloads/`

Also add rate-limiting, authentication, and HTTPS for production use.

**Q: Why is the port 5001 and not 5000?**
Port 5000 is often reserved by Windows (Hyper-V/WSL2) or macOS (AirPlay Receiver). 5001 avoids the conflict.

**Q: Can I change the output filename?**
Not from the UI yet. yt-dlp names files with an internal job ID; the friendly name is applied when you click **Save**. PRs welcome!

**Q: Does it work with YouTube playlists?**
Yes — the **Playlist** tab handles both `youtube.com/playlist?list=...` and watch URLs with `&list=...`. You can also cap how many videos to grab.

**Q: How many links can I paste in Bulk?**
No hard limit, but the queue downloads 2 at a time. Pasting 100+ links works but will take a while.

**Q: Are files deleted after download?**
No. Files stay in `downloads/` on the server. Add a cleanup task (e.g., cron job) if you need auto-deletion.

**Q: Can I use this on Windows, macOS, and Linux?**
Yes — the only platform-specific bits are the FFmpeg/Deno install steps, which the docs cover for all three.

**Q: How do I add a "Save All" for my playlist downloads?**
The Playlist tab already has **💾 Save All** — it works exactly like the Bulk tab's version.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the repo
2. Create a branch: `git checkout -b feature/amazing-feature`
3. Commit: `git commit -m "Add amazing feature"`
4. Push: `git push origin feature/amazing-feature`
5. Open a Pull Request

Please test with a **public-domain** YouTube video before submitting.

### Ideas for contributions
- ✅ ~~Playlist support~~ (done!)
- Drag-and-drop URL paste
- Progress persistence (resume jobs after server restart)
- Auto-cleanup of old downloads
- Docker image
- User authentication for public deployments
- Dark/light theme toggle
- Subtitle / chapter download
- Direct download (skip "Save" click for browser mode)

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2026 whospiko

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

> Replace `whospiko` if you prefer a different author name.

---

## 🙏 Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — the engine that makes this possible
- [FFmpeg](https://ffmpeg.org/) — audio/video processing
- [Deno](https://deno.land/) — modern JS runtime
- [Flask](https://flask.palletsprojects.com/) — simple, powerful web framework
- All contributors and users of this project

---

## ⭐ Show Your Support

If this project helped you, please give it a ⭐ on GitHub — it means a lot!

---

<p align="center">Made with ❤️ and Python</p>