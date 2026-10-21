from urllib.parse import urlencode

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


def main():
    """Print public video IDs from one user-supplied playlist."""
    playlist_id = input("Public YouTube playlist ID: ").strip()
    if not playlist_id:
        raise SystemExit("Playlist ID cannot be blank.")

    playlist_url = f"https://www.youtube.com/playlist?{urlencode({'list': playlist_id})}"
    options = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }

    try:
        with YoutubeDL(options) as ydl:
            playlist = ydl.extract_info(playlist_url, download=False)
    except DownloadError as error:
        raise SystemExit(f"Unable to fetch the playlist: {error}") from error

    if not playlist:
        raise SystemExit("yt-dlp returned no playlist information.")

    video_ids = [
        entry["id"]
        for entry in playlist.get("entries", [])
        if entry and entry.get("id")
    ]
    if not video_ids:
        raise SystemExit("No video IDs found in the playlist.")

    for video_id in video_ids:
        print(video_id)


if __name__ == "__main__":
    main()
