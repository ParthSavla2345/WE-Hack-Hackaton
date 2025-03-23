from flask import Flask, render_template, jsonify
import subprocess

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/run-detection', methods=['GET'])
def run_detection():
    try:
        subprocess.Popen(["python", "detection.py"])  # Runs detection.py
        return jsonify({"status": "success", "message": "Detection started!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)