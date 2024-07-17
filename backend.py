import uuid
from flask import Flask, request, jsonify

app = Flask(__name__)
sessions = {}
files = {}

@app.route('/new-chat', methods=['POST'])
def new_chat():
    session_id = str(uuid.uuid4())
    sessions[session_id] = []
    return jsonify({"session_id" : session_id})

@app.route('/get-history/<session_id>', methods=['GET'])
def get_history(session_id):
    return jsonify(sessions.get(session_id, []))

@app.route('/get-chats', methods=['GET'])
def get_chats():
    return jsonify(sessions)

@app.route('/get-all-sessions', methods=['GET'])
def get_all_sessions():
    return jsonify(list(sessions.keys()))

# @app.route('/delete-chat', methods=['DELETE'])
# def delete_chat(session_id):
#     for session in sessions:
#         if session == sessions[session_id]:
#             sessions[session_id].
@app.route('/save-file-info', methods=['POST'])
def save_files():
    data = request.json
    file_name = data.get('file_name')
    file_path = data.get('file_path')


    if not file_path or not file_name:
        return jsonify({"error" : "Both file_name and file_path are required"}), 400

    if file_path in files.values() or file_name in files:
        return jsonify({"error" : "Path or Name already exists in the database"}), 400
    
    files[file_name] = file_path

    return jsonify({
        "file_name" : file_name,
        "file_path" : file_path
    })

@app.route('/get-files-info', methods=['GET'])
def get_files():
    return jsonify([{"file_name": key, "file_path": value} for key, value in files.items()])

@app.route('/add-message/<session_id>', methods=['POST'])
def add_messages(session_id):
    message = request.json.get('message')

    if not isinstance(message, dict) or 'role' not in message or 'content' not in message:
        return jsonify({"error": "Invalid message format"}), 400

    if session_id in sessions:
        sessions[session_id].append(message)
    else:
        sessions[session_id] = [message]
    
    return jsonify(sessions[session_id])

if __name__ == '__main__':
    app.run(port=5000)

