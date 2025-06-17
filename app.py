from flask import Flask, render_template, jsonify, request
from src.api_client import MangaAPIClient
from src.ai_interface import AISession
import uuid
import logging

app = Flask(__name__, static_folder='frontend', static_url_path='')
sessions = {}
logging.basicConfig(level=logging.INFO)


@app.route('/')
def index():
    return app.send_static_file('index.html')


logging.basicConfig(level=logging.INFO)


@app.route('/api/session', methods=['POST'])
def create_session():
    try:
        api = MangaAPIClient()
        ai_session = AISession(api)

        # Start AI session with initial preferences
        ai_session.start_session()

        # Set initial preferences based on AI_CONFIG
        initial_prefs = {
            'keywords': ['action', 'fantasy', 'magic'],
            'genres': ['Action', 'Fantasy', 'Adventure'],
            'themes': ['Adventure', 'Fantasy'],
            'preferred_demographics': ['shonen', 'seinen']
        }

        # Add to user_profile with the correct key
        ai_session.user_profile = {
            'initial_prefs': initial_prefs
        }

        # Log the initial preferences
        app.logger.info(f"Initial preferences: {initial_prefs}")

        # Get initial recommendations
        indices = ai_session.get_recommendations()
        app.logger.info(f"Recommendation indices: {indices}")

        if not indices:
            # If still empty, return first 10 manga as fallback
            app.logger.warning("Using fallback recommendations")
            indices = list(range(min(10, len(ai_session.recommender.data))))

        recommendations = [ai_session.recommender.data[i]
                           for i in indices[:10]]

        # Store session
        session_id = str(uuid.uuid4())
        sessions[session_id] = ai_session

        return jsonify({
            'session_id': session_id,
            'recommendations': recommendations
        })
    except Exception as e:
        logging.error(f"Session creation failed: {str(e)}")
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
        # Convert manga IDs to indices
        manga_ids = [m['id'] for m in ai_session.recommender.data]
        indices = []
        for id in likes:
            try:
                idx = manga_ids.index(id)
                indices.append(idx)
            except ValueError:
                logging.warning(f"Manga ID {id} not found in dataset")

        # Update preferences based on user likes
        ai_session.update_preferences(indices)

        # Get new recommendations
        new_indices = ai_session.get_recommendations()
        recommendations = [ai_session.recommender.data[i]
                           for i in new_indices[:10]]

        return jsonify({'recommendations': recommendations})
    except Exception as e:
        logging.error(f"Recommendation failed: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
