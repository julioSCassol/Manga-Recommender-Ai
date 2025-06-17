import numpy as np
from sklearn.preprocessing import MinMaxScaler
# Assuming recommender.py is in the same package
from .recommender import MangaRecommender
import logging

# Configure logging for the module
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

        # Call search_manga. The MangaAPIClient's search_manga method is designed
        # to handle pagination and return data that's already processed via
        # _process_results. This means it already contains authors, artists,
        # genres, themes, etc., extracted from the 'relationships' data.
        # This significantly reduces the number of individual API calls compared
        # to fetching details for each manga separately.
        initial_data = self.api.search_manga({
            'content_rating': ['safe', 'suggestive'],
            'limit': 500  # Adjusted limit to get more data initially if available
            # (MangaAPIClient.search_manga handles max 100 per API call)
        })

        if not initial_data:
            raise ValueError("No initial manga data found from API search.")

        # The 'initial_data' list now contains dictionaries, each representing
        # a manga with fields like 'id', 'title', 'authors', 'artists', 'genres',
        # 'themes', 'year', 'rating', etc., already populated by MangaAPIClient.
        # No need for further individual API calls or complex manual reprocessing here.
        logging.info(f"Received {len(initial_data)
                                 } manga entries from API search.")

        if initial_data:
            self.recommender = MangaRecommender(initial_data)
            self._normalize_features()
            logging.info(f"Successfully initialized recommender with {
                         len(initial_data)} manga entries.")
        else:
            raise ValueError(
                "No valid manga data processed from initial search.")

    # Removed the redundant _get_manga_title, _get_creators, _get_manga_tags, _get_all_tags methods.
    # These methods were used for manual processing which is now handled
    # efficiently by MangaAPIClient's _process_results when calling search_manga.

    def _normalize_features(self):
        """Normalizes numerical features like year and rating."""
        if not self.recommender or not hasattr(self.recommender, 'data') or not self.recommender.data:
            logging.warning(
                "Recommender not initialized or data is empty for normalization.")
            return

        data = self.recommender.data

        # Normalize years (assuming 1960-current year range or similar)
        # Filter out entries where 'year' is None or not a number
        years = np.array([m.get('year', 2000)
                          for m in data if m.get('year') is not None and isinstance(m.get('year'), (int, float))]).reshape(-1, 1)
        if len(years) > 0:
            # Fit the scaler to the range of years in your data
            self.scaler.fit(years)
            normalized_years = self.scaler.transform(years).flatten()
            j = 0  # Use a separate counter for normalized values
            for i, manga in enumerate(data):
                if manga.get('year') is not None and isinstance(manga.get('year'), (int, float)):
                    if j < len(normalized_years):
                        manga['normalized_year'] = normalized_years[j]
                        j += 1
                else:
                    # Assign a default normalized value or handle as missing
                    manga['normalized_year'] = 0.5

        # Normalize ratings (0-10)
        # Filter out entries where 'rating' is not a number
        ratings = np.array([m.get('rating', 0)
                            for m in data if isinstance(m.get('rating'), (int, float))]).reshape(-1, 1)
        if len(ratings) > 0:
            # Fit the scaler to the range of ratings in your data
            self.scaler.fit(ratings)
            normalized_ratings = self.scaler.transform(ratings).flatten()
            j = 0  # Use a separate counter for normalized values
            for i, manga in enumerate(data):
                if isinstance(manga.get('rating'), (int, float)):
                    if j < len(normalized_ratings):
                        manga['normalized_rating'] = normalized_ratings[j]
                        j += 1
                else:
                    # Assign a default normalized value or handle as missing
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
                        # Ensure indices are valid
                        if 0 <= i < len(self.recommender.data)]

        if not liked_mangas:
            logging.info(
                "No valid liked manga indices provided. User profile not updated.")
            return

        # Aggregate genre counts
        genre_counts = {}
        for manga in liked_mangas:
            for genre in manga.get('genres', []):
                genre_counts[genre] = genre_counts.get(genre, 0) + 1

        # Aggregate theme counts
        theme_counts = {}
        for manga in liked_mangas:
            for theme in manga.get('themes', []):
                theme_counts[theme] = theme_counts.get(theme, 0) + 1

        # Aggregate author and artist counts
        author_counts = {}
        artist_counts = {}
        for manga in liked_mangas:
            for author in manga.get('authors', []):
                author_counts[author] = author_counts.get(author, 0) + 1
            for artist in manga.get('artists', []):
                artist_counts[artist] = artist_counts.get(artist, 0) + 1

        # Calculate average year and rating
        years = [m.get('year') for m in liked_mangas if m.get(
            'year') is not None and isinstance(m.get('year'), (int, float))]
        avg_year = np.mean(years) if years else None

        ratings = [m.get('rating') for m in liked_mangas if isinstance(
            m.get('rating'), (int, float))]
        avg_rating = np.mean(ratings) if ratings else None

        # Update the user profile with aggregated preferences
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
        """
        Generates recommendations based on the user's current preferences.
        It applies a rule-based scoring system to find matching manga.
        """
        if not self.recommender or not hasattr(self.recommender, 'data') or not self.recommender.data:
            logging.warning(
                "Recommender not initialized or data is empty. Cannot generate recommendations.")
            return []

        data = self.recommender.data
        recommendations = []

        # Get the current preferences. 'preferences' takes precedence if user feedback exists,
        # otherwise, 'initial_prefs' is used (which would be set externally, e.g., in main.py).
        preferences = self.user_profile.get(
            'preferences') or self.user_profile.get('initial_prefs')

        if preferences:
            logging.info("Generating recommendations using user preferences.")
            for idx, manga in enumerate(data):
                score = 0

                # Score by common genres
                manga_genres = set(manga.get('genres', []))
                pref_genres = set()
                if 'genres' in preferences:
                    # 'genres' could be a dict (from update_preferences) or a list (from initial_prefs)
                    if isinstance(preferences['genres'], dict):
                        pref_genres = set(preferences['genres'].keys())
                    else:
                        pref_genres = set(preferences['genres'])
                genre_match = len(manga_genres & pref_genres)
                score += genre_match * 2  # Higher weight for genre match

                # Score by common themes
                manga_themes = set(manga.get('themes', []))
                pref_themes = set()
                if 'themes' in preferences:
                    if isinstance(preferences['themes'], dict):
                        pref_themes = set(preferences['themes'].keys())
                    else:
                        pref_themes = set(preferences['themes'])
                theme_match = len(manga_themes & pref_themes)
                score += theme_match * 1.5  # Moderate weight for theme match

                # Score by preferred authors
                if 'authors' in preferences:
                    for author in manga.get('authors', []):
                        if author in preferences['authors']:
                            # If 'authors' is a dict (from update_preferences), use its count; else default to 1
                            author_count = preferences['authors'][author] if isinstance(
                                preferences['authors'], dict) else 1
                            score += author_count * 1.0

                # Score by preferred artists
                if 'artists' in preferences:
                    for artist in manga.get('artists', []):
                        if artist in preferences['artists']:
                            # If 'artists' is a dict, use its count; else default to 1
                            artist_count = preferences['artists'][artist] if isinstance(
                                preferences['artists'], dict) else 1
                            score += artist_count * 1.0

                # Score by year proximity to average preferred year
                if 'avg_year' in preferences and preferences['avg_year'] is not None and manga.get('year') is not None:
                    year_diff = abs(manga['year'] - preferences['avg_year'])
                    # Score decreases with larger year difference
                    score += max(0, 5 - year_diff / 5)

                # Score by rating proximity to average preferred rating
                if 'avg_rating' in preferences and preferences['avg_rating'] is not None and manga.get('rating') is not None:
                    rating_diff = abs(
                        manga['rating'] - preferences['avg_rating'])
                    # Score decreases with larger rating difference
                    score += max(0, 5 - rating_diff)

                # Score by preferred content rating
                if 'preferred_content_rating' in preferences and manga.get('contentRating') and isinstance(preferences['preferred_content_rating'], list):
                    if manga['contentRating'] in preferences['preferred_content_rating']:
                        score += 2

                # Score by preferred demographic
                if 'preferred_demographics' in preferences and manga.get('demographic') and isinstance(preferences['preferred_demographics'], list):
                    if manga['demographic'] in preferences['preferred_demographics']:
                        score += 1.5

                # Score by preferred status
                if 'preferred_status' in preferences and manga.get('status') and isinstance(preferences['preferred_status'], list):
                    if manga['status'] in preferences['preferred_status']:
                        score += 1

                recommendations.append((idx, score))

            # Sort recommendations by score and return top N
            recommendations.sort(key=lambda x: x[1], reverse=True)
            return [idx for idx, score in recommendations[:50]]
        else:
            # Fallback for when no preferences (neither 'preferences' nor 'initial_prefs') are found
            logging.info(
                "No user preferences found in profile. Returning a default set of top 10 manga from the loaded data.")
            # This could be improved to return truly popular manga from the dataset
            # instead of just the first 10, e.g., by sorting by raw rating.
            return list(range(min(10, len(data))))

    def get_similarity_reason(self, manga_idx):
        """
        Explains why a specific manga was recommended based on user preferences.
        """
        # Ensure recommender is initialized, data exists, preferences are set, and index is valid
        if (not self.recommender or not hasattr(self.recommender, 'data') or not self.recommender.data or
            'preferences' not in self.user_profile or
            not self.user_profile['preferences'] or
                not (0 <= manga_idx < len(self.recommender.data))):
            return "Based on general preferences or initial data."

        manga = self.recommender.data[manga_idx]
        # Use 'preferences' key as it's built from liked manga
        prefs = self.user_profile['preferences']
        reasons = []

        # Check common genres
        common_genres = set(manga.get('genres', [])) & set(
            prefs['genres'].keys()) if isinstance(prefs.get('genres'), dict) else set()
        if common_genres:
            reasons.append(f"Similar genres: {', '.join(common_genres)}")

        # Check common themes
        common_themes = set(manga.get('themes', [])) & set(
            prefs['themes'].keys()) if isinstance(prefs.get('themes'), dict) else set()
        if common_themes:
            reasons.append(f"Similar themes: {', '.join(common_themes)}")

        # Check common authors
        common_authors = set(manga.get('authors', [])) & set(
            prefs['authors'].keys()) if isinstance(prefs.get('authors'), dict) else set()
        if common_authors:
            reasons.append(f"Similar authors: {', '.join(common_authors)}")

        # Check year proximity
        if prefs.get('avg_year') is not None and manga.get('year') is not None and abs(manga['year'] - prefs['avg_year']) <= 5:
            reasons.append(f"Similar publication year ({manga['year']})")

        # Check rating proximity
        # Adjust threshold as needed
        if prefs.get('avg_rating') is not None and manga.get('rating') is not None and abs(manga['rating'] - prefs['avg_rating']) <= 1.0:
            reasons.append(f"Similar average rating ({manga['rating']:.1f})")

        # Check content rating match
        if prefs.get('preferred_content_rating') and manga.get('contentRating') in prefs['preferred_content_rating']:
            reasons.append(f"Matches preferred content rating ({
                           manga['contentRating']})")

        # Check demographic match
        if prefs.get('preferred_demographics') and manga.get('demographic') in prefs['preferred_demographics']:
            reasons.append(
                f"Matches preferred demographic ({manga['demographic']})")

        # Check status match
        if prefs.get('preferred_status') and manga.get('status') in prefs['preferred_status']:
            reasons.append(f"Matches preferred status ({manga['status']})")

        return "; ".join(reasons) if reasons else "No specific similarity information available based on current preferences."
