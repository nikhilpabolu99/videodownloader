from flask import Flask, request, jsonify, send_file, render_template
import yt_dlp
import os
from uuid import uuid4
from urllib.parse import unquote

app = Flask(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch-info')
def fetch_info():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Missing URL'}), 400

    ydl_opts = {"quiet": True, "skip_download": True}
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
                if f.get("vcodec") != "none" or f.get("acodec") != "none"
            ]
            return jsonify({"title": info.get("title", ""), "formats": formats})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download')
def download():
    url = unquote(request.args.get("url", ""))
    format_id = request.args.get("format_id")

    if not url or not format_id:
        return "Missing parameters", 400

    uid = str(uuid4())
    output_path = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

    is_instagram = 'instagram' in url.lower()
    is_youtube = 'youtu' in url.lower() or 'youtube' in url.lower()

    # yt_dlp options
    ydl_opts = {
        'format': f'{format_id}+bestaudio/best' if not is_instagram else f'{format_id}',
        'outtmpl': output_path,
        'quiet': True,
    }

    # Only merge for non-Instagram sources
    if not is_instagram:
        ydl_opts['merge_output_format'] = 'mp4'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Locate downloaded file
        downloaded_file = None
        for file in os.listdir(DOWNLOAD_DIR):
            if file.startswith(uid):
                downloaded_file = os.path.join(DOWNLOAD_DIR, file)
                break

        if not downloaded_file:
            return "Download failed", 500

        return send_file(downloaded_file, as_attachment=True)

    except Exception as e:
        return str(e), 500

@app.after_request
def cleanup(response):
    # Clean up all files after each request
    for file in os.listdir(DOWNLOAD_DIR):
        try:
            os.remove(os.path.join(DOWNLOAD_DIR, file))
        except Exception:
            pass
    return response

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
