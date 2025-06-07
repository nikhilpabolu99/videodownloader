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

    if not url or not format_id:
        return "Missing parameters", 400

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

    if is_instagram:
        # Instagram: download selected format as is, no merge
        ydl_opts['format'] = format_id

    elif is_youtube:
        # For YouTube, check format type: if only video, merge with best audio
        try:
            # Extract info to check format details
            with yt_dlp.YoutubeDL({'quiet': True, 'nocheckcertificate': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                selected_format = None
                for f in info['formats']:
                    if f['format_id'] == format_id:
                        selected_format = f
                        break

                if not selected_format:
                    return "Format not found", 400

                # Check if selected format is video-only (no audio)
                is_video_only = (selected_format.get('vcodec') != 'none' and selected_format.get('acodec') == 'none')

                if is_video_only:
                    ydl_opts['format'] = f"{format_id}+bestaudio/best"
                    ydl_opts['merge_output_format'] = 'mp4'
                else:
                    ydl_opts['format'] = format_id
        except Exception as e:
            print(f"Error processing YouTube format: {e}")
            # fallback to simple format download
            ydl_opts['format'] = format_id
            ydl_opts['merge_output_format'] = 'mp4'

    else:
        # Other URLs: merge selected format with best audio if possible
        ydl_opts['format'] = f"{format_id}+bestaudio/best"
        ydl_opts['merge_output_format'] = 'mp4'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        downloaded_file = None
        for file in os.listdir(DOWNLOAD_DIR):
            if file.startswith(uid):
                downloaded_file = os.path.join(DOWNLOAD_DIR, file)
                break

        if not downloaded_file:
            return "Download failed", 500

        return send_file(downloaded_file, as_attachment=True)

    except Exception as e:
        print(f"Error downloading URL {url}: {e}")
        return str(e), 500


@app.after_request
def cleanup(response):
    # Clean up all files after each request to keep disk clean
    for file in os.listdir(DOWNLOAD_DIR):
        try:
            os.remove(os.path.join(DOWNLOAD_DIR, file))
        except Exception:
            pass
    return response


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
