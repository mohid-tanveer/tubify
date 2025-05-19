# Tubify

## Overview

### Project Description

Tubify is a powerful and engaging web application that connects directly with a user’s Spotify account to create a more social, interactive, and exploratory music experience. It allows users to create and manage Tubify-specific playlists, watch YouTube videos of their favorite tracks, receive intelligent music suggestions based on both their own and their friends’ listening histories, and share their thoughts by rating and reviewing songs. Tubify goes beyond traditional music apps by blending listening, discovery, and social interaction into one unified platform.

With a strong emphasis on user experience, Tubify is designed around a clean, modern interface that feels intuitive and responsive. Whether you’re curating your perfect playlist, discovering what your friends are listening to, or diving into new genres, Tubify ensures that every feature is easy to access and enjoyable to use. It promotes a more social approach to music consumption, helping users stay connected through shared music preferences, and makes it seamless to exchange discoveries, build collaborative playlists, and explore overlapping or contrasting musical tastes.

At the heart of Tubify is a sophisticated and adaptive recommendation engine that delivers highly personalized music suggestions. This system analyzes a combination of the user’s listening history, their friends’ activity, and general track popularity to offer recommendations that are not only relevant but contextually meaningful. More than just surfacing familiar songs, Tubify also aims to actively shape and evolve each user’s musical taste. It introduces tracks that sit at the edge of their preferences, songs that challenge and expand their comfort zone while still aligning with their listening patterns. A dynamic re-ranking mechanism takes user feedback into account, continuously refining future suggestions by either boosting similar content or increasing diversity to avoid echo chambers. This creates a discovery environment that is both thoughtful and adventurous, helping users find new favorites and grow their music identity over time.

Tubify relies on a robust backend integration with both Spotify and YouTube APIs, giving it access to each user’s music library, listening behavior, and video content. These integrations allow users to log in securely with their Spotify or Google accounts, and to seamlessly access, import, or create playlists within the Tubify ecosystem. To handle large-scale usage, the backend is optimized to gracefully manage API rate limits, ensuring that key operations remain responsive even under heavy load. This technical foundation allows Tubify to deliver real-time functionality, such as playlist syncing, video playback, and friend-based recommendations, without compromising performance or reliability.

By combining personalized discovery, social connection, and multimedia content in a single experience, Tubify re-imagines how people engage with music online. It is not just a companion to Spotify; it is a space where music becomes more social, insightful, and engaging.

### Core Features

- Create and manage Tubify playlists
- Watch YouTube videos for their favorite songs
- Get suggestions based on their own and their friends' listening history
- Review and rate songs

### System Design

![System Design](./docs/systemDiagram.png)

### Demo Videos

<details>
<summary>User Startup</summary>

![User Startup](./gifs/users-startup.gif)

</details>

<details>
<summary>View Friends Liked Songs</summary>

![View Friends Liked Songs](./gifs/users-liked-songs.gif)

</details>

<details>
<summary>View Reviews</summary>

![View Reviews](./gifs/users-reviews.gif)

</details>

<details>
<summary>Create Playlists</summary>

![Create Playlists](./gifs/playlists-creation.gif)

</details>

<details>
<summary>Watch through Playlists</summary>

![Watch through Playlists](./gifs/playlists-videos.gif)

</details>

<details>
<summary>View Recommendations</summary>

![View Recommendations](./gifs/recommendations.gif)

</details>

<details>
<summary>View Recommendation Analysis</summary>

![View Recommendation Analysis](./gifs/recommendations-analysis.gif)

</details>

<details>
<summary>Watch through Recommendations</summary>

![Watch through Recommendations](./gifs/recommendations-videos.gif)

</details>

## Dependencies

### API Setups and Frameworks

- [Spotify API](https://developer.spotify.com/documentation/web-api)
- [YouTube API](https://developers.google.com/youtube/v3)
- [Genius API](https://genius.com/api-clients)
- [Google OAuth](https://console.cloud.google.com/apis/credentials)
- [Node.js](https://nodejs.org/)
- [React via Vite](https://vitejs.dev/)
- [Python](https://www.python.org/)
- [PostgreSQL](https://www.postgresql.org/)

### Python Dependencies

listed in:

- `requirements.txt` for `backend`
- `tubify-core/src/backend/scripts/requirements.txt` for `backend/scripts`

### Environment Variables

`tubify-core/.env` needs:

(note: for frontend environment variables all keys and prefixes can be named as you want, but prefixes must end with '\_')

- `VITE_PLAYLISTS_CACHE_KEY` - Playlists cache key
- `VITE_PLAYLISTS_CACHE_TIMESTAMP_KEY` - Playlists cache timestamp key
- `VITE_PLAYLIST_DETAIL_CACHE_PREFIX` - Playlist detail cache prefix
- `VITE_PLAYLIST_DETAIL_TIMESTAMP_PREFIX` - Playlist detail timestamp prefix
- `VITE_CACHE_TTL` - Cache TTL (in milliseconds so 300000 = 5 minutes)
- `VITE_USER_CACHE_DURATION` - User cache duration (in milliseconds)
- `VITE_RECOMMENDATIONS_CACHE_TTL` - Recommendations cache TTL (in milliseconds)
- `VITE_LISTENING_HABITS_CACHE_TTL` - Listening habits cache TTL (in milliseconds)
- `VITE_USER_PROFILE_CACHE_PREFIX` - User profile cache prefix
- `VITE_USER_PROFILE_TIMESTAMP_PREFIX` - User profile timestamp prefix
- `VITE_USER_PLAYLISTS_CACHE_PREFIX` - User playlists cache prefix
- `VITE_USER_PLAYLISTS_TIMESTAMP_PREFIX` - User playlists timestamp prefix
- `VITE_PUBLIC_PLAYLIST_CACHE_PREFIX` - Public playlist cache prefix
- `VITE_PUBLIC_PLAYLIST_TIMESTAMP_PREFIX` - Public playlist timestamp prefix
- `VITE_USER_PROFILE_CACHE_KEY` - User profile cache key
- `VITE_USER_PROFILE_CACHE_TIMESTAMP_KEY` - User profile cache timestamp key
- `VITE_USER_PLAYLISTS_CACHE_KEY` - User playlists cache key
- `VITE_USER_PLAYLISTS_CACHE_TIMESTAMP_KEY` - User playlists cache timestamp key
- `VITE_LISTENING_HABITS_CACHE_KEY` - Listening habits cache key
- `VITE_LISTENING_HABITS_TIMESTAMP_KEY` - Listening habits timestamp key
- `VITE_USER_PLAYLIST_CACHE_TIMESTAMP_KEY` - User playlist cache timestamp key
- `VITE_LIKED_SONGS_CACHE_KEY` - Liked songs cache key
- `VITE_LIKED_SONGS_CACHE_TIMESTAMP_KEY` - Liked songs cache timestamp key
- `VITE_FRIEND_LIKED_SONGS_CACHE_PREFIX` - Friend liked songs cache prefix
- `VITE_FRIEND_LIKED_SONGS_TIMESTAMP_PREFIX` - Friend liked songs timestamp prefix
- `VITE_RECOMMENDATIONS_CACHE_KEY` - Recommendations cache key

`tubify-core/src/backend/.env` needs:

- `SPOTIFY_CLIENT_ID` - Spotify Client ID (from Spotify Developer Dashboard)
- `SPOTIFY_CLIENT_SECRET` - Spotify Client Secret (from Spotify Developer Dashboard)
- `SPOTIFY_REDIRECT_URI` - Spotify Redirect URI (from Spotify Developer Dashboard)
- `SECRET_KEY` - Secret key for JWT (generated using `openssl rand -base64 32`)
- `CERT_FILE` = "../ssl/localhost.pem" - Certificate file (generated using `openssl genrsa -out localhost-key.pem 2048 && openssl req -new -key localhost-key.pem -out localhost.csr && openssl x509 -req -days 365 -in localhost.csr -signkey localhost-key.pem -out localhost.pem`)
- `KEY_FILE` = "../ssl/localhost-key.pem" - Key file (generated using with above command)
- `DATABASE_URL` - Database URL (e.g. `postgresql://username:password@localhost:5432/database_name`)
- `FRONTEND_URL` = "<https://localhost:3000>"
- `MAIL_USERNAME` = "<noreply.tubify@gmail.com>"
- `MAIL_PASSWORD` - Mail password
- `MAIL_FROM` = "<noreply.tubify@gmail.com>"
- `MAIL_PORT` = 587
- `MAIL_SERVER` = "smtp.gmail.com"
- `MAIL_STARTTLS` = True
- `MAIL_SSL_TLS` = False
- `JWT_SECRET_KEY` - Secret key for JWT (generated using `openssl rand -base64 32`)
- `GOOGLE_CLIENT_ID` - Google Client ID (from Google Developer Dashboard)
- `GOOGLE_CLIENT_SECRET` - Google Client Secret (from Google Developer Dashboard)
- `YOUTUBE_API_KEY` - YouTube API Key (from YouTube Developer Dashboard)
- `GITHUB_CLIENT_ID` - GitHub Client ID (from GitHub Developer Dashboard)
- `GITHUB_CLIENT_SECRET` - GitHub Client Secret (from GitHub Developer Dashboard)
- `DEV_MODE` - Development mode (True/False)

`tubify-core/src/backend/scripts/.env` needs:

- `SPOTIFY_CLIENT_ID` - Spotify Client ID (from Spotify Developer Dashboard)
- `SPOTIFY_CLIENT_SECRET` - Spotify Client Secret (from Spotify Developer Dashboard)
- `SPOTIFY_REDIRECT_URI` - Spotify Redirect URI (from Spotify Developer Dashboard)
- `DATABASE_URL` - Database URL (e.g. `postgresql://username:password@localhost:5432/database_name`)
- `GENIUS_API_TOKEN` - Genius API Key (from Genius Developer Dashboard)

## Quick Start

After setting up API accounts (linked above) and environment variables, run the following commands to start the Tubify server.

1. Clone the repository

   ```bash
   git clone https://github.com/Rhodes-CS-comp486/tubify.git
   ```

2. Install Python dependencies

   ```bash
   cd tubify # navigate to top-level directory
   python -m venv .venv # create virtual environment
   source .venv/bin/activate # activate virtual environment
   pip install -r requirements.txt # install dependencies
   cd tubify-core/src/backend/scripts # navigate to backend/scripts directory
   deactivate # deactivate base Tubify virtual environment
   python -m venv .venv # create virtual environment for scripts
   source .venv/bin/activate # activate scripts virtual environment
   pip install -r requirements.txt # install dependencies
   ```

3. Install Node.js dependencies

   ```bash
   cd tubify-core # from the top-level directory go to tubify-core
   npm install # install dependencies
   ```

4. Run the frontend server

   ```bash
   cd tubify-core # from the top-level directory go to tubify-core
   npm start # run the frontend server
   ```

5. Run the backend server

   ```bash
   source .venv/bin/activate # activate scripts virtual environment in the top-level directory
   cd tubify-core/src/backend # from the top-level directory go to backend
   uvicorn main:app \
   --reload \
   --ssl-keyfile=../ssl/localhost-key.pem \
   --ssl-certfile=../ssl/localhost.pem # run the backend server
   ```

6. (Optional: only required if building the database from scratch) Run the scripts

   ```bash
   cd tubify-core/src/backend/scripts # from the top-level directory go to backend/scripts
   source .venv/bin/activate # activate scripts virtual environment
   python update_spotify_playlists.py # run the update spotify playlists script
   python download_songs.py # run the download songs script
   python extract_audio_features.py # run the extract audio features script
   python extract_lyrics_embeddings.py # run the extract lyrics embeddings script
   cd .. # navigate back to the backend directory
   deactivate # deactivate scripts virtual environment
   source ../../../.venv/bin/activate # activate base Tubify virtual environment
   python batch_add_videos.py # run the batch add videos script (in the backend directory due to function imports)
   ```
