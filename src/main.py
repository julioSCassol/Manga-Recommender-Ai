from .api_client import MangaAPIClient
from .ai_interface import AISession
import json


# sepa quando for transformar em api, mandar soh o id do manga
# ai o front pega info do manga com o id
def main():
    api = MangaAPIClient()
    ai_session = AISession(api)

    try:
        print("Iniciando sistema...")
        ai_session.start_session()

        print("\n=== Recomendação Inicial (baseada em preferências configuradas) ===")
        initial_user_prefs = {
            'keywords': ['action', 'fantasy', 'magic'],
            'genres': ['Action', 'Fantasy', 'Adventure'],
            'authors': [],
            'artists': [],
            'avg_year': 2018,
            'avg_rating': 7.5,
            'preferred_content_rating': ['safe', 'suggestive'],
            'preferred_demographics': ['shoujo'],
            'preferred_status': ['ongoing']
        }
        initial_indices = ai_session.recommender.find_similar(
            initial_user_prefs, n=10)

        print(f"Initial indices: {initial_indices}")

        if not initial_indices:
            print(
                "No initial recommendations found based on default preferences. Consider adjusting them.")
            return

        initial_results = [{
            'title': ai_session.recommender.data[i]['title'],
            'author': ai_session.recommender.data[i].get('authors', ['Desconhecido'])[0],
            'year': ai_session.recommender.data[i].get('year', 'N/A'),
            'rating': ai_session.recommender.data[i].get('rating', 0),
            'status': ai_session.recommender.data[i].get('status', 'N/A')
        } for i in initial_indices]

        print(json.dumps(initial_results, indent=2, ensure_ascii=False))

        liked_indices_for_feedback = [
            initial_indices[0], initial_indices[1], initial_indices[2]]
        print("\nUsuário curtiu:")
        for idx in liked_indices_for_feedback:
            manga_title = ai_session.recommender.data[idx]['title']
            manga_author = ai_session.recommender.data[idx].get(
                'authors', ['Desconhecido'])[0]
            print(f"- {manga_title} ({manga_author})")

        ai_session.update_preferences(liked_indices_for_feedback)

        print("\n=== Recomendação Personalizada ===")
        personalized_indices = ai_session.get_recommendations()
        if not personalized_indices:
            print(
                "No personalized recommendations found. Consider adjusting user preferences or dataset.")
            return

        personalized_results = [{
            'title': ai_session.recommender.data[i]['title'],
            'author': ai_session.recommender.data[i].get('authors', ['Desconhecido'])[0],
            'similarity_reason': ai_session.get_similarity_reason(i)
        } for i in personalized_indices[:10]]

    except KeyboardInterrupt:
        print("\nOperação cancelada pelo usuário.")
    except Exception as e:
        print(f"\nErro: {str(e)}")
    finally:
        print("\nFim da sessão.")


if __name__ == '__main__':
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()