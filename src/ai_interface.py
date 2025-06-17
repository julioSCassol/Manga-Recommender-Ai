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
        initial_data = self.api.search_manga({
            'content_rating': ['safe', 'suggestive'],
            'includes': ['author', 'artist', 'tag'],
            'limit': 20
        })

        if initial_data and isinstance(initial_data, list):
            processed_data = []
            for i, manga_summary in enumerate(initial_data):
                manga_id = manga_summary.get('id')
                if manga_id:
                    full_manga_details = self.api.get_manga_details(manga_id)
                    if full_manga_details:
                        processed_data.append(full_manga_details)
                    else:
                        print(
                            f"Failed to fetch full details for manga ID: {manga_id}")
                else:
                    print(f"Manga summary missing ID: {manga_summary}")

            if processed_data:
                self.recommender = MangaRecommender(processed_data)
                self._normalize_features()
                print(f"Successfully initialized recommender with {
                      len(processed_data)} manga entries.")
            else:
                raise ValueError(
                    "No valid manga data processed after fetching full details.")

        else:
            raise ValueError("Invalid data received from API")

    def _get_manga_title(self, manga):
        """Obtém o título do mangá em inglês ou japonês"""
        title = manga.get('title', {})
        if isinstance(title, dict):
            return title.get('en') or title.get('ja') or next(iter(title.values()), '') or ''
        return str(title)

    def _get_creators(self, manga, role):
        """Obtém lista de criadores (autores/artistas)"""
        creators = manga.get(role+'s', [])
        if isinstance(creators, list):
            return [c if isinstance(c, str) else str(c) for c in creators]
        return []

    def _get_manga_tags(self, manga, group):
        """Obtém tags específicas (gêneros ou temas)"""
        tags = manga.get('tags', [])
        result = []
        for tag in tags:
            if isinstance(tag, dict) and tag.get('group') == group:
                name = tag.get('name', {})
                if isinstance(name, dict):
                    result.append(name.get('en') or next(
                        iter(name.values()), ''))
        return result

    def _get_all_tags(self, manga):
        """Obtém todas as tags como strings simples"""
        tags = manga.get('tags', [])
        result = []
        for tag in tags:
            if isinstance(tag, dict):
                name = tag.get('name', {})
                if isinstance(name, dict):
                    result.append(name.get('en') or next(
                        iter(name.values()), ''))
        return result

    def _normalize_features(self):
        """Normaliza as features numéricas"""
        if not self.recommender or not hasattr(self.recommender, 'data'):
            return

        data = self.recommender.data

        years = np.array([m.get('year', 2000)
                         for m in data if m.get('year') is not None]).reshape(-1, 1)
        if len(years) > 0:
            normalized_years = self.scaler.fit_transform(years).flatten()
            for i, manga in enumerate(data):
                if i < len(normalized_years):
                    manga['normalized_year'] = normalized_years[i]

        ratings = np.array([m.get('rating', 0) for m in data]).reshape(-1, 1)
        if len(ratings) > 0:
            normalized_ratings = self.scaler.fit_transform(ratings).flatten()
            for i, manga in enumerate(data):
                if i < len(normalized_ratings):
                    manga['normalized_rating'] = normalized_ratings[i]

    def update_preferences(self, liked_indices):
        """Atualiza preferências com base nos mangás curtidos"""
        if not self.recommender or not hasattr(self.recommender, 'data'):
            return

        liked_mangas = [self.recommender.data[i] for i in liked_indices
                        if i < len(self.recommender.data)]

        if not liked_mangas:
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

        years = [m.get('year', 2000)
                 for m in liked_mangas if m.get('year') is not None]
        avg_year = np.mean(years) if years else None

        ratings = [m.get('rating', 0) for m in liked_mangas]
        avg_rating = np.mean(ratings) if ratings else None

        self.user_profile['preferences'] = {
            'genres': genre_counts,
            'themes': theme_counts,
            'authors': author_counts,
            'artists': artist_counts,
            'avg_year': avg_year,
            'avg_rating': avg_rating,
            'preferred_content_rating': list({m.get('contentRating', '') for m in liked_mangas}),
            'preferred_demographics': list({m.get('demographic', '') for m in liked_mangas}),
            'preferred_status': list({m.get('status', '') for m in liked_mangas})
        }

    def get_recommendations(self):
        """Gera recomendações baseadas nas preferências"""
        if not self.recommender or not hasattr(self.recommender, 'data'):
            return []

        data = self.recommender.data
        recommendations = []

        # Check both 'preferences' and 'initial_prefs' keys
        preferences = self.user_profile.get(
            'preferences') or self.user_profile.get('initial_prefs')

        if preferences:
            # Add debug logging
            print(f"Using preferences: {preferences.keys()}")

            for idx, manga in enumerate(data):
                score = 0

                # Handle genres
                manga_genres = set(manga.get('genres', []))
                pref_genres = set()
                if 'genres' in preferences:
                    if isinstance(preferences['genres'], dict):
                        pref_genres = set(preferences['genres'].keys())
                    else:
                        pref_genres = set(preferences['genres'])
                genre_match = len(manga_genres & pref_genres)
                score += genre_match * 2

                # Handle themes
                manga_themes = set(manga.get('themes', []))
                pref_themes = set()
                if 'themes' in preferences:
                    if isinstance(preferences['themes'], dict):
                        pref_themes = set(preferences['themes'].keys())
                    else:
                        pref_themes = set(preferences['themes'])
                theme_match = len(manga_themes & pref_themes)
                score += theme_match * 1.5

                # Handle authors
                if 'authors' in preferences:
                    for author in manga.get('authors', []):
                        if author in preferences['authors']:
                            author_count = preferences['authors'][author] if isinstance(
                                preferences['authors'], dict) else 1
                            score += author_count * 1.0

                # Handle artists
                if 'artists' in preferences:
                    for artist in manga.get('artists', []):
                        if artist in preferences['artists']:
                            artist_count = preferences['artists'][artist] if isinstance(
                                preferences['artists'], dict) else 1
                            score += artist_count * 1.0

                if 'avg_year' in preferences and preferences['avg_year'] and manga.get('year'):
                    year_diff = abs(manga['year'] - preferences['avg_year'])
                    score += max(0, 5 - year_diff / 5)

                if 'avg_rating' in preferences and preferences['avg_rating'] and manga.get('rating'):
                    rating_diff = abs(
                        manga['rating'] - preferences['avg_rating'])
                    score += max(0, 5 - rating_diff)

                if 'preferred_content_rating' in preferences and manga.get('contentRating'):
                    if manga['contentRating'] in preferences['preferred_content_rating']:
                        score += 2

                if 'preferred_demographics' in preferences and manga.get('demographic'):
                    if manga['demographic'] in preferences['preferred_demographics']:
                        score += 1.5

                if 'preferred_status' in preferences and manga.get('status'):
                    if manga['status'] in preferences['preferred_status']:
                        score += 1

                recommendations.append((idx, score))

            recommendations.sort(key=lambda x: x[1], reverse=True)
            return [idx for idx, score in recommendations[:50]]
        else:
            # Fallback to default recommendations if no preferences are found
            print("No preferences found, returning default recommendations")
            return list(range(min(10, len(data))))

    def get_similarity_reason(self, manga_idx):
        """Explica por que o mangá foi recomendado"""
        if (not self.recommender or not hasattr(self.recommender, 'data') or
           'preferences' not in self.user_profile or
                manga_idx >= len(self.recommender.data)):
            return "Baseado nas preferências iniciais"

        manga = self.recommender.data[manga_idx]
        prefs = self.user_profile['preferences']
        reasons = []

        common_genres = set(manga.get('genres', [])) & set(
            prefs['genres'].keys())
        if common_genres:
            reasons.append(f"Gêneros similares: {', '.join(common_genres)}")

        common_themes = set(manga.get('themes', [])) & set(
            prefs['themes'].keys())
        if common_themes:
            reasons.append(f"Temas similares: {', '.join(common_themes)}")

        common_authors = set(manga.get('authors', [])) & set(
            prefs['authors'].keys())
        if common_authors:
            reasons.append(f"Autores similares: {', '.join(common_authors)}")

        if prefs['avg_year'] and manga.get('year') and abs(manga['year'] - prefs['avg_year']) <= 5:
            reasons.append(f"Ano de publicação similar ({manga['year']})")

        return "; ".join(reasons) if reasons else "Sem informações de similaridade"
