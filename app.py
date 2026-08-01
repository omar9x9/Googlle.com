import os
from flask import Flask, request, jsonify

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# مصفوفة مؤقتة لحفظ الأجهزة والملفات (للتجربة السريعة على ريندر)
received_data = {}

@app.route('/')
def home():
    return "<h1>Server is Running Online!</h1>", 200

@app.route('/api/upload_file', methods=['POST'])
def upload_file():
    device_name = request.form.get("device_name", "Unknown Device")
    
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400

    device_folder = os.path.join(UPLOAD_FOLDER, device_name)
    if not os.path.exists(device_folder):
        os.makedirs(device_folder)

    file_path = os.path.join(device_folder, file.filename)
    file.save(file_path)

    # حفظ البيانات في الذاكرة مؤقتاً للتجربة
    if device_name not in received_data:
        received_data[device_name] = []
    
    if file.filename not in received_data[device_name]:
        received_data[device_name].append(file.filename)
    
    return jsonify({"status": "success", "message": "Uploaded to Render!"}), 200

@app.route('/api/get_devices', methods=['GET'])
def get_devices():
    return jsonify({"devices": list(received_data.keys())}), 200

@app.route('/api/get_files/<device_name>', methods=['GET'])
def get_files(device_name):
    files = received_data.get(device_name, [])
    formatted_files = [{"file_name": f, "download_url": f"/api/download/{device_name}/{f}"} for f in files]
    return jsonify({"files": formatted_files}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
