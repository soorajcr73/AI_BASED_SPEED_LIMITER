from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

from detect import process_video

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# -------------------------------
# Upload Video Route
# -------------------------------
@app.route("/upload", methods=["POST"])
def upload_video():

    file = request.files["video"]

    input_path = os.path.join(UPLOAD_FOLDER, file.filename)

    output_filename = "processed_" + file.filename
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    file.save(input_path)

    print("Processing video...")

    final_speed, events = process_video(input_path, output_path)

    return jsonify({

        "final_speed": final_speed,

        "events": events,

        "video_url": "/video/" + output_filename

    })


# -------------------------------
# Serve Processed Video
# -------------------------------
@app.route("/video/<filename>")
def serve_video(filename):

    return send_from_directory(OUTPUT_FOLDER, filename)


# -------------------------------
# Run Flask Server
# -------------------------------
if __name__ == "__main__":

    app.run(debug=True)
