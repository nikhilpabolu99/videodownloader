# app.py
from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
from uuid import uuid4

app = Flask(__name__)

@app.route('/fetch-info')
def fetch_info():
    url = request.args.get('url')
    ydl_opts = {"quiet": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = [{
            "format_id": f["format_id"],
            "ext": f["ext"],
            "resolution": f.get("height", "audio") or "audio",
            "format_note": f.get("format_note", "")
        } for f in info['formats'] if f.get("vcodec") != "none" or f.get("acodec") != "none"]
        return jsonify({"title": info.get("title", ""), "formats": formats})

@app.route('/download')
def download_video():
    url = request.args.get('url')
    format_id = request.args.get('format_id')
    filename = f"{uuid4()}.mp4"
    ydl_opts = {
        "format": format_id,
        "outtmpl": filename,
        "quiet": True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return send_file(filename, as_attachment=True, download_name="video.mp4", mimetype="video/mp4")

@app.after_request
def cleanup(response):
    for file in os.listdir("."):
        if file.endswith(".mp4"):
            os.remove(file)
    return response

if __name__ == '__main__':
    app.run(debug=True)
