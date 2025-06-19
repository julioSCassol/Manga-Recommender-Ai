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

# New endpoint to get top manga
@app.route('/api/top-manga', methods=['GET'])
def get_top_manga():
    try:
        api = MangaAPIClient()
        
        # Fetch top manga with high ratings
        top_manga = api.search_manga({
            'content_rating': ['safe', 'suggestive'],
            'order[rating]': 'desc',
            'limit': 100
        })
        
        # Sort by rating descending
        top_manga.sort(key=lambda x: x.get('rating', 0), reverse=True)
        
        return jsonify({
            'top_manga': top_manga[:100]  # Return top 100
        })
    except Exception as e:
        logging.error(f"Failed to fetch top manga: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/session', methods=['POST'])
def create_session():
    try:
        data = request.json
        preferences = data.get('preferences', {})
        api = MangaAPIClient()
        ai_session = AISession(api)
        ai_session.start_session()

        # Map time period to average year
        period_map = {
            '1990s': 1995,
            '2000s': 2005,
            '2010s': 2015,
            'recent': 2020,
            'classic': 1985,
            'any': None
        }
        avg_year = period_map.get(preferences.get('time_period', 'any'), None)
        
        # Create initial preferences
        initial_user_prefs = {
            'keywords': preferences.get('genres', []) + preferences.get('themes', []),
            'genres': preferences.get('genres', []),
            'themes': preferences.get('themes', []),
            'preferred_publication_types': preferences.get('preferred_demographics', []),
            'preferred_content_rating': preferences.get('preferred_content_rating', []),
            'preferred_status': preferences.get('preferred_status', []),
            'avg_year': avg_year,
            'avg_rating': preferences.get('min_rating', 7.0)
        }

        app.logger.info(f"Initial preferences: {initial_user_prefs}")
        ai_session.user_profile['initial_prefs'] = initial_user_prefs

        initial_indices = ai_session.recommender.find_similar(
            initial_user_prefs, n=10
        )

        if not initial_indices:
            app.logger.warning("Using fallback recommendations")
            initial_indices = list(range(min(10, len(ai_session.recommender.data))))

        recommendations = [ai_session.recommender.data[i] for i in initial_indices]

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
        recommendations = [ai_session.recommender.data[i] for i in new_indices[:10]]

        return jsonify({'recommendations': recommendations})
    except Exception as e:
        logging.error(f"Recommendation failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)