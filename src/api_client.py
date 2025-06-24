import requests
from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional
from dateutil import parser
import json
from pathlib import Path
import base64


class MangaAPIClient:
    def __init__(self, max_cache_age: int = 99999999, cache_dir: str = ".manga_cache", cache_filename: str = "cache.json"):
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
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_filepath = self.cache_dir / \
            cache_filename
        self._load_persistent_cache()

    def _convert_datetimes_to_iso(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._convert_datetimes_to_iso(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_datetimes_to_iso(elem) for elem in obj]
        else:
            return obj

    def _convert_iso_to_datetimes(self, obj):
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
        except Exception as e:
            print(f"Failed to save entire cache to {
                  self.cache_filepath}: {str(e)}")

    def _load_persistent_cache(self):
        if not self.cache_filepath.exists():
            print(f"No cache file found at {
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

        except Exception as e:
            print(f"Failed to load cache file {self.cache_filepath}: {str(e)}. "
                  "Cache might be corrupt or malformed. Starting with empty cache.")
            self.cache = {}
            try:
                corrupt_path = self.cache_filepath.with_name(
                    self.cache_filepath.name + '.corrupt')
                self.cache_filepath.rename(corrupt_path)
            except Exception as unlink_error:
                print(
                    f"Failed to rename corrupt cache file: {unlink_error}")

    def _generate_cache_key(self, params: Dict) -> tuple:
        return tuple(sorted((k, tuple(v) if isinstance(v, list) else v)
                            for k, v in params.items()))
    def search_manga(self, filters: Dict, limit: int = 100) -> List[Dict]:
        all_results = []
        current_offset = 0
        total_manga_retrieved = 0
        retrieval_time = datetime.now()

        i = 0
        while total_manga_retrieved < limit:
            params = self._build_params(filters, min(
                limit - total_manga_retrieved, 100), current_offset)
            cache_key = self._generate_cache_key(params)

            page_results = self.cache[cache_key]['data']
            all_results.extend(page_results)
            total_manga_retrieved += len(page_results)
            current_offset += len(page_results)
            if len(page_results) < min(limit - total_manga_retrieved + len(page_results), 100):
                break
            continue

            response = self._safe_request(
                method='GET',
                url=f"{self.base_url}/manga",
                params=params,
                retries=self.max_retries
            )
            i += 1
            print(i)

            if not response:
                break

            try:
                data = response.json()
                processed_page_results = self._process_results(data)
                all_results.extend(processed_page_results)
                total_manga_retrieved += len(processed_page_results)

                self.cache[cache_key] = {
                    'timestamp': datetime.now(),
                    'retrieval_time': retrieval_time,
                    'data': processed_page_results
                }
                self._save_persistent_cache()

                if data.get('total', 0) <= total_manga_retrieved or len(processed_page_results) == 0:
                    break

                current_offset += len(processed_page_results)

            except Exception as e:
                print(f"Error processing manga search page: {str(e)}")
                break

        return all_results[:limit]

    def _build_params(self, filters: Dict, limit: int, offset: int = 0) -> Dict:
        params = {
            'limit': limit,
            'offset': offset
        }

        param_mapping = {
            'year': 'year',
            'authors': 'authors',
            'artists': 'artists',
            'last_chapter_date': 'updatedAtSince',
            'genres': 'includedTags[]',
            'language': 'originalLanguage[]',
            'publication_type': 'publicationDemographic[]',
            'status': 'status[]'
        }

        for key, api_key in param_mapping.items():
            if key in filters:
                if isinstance(filters[key], list):
                    params[api_key] = filters[key]
                else:
                    params[api_key] = [filters[key]]

        return params

    def get_manga_rating(self, manga_id: str) -> float:
        try:
            response = self._safe_request(
                'GET', f"{self.base_url}/statistics/manga/{manga_id}")
            if response:
                data = response.json()
                stats = data["statistics"][manga_id]
                rating = stats["rating"]["bayesian"]

                if rating is None:
                    return 0.0
                return rating
        except Exception as e:
            print(f"Failed to get rating for {manga_id}: {str(e)}")
        return 0

    def _process_results(self, data: Dict) -> List[Dict]:
        processed = []
        for manga in data.get('data', []):
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

                processed.append({
                    'id': manga.get('id', ''),
                    'title': attributes.get('title', {}).get('en', 'No title'),
                    'description': attributes.get('description', {}).get('en', ''),
                    'year': attributes.get('year'),
                    'authors': self._safe_get_creators(relationships, 'author'),
                    'artists': self._safe_get_creators(relationships, 'artist'),
                    'last_updated': parser.parse(attributes.get('updatedAt')) if attributes.get('updatedAt') else None,
                    'genres': genres,
                    'themes': themes,
                    'rating': self.get_manga_rating(manga.get('id', '')),
                    'language': attributes.get('originalLanguage'),
                    'content_rating': attributes.get('contentRating'),
                    'publication_type': attributes.get('publicationDemographic'),
                    'status': attributes.get('status'),
                    'cover_art': self._safe_find_cover_art(relationships, manga.get('id', '')),
                    'stats': self._get_statistics(manga.get('id', ''))
                })

            except KeyError as e:
                print(f"Skipping manga due to missing key: {str(e)}")
                continue

        return processed

    def _safe_request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
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
                    print(
                        f"Attempt {attempt + 1}/{retries} failed: {str(e)}")
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    print(f"Request failed after {retries} attempts: {str(e)}")
                    return None
            except Exception as e:
                print(f"Unexpected error: {str(e)}")
                return None
        return None

    def _get_statistics(self, manga_id: str) -> Dict:
        try:
            response = self._safe_request(
                'GET',
                f"{self.base_url}/statistics/manga/{manga_id}"
            )
            return response.json().get('statistics', {}).get(manga_id, {}) if response else {}
        except Exception as e:
            print(f"Failed to get stats for {manga_id}: {str(e)}")
            return {}

    def _safe_get_creators(self, relationships: List[Dict], role: str) -> List[str]:
        try:
            return [
                self._get_creator_details(r['id'])
                for r in self._filter_relationships(relationships, role)
                if r.get('id')
            ]
        except Exception as e:
            print(f"Failed to get {role}s: {str(e)}")
            return []

    def _filter_relationships(self, relationships: List[Dict], type_: str) -> List[Dict]:
        return [r for r in relationships if r.get('type') == type_]

    def _get_creator_details(self, creator_id: str) -> str:
        cache_key = (
            "creator_details", creator_id)

        if self._is_cache_valid(cache_key):
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
                return name
        except Exception as e:
            print(f"Failed to get creator {creator_id}: {str(e)}")

        return "Unknown"

    def _safe_find_cover_art(self, relationships: List[Dict], mangaId) -> Optional[str]:
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
            print(f"Failed to find cover art: {str(e)}")
            return None

    def __del__(self):
        self.session.close()
        self._save_persistent_cache()
