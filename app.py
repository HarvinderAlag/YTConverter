from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pytube import YouTube
from pytube.exceptions import PytubeError
import os
import time
from functools import wraps

app = Flask(__name__)
CORS(app)

# Rate limiting storage
request_times = {}

def rate_limit(max_per_minute=10):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            window_start = now - 60  # 1 minute window
            
            # Clean up old requests
            request_times[ip] = [t for t in request_times.get(ip, []) if t > window_start]
            
            # Check if rate limit exceeded
            if len(request_times[ip]) >= max_per_minute:
                return jsonify({"error": "Rate limit exceeded. Try again in a minute."}), 429
            
            # Add current request time
            request_times[ip].append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator

@app.route('/api/video-info/<video_id>', methods=['GET'])
@rate_limit(max_per_minute=10)
def get_video_info(video_id):
    try:
        yt = YouTube(f'https://www.youtube.com/watch?v={video_id}')
        
        return jsonify({
            "title": yt.title,
            "duration": yt.length,
            "views": yt.views,
            "thumbnail": yt.thumbnail_url,
            "success": True
        })
    except PytubeError as e:
        return jsonify({"error": str(e), "success": False}), 400
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "success": False}), 500

@app.route('/api/convert/<video_id>', methods=['POST'])
@rate_limit(max_per_minute=5)
def convert_video(video_id):
    try:
        format_type = request.args.get('format', 'mp3')
        yt = YouTube(f'https://www.youtube.com/watch?v={video_id}')
        
        if format_type == 'mp3':
            # Get audio stream
            stream = yt.streams.filter(only_audio=True).first()
            filename = f"{yt.title}.mp3"
        else:
            # Get video stream based on quality preference
            if format_type == 'high':
                stream = yt.streams.get_highest_resolution()
            elif format_type == 'low':
                stream = yt.streams.get_lowest_resolution()
            else:  # mp4 default to medium quality
                stream = yt.streams.filter(file_extension='mp4').first()
            
            filename = f"{yt.title}.mp4"
        
        # Clean filename from invalid characters
        filename = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_')).rstrip()
        
        # Download the stream
        output_path = stream.download(output_path='downloads', filename=filename)
        
        return jsonify({
            "success": True,
            "message": "Conversion successful",
            "filename": filename,
            "downloadUrl": f"/download/{os.path.basename(output_path)}"
        })
    except PytubeError as e:
        return jsonify({"error": str(e), "success": False}), 400
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "success": False}), 500

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
        return send_file(
            os.path.join('downloads', filename),
            as_attachment=True,
            download_name=filename
        )
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    # Create downloads directory if it doesn't exist
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    app.run(debug=True)
