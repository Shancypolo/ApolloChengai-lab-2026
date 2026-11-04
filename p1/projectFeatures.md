Some features below probably wont make it to the final product.

1. sort or group videos by publish date, author, and topic
2. optionally extend chats for more information about a video
3. customizable summary preferences
4. store past video summary of playlist
5. support multiple playlists
6. automatic fetch new videos added to playlist and summarize on startup

## PageOne

- Local Python Flask app with Jinja2 server-rendered pages and locally served CSS. Two local JavaScript helpers provide same-origin HTML swaps and visual scroll stability; Python still owns data, AI, routes, and HTML rendering.
- Main-page forms and ordinary same-origin content links update in place and poll job progress; the Home, Archive, and Settings header links keep full-page navigation. The browser request helper rejects cross-origin destinations and redirects.
- A horizontal Home, Archive, and Settings navigation; a fixed session token and USD-cost meter sits at the bottom left.
- A text-only `P. 1` masthead, single white surface, generous open space, and horizontal editorial rules; Home, Archive, and Settings keep visible copy minimal.
- Viewport-scaled masthead and search, wide archive and result lists, and readable notes on narrow screens. Settings use two columns on desktop and stack below 900 pixels; Archive and Settings include brief purpose captions.
- Inline failure notices with rotating log and terminal diagnostics; `run.py` also shows a local notice when required packages are missing.
- Archive index search matches source and video titles in Python.
- HTTPS YouTube video and playlist links are checked against an explicit host and ID allowlist.
- Playlist titles load before summaries. GPT-6 Luna assigns topic labels from title strings only; uninformative titles receive `Other`.
- Users can sort immediately by playlist order, title, publish date, author, or topic, filter the title list, and select all, none, or individual videos. Title lists paginate at 48 per page, retain continuous numbering, and preserve selections across pages; checking a title refreshes the selected count. The check circle is 33 pixels on desktop and smaller on narrow screens. Responsive grids display two or three columns as the viewport grows, and expanded summaries stay in their grid cells.
- Selected videos are grouped into bounded AI requests and processed sequentially; saved summaries are reused by video ID unless the user requests a refresh.
- Collapsed summaries in batch results and archive detail can be searched by title, topic, or summary text through Python routes.
- Summary and follow-up prompts use English. Follow-ups show loading progress, fetch captions, and store only the question and answer. Follow-up results appear in a shared answer dock while the current list remains visible; a failed answer can be retried with its question retained.
- Failed source lookup offers an in-place retry using the validated URL, source type, target list, and replacement setting held in the in-memory job. Failed summary rows can be retried one video at a time through `/retry-video/<source_key>/<video_id>`.
- API calls have up to four attempts total for transient connection, timeout, rate-limit, and server failures, with 0.5/1/2-second backoff. Authentication errors, other client errors, and malformed model responses are not retried. The OpenAI SDK automatic retry is disabled; each app attempt records its own usage state and safe retry log entry.
- Local JSON archive stores source rows, title topics, summaries, chat turns, timestamps, and summary preferences. Archive and Settings show the archive and error-log file paths.
- Archive groups playlist, custom-list, and single-video summaries. Lists can be created or deleted; videos can be copied or moved between lists; a saved video summary can be deleted separately.
- Home can add a video link or one-video playlist to an existing list; larger playlists get their own list. Repeat playlist checks add new IDs and summarize them by default, while replacing existing text requires the Home approval checkbox.
- General settings choose the default playlist sort, archive sort, automatic new-video summary behavior, interface size, and reading width.
- Multiple playlists can be saved side by side; automatic startup refresh of newly added playlist videos remains deferred.
- Session input, output, reasoning, cached-read, and cache-write token counts plus USD cost stay in process memory and are discarded after the browser session or ledger expiry.
- Rotating diagnostic logs omit transcript text, prompts, model output, and credentials.

## Limits

- English captions are required. Caption retrieval or YouTube extraction may fail due to availability or service changes.
- `yt-dlp` listing is not the official YouTube Data API; review the technical handoff for source and terms considerations.
- Date and author metadata may be `Unknown`.
- Cost uses documented GPT-6 Luna input, cached-input, 30-minute cache-write, 12-hour cache-write, and output rates. Missing or invalid cache-write breakdowns make an attempt unpriced; displayed totals round to eight decimal places.
- Local in-page requests use same-origin HTML from Flask; YouTube extraction and OpenAI calls remain server-side. The JavaScript transport does not update the address bar or browser history for in-page swaps.
- No added accessibility or localization layer is included, by request.
