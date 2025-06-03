from flask import Flask, request, jsonify, send_file, render_template
import yt_dlp
import os
from uuid import uuid4

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch-info')
def fetch_info():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [{
                "format_id": f["format_id"],
                "ext": f["ext"],
                "resolution": f.get("height", "audio") or "audio",
                "format_note": f.get("format_note", "")
            } for f in info.get("formats", []) if f.get("vcodec") != "none" or f.get("acodec") != "none"]

            return jsonify({
                "title": info.get("title", "Untitled"),
                "formats": formats
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download')
def download_video():
    url = request.args.get('url')
    format_id = request.args.get('format_id')
    if not url or not format_id:
        return "Missing parameters", 400

    filename = f"{uuid4()}.mp4"
    ydl_opts = {
        "format": format_id,
        "outtmpl": filename,
        "quiet": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return send_file(filename, as_attachment=True, download_name="video.mp4", mimetype="video/mp4")

    except Exception as e:
        return f"Download failed: {e}", 500

    finally:
        if os.path.exists(filename):
            os.remove(filename)

@app.after_request
def cleanup(response):
    for file in os.listdir("."):
        if file.endswith(".mp4"):
            try:
                os.remove(file)
            except:
                pass
    return response

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
