import numpy as np
from sklearn.preprocessing import MinMaxScaler
from .recommender import MangaRecommender


class AISession:
    def __init__(self, api_client):
        self.api = api_client
        self.user_profile = {}
        self.recommender = None
        self.scaler = MinMaxScaler()

    def start_session(self):
        try:
            initial_data = self.api.search_manga({}, limit=1000)

            if not initial_data:
                raise ValueError(
                    "No initial manga data found from API search.")

            self.recommender = MangaRecommender(initial_data)

            self._normalize_features()

        except Exception as e:
            print(f"Failed to initialize session: {str(e)}")
            print("Full exception traceback:")
            raise ValueError("Failed to initialize AI session") from e

    def _normalize_features(self):
        if not self.recommender or not hasattr(self.recommender, 'data') or not self.recommender.data:
            print(
                "Recommender not initialized or data is empty for normalization.")
            return

        data = self.recommender.data

        years = np.array([m.get('year', 2000)
                          for m in data if m.get('year') is not None and isinstance(m.get('year'), (int, float))]).reshape(-1, 1)
        if len(years) > 0:
            self.scaler.fit(years)
            normalized_years = self.scaler.transform(years).flatten()
            j = 0
            for i, manga in enumerate(data):
                if manga.get('year') is not None and isinstance(manga.get('year'), (int, float)):
                    if j < len(normalized_years):
                        manga['normalized_year'] = normalized_years[j]
                        j += 1
                else:
                    manga['normalized_year'] = 0.5

        ratings = np.array([m.get('rating', 0)
                            for m in data if isinstance(m.get('rating'), (int, float))]).reshape(-1, 1)
        if len(ratings) > 0:
            self.scaler.fit(ratings)
            normalized_ratings = self.scaler.transform(ratings).flatten()
            j = 0
            for i, manga in enumerate(data):
                if isinstance(manga.get('rating'), (int, float)):
                    if j < len(normalized_ratings):
                        manga['normalized_rating'] = normalized_ratings[j]
                        j += 1
                else:
                    manga['normalized_rating'] = 0.5

    def update_preferences(self, liked_indices):
        if not self.recommender or not hasattr(self.recommender, 'data') or not self.recommender.data:
            print(
                "Recommender not initialized or data is empty. Cannot update preferences.")
            return

        liked_mangas = [self.recommender.data[i] for i in liked_indices
                        if 0 <= i < len(self.recommender.data)]

        if not liked_mangas:
            print(
                "No valid liked manga indices provided. User profile not updated.")
            return

        genre_counts = {}
        for manga in liked_mangas:
            for genre in manga.get('genres', []):
                genre_counts[genre] = genre_counts.get(genre, 0) + 1

        theme_counts = {}
        for manga in liked_mangas:
            for theme in manga.get('themes', []):
                theme_counts[theme] = theme_counts.get(theme, 0) + 1

        author_counts = {}
        artist_counts = {}
        for manga in liked_mangas:
            for author in manga.get('authors', []):
                author_counts[author] = author_counts.get(author, 0) + 1
            for artist in manga.get('artists', []):
                artist_counts[artist] = artist_counts.get(artist, 0) + 1

        years = [m.get('year') for m in liked_mangas if m.get(
            'year') is not None and isinstance(m.get('year'), (int, float))]
        avg_year = np.mean(years) if years else None

        ratings = [m.get('rating') for m in liked_mangas if isinstance(
            m.get('rating'), (int, float))]
        avg_rating = np.mean(ratings) if ratings else None

        self.user_profile['preferences'] = {
            'genres': genre_counts,
            'themes': theme_counts,
            'authors': author_counts,
            'artists': artist_counts,
            'avg_year': avg_year,
            'avg_rating': avg_rating,
            'preferred_content_rating': list(set(m.get('contentRating', '') for m in liked_mangas if m.get('contentRating'))),
            'preferred_demographics': list(set(m.get('demographic', '') for m in liked_mangas if m.get('demographic'))),
            'preferred_status': list(set(m.get('status', '') for m in liked_mangas if m.get('status')))
        }
        print(self.user_profile['preferences'])

    def get_recommendations(self):
        if not self.recommender or not hasattr(self.recommender, 'data') or not self.recommender.data:
            print(
                "Recommender not initialized or data is empty. Cannot generate recommendations.")
            return []

        preferences = self.user_profile.get(
            'preferences') or self.user_profile.get('initial_prefs')

        if preferences:
            print("Generating recommendations using user preferences.")
            indices = self.recommender.find_similar(preferences, n=50)
            return [self.recommender.data[i] for i in indices]
        else:
            print(
                "No user preferences found in profile. Returning a default set of top manga from the loaded data.")
            sorted_data = sorted(self.recommender.data,
                                 key=lambda x: x.get('rating', 0),
                                 reverse=True)
            return sorted_data[:10]
