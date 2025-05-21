import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MultiLabelBinarizer
from scipy.sparse import hstack, csr_matrix

class MangaRecommender:
    def __init__(self, data):
        self.data = data
        self._prepare_features()
        
    def _prepare_features(self):
        """Create AI-ready feature matrix from manga data"""
        all_genres = set()
        for manga in self.data:
            if 'genres' in manga:
                all_genres.update(manga['genres'])
        
        self.tfidf = TfidfVectorizer(
            stop_words='english',
            max_features=5000
        )
        self.mlb = MultiLabelBinarizer(classes=list(all_genres))
        
        text_data = []
        genre_data = []
        
        for manga in self.data:
            title = manga.get('title', '')
            description = manga.get('description', '')
            text_data.append(f"{title} {description}".strip())
            
            genre_data.append(manga.get('genres', []))
        
        self.tfidf_matrix = self.tfidf.fit_transform(text_data)
        self.genre_matrix = self.mlb.fit_transform(genre_data)
        
        self.feature_matrix = hstack([self.tfidf_matrix, self.genre_matrix]).tocsr()
    
    def recommend(self, manga_index, n=5):
        """Get similar manga recommendations"""
        similarities = cosine_similarity(
            self.feature_matrix[manga_index],
            self.feature_matrix
        )
        return similarities[0].argsort()[-n-1:-1][::-1].tolist()
    
    def find_similar(self, user_preferences, n=10):
        """Content-based filtering"""
        # filtra generos
        valid_genres = [g for g in user_preferences.get('genres', []) 
                      if g in self.mlb.classes_]
        
        # cria vetor de preferências
        pref_text = " ".join(user_preferences.get('keywords', []))
        pref_vector = self.tfidf.transform([pref_text])
        pref_genres = self.mlb.transform([valid_genres]) if valid_genres \
                      else np.zeros((1, len(self.mlb.classes_)))
        
        # combina features
        user_vector = hstack([pref_vector, pref_genres])
        
        # calcula similaridade
        scores = cosine_similarity(user_vector, self.feature_matrix)
        return scores[0].argsort()[-n:][::-1].tolist()