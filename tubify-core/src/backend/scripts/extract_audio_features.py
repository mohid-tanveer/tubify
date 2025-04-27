#!/usr/bin/env python3

import os
import json
import numpy as np
import librosa
import asyncio
import concurrent.futures
import threading
import time
from databases import Database
from dotenv import load_dotenv
import pickle
import logging
import psutil
import warnings

# set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("audio_feature_extraction")

# ignore librosa warnings
warnings.filterwarnings("ignore", category=UserWarning, module="librosa")

# load environment variables
load_dotenv()

# directory containing audio files
SONGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "songs")

# file to store processed song ids
PROCESSED_SONGS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "processed_song_ids.pkl"
)

# hardware acceleration settings
# determine optimal number of workers based on CPU count
CPU_COUNT = psutil.cpu_count(logical=False) or 1  # physical cores, fallback to 1
MAX_WORKERS = 12  # leave one core free for system processes
BATCH_SIZE = 10  # number of songs to process in each batch

# threading lock for safe updates to shared data
pickle_lock = threading.Lock()

# check if GPU acceleration via cupy is available
try:
    import cupy as cp

    HAS_GPU = True
    logger.info("GPU acceleration enabled via cupy")
except ImportError:
    HAS_GPU = False
    logger.info("GPU acceleration not available, using CPU only")


async def get_all_song_ids(database):
    """get all song ids from the database"""
    try:
        rows = await database.fetch_all("SELECT id FROM songs")
        return [row["id"] for row in rows]
    except Exception as e:
        logger.error(f"error fetching song ids: {e}")
        return []


def load_processed_song_ids():
    """load the list of already processed song ids"""
    if os.path.exists(PROCESSED_SONGS_FILE):
        try:
            with pickle_lock:
                with open(PROCESSED_SONGS_FILE, "rb") as f:
                    return pickle.load(f)
        except Exception as e:
            logger.error(f"error loading processed song ids: {e}")
    return set()


def save_processed_song_ids(processed_song_ids):
    """save the updated list of processed song ids"""
    try:
        with pickle_lock:
            temp_file = f"{PROCESSED_SONGS_FILE}.tmp"
            with open(temp_file, "wb") as f:
                pickle.dump(processed_song_ids, f)
            os.replace(temp_file, PROCESSED_SONGS_FILE)
    except Exception as e:
        logger.error(f"error saving processed song ids: {e}")


def extract_audio_features(file_path):
    """extract audio features from a song file using librosa with GPU acceleration if available"""
    try:
        # load audio at native sampling rate, convert to mono
        y, sr = librosa.load(file_path, sr=None, mono=True)

        # use GPU if available for computationally intensive operations
        if HAS_GPU:
            # transfer audio data to GPU
            y_gpu = cp.asarray(y)

            # FFT on GPU (for chroma and spectral features)
            D = cp.abs(cp.fft.rfft(y_gpu))

            # convert back to numpy for librosa compatibility
            D_np = cp.asnumpy(D)
            del D  # free GPU memory

            # release GPU memory
            del y_gpu

            # continue with CPU operations using D_np where needed
        else:
            D_np = None  # not used in CPU path

        # extract features
        # mfcc - capture the spectral envelope of the audio (13 coefficients)
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)

        # chroma STFT maps energy to 12 pitch classes (C to B)
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)

        # spectral contrast measures the difference between peaks and valleys in the spectrum
        spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)

        # harmonic/percussive source separation
        y_harmonic, y_percussive = librosa.effects.hpss(y)
        eps = 1e-10  # avoid division by zero

        # tempo
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        try:
            from librosa.feature.rhythm import tempo as compute_tempo

            tempo_vals = compute_tempo(onset_envelope=onset_env, sr=sr)
        except ImportError:
            tempo_vals = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)
        tempo = float(tempo_vals[0])  # tempo in BPM

        # additional features (optimize by reusing calculations)

        # spectral centroid in Hz
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]

        # acousticness - ratio of non-percussive (harmonic) energy vs total energy
        norm_centroid = np.mean(centroid) / (np.percentile(centroid, 95) + eps)
        harmonic_energy = np.mean(librosa.feature.rms(y=y_harmonic))
        percussive_energy = np.mean(librosa.feature.rms(y=y_percussive))
        hnr = harmonic_energy / (harmonic_energy + percussive_energy + eps)
        acoustic_component = 1.0 - norm_centroid
        # combine normalized spectral centroid (lower = more acoustic) and harmonic-to-noise ratio
        acousticness = 0.5 * acoustic_component + 0.5 * hnr
        acousticness = np.clip(acousticness, 0.0, 1.0)

        # energy - based on integrated loudness
        # compute integrated loudness via RMS and spectral centroid
        rms = librosa.feature.rms(y=y)[0]
        rms_norm = np.mean(rms) / (np.percentile(rms, 95) + eps)
        centroid_norm = np.mean(centroid) / (np.percentile(centroid, 95) + eps)
        energy = np.clip(0.5 * rms_norm + 0.5 * centroid_norm, 0.0, 1.0)
        loudness = librosa.amplitude_to_db(
            rms, ref=np.max
        ).mean()  # average loudness in dB

        # danceability - based on beat strength and regularity
        # combines beat strength (PLP), tempo, and rhythmic regularity
        pulse = librosa.beat.plp(onset_envelope=onset_env, sr=sr)
        beat_strength = np.mean(pulse)
        _, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
        if len(beat_frames) > 1:
            intervals = np.diff(librosa.frames_to_time(beat_frames, sr=sr))
            beat_reg = 1.0 - (np.std(intervals) / (np.mean(intervals) + eps))
        else:
            beat_reg = 0.0
        # normalize tempo to [0,1] over plausible BPM range
        tempo_norm = np.clip((tempo - 40) / (200 - 40), 0.0, 1.0)
        danceability = np.clip(
            0.3 * (beat_strength / (beat_strength + eps))
            + 0.5 * tempo_norm
            + 0.2 * beat_reg,
            0.0,
            1.0,
        )

        # liveness - based on presence of audience/background noise
        # live recordings often exhibit higher spectral flatness and zero-crossing rate

        # spectral flatness: live recordings often noisier
        flatness = librosa.feature.spectral_flatness(y=y)[0].mean()
        # zero-crossing rate: live tracks often more dynamic
        zcr = librosa.feature.zero_crossing_rate(y=y)[0].mean()
        # combine and clamp
        liveness = np.clip(0.8 * flatness + 0.2 * (zcr * 10), 0, 1)

        # valence - based on spectral qualities that correlate with "happiness"
        # positiveness based on mode (major/minor) and brightness
        # mean chroma vector
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)
        # key estimation
        key = int(np.argmax(chroma_mean))  # 0-11 representing C, C#, D, etc.
        # mode estimation (major vs minor)
        # simplified approach: major tends to have stronger 3rd and 6th degrees
        major_degrees = np.roll(chroma_mean, -key)[[4, 9]]  # major 3rd and 6th
        minor_degrees = np.roll(chroma_mean, -key)[[3, 8]]  # minor 3rd and 6th
        mode = 1 if np.mean(major_degrees) > np.mean(minor_degrees) else 0
        spectral_brightness = np.mean(centroid) / (np.percentile(centroid, 95) + eps)
        spectral_brightness = np.clip(spectral_brightness, 0.0, 1.0)
        valence = 0.5 * float(mode) + 0.5 * spectral_brightness
        valence = np.clip(valence, 0.0, 1.0)

        # speechiness - based on presence of speech-like qualities
        # degree of spoken-word content vs music
        non_silent = librosa.effects.split(y, top_db=35)
        nonsilent_duration = sum([end - start for start, end in non_silent])
        vad_score = nonsilent_duration / len(y)
        non_hnr = percussive_energy / (harmonic_energy + percussive_energy + eps)
        speechiness = 0.5 * vad_score + 0.5 * non_hnr
        speechiness = np.clip(speechiness, 0.0, 1.0)

        # instrumentalness - inverse proxy for vocal presence using mel-spectrogram energy in vocal band
        S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
        mel_freqs = librosa.mel_frequencies(n_mels=128, fmin=0, fmax=sr / 2)
        vocal_idx = np.where((mel_freqs >= 300) & (mel_freqs <= 3000))[0]
        vocal_energy = np.sum(S[vocal_idx, :])
        total_energy_spec = np.sum(S)
        vocal_ratio = vocal_energy / (total_energy_spec + eps)
        instrumentalness = np.clip(1.0 - vocal_ratio, 0.0, 1.0)

        # take mean of features to reduce dimensionality and ensure they're Python lists of float values
        mfcc_mean = [float(x) for x in np.mean(mfcc, axis=1).tolist()]
        chroma_mean = [float(x) for x in chroma_mean.tolist()]
        spectral_contrast_mean = [
            float(x) for x in np.mean(spectral_contrast, axis=1).tolist()
        ]

        # create combined feature vector including all features
        # ensure all values are explicit Python floats
        feature_vector = (
            mfcc_mean
            + chroma_mean
            + spectral_contrast_mean
            + [
                float(2),
                float(acousticness),
                float(danceability),
                float(energy),
                float(loudness),
                float(liveness),
                float(valence),
                float(speechiness),
                float(instrumentalness),
                float(mode),
                float(key),
            ]
        )

        # clear large variables to free memory
        del y, harmonic, pulse, onset_env
        if HAS_GPU:
            cp.get_default_memory_pool().free_all_blocks()

        return {
            "mfcc": mfcc_mean,
            "chroma": chroma_mean,
            "spectral_contrast": spectral_contrast_mean,
            "tempo": float(tempo),
            "acousticness": float(acousticness),
            "danceability": float(danceability),
            "energy": float(energy),
            "loudness": float(loudness),
            "liveness": float(liveness),
            "valence": float(valence),
            "speechiness": float(speechiness),
            "instrumentalness": float(instrumentalness),
            "mode": int(mode),
            "key": int(key),
            "feature_vector": feature_vector,
        }
    except Exception as e:
        logger.error(f"error extracting features from {file_path}: {e}")
        return None


async def store_features_in_db(database, song_id, features):
    """store the extracted audio features in the database"""
    try:
        # convert numpy arrays to lists for json serialization
        mfcc_json = json.dumps(features["mfcc"])
        chroma_json = json.dumps(features["chroma"])
        spectral_contrast_json = json.dumps(features["spectral_contrast"])

        feature_vector = [float(x) for x in features["feature_vector"]]

        # check if entry already exists
        existing = await database.fetch_one(
            "SELECT 1 FROM song_audio_features WHERE song_id = :song_id",
            values={"song_id": song_id},
        )

        if existing:
            # update existing record
            await database.execute(
                """
                UPDATE song_audio_features 
                SET mfcc = :mfcc, chroma = :chroma, spectral_contrast = :spectral_contrast, 
                    tempo = :tempo, acousticness = :acousticness, danceability = :danceability, 
                    energy = :energy, loudness = :loudness, liveness = :liveness, valence = :valence, 
                    speechiness = :speechiness, instrumentalness = :instrumentalness, mode = :mode, 
                    key = :key, feature_vector = :feature_vector, 
                    processed_at = CURRENT_TIMESTAMP
                WHERE song_id = :song_id
                """,
                values={
                    "mfcc": mfcc_json,
                    "chroma": chroma_json,
                    "spectral_contrast": spectral_contrast_json,
                    "tempo": float(features["tempo"]),
                    "acousticness": float(features["acousticness"]),
                    "danceability": float(features["danceability"]),
                    "energy": float(features["energy"]),
                    "loudness": float(features["loudness"]),
                    "liveness": float(features["liveness"]),
                    "valence": float(features["valence"]),
                    "speechiness": float(features["speechiness"]),
                    "instrumentalness": float(features["instrumentalness"]),
                    "mode": int(features["mode"]),
                    "key": int(features["key"]),
                    "feature_vector": feature_vector,
                    "song_id": song_id,
                },
            )
        else:
            # insert new record
            await database.execute(
                """
                INSERT INTO song_audio_features 
                (song_id, mfcc, chroma, spectral_contrast, tempo, acousticness, danceability, energy, loudness, liveness, valence, speechiness, instrumentalness, mode, key, feature_vector) 
                VALUES (:song_id, :mfcc, :chroma, :spectral_contrast, :tempo, :acousticness, :danceability, :energy, :loudness, :liveness, :valence, :speechiness, :instrumentalness, :mode, :key, :feature_vector)
                """,
                values={
                    "song_id": song_id,
                    "mfcc": mfcc_json,
                    "chroma": chroma_json,
                    "spectral_contrast": spectral_contrast_json,
                    "tempo": float(features["tempo"]),
                    "acousticness": float(features["acousticness"]),
                    "danceability": float(features["danceability"]),
                    "energy": float(features["energy"]),
                    "loudness": float(features["loudness"]),
                    "liveness": float(features["liveness"]),
                    "valence": float(features["valence"]),
                    "speechiness": float(features["speechiness"]),
                    "instrumentalness": float(features["instrumentalness"]),
                    "mode": int(features["mode"]),
                    "key": int(features["key"]),
                    "feature_vector": feature_vector,
                },
            )

        return True
    except Exception as e:
        logger.error(f"database error when storing features for song {song_id}: {e}")
        return False


def process_song_sync(song_id, songs_dir):
    """synchronous version of process_song for parallel execution"""
    song_path = os.path.join(songs_dir, f"{song_id}.mp3")

    if not os.path.exists(song_path):
        logger.warning(f"song file not found: {song_path}")
        return song_id, None

    logger.info(f"processing song: {song_id}")
    features = extract_audio_features(song_path)
    return song_id, features


async def process_batch(database, batch_song_ids, processed_song_ids):
    """process a batch of songs in parallel using a thread pool"""
    start_time = time.time()

    # create thread pool for parallel feature extraction
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # submit all tasks to the executor
        future_to_song = {
            executor.submit(process_song_sync, song_id, SONGS_DIR): song_id
            for song_id in batch_song_ids
        }

        # process results as they complete
        batch_processed = 0
        for future in concurrent.futures.as_completed(future_to_song):
            song_id, features = future.result()

            if features:
                # store features in database
                success = await store_features_in_db(database, song_id, features)
                if success:
                    with pickle_lock:
                        processed_song_ids.add(song_id)
                    batch_processed += 1

    batch_time = time.time() - start_time
    songs_per_second = len(batch_song_ids) / batch_time if batch_time > 0 else 0
    logger.info(
        f"Processed batch of {len(batch_song_ids)} songs in {batch_time:.2f}s "
        f"({songs_per_second:.2f} songs/sec). Successfully processed: {batch_processed}"
    )

    return batch_processed


async def main():
    """main function to extract features from songs"""
    start_time = time.time()
    logger.info(
        f"starting audio feature extraction process with {MAX_WORKERS} worker threads"
    )
    if HAS_GPU:
        logger.info("GPU acceleration enabled")

    # system info
    memory = psutil.virtual_memory()
    logger.info(
        f"System info: {CPU_COUNT} CPU cores, {memory.total / (1024**3):.1f}GB RAM "
        f"({memory.percent}% used)"
    )

    # ensure songs directory exists
    os.makedirs(SONGS_DIR, exist_ok=True)

    # initialize database connection
    database = Database(os.getenv("DATABASE_URL"))
    await database.connect()
    logger.info("database connected")

    try:
        # get all song ids from database
        all_song_ids = await get_all_song_ids(database)
        logger.info(f"found {len(all_song_ids)} songs in database")

        # load already processed song ids
        processed_song_ids = load_processed_song_ids()
        logger.info(f"{len(processed_song_ids)} songs already processed")

        # filter out already processed songs
        songs_to_process = [
            song_id for song_id in all_song_ids if song_id not in processed_song_ids
        ]
        total_songs = len(songs_to_process)
        logger.info(f"{total_songs} songs to process")

        if not songs_to_process:
            logger.info("No songs to process. Exiting.")
            return

        # process songs in batches for better memory management and progress tracking
        total_processed = 0
        for i in range(0, total_songs, BATCH_SIZE):
            batch = songs_to_process[i : i + BATCH_SIZE]
            logger.info(
                f"Processing batch {i//BATCH_SIZE + 1}/{(total_songs+BATCH_SIZE-1)//BATCH_SIZE} "
                f"({len(batch)} songs)"
            )

            # process batch
            batch_processed = await process_batch(database, batch, processed_song_ids)
            total_processed += batch_processed

            # save progress after each batch
            save_processed_song_ids(processed_song_ids)

            # progress report
            progress = (i + len(batch)) / total_songs
            elapsed = time.time() - start_time
            songs_per_second = (i + len(batch)) / elapsed if elapsed > 0 else 0
            eta = (
                (total_songs - (i + len(batch))) / songs_per_second
                if songs_per_second > 0
                else 0
            )

            logger.info(
                f"Overall progress: {progress:.1%} ({total_processed}/{total_songs} songs processed successfully)"
            )
            logger.info(f"Elapsed time: {elapsed:.2f}s. ETA: {eta:.2f}s")

            # report memory usage
            memory = psutil.virtual_memory()
            logger.info(
                f"Memory usage: {memory.percent}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)"
            )

            # clear some memory if needed
            if memory.percent > 80:
                import gc

                gc.collect()
                if HAS_GPU:
                    cp.get_default_memory_pool().free_all_blocks()
                logger.info("Forced garbage collection to free memory")

        # save final progress
        save_processed_song_ids(processed_song_ids)

        # final report
        total_time = time.time() - start_time
        logger.info(
            f"Finished processing {total_processed}/{total_songs} songs in {total_time:.2f}s"
        )
        logger.info(
            f"Average processing speed: {total_processed/total_time:.2f} songs/second"
        )

    finally:
        # disconnect from database
        await database.disconnect()
        logger.info("database disconnected")


if __name__ == "__main__":
    asyncio.run(main())
