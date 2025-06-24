import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MultiLabelBinarizer
from scipy.sparse import hstack
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class MangaRecommender:
    def __init__(self, data):
        self.data = data
        self._prepare_features()

    def _prepare_features(self):
        all_genres = set()
        all_publication_types = set()
        all_content_ratings = set()
        all_statuses = set()

        # First pass: collect all unique values and ratings
        ratings = []
        for manga in self.data:
            # Collect rating
            rating = manga.get('rating', 0)
            ratings.append(rating)

            # Collect other features
            if 'genres' in manga and isinstance(manga['genres'], list):
                all_genres.update(manga['genres'])

            publication_type = manga.get('publication_type')
            if publication_type and isinstance(publication_type, str):
                all_publication_types.add(publication_type)

            content_rating = manga.get(
                'content_rating') or manga.get('contentRating')
            if content_rating and isinstance(content_rating, str):
                all_content_ratings.add(content_rating)

            status = manga.get('status')
            if status and isinstance(status, str):
                all_statuses.add(status)

        # Normalize ratings
        self.min_rating = min(ratings) if ratings else 0
        self.max_rating = max(ratings) if ratings else 10
        self.normalized_ratings = np.array(
            [(r - self.min_rating) / (self.max_rating - self.min_rating + 1e-8)
             for r in ratings]
        ).reshape(-1, 1)

        # Rest of your feature preparation code...
        self.tfidf = TfidfVectorizer(stop_words='english', max_features=5000)
        self.mlb_genres = MultiLabelBinarizer(
            classes=list(all_genres) if all_genres else ['unknown_genre']
        )
        self.mlb_publication_types = MultiLabelBinarizer(
            classes=list(all_publication_types) if all_publication_types else [
                'unknown_publication_type']
        )
        self.mlb_content_ratings = MultiLabelBinarizer(
            classes=list(all_content_ratings) if all_content_ratings else [
                'unknown_content_rating']
        )
        self.mlb_statuses = MultiLabelBinarizer(
            classes=list(all_statuses) if all_statuses else ['unknown_status']
        )

        # Prepare data for transformation
        text_data = []
        genre_data = []
        publication_type_data = []
        content_rating_data = []
        status_data = []

        for manga in self.data:
            # Text features: title + description
            title = manga.get('title', '')
            description = manga.get('description', '')
            text_data.append(f"{title} {description}".strip())

            # Categorical features
            genre_data.append(manga.get('genres', []))

            pub_type_val = manga.get('publication_type')
            publication_type_data.append(
                [pub_type_val] if pub_type_val and isinstance(pub_type_val, str) else [])

            content_rating_val = manga.get(
                'content_rating') or manga.get('contentRating')
            content_rating_data.append([content_rating_val] if content_rating_val and isinstance(
                content_rating_val, str) else [])

            status_val = manga.get('status')
            status_data.append(
                [status_val] if status_val and isinstance(status_val, str) else [])

        # Transform features
        self.tfidf_matrix = self.tfidf.fit_transform(text_data)
        self.genre_matrix = self.mlb_genres.fit_transform(genre_data)
        self.publication_type_matrix = self.mlb_publication_types.fit_transform(
            publication_type_data
        )
        self.content_rating_matrix = self.mlb_content_ratings.fit_transform(
            content_rating_data)
        self.status_matrix = self.mlb_statuses.fit_transform(status_data)

        # Combine all features into single sparse matrix
        rating_weight = 6.0  # Adjust this value as needed
        content_rating_weight = 10.0  # Adjust this value as needed
        self.feature_matrix = hstack(
            [self.tfidf_matrix,
             self.genre_matrix,
             self.publication_type_matrix,
             self.content_rating_matrix * content_rating_weight,
             self.status_matrix,
             self.normalized_ratings * rating_weight
             ]).tocsr()

        logging.info(f"Feature matrix created with shape: {self.feature_matrix.shape}")

    def find_similar(self, user_preferences, n=10):
        """
        Content-based filtering for initial recommendations.
        Uses keywords, genres, and preferred_publication_types.
        """
        try:
            # Text preferences
            pref_text = " ".join(user_preferences.get('keywords', []))
            pref_vector = self.tfidf.transform([pref_text])

            # Genre preferences
            valid_genres = [g for g in user_preferences.get('genres', [])
                            if g in self.mlb_genres.classes_]
            pref_genres_matrix = self.mlb_genres.transform([valid_genres]) if valid_genres \
                else np.zeros((1, len(self.mlb_genres.classes_)))

            # Publication type preferences
            valid_publication_types = [pt for pt in user_preferences.get('preferred_publication_types', [])
                                       if pt in self.mlb_publication_types.classes_]
            pref_publication_types_matrix = self.mlb_publication_types.transform([valid_publication_types]) \
                if valid_publication_types \
                else np.zeros((1, len(self.mlb_publication_types.classes_)))

            # Content rating preferences
            valid_content_ratings = [cr for cr in user_preferences.get('preferred_content_rating', [])
                                     if cr in self.mlb_content_ratings.classes_]
            pref_content_ratings_matrix = self.mlb_content_ratings.transform([valid_content_ratings]) \
                if valid_content_ratings \
                else np.zeros((1, len(self.mlb_content_ratings.classes_)))

            # Status preferences
            valid_statuses = [s for s in user_preferences.get('preferred_status', [])
                              if s in self.mlb_statuses.classes_]
            pref_statuses_matrix = self.mlb_statuses.transform([valid_statuses]) \
                if valid_statuses \
                else np.zeros((1, len(self.mlb_statuses.classes_)))

            target_rating = user_preferences.get('avg_rating', 7.0)
            # Normalize the target rating
            normalized_target_rating = (target_rating - self.min_rating) / \
                (self.max_rating - self.min_rating + 1e-8)
            rating_vector = np.array([[normalized_target_rating]])

            # Combine all preference vectors
            user_vector = hstack([
                pref_vector,
                pref_genres_matrix,
                pref_publication_types_matrix,
                pref_content_ratings_matrix,
                pref_statuses_matrix,
                rating_vector
            ])

            # Calculate similarity scores
            scores = cosine_similarity(user_vector, self.feature_matrix)
            top_indices = scores[0].argsort()[-n:][::-1].tolist()
            logging.info(f"Found {len(top_indices)} similar manga based on preferences")
            return top_indices
        except Exception as e:
            logging.error(f"find_similar failed: {str(e)}")
            # Return random indices as fallback
            return list(np.random.choice(len(self.data), size=min(n, len(self.data)), replace=False))
