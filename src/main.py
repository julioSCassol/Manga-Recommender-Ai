import json
import requests

class MangaSearchAI:
    def __init__(self):
        self.base_url = "https://api.mangadex.org"
        
    def search_manga(self, filters):
        """
        Search manga based on provided filters
        
        Parameters:
        filters (dict): Dictionary containing search parameters like:
            - year (int): Publication year
            - authors (list): Author names
            - artists (list): Artist names
            - last_chapter_date (str): Last chapter date (YYYY-MM-DD)
            - genres (list): Genre IDs
            - rating (float): Minimum rating
            - language (str): Original language
            - publisher (str): Publisher name
            - content_rating (str): 'safe', 'suggestive', 'erotica', 'pornographic'
            - publication_type (str): 'manga', 'manhua', 'manhwa', 'novel', 'oel', 'oneshot', 'doujin'
            - status (str): 'ongoing', 'completed', 'hiatus', 'cancelled'
        """
        
        params = {}
        
        # Build the parameters based on provided filters
        if 'year' in filters:
            params['year'] = filters['year']
            
        if 'authors' in filters:
            params['authors'] = filters['authors']
            
        if 'artists' in filters:
            params['artists'] = filters['artists']
            
        if 'last_chapter_date' in filters:
            params['updatedAtSince'] = filters['last_chapter_date']
            
        if 'genres' in filters:
            params['includedTags'] = filters['genres']
            
        if 'rating' in filters:
            params['contentRating[]'] = filters.get('content_rating', ['safe', 'suggestive'])
            # Note: Mangadex doesn't have a direct rating filter, you'd need to fetch and filter
            
        if 'language' in filters:
            params['originalLanguage[]'] = filters['language']
            
        if 'publisher' in filters:
            # Publisher would need to be looked up first to get ID
            pass
            
        if 'content_rating' in filters:
            params['contentRating[]'] = filters['content_rating']
            
        if 'publication_type' in filters:
            params['publicationDemographic[]'] = filters['publication_type']
            
        if 'status' in filters:
            params['status[]'] = filters['status']
        
        # Make the API request
        response = requests.get(f"{self.base_url}/manga", params=params)
        
        if response.status_code == 200:
            return self._process_results(response.json())
        else:
            return {"error": f"API request failed with status {response.status_code}"}
    
    def _process_results(self, data):
        """Process the raw API response into a more useful format"""
        processed = []
        
        for manga in data.get('data', []):
            attributes = manga.get('attributes', {})
            
            # Get related manga IDs
            relationships = manga.get('relationships', [])
            related = [rel['id'] for rel in relationships if rel['type'] == 'manga']
            
            processed.append({
                'title': attributes.get('title', {}).get('en', 'No title'),
                'year': attributes.get('year'),
                'authors': self._get_creators(relationships, 'author'),
                'artists': self._get_creators(relationships, 'artist'),
                'last_chapter_date': attributes.get('updatedAt'),
                'genres': [tag['attributes']['name']['en'] for tag in attributes.get('tags', [])],
                'rating': attributes.get('rating', {}).get('bayesian', 0),
                'language': attributes.get('originalLanguage'),
                'content_rating': attributes.get('contentRating'),
                'publication_type': attributes.get('publicationDemographic'),
                'status': attributes.get('status'),
                'related_manga': related
            })
            
        return processed
    
    def _get_creators(self, relationships, role):
        """Helper to extract authors or artists from relationships"""
        creators = []
        for rel in relationships:
            if rel['type'] == role:
                # You'd need to fetch creator details here
                creators.append(rel['id'])
        return creators


# Example usage
if __name__ == "__main__":
    ai = MangaSearchAI()
    
    results = ai.search_manga({
        'year': 2020,
        'content_rating': ['safe', 'suggestive'],
        'language': 'en',
        'status': 'completed'
    })
    
    r = json.dumps(results, indent=4, ensure_ascii=False)
    print(r)
