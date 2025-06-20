import numpy as np
from sklearn.preprocessing import MinMaxScaler
import logging
from .recommender import MangaRecommender

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


class AISession:
    def __init__(self, api_client):
        self.api = api_client
        self.user_profile = {}
        self.recommender = None
        self.scaler = MinMaxScaler()

    def start_session(self):
        """
        Initializes the AI session by fetching manga data.
        It relies on api_client.search_manga to get already processed and enriched data
        efficiently, avoiding individual get_manga_details calls for bulk loading.
        """
        logging.info("Starting AI session: Fetching initial manga data...")
        
        try:
            # Fetch initial manga data
            initial_data = self.api.search_manga({
                'content_rating': ['safe', 'suggestive'],
                'limit': 1000
            })
            
            if not initial_data:
                raise ValueError("No initial manga data found from API search.")
            
            # Initialize recommender
            logging.info("Creating MangaRecommender instance...")
            self.recommender = MangaRecommender(initial_data)
            logging.info(f"Initialized recommender with {len(initial_data)} manga entries")
            
            # Normalize features
            self._normalize_features()
            logging.info("Feature normalization complete")
            
        except Exception as e:
            logging.error(f"Failed to initialize session: {str(e)}")
            logging.exception("Full exception traceback:")
            raise ValueError("Failed to initialize AI session") from e

    def _normalize_features(self):
        """Normalizes numerical features like year and rating."""
        if not self.recommender or not hasattr(self.recommender, 'data') or not self.recommender.data:
            logging.warning(
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
        """
        Updates user preferences based on a list of liked manga indices.
        This forms the basis for personalized recommendations.
        """
        if not self.recommender or not hasattr(self.recommender, 'data') or not self.recommender.data:
            logging.warning(
                "Recommender not initialized or data is empty. Cannot update preferences.")
            return

        liked_mangas = [self.recommender.data[i] for i in liked_indices
                        if 0 <= i < len(self.recommender.data)]

        if not liked_mangas:
            logging.info(
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
        logging.info("User preferences updated based on liked manga.")

    def get_recommendations(self):
        if not self.recommender or not hasattr(self.recommender, 'data') or not self.recommender.data:
            logging.warning(
                "Recommender not initialized or data is empty. Cannot generate recommendations.")
            return []

        # Use recommender for personalized results
        preferences = self.user_profile.get(
            'preferences') or self.user_profile.get('initial_prefs')
        
        if preferences:
            logging.info("Generating recommendations using user preferences.")
            # Get recommendations based on preferences
            indices = self.recommender.find_similar(preferences, n=50)
            return [self.recommender.data[i] for i in indices]
        else:
            logging.info(
                "No user preferences found in profile. Returning a default set of top manga from the loaded data.")
            # Return top rated from the initial dataset, not from API
            sorted_data = sorted(self.recommender.data, 
                                key=lambda x: x.get('rating', 0), 
                                reverse=True)
            return sorted_data[:10]

    def get_similarity_reason(self, manga_idx):
        """
        Explains why a specific manga was recommended based on user preferences.
        """
        if (not self.recommender or not hasattr(self.recommender, 'data') or not self.recommender.data or
            'preferences' not in self.user_profile or
            not self.user_profile['preferences'] or
                not (0 <= manga_idx < len(self.recommender.data))):
            return "Based on general preferences or initial data."

        manga = self.recommender.data[manga_idx]
        prefs = self.user_profile['preferences']
        reasons = []

        common_genres = set(manga.get('genres', [])) & set(
            prefs['genres'].keys()) if isinstance(prefs.get('genres'), dict) else set()
        if common_genres:
            reasons.append(f"Similar genres: {', '.join(common_genres)}")

        common_themes = set(manga.get('themes', [])) & set(
            prefs['themes'].keys()) if isinstance(prefs.get('themes'), dict) else set()
        if common_themes:
            reasons.append(f"Similar themes: {', '.join(common_themes)}")

        common_authors = set(manga.get('authors', [])) & set(
            prefs['authors'].keys()) if isinstance(prefs.get('authors'), dict) else set()
        if common_authors:
            reasons.append(f"Similar authors: {', '.join(common_authors)}")

        if prefs.get('avg_year') is not None and manga.get('year') is not None and abs(manga['year'] - prefs['avg_year']) <= 5:
            reasons.append(f"Similar publication year ({manga['year']})")

        if prefs.get('avg_rating') is not None and manga.get('rating') is not None and abs(manga['rating'] - prefs['avg_rating']) <= 1.0:
            reasons.append(f"Similar average rating ({manga['rating']:.1f})")

        if prefs.get('preferred_content_rating') and manga.get('contentRating') in prefs['preferred_content_rating']:
            reasons.append(f"Matches preferred content rating ({manga['contentRating']})")

        if prefs.get('preferred_demographics') and manga.get('demographic') in prefs['preferred_demographics']:
            reasons.append(
                f"Matches preferred demographic ({manga['demographic']})")

        if prefs.get('preferred_status') and manga.get('status') in prefs['preferred_status']:
            reasons.append(f"Matches preferred status ({manga['status']})")

        return "; ".join(reasons) if reasons else "No specific similarity information available based on current preferences."