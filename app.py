import sys
import os
from src.api_client import MangaAPIClient
from src.ai_interface import AISession
import json
import uuid
from flask import Flask, render_template, jsonify, request

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

app = Flask(__name__, static_folder='frontend', static_url_path='')
sessions = {}

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/session', methods=['POST'])
def create_session():
    api = MangaAPIClient()
    ai_session = AISession(api)
    
    try:
        ai_session.start_session()
        session_id = str(uuid.uuid4())
        sessions[session_id] = ai_session
        
        indices = ai_session.get_recommendations()
        recommendations = [ai_session.recommender.data[i] for i in indices[:10]]
        
        return jsonify({
            'session_id': session_id,
            'recommendations': recommendations
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recommend', methods=['POST'])
def get_recommendations():
    data = request.json
    session_id = data.get('session_id')
    likes = data.get('likes', [])
    
    if not session_id or session_id not in sessions:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    ai_session = sessions[session_id]
    
    try:
        manga_ids = [m['id'] for m in ai_session.recommender.data]
        indices = [manga_ids.index(id) for id in likes if id in manga_ids]
        
        ai_session.update_preferences(indices)
        new_indices = ai_session.get_recommendations()
        recommendations = [ai_session.recommender.data[i] for i in new_indices[:10]]
        
        return jsonify({'recommendations': recommendations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)