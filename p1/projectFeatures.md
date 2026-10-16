Some features below probably wont make it to the final product.

1. sort or group videos by publish date, author, and topic
2. optionally extend chats for more information about a video
3. customizable summary preferences
4. store past video summary of playlist
5. support multiple playlists
6. automatic fetch new videos added to playlist and summarize on startup

create a python terminal program that inputs the videoid of a youtube video, calls to get transcript, then calls openai responses api with 5.6 luna high, no tools, to output an academic summary essay/paragraph and outputs to terminal, then quits.

possible apis:
yt-dlp CLI (--flat-playlist --print id)	High	Whole playlist	No API key; extracts video IDs without downloading media. Handles pagination automatically.	Unofficial; occasional incomplete extraction and YouTube blocking. 

GitHub
yt-dlp Python API (extract_flat)	High	Whole playlist	Programmatic extraction with structured results; easy integration with transcription pipelines.	Same extraction limitations as CLI.
Pytubefix Playlist (video_urls)	High	Whole playlist	Simple Python interface returning URLs; supports pagination internally.	Can break when YouTube changes playlist formats.