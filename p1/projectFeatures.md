## PageOne

- Local Python Flask app with Jinja2 pages and external CSS; the interface has no JavaScript.
- A horizontal Home, Archive, and Settings navigation; a fixed session token and USD-cost meter sits at the bottom left.
- A text-only `P. 1` masthead, single white surface, generous open space, and horizontal editorial rules; Home, Archive, and Settings keep visible copy minimal.
- Viewport-scaled masthead and search, wide archive and result lists, and readable notes on narrow screens.
- Script-free inline failure notices with rotating log and terminal diagnostics; `run.py` also shows a local notice when required packages are missing.
- Archive index search matches source and video titles in Python.
- HTTPS YouTube video and playlist links are checked against an explicit host and ID allowlist.
- Playlist titles load before summaries. GPT-6 Luna assigns topic labels from title strings only; uninformative titles receive `Other`.
- Users can sort immediately by playlist order, title, publish date, author, or topic, filter the title list, and select all, none, or individual videos using large selection circles.
- Selected videos are summarized in a background batch; saved summaries are reused by video ID unless the user requests a refresh.
- Collapsed summaries in batch results and archive detail can be searched by title, topic, or summary text without JavaScript.
- Summary and follow-up prompts use English. Follow-ups show loading progress, fetch captions, and store only the question and answer.
- Local JSON archive stores source rows, title topics, summaries, chat turns, timestamps, and summary preferences. Archive and Settings show the archive and error-log file paths.
- Archive groups playlist, custom-list, and single-video summaries. Lists can be created or deleted; videos can be copied or moved between lists; a saved video summary can be deleted separately.
- Home can add a video link or one-video playlist to an existing list; larger playlists get their own list. Repeat playlist checks add new IDs and summarize them by default, while replacing existing text requires the Home approval checkbox.
- General settings choose the default playlist sort, archive sort, and automatic new-video summary behavior.
- Multiple playlists can be saved side by side; automatic startup refresh of newly added playlist videos remains deferred.
- Session token counts and estimated model cost stay in process memory and are discarded after the browser session or ledger expiry.
- Rotating diagnostic logs omit transcript text, prompts, model output, and credentials.

## Limits

- English captions are required. Caption retrieval or YouTube extraction may fail due to availability or service changes.
- `yt-dlp` listing is not the official YouTube Data API; review the technical handoff for source and terms considerations.
- Date and author metadata may be `Unknown`.
- Cost uses the documented GPT-6 Luna token rates and reports partial values when usage detail is unavailable.
- No added accessibility or localization layer is included, by request.
