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
        api = MangaAPIClient()
        ai_session = AISession(api)
        ai_session.start_session()

        initial_user_prefs = {
            'keywords': ['action', 'fantasy', 'magic'],
            'genres': ['Action', 'Fantasy', 'Adventure'],
            'themes': ['Adventure', 'Fantasy'],
            'preferred_publication_types': ['shoujo']
        }

        ai_session.user_profile['initial_prefs'] = initial_user_prefs

        app.logger.info(f"Initial preferences: {initial_user_prefs}")

        initial_indices = ai_session.recommender.find_similar(
            initial_user_prefs, n=10)

        if not initial_indices:
            app.logger.warning("Using fallback recommendations")
            indices = list(range(min(10, len(ai_session.recommender.data))))

        recommendations = [ai_session.recommender.data[i]
                           for i in initial_indices]

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
        manga_ids = [m['id'] for m in ai_session.recommender.data]
        indices = []
        for id in likes:
            try:
                idx = manga_ids.index(id)
                indices.append(idx)
            except ValueError:
                logging.warning(f"Manga ID {id} not found in dataset")

        ai_session.update_preferences(indices)

        new_indices = ai_session.get_recommendations()
        recommendations = [ai_session.recommender.data[i]
                           for i in new_indices[:10]]

        return jsonify({'recommendations': recommendations})
    except Exception as e:
        logging.error(f"Recommendation failed: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
