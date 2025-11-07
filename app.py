import os
import base64
import hashlib
import requests
import webbrowser
import threading
import signal
import sys
import json
import asyncio
import aiohttp
from flask import Flask, request
import argparse
import keyring
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Spotify API credentials
CLIENT_ID = os.getenv("CLIENT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")
# list of scopes your application needs

SCOPES = [
    "user-read-private",
    "user-read-email",
    "playlist-read-private",
    "playlist-modify-public",
    "playlist-modify-private",
    "user-library-read",
    "user-library-modify",
    "user-read-recently-played",
    "user-top-read"
    ]
# convert scopes list to a space-separated string
SCOPES = " ".join(SCOPES)
# Generate a code verifier and challenge for PKCE
def generate_code_verifier_and_challenge():
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode("utf-8")
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("utf-8")).digest()
    ).rstrip(b"=").decode("utf-8")
    return code_verifier, code_challenge

# Initialize Flask app
app = Flask(__name__)

auth_code_global = None
stop_event = threading.Event()

def signal_handler(sig, frame):
    stop_event.set()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

@app.route("/callback")
def callback():
    global auth_code_global
    auth_code_global = request.args.get("code")
    stop_event.set()
    return "Authorization code received! You can close this tab."

def get_authorization_code():
    # Step 1: Generate code verifier and challenge
    code_verifier, code_challenge = generate_code_verifier_and_challenge()

    # Step 2: Generate authorization URL
    auth_url = (
        "https://accounts.spotify.com/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&scope={SCOPES}"
    )

    # Step 3: Prompt user to open the URL
    print("Open the following URL in your browser to authorize the application:")
    print(auth_url)
    webbrowser.open(auth_url)

    # Step 4: Start the Flask server in a separate thread to listen for the callback
    print("Waiting for authorization code...")
    flask_thread = threading.Thread(target=app.run, kwargs={"port": 5000, "debug": False, "use_reloader": False})
    flask_thread.start()

    # Wait for the stop event to be set
    stop_event.wait()

    # Step 5: Return the authorization code
    return auth_code_global, code_verifier

def get_access_token(auth_code, code_verifier):
    # Step 5: Exchange authorization code for an access token
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(token_url, data=payload, headers=headers)

    if response.status_code != 200:
        print(f"Failed to get token: {response.json()}")
        exit(1)

    token_data = response.json()
    return token_data["access_token"]

# Define a service name for the Keychain
token_service_name = "SpotifyAccessToken"

def save_access_token_to_keychain(access_token):
    """
    Save the access token securely to the macOS Keychain.

    Args:
        access_token (str): Spotify API access token.
    """
    keyring.set_password(token_service_name, "access_token", access_token)

def load_access_token_from_keychain():
    """
    Load the access token securely from the macOS Keychain.

    Returns:
        str: The access token if it exists, otherwise None.
    """
    return keyring.get_password(token_service_name, "access_token")

def is_token_expired(access_token):
    """
    Check if the access token is expired by making a simple API call.

    Args:
        access_token (str): Spotify API access token.

    Returns:
        bool: True if the token is expired, False otherwise.
    """
    profile_url = "https://api.spotify.com/v1/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(profile_url, headers=headers)

    # If the token is expired, Spotify API returns a 401 status code
    return response.status_code == 401

def get_user_profile(access_token):
    # Step 6: Use the access token to access Spotify's Web API
    profile_url = "https://api.spotify.com/v1/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(profile_url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to fetch profile: {response.json()}")
        exit(1)

    return response.json()

def get_user_playlists(access_token):
    playlists_url = "https://api.spotify.com/v1/me/playlists"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(playlists_url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to fetch playlists: {response.json()}")
        exit(1)

    return response.json()

def get_user_liked_songs(access_token, limit=None):
    liked_songs_url = "https://api.spotify.com/v1/me/tracks"
    headers = {"Authorization": f"Bearer {access_token}"}
    all_tracks = []
    params = {"limit": 50, "offset": 0}  # Spotify API allows a maximum of 50 items per request
    total_fetched = 0

    while True:
        response = requests.get(liked_songs_url, headers=headers, params=params)

        if response.status_code != 200:
            print(f"Failed to fetch liked songs: {response.json()}")
            exit(1)

        data = response.json()
        all_tracks.extend(data["items"])
        total_fetched += len(data["items"])

        # Check if we've reached the user-specified limit
        if limit is not None and total_fetched >= limit:
            return {"items": all_tracks[:limit]}

        # Check if there are more tracks to fetch
        if data["next"] is None:
            break

        # Update the offset for the next request
        params["offset"] += params["limit"]

    return {"items": all_tracks}

# Add a cache to store artist details
artist_cache = {}

def get_cached_artist(artist_id):
    return artist_cache.get(artist_id)

def cache_artist(artist_id, artist_data):
    artist_cache[artist_id] = artist_data

async def fetch_artist(session, access_token, artist_id, total_requests, current_request):
    cached_artist = get_cached_artist(artist_id)
    if cached_artist:
        print(f"[{current_request}/{total_requests}] Artist {artist_id} fetched from cache.")
        return cached_artist

    artist_url = f"https://api.spotify.com/v1/artists/{artist_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        async with session.get(artist_url, headers=headers) as response:
            if response.status == 429:  # Too Many Requests
                retry_after = int(response.headers.get("Retry-After", 1))
                print(f"[{current_request}/{total_requests}] Rate limited. Retrying after {retry_after} seconds...")
                await asyncio.sleep(retry_after)
                continue
            elif response.status != 200:
                print(f"[{current_request}/{total_requests}] Failed to fetch artist {artist_id}: {await response.text()}")
                return None
            artist_data = await response.json()
            cache_artist(artist_id, artist_data)
            print(f"[{current_request}/{total_requests}] Successfully fetched artist {artist_id}.")
            return artist_data

async def fetch_all_artists_with_progress(access_token, artist_ids):
    total_requests = len(artist_ids)
    completed_requests = 0

    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, artist_id in enumerate(artist_ids):
            tasks.append(fetch_artist(session, access_token, artist_id, total_requests, i + 1))

        for future in asyncio.as_completed(tasks):
            result = await future
            completed_requests += 1
            print(f"Progress: {completed_requests}/{total_requests} artists fetched.")

    return await asyncio.gather(*tasks)

def fetch_artist_details(access_token, artist_ids):
    """
    Fetch details for a list of artist IDs, including genres.

    Args:
        access_token (str): Spotify API access token.
        artist_ids (list): List of artist IDs to fetch details for.

    Returns:
        list: List of artist details including genres.
    """
    def get_artist_genres(artist_json):
        return artist_json.get("genres", [])

    # Fetch artist details asynchronously with progress updates
    artist_details = asyncio.run(fetch_all_artists_with_progress(access_token, artist_ids))

    # Extract genres for each artist
    artist_genres = {artist["id"]: get_artist_genres(artist) for artist in artist_details if artist}

    return artist_genres

def group_songs_by_genre(access_token, liked_songs):
    """
    Group songs from the liked songs list by genre.

    Args:
        access_token (str): Spotify API access token.
        liked_songs (list): List of liked songs with track details.

    Returns:
        dict: A dictionary where keys are genres and values are lists of tracks.
    """
    genre_to_tracks = {}

    # Extract artist IDs from liked songs
    artist_ids = set()
    for item in liked_songs:
        track = item.get("track", {})
        for artist in track.get("artists", []):
            artist_ids.add(artist.get("id"))

    # Fetch artist details to get genres
    artist_genres = fetch_artist_details(access_token, list(artist_ids))

    # Group tracks by genre
    for item in liked_songs:
        track = item.get("track", {})
        track_id = track.get("id")
        track_name = track.get("name")
        track_artists = [artist.get("name") for artist in track.get("artists", [])]

        for artist in track.get("artists", []):
            artist_id = artist.get("id")
            genres = artist_genres.get(artist_id, [])

            for genre in genres:
                if genre not in genre_to_tracks:
                    genre_to_tracks[genre] = []
                genre_to_tracks[genre].append({
                    "id": track_id,
                    "name": track_name,
                    "artists": track_artists
                })

    return genre_to_tracks

def main():
    parser = argparse.ArgumentParser(description="Spotify API Tool")
    parser.add_argument("--action", required=True, choices=["liked-songs", "playlists", "profile", "group-by-genre"], help="Action to perform: liked-songs, playlists, profile, group-by-genre")
    parser.add_argument("--limit", type=int, help="Limit the number of items to fetch (if applicable)")
    parser.add_argument("--output", type=str, default="genres.json", help="Output file for saving grouped genres (applicable for group-by-genre)")
    args = parser.parse_args()

    access_token = load_access_token_from_keychain()

    if not access_token or is_token_expired(access_token):
        if access_token:
            print("Access token expired. Re-authenticating...")
        auth_code, code_verifier = get_authorization_code()
        access_token = get_access_token(auth_code, code_verifier)
        print("Access token obtained successfully!")
        save_access_token_to_keychain(access_token)
    else:
        print("Access token loaded from Keychain!")

    if args.action == "liked-songs":
        limit = args.limit if args.limit else None
        liked_songs = get_user_liked_songs(access_token, limit=limit)
        print(json.dumps(liked_songs, indent=2))

    elif args.action == "playlists":
        playlists = get_user_playlists(access_token)
        print(json.dumps(playlists, indent=2))

    elif args.action == "profile":
        profile = get_user_profile(access_token)
        print(json.dumps(profile, indent=2))

    elif args.action == "group-by-genre":
        limit = args.limit if args.limit else None
        liked_songs = get_user_liked_songs(access_token, limit=limit)
        grouped_genres = group_songs_by_genre(access_token, liked_songs["items"])

        # Save grouped genres to file
        with open(args.output, "w") as file:
            json.dump(grouped_genres, file, indent=2)
        print(f"Grouped genres saved to {args.output}")

if __name__ == "__main__":
    main()
