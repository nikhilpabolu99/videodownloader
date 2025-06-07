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
                if (f.get("vcodec") != "none" or f.get("acodec") != "none")
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

    url_lower = url.lower()
    is_instagram = 'instagram' in url_lower
    is_youtube = 'youtu' in url_lower or 'youtube' in url_lower
    is_facebook = 'facebook' in url_lower or 'fb.watch' in url_lower

    try:
        if is_youtube:
            # Get info first to check format details
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = ydl.extract_info(url, download=False)

            # Find selected format details
            selected_format = None
            for f in info['formats']:
                if f['format_id'] == format_id:
                    selected_format = f
                    break

            if not selected_format:
                return "Selected format not found", 400

            ydl_opts = {
                'outtmpl': output_path,
                'quiet': True,
            }

            # Check if video only (no audio)
            video_only = (selected_format.get("vcodec") != "none" and selected_format.get("acodec") == "none")

            if video_only:
                # merge video with best audio
                ydl_opts['format'] = f"{format_id}+bestaudio/best"
                ydl_opts['merge_output_format'] = 'mp4'
            else:
                ydl_opts['format'] = format_id

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        elif is_instagram:
            # Instagram: no merge, no forcing format
            ydl_opts = {
                'outtmpl': output_path,
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        elif is_facebook:
            # Facebook: merge best video+audio
            ydl_opts = {
                'format': f'{format_id}+bestaudio/best',
                'outtmpl': output_path,
                'merge_output_format': 'mp4',
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        else:
            # Other URLs: default merge
            ydl_opts = {
                'format': f'{format_id}+bestaudio/best',
                'outtmpl': output_path,
                'merge_output_format': 'mp4',
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        # Find downloaded file
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
    # Clean up all downloaded files after every request to save space
    for file in os.listdir(DOWNLOAD_DIR):
        try:
            os.remove(os.path.join(DOWNLOAD_DIR, file))
        except Exception:
            pass
    return response

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
