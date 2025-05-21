API_CONFIG = {
    'base_url': 'https://api.mangadex.org',
    'default_params': {
        'includes[]': ['author', 'artist', 'cover_art'],
        'contentRating[]': ['safe', 'suggestive']
    }
}

# parametros
AI_CONFIG = {
    'max_initial_results': 200,
    'similarity_threshold': 0.65
}