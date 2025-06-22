import requests
from datetime import datetime, timedelta
import time
import logging
from typing import Dict, List, Optional
from dateutil import parser
import json
from pathlib import Path
import base64


class MangaAPIClient:
    def __init__(self, max_cache_age: int = 60, cache_dir: str = ".manga_cache", cache_filename: str = "cache.json"):
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
        self.last_cache_clean = datetime.now()

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_filepath = self.cache_dir / \
            cache_filename
        self._load_persistent_cache()

    def _convert_datetimes_to_iso(self, obj):
        """
        Recursively converts datetime objects in dicts and lists to ISO 8601 strings.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._convert_datetimes_to_iso(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_datetimes_to_iso(elem) for elem in obj]
        else:
            return obj

    def _convert_iso_to_datetimes(self, obj):
        """
        Recursively converts ISO 8601 strings in dicts and lists to datetime objects.
        """
        if isinstance(obj, str):
            try:
                parsed_dt = parser.parse(obj)
                current_year = datetime.now().year
                if parsed_dt.year > 1900 and parsed_dt.year < current_year + 5:
                    return parsed_dt
                else:
                    return obj
            except (ValueError, OverflowError):
                return obj
        elif isinstance(obj, dict):
            return {k: self._convert_iso_to_datetimes(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_iso_to_datetimes(elem) for elem in obj]
        else:
            return obj

    def _make_hashable(self, obj):
        """
        Recursively converts lists to tuples to make an object hashable.
        """
        if isinstance(obj, list):
            return tuple(self._make_hashable(elem) for elem in obj)
        elif isinstance(obj, dict):
            return tuple(sorted((k, self._make_hashable(v)) for k, v in obj.items()))
        else:
            return obj

    def _convert_tuples_to_lists(self, obj):
        if isinstance(obj, tuple):
            return [self._convert_tuples_to_lists(elem) for elem in obj]
        elif isinstance(obj, dict):
            return {k: self._convert_tuples_to_lists(v) for k, v in obj.items()}
        else:
            return obj

    def _save_persistent_cache(self):
        """Save the entire in-memory cache to the single cache.json file."""
        try:
            serializable_cache = {}
            for key, entry in self.cache.items():
                json_list_key = self._convert_tuples_to_lists(key)

                string_key_for_json = json.dumps(json_list_key, sort_keys=True)

                serializable_data_payload = self._convert_datetimes_to_iso(
                    entry['data'])

                encoded_data = base64.b64encode(
                    json.dumps(serializable_data_payload).encode('utf-8')
                ).decode('utf-8')

                serializable_cache[string_key_for_json] = {
                    'timestamp': entry['timestamp'].isoformat(),
                    'retrieval_time': entry['retrieval_time'].isoformat(),
                    'data': encoded_data
                }

            with open(self.cache_filepath, 'w', encoding='utf-8') as f:
                json.dump(serializable_cache, f, indent=2)
            logging.info(f"Cache saved to {self.cache_filepath}")
        except Exception as e:
            logging.error(f"Failed to save entire cache to {
                          self.cache_filepath}: {str(e)}")

    def _load_persistent_cache(self):
        """Load the entire cache from the single cache.json file."""
        if not self.cache_filepath.exists():
            logging.info(f"No cache file found at {
                         self.cache_filepath}. Starting with empty cache.")
            return

        try:
            with open(self.cache_filepath, 'r', encoding='utf-8') as f:
                loaded_json_cache = json.load(f)

            self.cache = {}
            for string_key_from_json, entry_raw in loaded_json_cache.items():
                json_list_key_raw = json.loads(string_key_from_json)

                cache_key = self._make_hashable(json_list_key_raw)

                encoded_data = entry_raw['data']
                decoded_json_str = base64.b64decode(
                    encoded_data.encode('utf-8')).decode('utf-8')
                loaded_data_payload = self._convert_iso_to_datetimes(
                    json.loads(decoded_json_str))

                timestamp = parser.parse(entry_raw.get(
                    'timestamp', datetime.fromtimestamp(0).isoformat()))
                retrieval_time = parser.parse(entry_raw.get(
                    'retrieval_time', datetime.fromtimestamp(0).isoformat()))

                self.cache[cache_key] = {
                    'data': loaded_data_payload,
                    'timestamp': timestamp,
                    'retrieval_time': retrieval_time
                }
            logging.info(f"Cache loaded from {self.cache_filepath} with {
                         len(self.cache)} entries.")

        except Exception as e:
            logging.warning(f"Failed to load cache file {self.cache_filepath}: {str(e)}. "
                            "Cache might be corrupt or malformed. Starting with empty cache.")
            self.cache = {}
            try:
                corrupt_path = self.cache_filepath.with_name(
                    self.cache_filepath.name + '.corrupt')
                self.cache_filepath.rename(corrupt_path)
                logging.info(f"Moved corrupt cache file to {corrupt_path}")
            except Exception as unlink_error:
                logging.warning(
                    f"Failed to rename corrupt cache file: {unlink_error}")

    def _generate_cache_key(self, params: Dict) -> tuple:
        """Generate a unique key for API request parameters"""
        return tuple(sorted((k, tuple(v) if isinstance(v, list) else v)
                            for k, v in params.items()))

    def _is_cache_valid(self, cache_key: tuple) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self.cache:
            return False
        if 'timestamp' not in self.cache[cache_key]:
            logging.warning(f"Cache entry for {
                            cache_key} is missing 'timestamp'. Considering invalid.")
            return False
        return datetime.now() - self.cache[cache_key]['timestamp'] < self.max_cache_age

    def _clean_old_cache(self):
        """Clean up old cache entries in memory and then save the cleaned cache."""
        if datetime.now() - self.last_cache_clean < timedelta(minutes=5):
            return

        logging.info("Cleaning old cache entries...")
        self.last_cache_clean = datetime.now()

        keys_to_delete = []
        for key, entry in list(self.cache.items()):
            if 'timestamp' not in entry or datetime.now() - entry['timestamp'] > self.max_cache_age:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self.cache[key]

        if keys_to_delete:
            logging.info(f"Removed {len(keys_to_delete)
                                    } expired cache entries.")
            self._save_persistent_cache()
        else:
            logging.info("No expired cache entries found to clean.")

    def search_manga(self, filters: Dict, limit: int = 100) -> List[Dict]:
        """
        Search manga with persistent caching
        """
        params = self._build_params(filters, limit)
        cache_key = self._generate_cache_key(params)

        self._clean_old_cache()

        if self._is_cache_valid(cache_key):
            logging.info("Returning cached results for manga search.")
            return self.cache[cache_key]['data']

        all_results = []
        retrieval_time = datetime.now()
        total_processed = 0

        try:
            while total_processed < limit:
                current_params = params.copy()
                current_params['offset'] = len(all_results)

                response = self._safe_request(
                    method='GET',
                    url=f"{self.base_url}/manga",
                    params=current_params,
                    retries=self.max_retries
                )

                if not response:
                    break

                data = response.json()
                processed = self._process_results(data)
                all_results.extend(processed)
                total_processed += len(processed)

                if data.get('total', 0) <= total_processed or len(processed) == 0:
                    break

        except Exception as e:
            logging.error(f"Manga search failed: {str(e)}")
            return []

        self.cache[cache_key] = {
            'timestamp': datetime.now(),
            'retrieval_time': retrieval_time,
            'data': all_results[:limit]
        }
        self._save_persistent_cache()

        logging.info(f"Fetched and cached {
                     len(all_results[:limit])} manga results.")
        return all_results[:limit]

    def get_manga_details(self, manga_id: str) -> Optional[Dict]:
        """Get manga details with persistent caching"""
        cache_key = ("manga_details",
                     manga_id)

        self._clean_old_cache()

        if self._is_cache_valid(cache_key):
            logging.info(f"Returning cached details for manga ID: {manga_id}.")
            return self.cache[cache_key]['data']

        retrieval_time = datetime.now()

        try:
            response = self._safe_request(
                method='GET',
                url=f"{self.base_url}/manga/{manga_id}",
                params={'includes[]': ['author', 'artist', 'cover_art', 'tag']},
                retries=self.max_retries
            )

            if not response:
                return None

            details = self._process_full_details(response.json())

            if details:
                self.cache[cache_key] = {
                    'timestamp': datetime.now(),
                    'retrieval_time': retrieval_time,
                    'data': details
                }
                self._save_persistent_cache()
                logging.info(
                    f"Fetched and cached details for manga ID: {manga_id}.")
            return details

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
            return response.json().get('statistics', {}).get(manga_id, {}) if response else {}
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
                'last_updated': parser.parse(attributes.get('updatedAt')) if attributes.get('updatedAt') else None,
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
        cache_key = (
            "creator_details", creator_id)

        self._clean_old_cache()

        if self._is_cache_valid(cache_key):
            logging.info(
                f"Returning cached creator details for ID: {creator_id}.")
            return self.cache[cache_key]['data']

        retrieval_time = datetime.now()

        try:
            response = self._safe_request(
                'GET', f"{self.base_url}/author/{creator_id}")
            if response:
                name = response.json()['data']['attributes'].get(
                    'name', 'Unknown')
                self.cache[cache_key] = {
                    'timestamp': datetime.now(),
                    'retrieval_time': retrieval_time,
                    'data': name
                }
                self._save_persistent_cache()
                logging.info(
                    f"Fetched and cached creator details for ID: {creator_id}.")
                return name
        except Exception as e:
            logging.warning(f"Failed to get creator {creator_id}: {str(e)}")

        return "Unknown"

    def _safe_find_cover_art(self, relationships: List[Dict], mangaId) -> Optional[str]:
        """Find cover art URL safely"""
        try:
            cover_art_relationship = next(
                (r for r in relationships if r.get('type') == 'cover_art'), None)

            if cover_art_relationship:
                response = self._safe_request(
                    'GET',
                    f"https://api.mangadex.org/cover/{
                        cover_art_relationship['id']}"
                )
                if response:
                    data = response.json()
                    image_filename = data.get('data', {}).get(
                        'attributes', {}).get('fileName')
                    if image_filename:
                        return f"https://mangadex.org/covers/{mangaId}/{image_filename}"
            return None
        except Exception as e:
            logging.warning(f"Failed to find cover art: {str(e)}")
            return None

    def __del__(self):
        """Ensure cache is saved on object destruction."""
        self.session.close()
        self._save_persistent_cache()
