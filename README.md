# unnamed-spotify-project

## Overview
This project is a Python-based tool for interacting with Spotify's Web API. It allows users to authenticate with Spotify, fetch their playlists, liked songs, and profile information, and group their liked songs by genre. The app uses Flask for handling OAuth callbacks and supports asynchronous operations for efficient data fetching.

## Features
- **User Authentication**: Implements Spotify's OAuth 2.0 PKCE flow to securely authenticate users.
- **Fetch User Data**:
  - Retrieve user profile information.
  - Fetch playlists and liked songs.
- **Group Songs by Genre**: Analyze liked songs and group them based on artist genres.
- **Command-Line Interface**: Perform actions via CLI arguments.

## Prerequisites
- Python 3.14 or higher
- Spotify Developer Account
- Flask
- Required Python packages (see `requirements.txt` or install dependencies manually).

## Installation
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd unnamed-spotify-project
   ```
2. Set up a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
1. **Set Up Spotify API Credentials**:
   - Create a Spotify Developer App at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
   - Note your `CLIENT_ID` and set the redirect URI to `http://127.0.0.1:5000/callback`.
   - Update the `CLIENT_ID` and `REDIRECT_URI` in `app.py`.

2. **Run the Application**:
   ```bash
   python app.py --action <action> [--limit <number>] [--output <file>]
   ```
   Replace `<action>` with one of the following:
   - `liked-songs`: Fetch liked songs.
   - `playlists`: Fetch user playlists.
   - `profile`: Fetch user profile information.
   - `group-by-genre`: Group liked songs by genre.

3. **Example**:
   ```bash
   python app.py --action group-by-genre --limit 100 --output genres.json
   ```

### Secure Token Storage

The application  uses the macOS Keychain to securely store the Spotify access token. The `keyring` library is used to interact with the Keychain. This ensures that sensitive information is stored securely and is not exposed in plain text files.

### Setup
Ensure the `keyring` library is installed in your Python environment. You can install it using pip:

```bash
pip install keyring
```

### Usage
When you run the application, it will automatically check the Keychain for an existing access token. If the token is expired or not found, the application will prompt you to authenticate with Spotify and securely store the new token in the Keychain.

## File Structure
- `app.py`: Main application script.
- `README.md`: Project documentation.

## License
This project is licensed under the MIT License. See the LICENSE file for details.

## Acknowledgments
- [Spotify Web API](https://developer.spotify.com/documentation/web-api/) for providing the API.
- Flask for the web framework.