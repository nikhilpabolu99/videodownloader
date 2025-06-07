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
                    "vcodec": f.get("vcodec", "none"),
                    "acodec": f.get("acodec", "none")
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

    # Fetch full format info
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            selected_format = next((f for f in info['formats'] if f['format_id'] == format_id), None)
            vcodec = selected_format.get("vcodec", "none")
            acodec = selected_format.get("acodec", "none")
    except Exception as e:
        return f"Error retrieving format: {e}", 500

    # Build ydl_opts based on content type
    if is_instagram:
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'quiet': True,
        }
    elif is_youtube and vcodec != 'none' and acodec == 'none':
        ydl_opts = {
            'format': f"{format_id}+bestaudio",
            'outtmpl': output_path,
            'merge_output_format': 'mp4',
            'quiet': True,
        }
    else:
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'merge_output_format': 'mp4',
            'quiet': True,
        }

    # Perform download
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        downloaded_file = next(
            (os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR) if f.startswith(uid)),
            None
        )

        if not downloaded_file:
            return "Download failed", 500

        return send_file(downloaded_file, as_attachment=True)
    except Exception as e:
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
