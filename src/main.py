from api_client import MangaAPIClient
from ai_interface import AISession
import json

def main():
    api = MangaAPIClient()
    ai_session = AISession(api)
    
    try:
        print("Iniciando sistema...")
        ai_session.start_session()
        
        # seta preferencia inicial
        ai_session.user_profile = {
            'initial_prefs': {
                'genres': ['Action', 'Fantasy'],
                'keywords': ['hero journey', 'magic']
            }
        }
        
        # get recomendações iniciais
        print("\n=== Recomendação Inicial ===")
        initial_indices = ai_session.get_recommendations()
        initial_titles = [ai_session.recommender.data[i]['title'] 
                        for i in initial_indices[:10]]
        print(json.dumps(initial_titles, indent=2, ensure_ascii=False))
        
        # simula user feedback
        ai_session.update_preferences([0, 1, 2])  # gostou dos 3 primeiros resultados
        
        # Get recomendação personalizada
        print("\n=== Recomendação Personalizada ===")
        personalized_indices = ai_session.get_recommendations()
        personalized_titles = [ai_session.recommender.data[i]['title'] 
                             for i in personalized_indices[:10]]
        print(json.dumps(personalized_titles, indent=2, ensure_ascii=False))
        
    except KeyboardInterrupt:
        print("\nOperacaoo cancelada pelo usuario.")
    except Exception as e:
        print(f"\nError: {str(e)}")
    finally:
        print("\nFim da sessao.")

if __name__ == "__main__":
    main()