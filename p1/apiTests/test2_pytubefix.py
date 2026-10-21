from urllib.parse import urlencode

from pytubefix import Playlist


def main():
    """Print video IDs from a public playlist using pytubefix."""
    playlist_id = input("Public YouTube playlist ID: ").strip()
    if not playlist_id:
        raise SystemExit("Playlist ID cannot be blank.")

    playlist_url = f"https://www.youtube.com/playlist?{urlencode({'list': playlist_id})}"
    playlist = Playlist(playlist_url)
    video_ids = [video.video_id for video in playlist.videos if video.video_id]

    if not video_ids:
        raise SystemExit("No video IDs found in the playlist.")

    for video_id in video_ids:
        print(video_id)


if __name__ == "__main__":
    main()
