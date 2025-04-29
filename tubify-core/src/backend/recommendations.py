from typing import List, Dict, Tuple, Optional, Any, Set
import numpy as np
from dotenv import load_dotenv
import logging
from pydantic import BaseModel
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from sklearn.neighbors import NearestNeighbors
from fastapi import APIRouter, Depends, HTTPException, Request
from database import database
import os
import time
from scipy.spatial.distance import cdist
from sklearn.preprocessing import StandardScaler
from sklearn.manifold import TSNE
import random
import json
from sklearn.decomposition import PCA
import numpy.typing as npt
from scipy.spatial.distance import cosine
from datetime import datetime, date
import traceback
import pandas as pd
from auth import get_current_user, get_db

# set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("recommendations")

# load environment variables
load_dotenv()

# configuration
CLUSTER_K = int(os.getenv("CLUSTER_K", 3))
MMR_LAMBDA = float(os.getenv("MMR_LAMBDA", 0.7))
KNN_NEIGHBORS = int(os.getenv("KNN_NEIGHBORS", 20))
KNN_NEIGHBORS_SIMILAR = int(os.getenv("KNN_NEIGHBORS_SIMILAR", 20))
FEEDBACK_WEIGHT = float(os.getenv("FEEDBACK_WEIGHT", 0.3))
CLUSTER_CACHE_TTL = 24 * 60 * 60  # 24 hours in seconds


# add a helper function to make numpy values JSON serializable
def make_json_serializable(obj):
    """Convert numpy types to Python standard types for JSON serialization"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


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
    try:
        if not song_ids:
            # if no song_ids provided, get a limited number of embeddings
            rows = await database.fetch_all(
                """
                SELECT song_id, lyrics_embedding
                FROM song_lyrics
                WHERE array_length(lyrics_embedding, 1) > 0
                LIMIT 1000
                """
            )
        else:
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

    # special normalization for tempo and loudness which can go outside 0-1 range
    if "tempo" in profile:
        # normalize tempo to 0-1 range (max normal tempo is about 200 bpm)
        profile["tempo"] = min(1.0, max(0.0, profile["tempo"] / 200.0))

    if "loudness" in profile:
        # loudness is usually in range -60 to 0 dB, normalize to 0-1
        profile["loudness"] = min(1.0, max(0.0, (profile["loudness"] + 60) / 60.0))

    # sanitize the entire profile to ensure all values are in correct range
    sanitized_profile = sanitize_audio_profile(profile)

    return sanitized_profile


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
    try:
        liked_songs = await get_user_liked_songs(user_id)
        if not liked_songs:
            logger.warning("User has no liked songs for lyrics embedding calculation")
            return None

        lyrics_embeddings = await get_song_lyrics_embeddings(liked_songs)
        if not lyrics_embeddings:
            logger.warning("No lyrics embeddings found for user's liked songs")
            return None

        # calculate average embedding vector
        vectors = []
        for song_id, embedding in lyrics_embeddings.items():
            # skip empty embeddings
            if not embedding or len(embedding) == 0:
                continue

            # convert to numpy array and verify it has data
            embedding_array = np.array(embedding)
            if embedding_array.size == 0:
                continue

            vectors.append(embedding_array)

        if not vectors:
            logger.warning("No valid lyrics embedding vectors found for user's songs")
            return None

        # check that all vectors have the same dimensionality
        dimensions = [v.shape[0] for v in vectors]
        if len(set(dimensions)) > 1:
            logger.warning(f"Inconsistent embedding dimensions: {dimensions}")
            # filter to keep only vectors with the most common dimension
            most_common_dim = max(set(dimensions), key=dimensions.count)
            vectors = [v for v in vectors if v.shape[0] == most_common_dim]

            if not vectors:
                logger.warning("No embeddings with consistent dimensions")
                return None

        # calculate mean of all vectors
        return np.mean(vectors, axis=0)
    except Exception as e:
        logger.error(f"error calculating user average lyrics embedding: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None


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


async def get_user_feature_clusters(
    user_id: int, k: int = CLUSTER_K, force_recalculate: bool = False
) -> List[np.ndarray]:
    """Cluster a user's liked-song feature vectors into k centroids with optimal k selection."""
    liked_songs = await get_user_liked_songs(user_id)
    features = await get_song_audio_features(liked_songs)
    vectors = [
        np.array(f["feature_vector"])
        for f in features.values()
        if "feature_vector" in f
    ]

    if not vectors:
        return []

    # if we have very few songs, don't cluster
    if len(vectors) < 3:
        return [np.mean(vectors, axis=0)]

    # determine optimal k using the elbow method if we have enough data
    if len(vectors) >= 10:
        # use min(5, len(vectors)/2) as max k to test
        max_k = min(5, len(vectors) // 2)
        if max_k > 1:
            distortions = []
            K = range(1, max_k + 1)
            vectors_array = np.array(vectors)

            for k_val in K:
                kmeans_model = KMeans(n_clusters=k_val, random_state=42, n_init=10)
                kmeans_model.fit(vectors_array)
                distortions.append(
                    sum(
                        np.min(
                            cdist(
                                vectors_array,
                                kmeans_model.cluster_centers_,
                                "euclidean",
                            ),
                            axis=1,
                        )
                    )
                    / vectors_array.shape[0]
                )

            # find elbow point - largest decrease in distortion
            k = 1  # default
            if len(distortions) > 1:
                deltas = np.array(
                    [
                        distortions[i] - distortions[i + 1]
                        for i in range(len(distortions) - 1)
                    ]
                )
                # normalize deltas by first delta to get relative improvements
                if deltas[0] != 0:
                    rel_deltas = deltas / deltas[0]
                    # find where relative improvement drops below 0.5 (diminishing returns)
                    below_threshold = np.where(rel_deltas < 0.5)[0]
                    if len(below_threshold) > 0:
                        k = below_threshold[0] + 1
                    else:
                        k = len(deltas)  # use max k if no clear elbow
        else:
            k = 1
    else:
        # for small datasets, use a simple heuristic
        k = min(CLUSTER_K, max(1, len(vectors) // 3))

    # ensure k is at least 1 and at most 5
    k = max(1, min(5, k))

    # perform clustering with selected k
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10).fit(vectors)

    # get cluster sizes to identify significant clusters
    labels = kmeans.labels_
    cluster_sizes = np.bincount(labels)

    # only keep clusters with at least 2 items or 10% of total items
    min_cluster_size = max(2, len(vectors) * 0.1)
    significant_clusters = [
        i for i, size in enumerate(cluster_sizes) if size >= min_cluster_size
    ]

    # if no significant clusters, fallback to average
    if not significant_clusters:
        return [np.mean(vectors, axis=0)]

    # return centroids of significant clusters
    return [kmeans.cluster_centers_[i] for i in significant_clusters]


def mmr_rerank(
    candidates: List[Tuple[str, float]],
    feature_vectors: Dict[str, np.ndarray],
    lambda_param: float = MMR_LAMBDA,
    top_n: int = 20,
    user_feedback: Optional[Dict[str, bool]] = None,
) -> List[Tuple[str, float]]:
    """
    Maximal Marginal Relevance reranking: balances relevance (score) and diversity.
    Incorporates user feedback to adjust ranking.
    """
    if not candidates:
        return []

    # make a copy to avoid modifying the original list
    candidates_copy = candidates.copy()

    # initialize selected items list
    selected: List[Tuple[str, float]] = []

    # early return if feature_vectors is empty
    if not feature_vectors:
        return candidates_copy[:top_n]

    # ensure all candidates have feature vectors
    candidates_copy = [
        (s, score) for s, score in candidates_copy if s in feature_vectors
    ]

    # if we have feedback, adjust lambda dynamically
    # a higher lambda focuses more on relevance, lower lambda focuses on diversity
    dynamic_lambda = lambda_param
    if user_feedback:
        # count positive and negative feedback
        positive = sum(1 for liked in user_feedback.values() if liked)
        negative = sum(1 for liked in user_feedback.values() if not liked)

        # if user has given more negative feedback, focus more on diversity
        if negative > positive:
            dynamic_lambda = max(0.3, lambda_param - 0.2)
        # if user has given more positive feedback, focus more on relevance
        elif positive > negative:
            dynamic_lambda = min(0.9, lambda_param + 0.1)

    # incrementally build the ranked list
    while len(selected) < top_n and candidates_copy:
        mmr_scores: List[Tuple[str, float]] = []

        for song_id, score in candidates_copy:
            # apply feedback adjustment if available
            if user_feedback and song_id in user_feedback:
                # boost score for liked songs, penalize disliked ones
                if user_feedback[song_id]:
                    score = min(1.0, score * 1.2)  # 20% boost for liked songs
                else:
                    score = max(0.0, score * 0.5)  # 50% penalty for disliked songs

            # calculate diversity term (maximum similarity to already selected items)
            diversity_term = 0.0
            if selected:
                similarities = []
                for chosen_id, _ in selected:
                    if chosen_id in feature_vectors and song_id in feature_vectors:
                        sim = cosine_similarity(
                            feature_vectors[song_id].reshape(1, -1),
                            feature_vectors[chosen_id].reshape(1, -1),
                        )[0][0]
                        similarities.append(sim)

                if similarities:
                    diversity_term = max(similarities)

            # calculate MMR score
            mmr_score = dynamic_lambda * score - (1 - dynamic_lambda) * diversity_term
            mmr_scores.append((song_id, mmr_score))

        if not mmr_scores:
            break

        # pick item with highest MMR score
        best_id, _ = max(mmr_scores, key=lambda x: x[1])

        # find original score
        for sid, s in candidates_copy:
            if sid == best_id:
                selected.append((sid, s))
                candidates_copy.remove((sid, s))
                break

    return selected


async def generate_recommendations(
    user_id: int, limit: int = 20
) -> List[Dict[str, Any]]:
    """generate hybrid music recommendations for a user with multi-interest clustering, diversity, and feedback"""
    # get songs the user has already liked
    user_liked_songs = await get_user_liked_songs(user_id)

    # get user feedback for personalization
    user_feedback = await get_user_feedback(user_id)

    # build exclusion list: user's liked songs + explicitly disliked songs
    exclude_songs = user_liked_songs.copy()
    for song_id, liked in user_feedback.items():
        if not liked:  # if the song was disliked
            exclude_songs.append(song_id)

    # content-based: multi-interest clusters with feedback
    user_audio_profile = await get_user_audio_profile(user_id)
    feature_vectors, _ = await get_user_feature_vectors_with_feedback(
        user_id, use_clustering=True
    )
    user_lyrics_embedding = await get_user_average_lyrics_embedding(user_id)

    # collaborative filtering: get songs liked by friends
    collaborative_recs = await get_songs_liked_by_friends(user_id, exclude_songs)

    # content-based recommendations from clusters and KNN
    content_cluster_recs: List[List[Tuple[str, float]]] = []

    # if we have enough data for clustering
    if feature_vectors:
        # get recommendations for each cluster
        for centroid in feature_vectors:
            # try KNN first, then fallback to similarity search
            knn_recs = await get_similar_songs_with_knn(
                centroid,
                user_liked_songs + list(collaborative_recs.keys()),
                n_neighbors=KNN_NEIGHBORS,
                user_feedback=user_feedback,
            )

            if knn_recs:
                recs = knn_recs
            else:
                # fallback to traditional similarity search
                recs = await find_similar_songs(
                    centroid,
                    user_audio_profile,
                    user_liked_songs + list(collaborative_recs.keys()),
                    user_lyrics_embedding,
                    limit=limit,
                )

            # fetch feature vectors for MMR
            song_ids = [sid for sid, _ in recs]
            audio_feats = await get_song_audio_features(song_ids)
            feat_map = {
                sid: np.array(audio_feats[sid]["feature_vector"]) for sid in audio_feats
            }

            # apply diversity reranking with feedback
            reranked = mmr_rerank(
                recs,
                feat_map,
                lambda_param=MMR_LAMBDA,
                top_n=limit,
                user_feedback=user_feedback,
            )

            content_cluster_recs.append(reranked)
    else:
        # no clusters available, use overall average vector
        avg_vector = await get_user_average_feature_vector(user_id)
        if avg_vector is not None:
            # try KNN first
            knn_recs = await get_similar_songs_with_knn(
                avg_vector,
                user_liked_songs + list(collaborative_recs.keys()),
                n_neighbors=KNN_NEIGHBORS,
                user_feedback=user_feedback,
            )

            if knn_recs:
                recs = knn_recs
            else:
                # fallback to traditional similarity search
                recs = await find_similar_songs(
                    avg_vector,
                    user_audio_profile,
                    user_liked_songs + list(collaborative_recs.keys()),
                    user_lyrics_embedding,
                    limit=limit,
                )

            # fetch feature vectors for MMR
            song_ids = [sid for sid, _ in recs]
            audio_feats = await get_song_audio_features(song_ids)
            feat_map = {
                sid: np.array(audio_feats[sid]["feature_vector"]) for sid in audio_feats
            }

            # apply diversity reranking with feedback
            reranked = mmr_rerank(
                recs,
                feat_map,
                lambda_param=MMR_LAMBDA,
                top_n=limit,
                user_feedback=user_feedback,
            )

            content_cluster_recs.append(reranked)

    # interleave cluster lists round-robin
    merged: List[Tuple[str, float]] = []
    pointers = [0] * len(content_cluster_recs)
    while len(merged) < limit:
        added = False
        for idx, recs in enumerate(content_cluster_recs):
            if pointers[idx] < len(recs):
                song_id, score = recs[pointers[idx]]
                pointers[idx] += 1
                if all(song_id != s for s, _ in merged):
                    merged.append((song_id, score))
                    added = True
                    if len(merged) >= limit:
                        break
        if not added:
            break

    content_based_recs = merged[:limit]

    # combine recommendations with weights, incorporating feedback
    combined_scores: Dict[str, float] = {}
    max_collab = max(collaborative_recs.values()) if collaborative_recs else 1

    for sid, count in collaborative_recs.items():
        base_score = 0.7 * (count / max_collab)
        # adjust based on feedback if available
        if sid in user_feedback:
            if user_feedback[sid]:
                base_score *= 1.3  # boost score by 30% for liked songs
            else:
                base_score *= 0.3  # reduce score by 70% for disliked songs
        combined_scores[sid] = base_score

    for sid, sim in content_based_recs:
        base_score = 0.3 * sim
        # adjust based on feedback if available
        if sid in user_feedback:
            if user_feedback[sid]:
                base_score *= 1.3  # boost score by 30% for liked songs
            else:
                base_score *= 0.3  # reduce score by 70% for disliked songs
        combined_scores[sid] = combined_scores.get(sid, 0) + base_score

    # sort and fetch top
    sorted_songs = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
    top_ids = [sid for sid, _ in sorted_songs[:limit]]
    song_details = await get_song_details(top_ids)

    for song in song_details:
        sid = song["id"]
        song["recommendation_score"] = combined_scores[sid]

        # add sources
        sources = []
        if sid in collaborative_recs:
            sources.append("friends")
        if any(sid == s for s, _ in content_based_recs):
            sources.append("similar_music")
        song["recommendation_sources"] = sources

        # add feedback status if available
        if sid in user_feedback:
            song["user_feedback"] = user_feedback[sid]

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
        # first get songs with friend counts to find the most popular songs
        songs_query = """
            WITH friend_likes AS (
                SELECT 
                    uls.song_id, 
                    uls.user_id as friend_id
                FROM user_liked_songs uls
                WHERE uls.user_id = ANY(:friend_ids)
        """

        params = {"friend_ids": friend_ids}

        if user_liked_songs:
            songs_query += " AND uls.song_id != ALL(:exclude_songs)"
            params["exclude_songs"] = user_liked_songs

        songs_query += """
            ),
            song_counts AS (
                SELECT 
                    song_id, 
                    COUNT(DISTINCT friend_id) as friend_count,
                    array_agg(DISTINCT friend_id) as friend_ids
                FROM friend_likes
                GROUP BY song_id
            )
            SELECT 
                s.id, 
                s.name,
                sc.friend_count,
                sc.friend_ids
            FROM songs s
            JOIN song_counts sc ON s.id = sc.song_id
            ORDER BY 
                -- prioritize songs liked by multiple friends
                sc.friend_count DESC, 
                -- then by popularity for tie-breaking
                s.popularity DESC
            LIMIT :limit
        """

        # ensure we have enough candidates to filter out some
        params["limit"] = limit * 3

        songs_rows = await database.fetch_all(songs_query, params)
        if not songs_rows:
            return []

        # select songs with diverse set of friends
        selected_songs = []
        friends_used = set()  # track which friends have already been used

        # first pass: add songs with new friends
        for row in songs_rows:
            song_id = row["id"]
            friend_ids_temp = row["friend_ids"]

            # calculate how many new friends this song would add
            new_friends = [f for f in friend_ids_temp if f not in friends_used]

            # only add the song if it has at least one new friend
            if new_friends:
                selected_songs.append(song_id)
                friends_used.update(friend_ids_temp)

                # stop once we've reached our limit
                if len(selected_songs) >= limit:
                    break

        # second pass: if we still need more songs, add any remaining songs
        if len(selected_songs) < limit:
            for row in songs_rows:
                if row["id"] not in selected_songs:
                    selected_songs.append(row["id"])
                    if len(selected_songs) >= limit:
                        break

        # now get full details for the selected songs
        details_query = """
            WITH friend_likes AS (
                SELECT 
                    uls.song_id, 
                    uls.user_id as friend_id,
                    u.username as friend_name
                FROM user_liked_songs uls
                JOIN users u ON uls.user_id = u.id
                WHERE uls.user_id = ANY(:friend_ids)
                AND uls.song_id = ANY(:song_ids)
            ),
            song_counts AS (
                SELECT 
                    song_id, 
                    COUNT(DISTINCT friend_id) as friend_count
                FROM friend_likes
                GROUP BY song_id
            ),
            -- get distinct friends for each song
            distinct_friends AS (
                SELECT
                    song_id,
                    friend_id,
                    friend_name
                FROM friend_likes
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
                (
                    -- get all distinct friends who liked this song
                    SELECT json_agg(
                        json_build_object(
                            'friend_id', df.friend_id,
                            'friend_name', df.friend_name
                        )
                    )
                    FROM distinct_friends df
                    WHERE df.song_id = s.id
                ) as friends_who_like
            FROM songs s
            JOIN song_counts sc ON s.id = sc.song_id
            JOIN albums a ON s.album_id = a.id
            JOIN song_artists sa ON s.id = sa.song_id
            JOIN artists ar ON sa.artist_id = ar.id
            WHERE s.id = ANY(:song_ids)
            GROUP BY s.id, a.name, a.image_url, sc.friend_count
            ORDER BY array_position(:song_ids, s.id)
        """

        details_params = {"friend_ids": friend_ids, "song_ids": selected_songs}

        rows = await database.fetch_all(details_query, details_params)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"error fetching friend recommendation details: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return []


async def get_api_recommendation_response(
    user_id: int, limit: int = 20
) -> Dict[str, Any]:
    """generate API response with recommendations"""

    start_time = time.time()

    try:
        # generate hybrid recommendations (combination of different sources)
        recommendations = await generate_recommendations(user_id, limit)

        # get recommendations from different sources for tab views
        friend_recommendations = await get_friend_recommendation_details(user_id, limit)
        similar_recommendations = await get_similar_recommendations(user_id, limit)
        lyrical_recommendations = await get_lyrical_recommendations(user_id, limit)

        # get all user feedback to apply to recommendations in all tabs
        user_feedback = await get_user_feedback(user_id)

        # helper to add feedback to each recommendation
        def add_feedback_to_recommendations(recs):
            if not recs:
                return []

            # check if recs is a list or dictionary
            if isinstance(recs, dict):
                # if it contains a 'recommendations' key, extract it first
                if "recommendations" in recs:
                    logger.warning(
                        f"Found nested 'recommendations' key in data, extracting"
                    )
                    recs = recs["recommendations"]

                # then convert dict to list if necessary
                if not isinstance(recs, list):
                    recs = [recs]
            elif not isinstance(recs, list):
                # if it's not a list or dict, convert to list with single value
                recs = [recs]

            for i in range(len(recs)):
                rec = recs[i]
                # check if rec is a string or dict
                if isinstance(rec, str):
                    # if it's a string (song_id), convert to dict first
                    logger.warning(f"Converting string recommendation to dict: {rec}")
                    recs[i] = {"id": rec}
                    rec = recs[i]

                if "id" in rec and rec["id"] in user_feedback:
                    rec["user_feedback"] = user_feedback[rec["id"]]

            return recs

        # apply feedback to all recommendation sets with better error handling
        try:
            recommendations = add_feedback_to_recommendations(recommendations)
        except Exception as e:
            logger.error(f"Error adding feedback to hybrid recommendations: {e}")

        try:
            friend_recommendations = add_feedback_to_recommendations(
                friend_recommendations
            )
        except Exception as e:
            logger.error(f"Error adding feedback to friend recommendations: {e}")

        try:
            similar_recommendations = add_feedback_to_recommendations(
                similar_recommendations
            )
        except Exception as e:
            logger.error(f"Error adding feedback to similar recommendations: {e}")

        try:
            lyrical_recommendations = add_feedback_to_recommendations(
                lyrical_recommendations
            )
        except Exception as e:
            logger.error(f"Error adding feedback to lyrical recommendations: {e}")

        # insert all recommendations into the database to get recommendation_ids
        # first delete old recommendation records
        await database.execute(
            """
            DELETE FROM recommendations
            WHERE user_id = :user_id
            """,
            {"user_id": user_id},
        )

        # helper function to insert recommendations and add ids
        async def insert_recommendations(recs, source_prefix):
            # map to track which cluster each song belongs to
            song_to_cluster = {}

            # initialize content_cluster_recs as empty to avoid undefined variable error
            content_cluster_recs = []

            # if content_cluster_recs is available, map songs to their clusters
            if "content_cluster_recs" in locals() and len(content_cluster_recs) > 0:
                for cluster_idx, cluster_recs in enumerate(content_cluster_recs):
                    for song_id, _ in cluster_recs:
                        song_to_cluster[song_id] = cluster_idx

            # check if recs has a nested structure
            if isinstance(recs, dict) and "recommendations" in recs:
                logger.warning(
                    f"Found nested 'recommendations' key in {source_prefix}, extracting"
                )
                recs = recs["recommendations"]

            # ensure recs is a list
            if not isinstance(recs, list):
                logger.warning(f"Converting non-list recommendations to list: {recs}")
                recs = [recs] if recs is not None else []

            # process each recommendation
            for i in range(len(recs)):
                rec = recs[i]
                # skip if it already has a recommendation_id
                if "recommendation_id" in rec:
                    continue

                # handle string recommendations
                if isinstance(rec, str):
                    logger.warning(f"Converting string recommendation to dict: {rec}")
                    recs[i] = {"id": rec}
                    rec = recs[i]

                # check if the recommendation has an ID
                if "id" not in rec:
                    logger.warning(f"Recommendation missing ID, skipping: {rec}")
                    continue

                sources = rec.get("recommendation_sources", [])
                if not sources and source_prefix:
                    sources = [source_prefix]

                try:
                    rec_id = await database.execute(
                        """
                        INSERT INTO recommendations (user_id, song_id, source)
                        VALUES (:user_id, :song_id, :source)
                        RETURNING id
                        """,
                        {
                            "user_id": user_id,
                            "song_id": rec["id"],
                            "source": ",".join(sources),
                        },
                    )
                    rec["recommendation_id"] = rec_id
                except Exception as insert_err:
                    logger.error(f"Error inserting recommendation: {insert_err}")

            return recs

        # insert all recommendations
        recommendations = await insert_recommendations(recommendations, "hybrid")
        friend_recommendations = await insert_recommendations(
            friend_recommendations, "friends"
        )
        similar_recommendations = await insert_recommendations(
            similar_recommendations, "similar"
        )
        lyrical_recommendations = await insert_recommendations(
            lyrical_recommendations, "lyrical"
        )

        # get analytics data for additional insight
        try:
            analytics = {
                "feedback_stats": {
                    "total": len(user_feedback),
                    "positive": sum(1 for v in user_feedback.values() if v),
                    "negative": sum(1 for v in user_feedback.values() if not v),
                }
            }
        except Exception as e:
            logger.error(f"error generating analytics data: {e}")
            analytics = {}

        end_time = time.time()
        logger.info(f"API response generated in {end_time - start_time:.2f} seconds")

        return {
            "recommendations": {
                "hybrid": recommendations,
                "friends": friend_recommendations,
                "similar": similar_recommendations,
                "lyrical": lyrical_recommendations,
            },
            "analytics": analytics,
        }
    except Exception as e:
        logger.error(f"Error generating API recommendation response: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate API recommendation response: {str(e)}",
        )


router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


# user dependency
async def get_current_user_id(request: Request):
    database = get_db()

    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await get_current_user(token, database=database)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user.id


class FeedbackModel(BaseModel):
    song_id: str
    liked: bool
    recommendation_id: Optional[int] = None
    tab: Optional[str] = None


@router.post("/feedback")
async def post_feedback(
    feedback: FeedbackModel, user_id: int = Depends(get_current_user_id)
):
    """record a user's like/dislike for a song recommendation"""
    try:
        # try to get the source of the recommendation if it exists
        source = None
        if feedback.recommendation_id:
            rec_row = await database.fetch_one(
                "SELECT source FROM recommendations WHERE id = :rec_id",
                {"rec_id": feedback.recommendation_id},
            )
            if rec_row:
                source = rec_row["source"]

        # check if feedback already exists for this song
        existing = await database.fetch_one(
            "SELECT id FROM recommendation_feedback WHERE song_id = :song_id AND user_id = :user_id",
            {"song_id": feedback.song_id, "user_id": user_id},
        )

        if existing:
            # update existing feedback
            await database.execute(
                """
                UPDATE recommendation_feedback 
                SET liked = :liked, feedback_at = CURRENT_TIMESTAMP,
                    source = COALESCE(:source, source)
                WHERE id = :id
                """,
                {"id": existing["id"], "liked": feedback.liked, "source": source},
            )
            logger.info(f"updated existing feedback for song {feedback.song_id}")
        else:
            # insert new feedback
            try:
                feedback_id = await database.execute(
                    """
                    INSERT INTO recommendation_feedback (song_id, user_id, liked, source)
                    VALUES (:song_id, :user_id, :liked, :source)
                    RETURNING id
                    """,
                    {
                        "song_id": feedback.song_id,
                        "user_id": user_id,
                        "liked": feedback.liked,
                        "source": source,
                    },
                )
                logger.info(f"inserted new feedback for song {feedback.song_id}")
            except Exception as insert_error:
                logger.error(f"failed to insert feedback: {insert_error}")
                raise insert_error

        # for analytics and monitoring, also track this in user liked songs if it was liked
        if feedback.liked:
            try:
                # check if song is already in user liked songs
                liked_song = await database.fetch_one(
                    "SELECT 1 FROM user_liked_songs WHERE user_id = :user_id AND song_id = :song_id",
                    {"user_id": user_id, "song_id": feedback.song_id},
                )

                if not liked_song:
                    # add to user liked songs for future recommendations
                    await database.execute(
                        """
                        INSERT INTO user_liked_songs (user_id, song_id) 
                        VALUES (:user_id, :song_id)
                        """,
                        {"user_id": user_id, "song_id": feedback.song_id},
                    )
                    logger.info(f"added song {feedback.song_id} to user_liked_songs")
            except Exception as like_error:
                # don't fail the whole feedback process if this part fails
                logger.warning(f"could not add to user_liked_songs: {like_error}")

        return {"success": True, "message": "feedback recorded successfully"}
    except Exception as e:
        logger.error(f"error recording feedback: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to record feedback")


@router.get("/")
async def get_recommendations(
    user_id: int = Depends(get_current_user_id), limit: int = 20
):
    """get personalized recommendations and log them"""
    try:
        # delete all previous recommendations for this user
        await database.execute(
            """
            DELETE FROM recommendations
            WHERE user_id = :user_id
            """,
            {"user_id": user_id},
        )

        # generate new recommendations
        recs = await generate_recommendations(user_id, limit)

        # get existing user feedback
        user_feedback = await get_user_feedback(user_id)

        # after fetching details, log to DB
        for song in recs:

            # save the recommendation record
            rec_id = await database.execute(
                """
                INSERT INTO recommendations (user_id, song_id, source)
                VALUES (:user_id, :song_id, :source)
                RETURNING id
                """,
                {
                    "user_id": user_id,
                    "song_id": song["id"],
                    "source": ",".join(song.get("recommendation_sources", [])),
                },
            )

            # add recommendation_id to each song for frontend feedback
            song["recommendation_id"] = rec_id

            # add existing feedback if available
            if song["id"] in user_feedback:
                song["user_feedback"] = user_feedback[song["id"]]

        return {"recommendations": recs}
    except Exception as e:
        logger.error(f"error generating recommendations: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail="failed to generate recommendations"
        )


@router.get("/api-response")
async def get_api_recommendation_response_route(
    user_id: int = Depends(get_current_user_id), limit: int = 20
):
    """get personalized recommendations with analytics data for API response"""
    try:
        response_data = await get_api_recommendation_response(user_id, limit)

        # convert numpy values to standard Python types for JSON serialization
        serializable_data = json.loads(
            json.dumps(response_data, default=make_json_serializable)
        )

        return serializable_data
    except Exception as e:
        logger.error(f"error generating API recommendation response: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail=f"failed to generate recommendations: {str(e)}"
        )


@router.get("/feedback")
async def get_user_recommendation_feedback(user_id: int = Depends(get_current_user_id)):
    """get a user's feedback history for recommendations"""
    try:
        query = """
            SELECT 
                rf.song_id,
                rf.liked,
                rf.feedback_at,
                s.name as song_name,
                s.spotify_uri,
                a.name as album_name,
                a.image_url as album_image_url,
                string_agg(ar.name, ', ') as artist_names
            FROM recommendation_feedback rf
            JOIN songs s ON rf.song_id = s.id
            JOIN albums a ON s.album_id = a.id
            JOIN song_artists sa ON s.id = sa.song_id
            JOIN artists ar ON sa.artist_id = ar.id
            WHERE rf.user_id = :user_id
            GROUP BY rf.song_id, rf.liked, rf.feedback_at, s.name, 
                     s.spotify_uri, a.name, a.image_url
            ORDER BY rf.feedback_at DESC
        """

        rows = await database.fetch_all(query, {"user_id": user_id})
        feedback = [dict(row) for row in rows]

        return {"feedback": feedback}
    except Exception as e:
        logger.error(f"error retrieving user feedback: {e}")
        raise HTTPException(
            status_code=500, detail="failed to retrieve feedback history"
        )


@router.get("/friends")
async def get_friend_recommendations(
    user_id: int = Depends(get_current_user_id), limit: int = 20
):
    """get recommendations based on friends' liked songs"""
    friend_recommendations = await get_friend_recommendation_details(user_id, limit)
    return {"recommendations": friend_recommendations}


@router.get("/similar")
async def get_similar_recommendations_route(
    user_id: int = Depends(get_current_user_id), limit: int = 20
):
    """get recommendations based on similar audio features to liked songs"""
    similar_recommendations = await get_similar_recommendations(user_id, limit)
    return {"recommendations": similar_recommendations}


async def get_lyrical_recommendations(
    user_id: int, limit: int = 20
) -> List[Dict[str, Any]]:
    """generate recommendations based on lyrical similarity"""
    try:
        # get songs the user has already liked
        user_liked_songs = await get_user_liked_songs(user_id)
        if not user_liked_songs:
            logger.warning("User has no liked songs for lyrical recommendations")
            return []

        # get user feedback for personalization
        user_feedback = await get_user_feedback(user_id)

        # build exclusion list: user's liked songs + explicitly disliked songs
        exclude_songs = user_liked_songs.copy()
        for song_id, liked in user_feedback.items():
            if not liked:  # if the song was disliked
                exclude_songs.append(song_id)

        # calculate user's average lyrics embedding
        user_lyrics_embedding = await get_user_average_lyrics_embedding(user_id)
        if user_lyrics_embedding is None:
            logger.warning("Not enough songs with lyrics vectors for user")
            return []

        # verify the embedding has data
        if user_lyrics_embedding.size == 0:
            logger.warning("user lyrics embedding is empty")
            return []

        # get song lyrics from the database
        query = """
            SELECT song_id, lyrics_embedding FROM song_lyrics
        """

        params = {}
        if exclude_songs:
            query += " WHERE song_id != ALL(:exclude_songs)"
            params["exclude_songs"] = exclude_songs

        rows = await database.fetch_all(query, params)

        if not rows:
            logger.warning("No songs with lyrics found in database")
            return []

        # calculate similarity
        similarities = []
        for row in rows:
            song_id = row["song_id"]
            embedding = np.array(row["lyrics_embedding"])

            # skip empty embeddings
            if embedding.size == 0:
                continue

            try:
                # calculate cosine similarity
                similarity = cosine_similarity(
                    user_lyrics_embedding.reshape(1, -1), embedding.reshape(1, -1)
                )[0][0]

                # adjust based on feedback
                if song_id in user_feedback:
                    if user_feedback[song_id]:
                        similarity = min(1.0, similarity * 1.2)  # boost liked songs
                    else:
                        similarity = max(
                            0.0, similarity * 0.5
                        )  # penalize disliked songs

                similarities.append((song_id, similarity))
            except ValueError as e:
                logger.warning(f"Error calculating similarity for song {song_id}: {e}")
                continue

        if not similarities:
            logger.warning("No similar songs found based on lyrics")
            return []

        # sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        similarities = similarities[:limit]

        # get song details
        song_ids = [song_id for song_id, _ in similarities]
        song_details = await get_song_details(song_ids)

        # add similarity scores
        similarity_dict = dict(similarities)
        for song in song_details:
            song_id = song["id"]
            song["lyrics_similarity"] = similarity_dict.get(song_id, 0)
            if song["id"] in user_feedback:
                song["user_feedback"] = user_feedback[song["id"]]

        return song_details

    except Exception as e:
        logger.error(f"Error generating lyrical recommendations: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return []


@router.get("/lyrical")
async def get_lyrical_recs_route(
    user_id: int = Depends(get_current_user_id), limit: int = 20
):
    """get recommendations based on lyrics similarity"""
    try:
        recommendations = await get_lyrical_recommendations(user_id, limit)
        return {"recommendations": recommendations}
    except Exception as e:
        logger.error(f"Error getting lyrical recommendations: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail="Error generating lyrical recommendations"
        )


async def get_user_feedback(user_id: int) -> Dict[str, bool]:
    """get user feedback for songs"""
    try:
        query = """
            SELECT song_id, liked 
            FROM recommendation_feedback
            WHERE user_id = :user_id
            ORDER BY feedback_at DESC
        """
        rows = await database.fetch_all(query, {"user_id": user_id})

        # use the most recent feedback if there are duplicates
        feedback = {}
        for row in rows:
            song_id = row["song_id"]
            if song_id not in feedback:
                feedback[song_id] = row["liked"]

        return feedback
    except Exception as e:
        logger.error(f"error retrieving user feedback: {e}")
        return {}


async def get_similar_songs_with_knn(
    user_profile_vector: np.ndarray,
    exclude_songs: List[str],
    n_neighbors: int = KNN_NEIGHBORS,
    user_feedback: Optional[Dict[str, bool]] = None,
) -> List[Tuple[str, float]]:
    """find similar songs using k-nearest neighbors algorithm"""
    try:
        query = """
            SELECT song_id, feature_vector
            FROM song_audio_features
        """

        params = {}
        if exclude_songs:
            query += " WHERE song_id != ALL(:exclude_songs)"
            params["exclude_songs"] = exclude_songs

        rows = await database.fetch_all(query, params)

        if not rows:
            return []

        # extract feature vectors and song ids
        song_ids = []
        feature_vectors = []

        for row in rows:
            song_ids.append(row["song_id"])
            feature_vectors.append(np.array(row["feature_vector"]))

        if not feature_vectors:
            return []

        # convert to numpy array for KNN
        feature_matrix = np.vstack(feature_vectors)

        # initialize and fit KNN model
        knn = NearestNeighbors(
            n_neighbors=min(n_neighbors, len(feature_vectors)), metric="cosine"
        )
        knn.fit(feature_matrix)

        # find k nearest neighbors
        distances, indices = knn.kneighbors(user_profile_vector.reshape(1, -1))

        # convert distances to similarities (1 - distance)
        similarities = 1 - distances.flatten()

        # get results with similarity scores
        results = []
        for idx, sim in zip(indices.flatten(), similarities):
            song_id = song_ids[idx]

            # apply feedback adjustments if available
            adjusted_sim = sim
            if user_feedback and song_id in user_feedback:
                # boost similarity for liked songs, reduce for disliked
                feedback_modifier = 0.2 if user_feedback[song_id] else -0.3
                adjusted_sim = max(0, min(1, sim + feedback_modifier))

            results.append((song_id, adjusted_sim))

        return results
    except Exception as e:
        logger.error(f"error finding similar songs with KNN: {e}")
        return []


async def get_user_feature_vectors_with_feedback(
    user_id: int, use_clustering: bool = True
) -> Tuple[List[np.ndarray], Dict[str, bool]]:
    """Get user feature vectors (clustered or average) and feedback data"""
    # get user feedback
    user_feedback = await get_user_feedback(user_id)

    if use_clustering:
        # get clustered feature vectors
        feature_vectors = await get_user_feature_clusters(user_id)
    else:
        # get average feature vector
        avg_vector = await get_user_average_feature_vector(user_id)
        feature_vectors = [avg_vector] if avg_vector is not None else []

    return feature_vectors, user_feedback


@router.get("/analytics")
async def get_recommendation_analytics(user_id: int = Depends(get_current_user_id)):
    """Get analytics data for recommendations"""
    try:
        # get the user's taste profile (average audio features)
        taste_profile = await get_user_audio_profile(user_id)

        # get the user's liked songs
        liked_songs = await get_user_liked_songs(user_id)
        total_liked_songs = len(liked_songs)

        # get top genres
        top_genres = await database.fetch_all(
            """
            SELECT g.name, COUNT(*) as count
            FROM user_liked_songs uls
            JOIN song_artists sa ON uls.song_id = sa.song_id
            JOIN artist_genres ag ON sa.artist_id = ag.artist_id
            JOIN genres g ON ag.genre_id = g.id
            WHERE uls.user_id = :user_id
            GROUP BY g.name
            ORDER BY count DESC
            LIMIT 10
            """,
            {"user_id": user_id},
        )

        top_genres_list = [
            {"name": genre["name"], "count": genre["count"]} for genre in top_genres
        ]

        # get user clusters - first try to get from cache
        user_clusters = await get_cached_cluster_data(user_id)
        clusters_data = None
        enhanced_clusters = None

        # if no cached data or it's expired, generate clusters
        if not user_clusters and total_liked_songs >= 5:
            try:
                # generate clusters if we have enough data
                clusters_data_raw = await get_user_clusters_with_details(user_id)

                # convert numpy values to Python standard types
                user_clusters = json.loads(
                    json.dumps(clusters_data_raw, default=make_json_serializable)
                )

                # cache the data for future use
                await save_cluster_data(user_id, user_clusters)

            except Exception as cluster_err:
                logger.error(f"Error generating cluster data: {cluster_err}")
                logger.error(traceback.format_exc())

        # process the cluster data if we have it
        if user_clusters:
            # create simplified clusters for visualization
            if "clusters" in user_clusters:
                # the enhanced_clusters will be the same as user_clusters for our purposes
                # since it already contains all the cluster details we need
                enhanced_clusters = {
                    "num_clusters": user_clusters["num_clusters"],
                    "clusters": user_clusters["clusters"],
                    "kmeans_info": user_clusters.get("kmeans_info", {}),
                    "song_count": user_clusters.get("song_count", 0),
                }

                # prepare simplified cluster representation for frontend
                song_points = []
                centers = []

                # process clusters to get points and centers
                for i, cluster in enumerate(user_clusters["clusters"]):
                    # skip empty clusters
                    if cluster.get("size", 0) == 0:
                        continue

                    # add points from this cluster
                    for point in cluster.get("points", []):
                        song_point = {
                            "x": point.get("x", 0),
                            "y": point.get("y", 0),
                            "cluster": i,
                            "song_id": point.get("song_id"),
                        }

                        # add title and artist data for tooltips
                        if "title" in point:
                            song_point["title"] = point["title"]
                        if "artist" in point:
                            song_point["artist"] = point["artist"]

                        song_points.append(song_point)

                    # add center for this cluster
                    if "center" in cluster:
                        centers.append(cluster["center"])

                # create the clusters data structure
                clusters_data = {
                    "num_clusters": len(
                        [c for c in user_clusters["clusters"] if c.get("size", 0) > 0]
                    ),
                    "song_points": song_points,
                    "centers": centers,
                }

                # filter out empty clusters from enhanced_clusters
                if enhanced_clusters and "clusters" in enhanced_clusters:
                    # keep only clusters with size > 0
                    enhanced_clusters["clusters"] = [
                        cluster
                        for cluster in enhanced_clusters["clusters"]
                        if cluster.get("size", 0) > 0
                    ]

                    # update the cluster IDs to be sequential (0, 1, 2...)
                    for i, cluster in enumerate(enhanced_clusters["clusters"]):
                        cluster["id"] = i

                    # update num_clusters to match the actual number of clusters after filtering
                    enhanced_clusters["num_clusters"] = len(
                        enhanced_clusters["clusters"]
                    )

        # get recommendation feedback stats
        feedback_stats = await database.fetch_one(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN liked = TRUE THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN liked = FALSE THEN 1 ELSE 0 END) as negative
            FROM recommendation_feedback
            WHERE user_id = :user_id
            """,
            {"user_id": user_id},
        )

        recommendation_success_rate = None
        positive_feedback = None
        negative_feedback = None

        if feedback_stats and feedback_stats["total"] > 0:
            total = feedback_stats["total"]
            positive = feedback_stats["positive"] or 0
            negative = feedback_stats["negative"] or 0

            recommendation_success_rate = positive / total if total > 0 else 0
            positive_feedback = positive
            negative_feedback = negative

        # prepare the response
        response = {
            "taste_profile": taste_profile or {},
            "total_liked_songs": total_liked_songs,
            "top_genres": top_genres_list,
            "clusters": clusters_data,
            "enhanced_clusters": enhanced_clusters,
            "recommendation_success_rate": recommendation_success_rate,
            "positive_feedback": positive_feedback,
            "negative_feedback": negative_feedback,
            "feedback_stats": (
                {
                    "total": feedback_stats["total"] if feedback_stats else 0,
                    "positive": (
                        feedback_stats["positive"] or 0 if feedback_stats else 0
                    ),
                    "negative": (
                        feedback_stats["negative"] or 0 if feedback_stats else 0
                    ),
                }
                if feedback_stats
                else None
            ),
        }

        return response
    except Exception as e:
        logger.error(f"Error generating recommendation analytics: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail="Error generating recommendation analytics"
        )


# helper function to get cached cluster data
async def get_cached_cluster_data(user_id: int) -> Optional[Dict[str, Any]]:
    """Get cached cluster data for a user if it exists and is still valid"""
    try:
        # get the cached data
        row = await database.fetch_one(
            """
            SELECT cluster_data, timestamp
            FROM user_cluster_cache
            WHERE user_id = :user_id
            """,
            {"user_id": user_id},
        )

        if not row:
            return None

        # check if the cache is still valid
        current_time = int(time.time())
        cache_time = row["timestamp"]

        if current_time - cache_time > CLUSTER_CACHE_TTL:
            logger.info(f"Cluster cache for user {user_id} is expired")
            return None

        # return the cached data
        return json.loads(row["cluster_data"])

    except Exception as e:
        logger.error(f"Error retrieving cached cluster data: {e}")
        return None


# helper function to save cluster data to cache
async def save_cluster_data(user_id: int, cluster_data: Dict[str, Any]):
    """save computed cluster data to cache"""
    try:
        current_time = int(time.time())

        # convert numpy values to standard Python types
        serializable_data = json.loads(
            json.dumps(cluster_data, default=make_json_serializable)
        )

        await database.execute(
            """
            INSERT INTO user_cluster_cache (user_id, cluster_data, timestamp)
            VALUES (:user_id, :cluster_data, :timestamp)
            ON CONFLICT (user_id) 
            DO UPDATE SET cluster_data = :cluster_data, timestamp = :timestamp
            """,
            {
                "user_id": user_id,
                "cluster_data": json.dumps(serializable_data),
                "timestamp": current_time,
            },
        )
    except Exception as e:
        logger.error(f"Error saving cluster data to cache: {e}")


# helper function to identify genres for a cluster
async def get_cluster_genres(song_ids: List[str], limit: int = 3) -> List[str]:
    try:
        if not song_ids:
            return []

        query = """
        WITH song_genres AS (
            SELECT s.id as song_id, g.name as genre_name
            FROM songs s
            JOIN song_artists sa ON s.id = sa.song_id
            JOIN artist_genres ag ON sa.artist_id = ag.artist_id
            JOIN genres g ON ag.genre_id = g.id
            WHERE s.id = ANY(:song_ids)
        )
        SELECT genre_name, COUNT(*) as count
        FROM song_genres
        GROUP BY genre_name
        ORDER BY count DESC
        LIMIT :limit
        """

        rows = await database.fetch_all(query, {"song_ids": song_ids, "limit": limit})
        return [row["genre_name"] for row in rows]
    except Exception as e:
        logger.error(f"Error getting cluster genres: {e}")
        return []


# helper function to get songs in a cluster
async def get_cluster_songs(
    song_ids: List[str], limit: int = 5
) -> List[Dict[str, Any]]:
    try:
        if not song_ids:
            return []

        query = """
        SELECT 
            s.id, 
            s.name, 
            string_agg(DISTINCT a.name, ', ') as artist_names,
            al.name as album_name,
            al.image_url as album_image
        FROM songs s
        JOIN song_artists sa ON s.id = sa.song_id
        JOIN artists a ON sa.artist_id = a.id
        JOIN albums al ON s.album_id = al.id
        WHERE s.id = ANY(:song_ids)
        GROUP BY s.id, s.name, al.name, al.image_url
        LIMIT :limit
        """

        rows = await database.fetch_all(query, {"song_ids": song_ids, "limit": limit})
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting cluster songs: {e}")
        return []


# enhanced function that returns detailed cluster information
async def get_user_clusters_with_details(
    user_id: int, k: int = CLUSTER_K, force_recalculate: bool = False
) -> Dict[str, Any]:
    """Get detailed cluster information including names, songs, and genre information"""

    # try to get cached data first unless force_recalculate is True
    if not force_recalculate:
        cached_data = await get_cached_cluster_data(user_id)
        if cached_data:
            return cached_data

    # get the user's liked songs
    liked_songs = await get_user_liked_songs(user_id)

    if not liked_songs:
        return {
            "num_clusters": 0,
            "clusters": [],
            "kmeans_info": {"inertia": 0, "iterations": 0},
            "song_count": 0,
        }

    # get audio features for all liked songs
    features = await get_song_audio_features(liked_songs)

    # map song_ids to their indices in the vectors list for later reference
    song_id_to_index = {}
    vectors = []
    song_ids = []

    for i, (song_id, feature) in enumerate(features.items()):
        if "feature_vector" in feature:
            song_id_to_index[song_id] = i
            vectors.append(np.array(feature["feature_vector"]))
            song_ids.append(song_id)

    if not vectors:
        return {
            "num_clusters": 0,
            "clusters": [],
            "kmeans_info": {"inertia": 0, "iterations": 0},
            "song_count": 0,
        }

    # dynamically determine the maximum number of clusters based on dataset size
    song_count = len(vectors)

    # calculate overall dataset variance to determine if songs are very similar
    vectors_array = np.array(vectors)
    overall_variance = np.var(vectors_array, axis=0).sum()

    # define variance thresholds
    very_high_variance = 2000.0
    high_variance = 1000.0
    low_variance = 0.5

    # define minimum songs per cluster to prevent tiny clusters
    min_songs_per_cluster = 15

    # adjust max_k based on both dataset size and variance
    # for very small datasets (< 10 songs), use 1-3 clusters
    if song_count < 10:
        max_k = min(3, song_count // 2)
    # for small datasets (10-30 songs), use 3-5 clusters
    elif song_count < 30:
        max_k = min(5, song_count // 4)
    # for medium datasets (30-100 songs), use 4-8 clusters
    elif song_count < 100:
        max_k = min(8, song_count // 12)
    # for large datasets (100-500 songs), use 6-12 clusters
    elif song_count < 500:
        max_k = min(12, song_count // 40)
    # for very large datasets (500+ songs), use 10-18 clusters
    else:
        max_k = min(18, song_count // 80)

    # special case for very high variance datasets - increase max_k significantly
    if overall_variance > very_high_variance:
        # for extremely high variance datasets (like yours with ~4000), allow more clusters
        max_k = min(25, max(max_k, song_count // 300))
        logger.info(f"Very high variance dataset detected, increasing max_k to {max_k}")
    # special case for high variance datasets - increase max_k moderately
    elif overall_variance > high_variance:
        max_k = min(20, max(max_k, song_count // 400))
        logger.info(f"High variance dataset detected, increasing max_k to {max_k}")
    # reduce max_k for low variance datasets
    elif overall_variance < low_variance:
        max_k = max(2, max_k // 2)
        logger.info(f"Low variance dataset detected, reducing max_k to {max_k}")

    # add a song-count based limit to ensure each cluster has enough songs
    # this prevents having too many clusters with too few songs in each
    max_k_by_song_count = song_count // min_songs_per_cluster
    if max_k_by_song_count < max_k:
        logger.info(
            f"Limiting max_k from {max_k} to {max_k_by_song_count} to ensure at least {min_songs_per_cluster} songs per cluster"
        )
        max_k = max(2, max_k_by_song_count)

    # ensure max_k is at least 2 to encourage multiple clusters when possible
    max_k = max(2, max_k)

    # if we have more than a few songs, determine optimal k using the elbow method
    if song_count >= 5 and max_k > 1:
        distortions = []
        K = range(1, max_k + 1)
        kmeans_models = []  # store the models for analysis

        for k_val in K:
            kmeans_model = KMeans(n_clusters=k_val, random_state=42, n_init=10)
            kmeans_model.fit(vectors_array)
            kmeans_models.append(kmeans_model)
            distortions.append(
                sum(
                    np.min(
                        cdist(
                            vectors_array,
                            kmeans_model.cluster_centers_,
                            "euclidean",
                        ),
                        axis=1,
                    )
                )
                / vectors_array.shape[0]
            )

        # calculate improvement percentages
        improvements = []
        for i in range(len(distortions) - 1):
            if distortions[i] > 0:
                imp = (distortions[i] - distortions[i + 1]) / distortions[i]
                improvements.append(imp)
            else:
                improvements.append(0)

        # dynamically adjust improvement threshold based on dataset variance
        # for very high variance datasets, use a much lower threshold to allow more clusters
        if overall_variance > very_high_variance:
            improvement_threshold = max(
                0.01, min(0.03, 0.03 - (overall_variance - very_high_variance) / 100000)
            )
        # for high variance datasets, use a lower threshold
        elif overall_variance > high_variance:
            improvement_threshold = max(
                0.02, min(0.04, 0.04 - (overall_variance - high_variance) / 20000)
            )
        # for normal to low variance datasets, use standard thresholds
        else:
            improvement_threshold = min(
                0.15, max(0.03, 0.05 + (low_variance - overall_variance) * 0.1)
            )

        logger.info(
            f"Using improvement threshold of {improvement_threshold:.4f} for elbow method"
        )

        # find optimal k - where adding more clusters gives less than the calculated threshold improvement
        optimal_k = 1
        for i, imp in enumerate(improvements):
            if imp < improvement_threshold:
                optimal_k = i + 1
                break
            optimal_k = i + 2  # if all improvements are significant

        k = optimal_k
        logger.info(
            f"Elbow method selected {k} clusters with variance {overall_variance:.4f}"
        )

        # check if the chosen k would yield balanced clusters
        # use the kmeans model we've already trained with the chosen k
        k_idx = k - 1  # convert to 0-based index
        if k_idx < len(kmeans_models):
            # get the cluster sizes to check for small clusters
            labels = kmeans_models[k_idx].labels_
            cluster_sizes = np.bincount(labels)
            smallest_cluster = np.min(cluster_sizes)

            if smallest_cluster < min_songs_per_cluster:
                logger.info(
                    f"Smallest cluster has only {smallest_cluster} songs, which is less than the minimum {min_songs_per_cluster}"
                )

                # try to find a k that provides better balanced clusters
                for test_k in range(k - 1, 1, -1):
                    test_idx = test_k - 1
                    test_labels = kmeans_models[test_idx].labels_
                    test_sizes = np.bincount(test_labels)
                    test_smallest = np.min(test_sizes)

                    if test_smallest >= min_songs_per_cluster:
                        k = test_k
                        logger.info(
                            f"Reduced k to {k} to ensure all clusters have at least {min_songs_per_cluster} songs"
                        )
                        break
    else:
        k = max(2, min(max_k, 3))  # default to at least 2 clusters when possible

    # ensure k is reasonable but bias toward more clusters for high variance datasets
    k = max(2, min(max_k, k))

    # for very high variance datasets, ensure minimum number of clusters is higher
    if overall_variance > very_high_variance:
        k = max(6, k)
    # for high variance datasets, ensure minimum number of clusters
    elif song_count >= 30 and overall_variance > high_variance:
        k = max(4, k)
    # for medium to large datasets with normal variance, ensure 3 clusters minimum
    elif song_count >= 30:
        k = max(3, k)

    logger.info(f"Final cluster count for user {user_id}: {k} clusters")

    # perform clustering with selected k
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(vectors_array)

    # check for small clusters and potentially merge them
    cluster_sizes = np.bincount(labels)

    # log cluster sizes
    for i, size in enumerate(cluster_sizes):
        logger.info(f"Cluster {i} size: {size} songs")

    # if we have any clusters smaller than the minimum threshold and more than 2 clusters total,
    # merge small clusters into their nearest neighbors
    if np.min(cluster_sizes) < min_songs_per_cluster and k > 2:
        logger.info(f"found small clusters, attempting to merge them with larger ones")

        # get the cluster centers
        centers = kmeans.cluster_centers_

        # create a new labels array that we'll modify
        new_labels = labels.copy()

        # for each small cluster
        for cluster_id in range(k):
            if cluster_sizes[cluster_id] < min_songs_per_cluster:
                # find the nearest cluster center
                center_distances = np.linalg.norm(
                    centers - centers[cluster_id].reshape(1, -1), axis=1
                )
                center_distances[cluster_id] = np.inf  # don't merge with self

                nearest_cluster = np.argmin(center_distances)
                logger.info(
                    f"Merging cluster {cluster_id} (size {cluster_sizes[cluster_id]}) into cluster {nearest_cluster} (size {cluster_sizes[nearest_cluster]})"
                )

                # reassign all songs from the small cluster to the nearest cluster
                new_labels[labels == cluster_id] = nearest_cluster

        # update labels with the merged clusters
        labels = new_labels

        # recalculate cluster sizes after merging
        cluster_sizes = np.bincount(labels)
        effective_k = len(cluster_sizes)

        logger.info(
            f"After merging small clusters, effective number of clusters: {effective_k}"
        )
        for i, size in enumerate(cluster_sizes):
            if size > 0:  # only log non-empty clusters
                logger.info(f"Cluster {i} size after merging: {size} songs")

    # get the cluster centers for the final clusters
    centers = kmeans.cluster_centers_

    # create a reduced-dimension representation for visualization (2d)
    if len(vectors) >= 3:
        tsne = TSNE(
            n_components=2, random_state=42, perplexity=min(30, len(vectors) - 1)
        )
        coords_2d = tsne.fit_transform(vectors_array)
    else:
        # for very small datasets, use pca instead
        pca = PCA(n_components=2)
        coords_2d = pca.fit_transform(vectors_array)

    # get song details for all cluster songs
    song_details = {}
    try:
        query = """
        SELECT 
            s.id, 
            s.name, 
            string_agg(DISTINCT a.name, ', ') as artist_names
        FROM songs s
        JOIN song_artists sa ON s.id = sa.song_id
        JOIN artists a ON sa.artist_id = a.id
        WHERE s.id = ANY(:song_ids)
        GROUP BY s.id, s.name
        """
        rows = await database.fetch_all(query, {"song_ids": song_ids})
        for row in rows:
            song_details[row["id"]] = {
                "name": row["name"],
                "artist_names": row["artist_names"],
            }
    except Exception as e:
        logger.error(f"Error getting song details: {e}")

    # group songs by cluster
    clusters = []
    for i in range(k):
        cluster_indices = np.where(labels == i)[0]
        cluster_song_ids = [song_ids[idx] for idx in cluster_indices]

        # get genres and representative songs for this cluster
        cluster_genres = await get_cluster_genres(cluster_song_ids)
        cluster_songs = await get_cluster_songs(cluster_song_ids)

        # calculate the audio profile for this cluster
        cluster_features = {}
        if cluster_indices.size > 0:
            cluster_vectors = [vectors[idx] for idx in cluster_indices]
            # get features that we can interpret (from the first vector's structure)
            feature_names = [
                "danceability",
                "energy",
                "valence",
                "acousticness",
                "instrumentalness",
                "speechiness",
                "liveness",
            ]

            # calculate avg feature values for the cluster
            feature_indices = {}
            for j, name in enumerate(feature_names):
                feature_indices[name] = j

            # create audio profile for this cluster
            audio_profile = {}

            # define the standard audio features we want to include
            audio_features = [
                "danceability",
                "energy",
                "valence",
                "acousticness",
                "instrumentalness",
                "speechiness",
                "liveness",
            ]

            # get the average values directly from the database for each cluster song
            try:
                query = """
                SELECT 
                    AVG(danceability) as danceability,
                    AVG(energy) as energy,
                    AVG(valence) as valence,
                    AVG(acousticness) as acousticness,
                    AVG(instrumentalness) as instrumentalness,
                    AVG(speechiness) as speechiness,
                    AVG(liveness) as liveness
                FROM song_audio_features
                WHERE song_id = ANY(:song_ids)
                """

                # fetch the average values for this cluster
                row = await database.fetch_one(query, {"song_ids": cluster_song_ids})

                if row:
                    # create the audio profile from the database averages
                    for feature in audio_features:
                        # get value from database - these are already in 0-1 range
                        value = row[feature] if row[feature] is not None else 0.0
                        audio_profile[feature] = value

                    # debug logging
                    logger.info(f"Cluster {i} audio profile: {feature} value = {value}")

            except Exception as e:
                logger.error(f"Error calculating audio profile for cluster {i}: {e}")
                # fallback to empty profile if there's an error
                audio_profile = {feature: 0.0 for feature in audio_features}
                logger.error(traceback.format_exc())

        # generate a cluster name based on audio profile and genres
        cluster_name = ""
        if cluster_genres:
            # use the top genre as the base
            cluster_name = cluster_genres[0] + " "

            # add audio characteristic descriptors
            if audio_profile.get("energy", 0) > 0.7:
                cluster_name += "energetic"
            elif audio_profile.get("energy", 0) < 0.4:
                cluster_name += "chill"
            elif audio_profile.get("valence", 0) > 0.6:
                cluster_name += "upbeat"
            elif audio_profile.get("valence", 0) < 0.4:
                cluster_name += "melancholic"
            elif audio_profile.get("acousticness", 0) > 0.6:
                cluster_name += "acoustic"
            elif audio_profile.get("instrumentalness", 0) > 0.5:
                cluster_name += "instrumental"
            else:
                cluster_name += "music"

        # create points for visualization with simplified hover info
        points = []
        for idx in cluster_indices:
            song_id = song_ids[idx]
            # get song details for hover info (title and artist only)
            song_info = song_details.get(
                song_id, {"name": "Unknown", "artist_names": "Unknown"}
            )

            # create point with simplified hover info
            points.append(
                {
                    "x": float(coords_2d[idx][0]),
                    "y": float(coords_2d[idx][1]),
                    "song_id": song_id,
                    "title": song_info["name"],
                    "artist": song_info["artist_names"],
                }
            )

        clusters.append(
            {
                "id": i,
                "name": cluster_name,
                "size": len(cluster_song_ids),
                "genres": cluster_genres,
                "audio_profile": sanitize_audio_profile(audio_profile),
                "songs": cluster_songs,
                "points": points,
                "center": {
                    "x": float(np.mean([p["x"] for p in points]) if points else 0),
                    "y": float(np.mean([p["y"] for p in points]) if points else 0),
                },
                "centroid": (
                    kmeans.cluster_centers_[i].tolist()
                    if i < len(kmeans.cluster_centers_)
                    else []
                ),
            }
        )

    # create results dictionary
    results = {
        "num_clusters": k,
        "clusters": clusters,
        "kmeans_info": {
            "inertia": float(kmeans.inertia_),
            "iterations": int(kmeans.n_iter_),
        },
        "song_count": len(vectors),
    }

    # cache the results
    await save_cluster_data(user_id, results)

    return results


async def get_similar_recommendations(
    user_id: int, limit: int = 20
) -> List[Dict[str, Any]]:
    """get recommendations based on similar audio features to liked songs"""
    try:
        # get songs the user has already liked
        user_liked_songs = await get_user_liked_songs(user_id)
        if not user_liked_songs:
            return []

        # get user feedback for personalization
        user_feedback = await get_user_feedback(user_id)

        # build exclusion list: user's liked songs + explicitly disliked songs
        exclude_songs = user_liked_songs.copy()
        for song_id, liked in user_feedback.items():
            if not liked:  # if the song was disliked
                exclude_songs.append(song_id)

        # get user's audio profile
        user_audio_profile = await get_user_audio_profile(user_id)
        user_average_vector = await get_user_average_feature_vector(user_id)
        user_lyrics_embedding = await get_user_average_lyrics_embedding(user_id)

        recommendations = []
        if user_average_vector is not None:
            # get similar songs using KNN first
            knn_results = await get_similar_songs_with_knn(
                user_average_vector,
                exclude_songs,
                n_neighbors=KNN_NEIGHBORS_SIMILAR,
                user_feedback=user_feedback,
            )

            # if KNN worked, use those results
            if knn_results:
                song_ids = [sid for sid, _ in knn_results[:limit]]
                song_details = await get_song_details(song_ids)

                # attach similarity scores to song details
                for i, song in enumerate(song_details):
                    song_id = song["id"]
                    # find the similarity score for this song
                    for sid, score in knn_results:
                        if sid == song_id:
                            song["similarity_score"] = score
                            break

                recommendations = song_details
            else:
                # fallback to traditional similarity search
                similar_songs = await find_similar_songs(
                    user_average_vector,
                    user_audio_profile,
                    exclude_songs,
                    user_lyrics_embedding,
                    limit=limit,
                )

                song_ids = [sid for sid, _ in similar_songs]
                song_details = await get_song_details(song_ids)

                # attach similarity scores to song details
                for i, song in enumerate(song_details):
                    song_id = song["id"]
                    # find the similarity score for this song
                    for sid, score in similar_songs:
                        if sid == song_id:
                            song["similarity_score"] = score
                            break

                recommendations = song_details

        # add feedback status if available
        for song in recommendations:
            if song["id"] in user_feedback:
                song["user_feedback"] = user_feedback[song["id"]]

        return recommendations
    except Exception as e:
        logger.error(f"Error getting similar recommendations: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return []


@router.get("/analytics/debug")
async def debug_recommendation_analytics(user_id: int = Depends(get_current_user_id)):
    """Debug endpoint for recommendation analytics"""
    try:
        # get cached cluster data if available
        cached_data = await get_cached_cluster_data(user_id)

        # if no cached data, generate new cluster data
        if not cached_data:
            clusters_data = await get_user_clusters_with_details(user_id)
            # convert to json-serializable format
            clusters_data = json.loads(
                json.dumps(clusters_data, default=make_json_serializable)
            )
        else:
            clusters_data = cached_data

        # extract audio profiles for easy inspection
        audio_profiles = []
        if clusters_data and "clusters" in clusters_data:
            for i, cluster in enumerate(clusters_data["clusters"]):
                if "audio_profile" in cluster:
                    audio_profiles.append(
                        {
                            "cluster_id": i,
                            "cluster_name": cluster.get("name", f"Cluster {i}"),
                            "audio_profile": cluster["audio_profile"],
                            "size": cluster.get("size", 0),
                        }
                    )

        return {"raw_clusters": clusters_data, "audio_profiles": audio_profiles}
    except Exception as e:
        logger.error(f"Error in debug analytics endpoint: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# helper function to sanitize audio profile values
def sanitize_audio_profile(profile: Dict[str, Any]) -> Dict[str, float]:
    """Ensure all audio profile values are between 0 and 1"""
    sanitized = {}
    if not profile:
        return sanitized

    for key, value in profile.items():
        try:
            # convert to float first
            float_val = float(value)

            # simply clamp to 0-1 range as these values should already be normalized
            sanitized[key] = max(0.0, min(1.0, float_val))
        except (ValueError, TypeError):
            # skip non-numeric values
            continue

    return sanitized
