from flask import Flask, request, jsonify, send_file, render_template
import yt_dlp
import os
from uuid import uuid4
from urllib.parse import unquote
import traceback

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
        traceback.print_exc()
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
        # Instagram: just download selected format (no merging)
        ydl_opts['format'] = format_id

    elif is_youtube:
        # YouTube: check if selected format is video-only; if yes, merge with best audio
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'nocheckcertificate': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                selected_format = next((f for f in info['formats'] if f['format_id'] == format_id), None)

                if not selected_format:
                    return "Format not found", 400

                is_video_only = (selected_format.get('vcodec') != 'none' and selected_format.get('acodec') == 'none')

                if is_video_only:
                    ydl_opts['format'] = f"{format_id}+bestaudio/best"
                    ydl_opts['merge_output_format'] = 'mp4'
                else:
                    ydl_opts['format'] = format_id
        except Exception as e:
            print(f"Error processing YouTube format: {e}")
            traceback.print_exc()
            # fallback to basic format download
            ydl_opts['format'] = format_id
            ydl_opts['merge_output_format'] = 'mp4'

    else:
        # Other URLs: attempt to merge selected format with best audio
        ydl_opts['format'] = f"{format_id}+bestaudio/best"
        ydl_opts['merge_output_format'] = 'mp4'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find the downloaded file in DOWNLOAD_DIR starting with uid
        downloaded_file = None
        for file in os.listdir(DOWNLOAD_DIR):
            if file.startswith(uid):
                downloaded_file = os.path.join(DOWNLOAD_DIR, file)
                break

        if not downloaded_file:
            return "Download failed: File not found after download", 500

        return send_file(downloaded_file, as_attachment=True)

    except Exception as e:
        print(f"Error downloading URL {url}: {e}")
        traceback.print_exc()
        return f"Download failed: {str(e)}", 500


@app.after_request
def cleanup(response):
    # Clean up all files in downloads after each request to keep disk clean
    for file in os.listdir(DOWNLOAD_DIR):
        try:
            os.remove(os.path.join(DOWNLOAD_DIR, file))
        except Exception:
            pass
    return response


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
