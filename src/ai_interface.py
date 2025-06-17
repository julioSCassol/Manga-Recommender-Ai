import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from .recommender import MangaRecommender

class AISession:
    def __init__(self, api_client):
        self.api = api_client
        self.user_profile = {}
        self.recommender = None
        
    def start_session(self):
        initial_data = self.api.search_manga({
            'content_rating': ['safe', 'suggestive'],
            'limit': 200
        })
        if initial_data:
            self.recommender = MangaRecommender(initial_data)
        else:
            raise ValueError("No data received from API")
    
    def update_preferences(self, liked_manga_ids):
        """Update AI model based on user likes"""
        if not self.recommender:
            return
            
        csr_matrix = self.recommender.feature_matrix.tocsr()
        liked_features = csr_matrix[liked_manga_ids]
        self.user_profile['preference_vector'] = np.asarray(
            liked_features.mean(axis=0)
        ).squeeze()
        
    def get_recommendations(self):
        """Hybrid recommendations"""
        if not self.recommender:
            return []
            
        if 'preference_vector' in self.user_profile:
            scores = cosine_similarity(
                [self.user_profile['preference_vector']],
                self.recommender.feature_matrix
            )
            recs = np.argsort(-scores[0])[:10]
        else:
            recs = self.recommender.find_similar(
                self.user_profile.get('initial_prefs', {})
            )
        
        return [int(i) for i in recs]