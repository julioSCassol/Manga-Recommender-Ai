# from .api_client import MangaAPIClient
# from .ai_interface import AISession
# import json


# def main():
#     api = MangaAPIClient()
#     ai_session = AISession(api)

#     try:
#         print("Starting Manga Recommendation System...")
#         ai_session.start_session()
#         print("System initialized successfully!\n")

#         # Collect user preferences interactively
#         print("=== Please tell us about your manga preferences ===")
#         keywords = input("Enter keywords you like (comma separated): ").split(',')
#         genres = input("Enter your favorite genres (comma separated): ").split(',')
#         themes = input("Enter themes you enjoy (comma separated): ").split(',')
#         demographics = input("Preferred demographics (shoujo, shonen, seinen, josei): ").split(',')
#         status = input("Preferred status (ongoing, completed, hiatus): ").split(',')
#         content_rating = input("Content rating preference (safe, suggestive, erotica, pornographic): ").split(',')

#         print("\n=== Initial Recommendations Based on Your Preferences ===")
#         initial_user_prefs = {
#             'keywords': [k.strip() for k in keywords if k.strip()],
#             'genres': [g.strip() for g in genres if g.strip()],
#             'themes': [t.strip() for t in themes if t.strip()],
#             'preferred_demographics': [d.strip() for d in demographics if d.strip()],
#             'preferred_status': [s.strip() for s in status if s.strip()],
#             'preferred_content_rating': [c.strip() for c in content_rating if c.strip()]
#         }

#         initial_indices = ai_session.recommender.find_similar(
#             initial_user_prefs, n=10)

#         if not initial_indices:
#             print("No initial recommendations found. Please try different preferences.")
#             return

#         # Display initial recommendations
#         for i, idx in enumerate(initial_indices):
#             manga = ai_session.recommender.data[idx]
#             print(f"{i+1}. {manga['title']} ({manga.get('year', 'N/A')})")
#             print(f"   Genres: {', '.join(manga.get('genres', []))}")
#             print(f"   Rating: {manga.get('rating', 0):.1f}\n")

#         # Collect user feedback
#         liked_indices = []
#         while True:
#             choices = input("\nWhich manga did you like? (Enter numbers separated by commas, or 'done'): ")
#             if choices.lower() == 'done':
#                 break
#             try:
#                 selected = [int(c.strip()) - 1 for c in choices.split(',')]
#                 valid_selections = [s for s in selected if 0 <= s < len(initial_indices)]
#                 liked_indices.extend(initial_indices[i] for i in valid_selections)
#                 print(f"Added {len(valid_selections)} selections to your preferences")
#             except ValueError:
#                 print("Please enter valid numbers separated by commas")

#         if liked_indices:
#             ai_session.update_preferences(liked_indices)
#             print("\nUpdating recommendations based on your preferences...")
#         else:
#             print("\nNo selections made. Using initial preferences for recommendations.")

#         # Show personalized recommendations
#         print("\n=== Personalized Recommendations ===")
#         personalized_indices = ai_session.get_recommendations()
#         for i, idx in enumerate(personalized_indices[:10]):
#             manga = ai_session.recommender.data[idx]
#             reason = ai_session.get_similarity_reason(idx)
#             print(f"{i+1}. {manga['title']}")
#             print(f"   Why: {reason}\n")

#     except KeyboardInterrupt:
#         print("\nOperation cancelled by user.")
#     except Exception as e:
#         print(f"\nError: {str(e)}")
#     finally:
#         print("\nSession ended. Happy reading!")


# if __name__ == '__main__':
#     import os
#     import sys
#     sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
#     main()