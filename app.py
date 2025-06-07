from flask import Flask, request, jsonify, send_file, render_template
import yt_dlp
import os
from uuid import uuid4
from urllib.parse import unquote

app = Flask(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.0.0 Safari/537.36"
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch-info')
def fetch_info():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Missing URL'}), 400

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": USER_AGENT
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [
                {
                    "format_id": f["format_id"],
                    "ext": f["ext"],
                    "resolution": f.get("height") or f.get("format_note") or "audio",
                }
                for f in info['formats']
                if (f.get("vcodec") != "none" or f.get("acodec") != "none")
            ]
            return jsonify({"title": info.get("title", ""), "formats": formats})
    except Exception as e:
        print(f"Error fetching info for URL {url}: {e}")
        return jsonify({"error": f"Failed to extract info: {str(e)}"}), 500

@app.route('/download')
def download():
    url = unquote(request.args.get("url", ""))
    format_id = request.args.get("format_id")

    if not url:
        return "Missing URL", 400

    uid = str(uuid4())
    output_path = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

    is_youtube = 'youtu' in url.lower()
    is_instagram = 'instagram' in url.lower()

    ydl_opts = {
        'outtmpl': output_path,
        'quiet': True,
        'nocheckcertificate': True,
        'merge_output_format': 'mp4',
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'http_headers': {
            "User-Agent": USER_AGENT
        }
    }

    # YouTube logic: always use bestvideo+bestaudio safely
    if is_youtube:
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    elif is_instagram:
        ydl_opts['format'] = format_id if format_id else 'best'
    else:
        ydl_opts['format'] = f"{format_id}+bestaudio/best" if format_id else 'best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        downloaded_file = next(
            (os.path.join(DOWNLOAD_DIR, file) for file in os.listdir(DOWNLOAD_DIR) if file.startswith(uid)), None
        )

        if not downloaded_file:
            return "Download failed", 500

        return send_file(downloaded_file, as_attachment=True)

    except Exception as e:
        print(f"Error downloading URL {url}: {e}")
        return str(e), 500

@app.after_request
def cleanup(response):
    # Clean up downloads
    for file in os.listdir(DOWNLOAD_DIR):
        try:
            os.remove(os.path.join(DOWNLOAD_DIR, file))
        except Exception:
            pass
    return response

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
