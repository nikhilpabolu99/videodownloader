from flask import Flask, request, jsonify, send_file, render_template
import yt_dlp
import os
from uuid import uuid4
from urllib.parse import unquote
from datetime import datetime

app = Flask(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.0.0 Safari/537.36"
)

YOUTUBE_COOKIES = "yt_cookies.txt"
INSTAGRAM_COOKIES = "ig_cookies.txt"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch-info')
def fetch_info():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Missing URL'}), 400

    url_lower = url.lower()
    is_youtube = 'youtu' in url_lower
    is_instagram = 'instagram' in url_lower

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": USER_AGENT
        }
    }

    if is_youtube and os.path.exists(YOUTUBE_COOKIES):
        ydl_opts["cookiefile"] = YOUTUBE_COOKIES
    elif is_instagram and os.path.exists(INSTAGRAM_COOKIES):
        ydl_opts["cookiefile"] = INSTAGRAM_COOKIES

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in info['formats']:
                vcodec = f.get("vcodec")
                acodec = f.get("acodec")
                print(f"vcodec:{vcodec},acodec:{acodec}")
                if vcodec == "none" and acodec != "none":
                    
                    label = "audio only"
                elif vcodec != "none" and (acodec == "none" or not acodec):
                    label = "video only"
                else:
                    label = "audio + video"

                formats.append({
                    "format_id": f["format_id"],
                    "ext": f["ext"],
                    "resolution": f.get("height") or f.get("format_note") or "unknown",
                    "label": f"{label} (vcodec: {vcodec}, acodec: {acodec})"
                })

            return jsonify({"title": info.get("title", ""), "formats": formats})
    except Exception as e:
        print(f"Error fetching info for URL {url}: {e}")
        return jsonify({"error": f"Failed to extract info: {str(e)}"}), 500


@app.route('/download')
def download():
    url = unquote(request.args.get("url", ""))
    format_id = request.args.get("format_id")

    if not url or not format_id:
        return "Missing parameters", 400

    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] IP: {user_ip} | URL: {url} | Format ID: {format_id}\n"
    print(log_entry.strip())

    uid = str(uuid4())
    output_path = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

    url_lower = url.lower()
    is_instagram = 'instagram' in url_lower
    is_youtube = 'youtu' in url_lower or 'youtube' in url_lower

    ydl_opts = {
        'outtmpl': output_path,
        'quiet': True,
        'nocheckcertificate': True,
        'http_headers': {
            "User-Agent": USER_AGENT
        }
    }

    if is_youtube and os.path.exists(YOUTUBE_COOKIES):
        ydl_opts['cookiefile'] = YOUTUBE_COOKIES
    elif is_instagram and os.path.exists(INSTAGRAM_COOKIES):
        ydl_opts['cookiefile'] = INSTAGRAM_COOKIES

    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'nocheckcertificate': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            selected_format = next((f for f in info['formats'] if f['format_id'] == format_id), None)

            if not selected_format:
                return "Format not found", 400

            vcodec = selected_format.get('vcodec')
            acodec = selected_format.get('acodec')
            has_video = vcodec and vcodec != 'none'
            has_audio = acodec and acodec != 'none'

            if has_video and not has_audio:
                ydl_opts['format'] = f"{format_id}+bestaudio"
                ydl_opts['merge_output_format'] = 'mp4'
                print(f"Downloading as: mp4-{format_id}+bestaudio")
            else:
                ydl_opts['format'] = format_id
                print(f"Downloading as: mp4-{format_id}")

    except Exception as e:
        print(f"Error getting format info: {e}")
        ydl_opts['format'] = format_id
        ydl_opts['merge_output_format'] = 'mp4'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        downloaded_file = next(
            (os.path.join(DOWNLOAD_DIR, file) for file in os.listdir(DOWNLOAD_DIR) if file.startswith(uid)),
            None
        )

        if not downloaded_file:
            return "Download failed", 500

        return send_file(downloaded_file, as_attachment=True)

    except Exception as e:
        print(f"Download error for {url}: {e}")
        return str(e), 500


@app.after_request
def cleanup(response):
    for file in os.listdir(DOWNLOAD_DIR):
        try:
            os.remove(os.path.join(DOWNLOAD_DIR, file))
        except Exception:
            pass
    return response


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
