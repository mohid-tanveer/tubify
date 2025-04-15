#!/usr/bin/env python3
"""
script to rename music files from format '{artist} - {title}_{id}.mp3' to '{id}.mp3'
this preserves just the song ID as the filename and removes unnecessary metadata from filenames
"""

import os
import re
import shutil

# path to songs directory
SONGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "songs")

# pattern to extract song_id from filename
# matches anything that ends with underscore followed by some characters and then extension
SONG_ID_PATTERN = re.compile(r".*_([A-Za-z0-9]+)(\.[a-zA-Z0-9]+)$")


def main():
    """rename all music files in songs directory to just song_id.extension"""

    # check if songs directory exists
    if not os.path.exists(SONGS_DIR):
        print(f"error: songs directory not found at {SONGS_DIR}")
        return

    # get all files in the songs directory
    files = os.listdir(SONGS_DIR)
    print(f"found {len(files)} files in songs directory")

    renamed_count = 0
    skipped_count = 0

    for filename in files:
        # check if file matches our expected pattern
        match = SONG_ID_PATTERN.match(filename)

        if match:
            # extract song_id and extension
            song_id, extension = match.groups()

            # new filename will be just song_id + extension
            new_filename = f"{song_id}{extension}"

            # full paths
            old_path = os.path.join(SONGS_DIR, filename)
            new_path = os.path.join(SONGS_DIR, new_filename)

            # if the destination file already exists, skip
            if os.path.exists(new_path) and new_path != old_path:
                print(
                    f"skipping {filename} - destination file {new_filename} already exists"
                )
                skipped_count += 1
                continue

            # rename file
            try:
                shutil.move(old_path, new_path)
                print(f"renamed: {filename} -> {new_filename}")
                renamed_count += 1
            except Exception as e:
                print(f"error renaming {filename}: {e}")
                skipped_count += 1
        else:
            print(f"skipping {filename} - doesn't match expected pattern")
            skipped_count += 1

    print(
        f"\nrenaming complete: {renamed_count} files renamed, {skipped_count} files skipped"
    )


if __name__ == "__main__":
    main()
