from typing import List, Dict, Tuple, Optional, Any
import numpy as np
from dotenv import load_dotenv
import logging
from sklearn.metrics.pairwise import cosine_similarity
from fastapi import APIRouter, Depends, HTTPException, Request
from database import database
import os
import time

# set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("recommendations")

# load environment variables
load_dotenv()


async def get_user_liked_songs(user_id: int) -> List[str]:
    """get list of song ids liked by a user"""
    try:
        rows = await database.fetch_all(
            "SELECT song_id FROM user_liked_songs WHERE user_id = :user_id",
            {"user_id": user_id},
        )
        return [row["song_id"] for row in rows]
    except Exception as e:
        logger.error(f"error fetching liked songs for user {user_id}: {e}")
        return []


async def get_user_friends(user_id: int) -> List[int]:
    """get list of friend ids for a user"""
    try:
        rows = await database.fetch_all(
            """
            SELECT 
                CASE WHEN user_id = :user_id THEN friend_id ELSE user_id END AS friend_id
            FROM friendships
            WHERE user_id = :user_id OR friend_id = :user_id
            """,
            {"user_id": user_id},
        )
        return [row["friend_id"] for row in rows]
    except Exception as e:
        logger.error(f"error fetching friends for user {user_id}: {e}")
        return []


async def get_songs_liked_by_friends(
    user_id: int, exclude_songs: List[str]
) -> Dict[str, int]:
    """
    get songs liked by user's friends that the user hasn't liked
    returns a dict mapping song_id to count of friends who liked it
    """
    friend_ids = await get_user_friends(user_id)
    if not friend_ids:
        return {}

    try:
        query = """
            SELECT song_id, COUNT(DISTINCT user_id) as friend_count
            FROM user_liked_songs
            WHERE user_id = ANY(:friend_ids)
        """

        params = {"friend_ids": friend_ids}

        if exclude_songs:
            query += " AND song_id != ALL(:exclude_songs)"
            params["exclude_songs"] = exclude_songs

        query += " GROUP BY song_id ORDER BY friend_count DESC"

        rows = await database.fetch_all(query, params)
        return {row["song_id"]: row["friend_count"] for row in rows}
    except Exception as e:
        logger.error(f"error fetching friend-liked songs for user {user_id}: {e}")
        return {}


async def get_song_audio_features(song_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """get audio feature vectors and individual features for a list of songs"""
    if not song_ids:
        return {}

    try:
        rows = await database.fetch_all(
            """
            SELECT song_id, feature_vector, tempo, acousticness, danceability, 
                   energy, loudness, liveness, valence, speechiness, 
                   instrumentalness, mode, key
            FROM song_audio_features
            WHERE song_id = ANY(:song_ids)
            """,
            {"song_ids": song_ids},
        )

        results = {}
        for row in rows:
            song_id = row["song_id"]
            results[song_id] = {
                "feature_vector": row["feature_vector"],
                "tempo": row["tempo"],
                "acousticness": row["acousticness"],
                "danceability": row["danceability"],
                "energy": row["energy"],
                "loudness": row["loudness"],
                "liveness": row["liveness"],
                "valence": row["valence"],
                "speechiness": row["speechiness"],
                "instrumentalness": row["instrumentalness"],
                "mode": row["mode"],
                "key": row["key"],
            }
        return results
    except Exception as e:
        logger.error(f"error fetching audio features: {e}")
        return {}


async def get_song_lyrics_embeddings(song_ids: List[str]) -> Dict[str, List[float]]:
    """get lyrics embeddings for a list of songs"""
    if not song_ids:
        return {}

    try:
        rows = await database.fetch_all(
            """
            SELECT song_id, lyrics_embedding
            FROM song_lyrics
            WHERE song_id = ANY(:song_ids) AND array_length(lyrics_embedding, 1) > 0
            """,
            {"song_ids": song_ids},
        )

        results = {}
        for row in rows:
            song_id = row["song_id"]
            results[song_id] = row["lyrics_embedding"]

        return results
    except Exception as e:
        logger.error(f"error fetching lyrics embeddings: {e}")
        return {}


async def get_song_details(song_ids: List[str]) -> List[Dict[str, Any]]:
    """get details for a list of songs"""
    if not song_ids:
        return []

    try:
        rows = await database.fetch_all(
            """
            SELECT s.id, s.name, s.spotify_uri, s.spotify_url, s.popularity, s.duration_ms,
                   a.name as album_name, a.image_url as album_image_url,
                   string_agg(ar.name, ', ') as artist_names
            FROM songs s
            JOIN albums a ON s.album_id = a.id
            JOIN song_artists sa ON s.id = sa.song_id
            JOIN artists ar ON sa.artist_id = ar.id
            WHERE s.id = ANY(:song_ids)
            GROUP BY s.id, a.name, a.image_url
            ORDER BY s.popularity DESC
            """,
            {"song_ids": song_ids},
        )

        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"error fetching song details: {e}")
        return []


async def get_user_audio_profile(user_id: int) -> Dict[str, float]:
    """calculate average audio feature values from a user's liked songs"""
    liked_songs = await get_user_liked_songs(user_id)
    if not liked_songs:
        return {}

    features = await get_song_audio_features(liked_songs)
    if not features:
        return {}

    # calculate average values for each audio feature
    profile = {
        "tempo": 0.0,
        "acousticness": 0.0,
        "danceability": 0.0,
        "energy": 0.0,
        "loudness": 0.0,
        "liveness": 0.0,
        "valence": 0.0,
        "speechiness": 0.0,
        "instrumentalness": 0.0,
    }

    # for mode and key, we'll track counts to find the most common values
    mode_counts = {0: 0, 1: 0}  # 0=minor, 1=major
    key_counts = {i: 0 for i in range(12)}  # 0-11 for musical keys

    song_count = 0
    for song_id, song_features in features.items():
        for feature in profile:
            if feature in song_features:
                profile[feature] += song_features[feature]

        # count occurrences of mode and key
        if "mode" in song_features:
            mode_counts[song_features["mode"]] += 1

        if "key" in song_features:
            key_counts[song_features["key"]] += 1

        song_count += 1

    # calculate averages
    if song_count > 0:
        for feature in profile:
            profile[feature] /= song_count

    # find most common mode and key
    if mode_counts:
        profile["mode"] = max(mode_counts, key=mode_counts.get)

    if key_counts:
        profile["key"] = max(key_counts, key=key_counts.get)

    return profile


async def get_user_average_feature_vector(user_id: int) -> Optional[np.ndarray]:
    """calculate average feature vector from a user's liked songs"""
    liked_songs = await get_user_liked_songs(user_id)
    if not liked_songs:
        return None

    features = await get_song_audio_features(liked_songs)
    if not features:
        return None

    # calculate average feature vector
    vectors = [
        np.array(feature["feature_vector"])
        for feature in features.values()
        if "feature_vector" in feature
    ]
    if not vectors:
        return None

    return np.mean(vectors, axis=0)


async def get_user_average_lyrics_embedding(user_id: int) -> Optional[np.ndarray]:
    """calculate average lyrics embedding from a user's liked songs"""
    liked_songs = await get_user_liked_songs(user_id)
    if not liked_songs:
        return None

    lyrics_embeddings = await get_song_lyrics_embeddings(liked_songs)
    if not lyrics_embeddings:
        return None

    # calculate average embedding vector
    vectors = [np.array(embedding) for embedding in lyrics_embeddings.values()]
    if not vectors:
        return None

    return np.mean(vectors, axis=0)


async def find_similar_songs(
    user_average_vector: np.ndarray,
    user_profile: Dict[str, float],
    exclude_songs: List[str],
    user_lyrics_embedding: Optional[np.ndarray] = None,
    limit: int = 50,
) -> List[Tuple[str, float]]:
    """find songs with similar audio features and lyrics to the user's average"""
    try:
        query = """
            SELECT song_id, feature_vector, tempo, acousticness, danceability, 
                   energy, loudness, liveness, valence, speechiness, 
                   instrumentalness, mode, key
            FROM song_audio_features
        """

        params = {}
        if exclude_songs:
            query += " WHERE song_id != ALL(:exclude_songs)"
            params["exclude_songs"] = exclude_songs

        rows = await database.fetch_all(query, params)

        # get lyrics embeddings for all potential songs
        song_ids = [row["song_id"] for row in rows]
        lyrics_embeddings = {}

        if user_lyrics_embedding is not None:
            lyrics_embeddings = await get_song_lyrics_embeddings(song_ids)

        # calculate similarity scores with weights for different feature types
        similarities = []
        for row in rows:
            song_id = row["song_id"]
            feature_vector = np.array(row["feature_vector"])

            # calculate weighted similarity score
            # 1. base similarity from feature vectors (MFCC, chroma, spectral features)
            vector_similarity = cosine_similarity(
                user_average_vector.reshape(1, -1), feature_vector.reshape(1, -1)
            )[0][0]

            # 2. calculate similarity for high-level audio features
            feature_similarity = 0.0

            # compare each audio feature with different weights
            features = {
                "tempo": {"weight": 0.05, "value": row["tempo"]},
                "acousticness": {"weight": 0.1, "value": row["acousticness"]},
                "danceability": {"weight": 0.15, "value": row["danceability"]},
                "energy": {"weight": 0.15, "value": row["energy"]},
                "loudness": {"weight": 0.05, "value": row["loudness"]},
                "liveness": {"weight": 0.05, "value": row["liveness"]},
                "valence": {"weight": 0.15, "value": row["valence"]},
                "speechiness": {"weight": 0.05, "value": row["speechiness"]},
                "instrumentalness": {"weight": 0.05, "value": row["instrumentalness"]},
            }

            # add special handling for mode and key (categorical features)
            # reward exact matches in mode (major/minor) and key
            mode_match = 1.0 if user_profile.get("mode") == row["mode"] else 0.0
            key_match = 1.0 if user_profile.get("key") == row["key"] else 0.0

            # calculate feature similarity
            for feature, data in features.items():
                if feature in user_profile:
                    # calculate difference, normalized by feature range
                    # for most features (0-1 range), just use absolute difference
                    if feature == "loudness":
                        # loudness is usually in range -60 to 0, normalize
                        diff = abs(data["value"] - user_profile[feature]) / 60.0
                    elif feature == "tempo":
                        # tempo can vary widely, normalize more gently
                        # consider tempos "similar" if within 20 BPM
                        diff = min(
                            1.0, abs(data["value"] - user_profile[feature]) / 20.0
                        )
                    else:
                        # all other features are in 0-1 range
                        diff = abs(data["value"] - user_profile[feature])

                    # convert difference to similarity (1.0 - diff)
                    sim = 1.0 - diff
                    feature_similarity += sim * data["weight"]

            # add mode and key contribution
            feature_similarity += mode_match * 0.1  # 10% weight for mode
            feature_similarity += key_match * 0.1  # 10% weight for key

            # 3. calculate lyrics similarity if available
            lyrics_similarity = 0.0
            if user_lyrics_embedding is not None and song_id in lyrics_embeddings:
                lyrics_vector = np.array(lyrics_embeddings[song_id])
                lyrics_similarity = cosine_similarity(
                    user_lyrics_embedding.reshape(1, -1), lyrics_vector.reshape(1, -1)
                )[0][0]

            # combine similarities:
            # 50% weight to audio feature vector
            # 30% weight to audio profile features
            # 20% weight to lyrics similarity (if available)
            if user_lyrics_embedding is not None and song_id in lyrics_embeddings:
                combined_similarity = (
                    vector_similarity * 0.5
                    + feature_similarity * 0.3
                    + lyrics_similarity * 0.2
                )
            else:
                # if no lyrics embeddings, adjust weights
                combined_similarity = vector_similarity * 0.6 + feature_similarity * 0.4

            similarities.append((song_id, combined_similarity))

        # sort by similarity score (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:limit]
    except Exception as e:
        logger.error(f"error finding similar songs: {e}")
        return []


async def generate_recommendations(
    user_id: int, limit: int = 20
) -> List[Dict[str, Any]]:
    """generate hybrid music recommendations for a user"""
    # get songs the user has already liked
    user_liked_songs = await get_user_liked_songs(user_id)

    # collaborative filtering: get songs liked by friends
    collaborative_recs = await get_songs_liked_by_friends(user_id, user_liked_songs)

    # content-based filtering: calculate user's average feature vector and audio profile
    user_avg_vector = await get_user_average_feature_vector(user_id)
    user_audio_profile = await get_user_audio_profile(user_id)

    # get user's average lyrics embedding (if available)
    user_lyrics_embedding = await get_user_average_lyrics_embedding(user_id)

    content_based_recs = []

    if user_avg_vector is not None and user_audio_profile:
        content_based_recs = await find_similar_songs(
            user_avg_vector,
            user_audio_profile,
            user_liked_songs + list(collaborative_recs.keys()),
            user_lyrics_embedding,
            limit=limit,
        )

    # combine recommendations with weights
    # collaborative weight: 0.7, content-based weight: 0.3
    combined_scores = {}

    # normalize collaborative scores (0-1)
    max_collab_score = max(collaborative_recs.values()) if collaborative_recs else 1
    for song_id, count in collaborative_recs.items():
        normalized_score = count / max_collab_score
        combined_scores[song_id] = 0.7 * normalized_score

    # add content-based scores
    for song_id, similarity in content_based_recs:
        if song_id in combined_scores:
            combined_scores[song_id] += 0.3 * similarity
        else:
            combined_scores[song_id] = 0.3 * similarity

    # sort by combined score
    sorted_songs = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
    top_song_ids = [song_id for song_id, _ in sorted_songs[:limit]]

    # fetch details for recommended songs
    song_details = await get_song_details(top_song_ids)

    # add recommendation score to song details
    for song in song_details:
        song_id = song["id"]
        song["recommendation_score"] = combined_scores[song_id]

        # add recommendation source (collaborative, content-based, or both)
        sources = []
        if song_id in collaborative_recs:
            sources.append("friends")
        if any(s[0] == song_id for s in content_based_recs):
            sources.append("similar_music")

        song["recommendation_sources"] = sources

    return song_details


async def get_friend_recommendation_details(
    user_id: int, limit: int = 20
) -> List[Dict[str, Any]]:
    """get detailed friend recommendations with which friends liked each song"""
    # get user's liked songs to exclude
    user_liked_songs = await get_user_liked_songs(user_id)

    # get friend ids
    friend_ids = await get_user_friends(user_id)
    if not friend_ids:
        return []

    try:
        query = """
            WITH friend_likes AS (
                SELECT 
                    uls.song_id, 
                    uls.user_id as friend_id,
                    u.username as friend_name,
                    p.profile_picture as friend_image
                FROM user_liked_songs uls
                JOIN users u ON uls.user_id = u.id
                JOIN profiles p ON u.id = p.user_id
                WHERE uls.user_id = ANY(:friend_ids)
        """

        params = {"friend_ids": friend_ids}

        if user_liked_songs:
            query += " AND uls.song_id != ALL(:exclude_songs)"
            params["exclude_songs"] = user_liked_songs

        query += """
            ),
            song_counts AS (
                SELECT 
                    song_id, 
                    COUNT(DISTINCT friend_id) as friend_count
                FROM friend_likes
                GROUP BY song_id
            )
            SELECT 
                s.id, 
                s.name, 
                s.spotify_uri, 
                s.spotify_url, 
                s.popularity,
                s.duration_ms,
                a.name as album_name, 
                a.image_url as album_image_url,
                string_agg(DISTINCT ar.name, ', ') as artist_names,
                sc.friend_count,
                json_agg(
                    json_build_object(
                        'friend_id', fl.friend_id,
                        'friend_name', fl.friend_name,
                        'friend_image', fl.friend_image
                    )
                ) as friends_who_like
            FROM songs s
            JOIN song_counts sc ON s.id = sc.song_id
            JOIN friend_likes fl ON s.id = fl.song_id
            JOIN albums a ON s.album_id = a.id
            JOIN song_artists sa ON s.id = sa.song_id
            JOIN artists ar ON sa.artist_id = ar.id
            GROUP BY s.id, a.name, a.image_url, sc.friend_count
            ORDER BY sc.friend_count DESC, s.popularity DESC
            LIMIT :limit
        """

        params["limit"] = limit

        rows = await database.fetch_all(query, params)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"error fetching friend recommendation details: {e}")
        return []


async def get_api_recommendation_response(
    user_id: int, limit: int = 20
) -> Dict[str, Any]:
    """generate API response with recommendations"""
    is_dev_mode = (
        os.getenv("ENVIRONMENT", "").lower() == "development"
        or os.getenv("DEBUG", "").lower() == "true"
    )

    start_time = time.time() if is_dev_mode else None

    # get hybrid recommendations
    if is_dev_mode:
        logger.info(f"Generating hybrid recommendations for user_id={user_id}")

    recommendations = await generate_recommendations(user_id, limit)

    if is_dev_mode:
        logger.info(
            f"Received {len(recommendations)} hybrid recommendations in {time.time() - start_time:.2f}s"
        )
        for i, rec in enumerate(recommendations[:5]):
            sources = rec.get("recommendation_sources", [])
            source_str = ", ".join(sources) if sources else "unknown"
            logger.info(
                f"  Hybrid rec {i+1}: {rec['name']} by {rec['artist_names']} (sources: {source_str})"
            )
        if len(recommendations) > 5:
            logger.info(f"  ... and {len(recommendations) - 5} more")

    # get friend-specific recommendations with details
    if is_dev_mode:
        friend_time = time.time()
        logger.info(f"Generating friend recommendations for user_id={user_id}")

    friend_recommendations = await get_friend_recommendation_details(user_id, limit)

    if is_dev_mode:
        logger.info(
            f"Received {len(friend_recommendations)} friend recommendations in {time.time() - friend_time:.2f}s"
        )
        for i, rec in enumerate(friend_recommendations[:5]):
            friend_count = rec.get("friend_count", 0)
            logger.info(
                f"  Friend rec {i+1}: {rec['name']} by {rec['artist_names']} (liked by {friend_count} friends)"
            )
        if len(friend_recommendations) > 5:
            logger.info(f"  ... and {len(friend_recommendations) - 5} more")

    # get lyrical recommendations (if lyrics data is available)
    user_liked_songs = await get_user_liked_songs(user_id)
    user_lyrics_embedding = await get_user_average_lyrics_embedding(user_id)

    if is_dev_mode:
        lyrical_time = time.time()
        logger.info(f"Generating lyrical recommendations for user_id={user_id}")

    lyrical_recommendations = []
    if user_lyrics_embedding is not None:
        try:
            # get all song ids with lyrics embeddings (excluding liked songs)
            query = """
            SELECT song_id, lyrics_embedding
            FROM song_lyrics
            WHERE array_length(lyrics_embedding, 1) > 0
            """

            params = {}
            if user_liked_songs:
                query += " AND song_id != ALL(:exclude_songs)"
                params["exclude_songs"] = user_liked_songs

            rows = await database.fetch_all(query, params)

            # calculate similarity with user's average lyrics embedding
            similarities = []
            for row in rows:
                song_id = row["song_id"]
                lyrics_vector = np.array(row["lyrics_embedding"])

                similarity = cosine_similarity(
                    user_lyrics_embedding.reshape(1, -1), lyrics_vector.reshape(1, -1)
                )[0][0]

                similarities.append((song_id, similarity))

            # sort by similarity score (highest first)
            similarities.sort(key=lambda x: x[1], reverse=True)
            top_similar = similarities[:limit]

            # get song details
            song_ids = [song_id for song_id, _ in top_similar]
            lyrical_recommendations = await get_song_details(song_ids)

            # add similarity scores to results
            similarity_dict = dict(top_similar)
            for song in lyrical_recommendations:
                song_id = song["id"]
                song["lyrics_similarity"] = similarity_dict.get(song_id, 0)

            if is_dev_mode:
                logger.info(
                    f"Received {len(lyrical_recommendations)} lyrical recommendations in {time.time() - lyrical_time:.2f}s"
                )
                for i, rec in enumerate(lyrical_recommendations[:5]):
                    similarity = rec.get("lyrics_similarity", 0)
                    logger.info(
                        f"  Lyrical rec {i+1}: {rec['name']} by {rec['artist_names']} (similarity: {similarity:.4f})"
                    )
                if len(lyrical_recommendations) > 5:
                    logger.info(f"  ... and {len(lyrical_recommendations) - 5} more")
        except Exception as e:
            logger.error(f"error generating lyrical recommendations: {e}")
            if is_dev_mode:
                logger.info("Failed to generate lyrical recommendations")

    if is_dev_mode:
        total_time = time.time() - start_time
        logger.info(f"Total recommendation generation completed in {total_time:.2f}s")
        logger.info(
            f"Summary: {len(recommendations)} hybrid, {len(friend_recommendations)} friend, {len(lyrical_recommendations)} lyrical recommendations"
        )

    return {
        "recommendations": {
            "hybrid": recommendations,
            "from_friends": friend_recommendations,
            "lyrical": lyrical_recommendations,
        }
    }


router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


# user dependency
async def get_current_user_id(request: Request):
    from auth import get_current_user, get_db

    database = get_db()

    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await get_current_user(token, database=database)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user.id


@router.get("/")
async def get_recommendations(
    user_id: int = Depends(get_current_user_id), limit: int = 20
):
    """get personalized recommendations for the authenticated user"""
    return await get_api_recommendation_response(user_id, limit)


@router.get("/friends")
async def get_friend_recommendations(
    user_id: int = Depends(get_current_user_id), limit: int = 20
):
    """get recommendations based on friends' liked songs"""
    friend_recommendations = await get_friend_recommendation_details(user_id, limit)
    return {"recommendations": friend_recommendations}


@router.get("/similar")
async def get_similar_recommendations(
    user_id: int = Depends(get_current_user_id), limit: int = 20
):
    """get recommendations based on audio similarity to liked songs"""
    # get songs the user has already liked
    user_liked_songs = await get_user_liked_songs(user_id)

    # calculate user's average feature vector and audio profile
    user_avg_vector = await get_user_average_feature_vector(user_id)
    user_audio_profile = await get_user_audio_profile(user_id)

    # get user's average lyrics embedding (if available)
    user_lyrics_embedding = await get_user_average_lyrics_embedding(user_id)

    if user_avg_vector is None or not user_audio_profile:
        return {
            "recommendations": [],
            "message": "Not enough liked songs with audio features",
        }

    # find similar songs
    similar_songs = await find_similar_songs(
        user_avg_vector,
        user_audio_profile,
        user_liked_songs,
        user_lyrics_embedding,
        limit=limit,
    )

    # get song details
    song_ids = [song_id for song_id, _ in similar_songs]
    song_details = await get_song_details(song_ids)

    # add similarity scores
    similarity_dict = dict(similar_songs)
    for song in song_details:
        song_id = song["id"]
        song["similarity_score"] = similarity_dict.get(song_id, 0)

    return {"recommendations": song_details}


async def get_lyrical_recommendations(
    user_id: int, limit: int = 20
) -> List[Dict[str, Any]]:
    """get recommendations based purely on lyrical content similarity"""
    # get songs the user has already liked
    user_liked_songs = await get_user_liked_songs(user_id)

    # get user's average lyrics embedding
    user_lyrics_embedding = await get_user_average_lyrics_embedding(user_id)

    if user_lyrics_embedding is None:
        return []

    try:
        # get all song ids with lyrics embeddings (excluding liked songs)
        query = """
        SELECT song_id, lyrics_embedding
        FROM song_lyrics
        WHERE array_length(lyrics_embedding, 1) > 0
        """

        params = {}
        if user_liked_songs:
            query += " AND song_id != ALL(:exclude_songs)"
            params["exclude_songs"] = user_liked_songs

        rows = await database.fetch_all(query, params)

        # calculate similarity with user's average lyrics embedding
        similarities = []
        for row in rows:
            song_id = row["song_id"]
            lyrics_vector = np.array(row["lyrics_embedding"])

            similarity = cosine_similarity(
                user_lyrics_embedding.reshape(1, -1), lyrics_vector.reshape(1, -1)
            )[0][0]

            similarities.append((song_id, similarity))

        # sort by similarity score (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_similar = similarities[:limit]

        # get song details
        song_ids = [song_id for song_id, _ in top_similar]
        song_details = await get_song_details(song_ids)

        # add similarity scores to results
        similarity_dict = dict(top_similar)
        for song in song_details:
            song_id = song["id"]
            song["lyrics_similarity"] = similarity_dict.get(song_id, 0)

        return song_details
    except Exception as e:
        logger.error(f"error generating lyrical recommendations: {e}")
        return []


@router.get("/lyrical")
async def get_lyrical_recs(
    user_id: int = Depends(get_current_user_id), limit: int = 20
):
    """get recommendations based on lyrical content similarity"""
    lyrical_recommendations = await get_lyrical_recommendations(user_id, limit)

    if not lyrical_recommendations:
        return {
            "recommendations": [],
            "message": "Not enough liked songs with lyrics data",
        }

    return {"recommendations": lyrical_recommendations}
