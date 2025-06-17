import requests
from datetime import datetime, timedelta
import time
import logging
from typing import Dict, List, Optional
from dateutil import parser


class MangaAPIClient:
    def __init__(self, max_cache_age: int = 60):
        self.base_url = "https://api.mangadex.org"
        self.cache: Dict = {}
        self.max_cache_age = timedelta(minutes=max_cache_age)
        self.request_timeout = 15
        self.retry_delay = 3
        self.max_retries = 3
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MangaAI/1.0 (+https://github.com/your-repo)'
        })

    def search_manga(self, filters: Dict, limit: int = 100) -> List[Dict]:
        """
        Search manga with enhanced reliability and pagination handling
        """
        params = self._build_params(filters, limit)
        cache_key = self._generate_cache_key(params)

        if self._is_cache_valid(cache_key):
            logging.info("Returning cached results")
            return self.cache[cache_key]['data']

        all_results = []
        retries = 0
        total_processed = 0

        try:
            while total_processed < limit:
                response = self._safe_request(
                    method='GET',
                    url=f"{self.base_url}/manga",
                    params=params,
                    retries=self.max_retries
                )

                if not response:
                    break

                data = response.json()
                processed = self._process_results(data)
                all_results.extend(processed)
                total_processed += len(processed)

                if not data.get('offset') or len(processed) == 0:
                    break

                params['offset'] = data['offset'] + data['limit']

        except Exception as e:
            logging.error(f"Search failed: {str(e)}")

        self.cache[cache_key] = {
            'timestamp': datetime.now(),
            'data': all_results[:limit]
        }
        return self.cache[cache_key]['data']

    def get_manga_details(self, manga_id: str) -> Optional[Dict]:
        """Get manga details with error handling"""
        try:
            response = self._safe_request(
                method='GET',
                url=f"{self.base_url}/manga/{manga_id}",
                params={'includes[]': ['author', 'artist', 'cover_art', 'tag']},
                retries=self.max_retries
            )
            return self._process_full_details(response.json()) if response else None
        except Exception as e:
            logging.error(f"Failed to get details for {manga_id}: {str(e)}")
            return None

    def _build_params(self, filters: Dict, limit: int) -> Dict:
        """Construct and validate API parameters"""
        params = {
            'limit': min(limit, 100),
            'includes[]': ['author', 'artist', 'cover_art', 'tag'],
            'contentRating[]': filters.get('content_rating', ['safe', 'suggestive']),
            'order[rating]': 'desc'
        }

        param_mapping = {
            'year': 'year',
            'authors': 'authors',
            'artists': 'artists',
            'last_chapter_date': 'updatedAtSince',
            'genres': 'includedTags',
            'language': 'originalLanguage[]',
            'publication_type': 'publicationDemographic[]',
            'status': 'status[]'
        }

        for key, api_key in param_mapping.items():
            if key in filters:
                params[api_key] = filters[key]

        return params

    def _process_results(self, data: Dict) -> List[Dict]:
        """Process API response with error handling"""
        processed = []
        for manga in data.get('data', []):
            try:
                attributes = manga.get('attributes', {})
                relationships = manga.get('relationships', [])

                processed.append({
                    'id': manga.get('id', ''),
                    'title': attributes.get('title', {}).get('en', 'No title'),
                    'description': attributes.get('description', {}).get('en', ''),
                    'year': attributes.get('year'),
                    'authors': self._safe_get_creators(relationships, 'author'),
                    'artists': self._safe_get_creators(relationships, 'artist'),
                    'last_updated': parser.parse(attributes.get('updatedAt')) if attributes.get('updatedAt') else None,
                    'genres': [
                        tag['attributes']['name'].get('en') or next(
                            iter(tag['attributes']['name'].values()))
                        for tag in self._filter_relationships(relationships, 'tag')
                        if tag.get('attributes', {}).get('name') and tag['attributes'].get('group') == 'genre'
                    ],
                    'themes': [
                        tag['attributes']['name'].get('en') or next(
                            iter(tag['attributes']['name'].values()))
                        for tag in self._filter_relationships(relationships, 'tag')
                        if tag.get('attributes', {}).get('name') and tag['attributes'].get('group') == 'theme'
                    ],
                    'rating': attributes.get('rating', {}).get('bayesian', 0),
                    'language': attributes.get('originalLanguage'),
                    'content_rating': attributes.get('contentRating'),
                    'publication_type': attributes.get('publicationDemographic'),
                    'status': attributes.get('status'),
                    'cover_art': self._safe_find_cover_art(relationships, manga.get('id', '')),
                    'stats': self._get_statistics(manga.get('id', ''))
                })
                print(attributes)

            except KeyError as e:
                logging.warning(f"Skipping manga due to missing key: {str(e)}")
                continue

        return processed

    def _safe_request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """Execute request with retries and error handling"""
        retries = kwargs.pop('retries', self.max_retries)
        for attempt in range(retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=self.request_timeout,
                    **kwargs
                )
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    logging.warning(
                        f"Attempt {attempt + 1}/{retries} failed: {str(e)}")
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    logging.error(f"Request failed after {
                                  retries} attempts: {str(e)}")
                    return None
            except Exception as e:
                logging.error(f"Unexpected error: {str(e)}")
                return None
        return None

    def _get_statistics(self, manga_id: str) -> Dict:
        """Get statistics with error handling"""
        try:
            response = self._safe_request(
                'GET',
                f"{self.base_url}/statistics/manga/{manga_id}"
            )
            return response.json().get('statistics', {}) if response else {}
        except Exception as e:
            logging.warning(f"Failed to get stats for {manga_id}: {str(e)}")
            return {}

    def _safe_get_creators(self, relationships: List[Dict], role: str) -> List[str]:
        """Get creators with error handling"""
        try:
            return [
                self._get_creator_details(r['id'])
                for r in self._filter_relationships(relationships, role)
                if r.get('id')
            ]
        except Exception as e:
            logging.warning(f"Failed to get {role}s: {str(e)}")
            return []

    def _process_full_details(self, data: Dict) -> Optional[Dict]:
        """Process the full manga details response with error handling"""
        if not data or 'data' not in data:
            logging.warning("No data found in full details response.")
            return None

        manga = data['data']
        try:
            attributes = manga.get('attributes', {})
            relationships = manga.get('relationships', [])

            all_tags = attributes.get('tags', [])
            genres = []
            themes = []

            for tag in all_tags:
                tag_attributes = tag.get('attributes', {})
                tag_name_multilingual = tag_attributes.get('name', {})
                tag_group = tag_attributes.get('group')

                tag_name = tag_name_multilingual.get('en') or next(
                    iter(tag_name_multilingual.values()), 'Unknown Tag')

                if tag_group == 'genre':
                    genres.append(tag_name)
                elif tag_group == 'theme':
                    themes.append(tag_name)

            return {
                'id': manga.get('id', ''),
                'title': attributes.get('title', {}).get('en', 'No title'),
                'description': attributes.get('description', {}).get('en', ''),
                'year': attributes.get('year'),
                'authors': self._safe_get_creators(relationships, 'author'),
                'artists': self._safe_get_creators(relationships, 'artist'),
                'last_updated': attributes.get('updatedAt'),
                'genres': genres,
                'themes': themes,
                'rating': attributes.get('rating', {}).get('bayesian', 0),
                'language': attributes.get('originalLanguage'),
                'content_rating': attributes.get('contentRating'),
                'publication_type': attributes.get('publicationDemographic'),
                'status': attributes.get('status'),
                'cover_art': self._safe_find_cover_art(relationships, manga.get('id', '')),
                'stats': self._get_statistics(manga.get('id', ''))
            }
        except KeyError as e:
            logging.error(f"Error processing manga details due to missing key: {
                          str(e)} in {manga.get('id')}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error processing manga details for {
                          manga.get('id')}: {str(e)}")
            return None

    def _filter_relationships(self, relationships: List[Dict], type_: str) -> List[Dict]:
        return [r for r in relationships if r.get('type') == type_]

    def _get_creator_details(self, creator_id: str) -> str:
        """Get creator details with caching"""
        cache_key = f"creator_{creator_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            response = self._safe_request(
                'GET', f"{self.base_url}/author/{creator_id}")
            if response:
                name = response.json()['data']['attributes'].get(
                    'name', 'Unknown')
                self.cache[cache_key] = name
                return name
        except Exception as e:
            logging.warning(f"Failed to get creator {creator_id}: {str(e)}")

        return "Unknown"

    def _safe_find_cover_art(self, relationships: List[Dict], mangaId) -> Optional[str]:
        """Find cover art URL safely"""
        try:
            cover_art = next(
                (r for r in relationships if r.get('type') == 'cover_art'), None)
            r = self._safe_request(
                'GET',
                f"https://api.mangadex.org/cover/{cover_art['id']}"
            )
            data = r.json()
            imageUrl = data.get('data', {}).get('attributes', {}).get('fileName')
            return f"https://mangadex.org/covers/{mangaId}/{imageUrl}" if cover_art else None
        except Exception as e:
            logging.warning(f"Failed to find cover art: {str(e)}")
            return None

    def _generate_cache_key(self, params: Dict) -> tuple:
        return tuple(sorted((k, tuple(v) if isinstance(v, list) else v)
                            for k, v in params.items()))

    def _is_cache_valid(self, cache_key: tuple) -> bool:
        return cache_key in self.cache and \
            datetime.now() - \
            self.cache[cache_key]['timestamp'] < self.max_cache_age

    def __del__(self):
        self.session.close()
