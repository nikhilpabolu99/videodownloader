@app.route('/test-yt')
def test_yt():
    try:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        ydl_opts = {
            'quiet': True,
            'format': 'best[ext=mp4]',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({"title": info.get("title", "no title")})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
