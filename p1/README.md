# PageOne

## What it does

PageOne helps you choose what to learn from a YouTube playlist without watching every video first. Paste a video or playlist link to see its titles, then select the videos you want summarized. You can search the list and arrange it by date, author, title, or a topic suggested from the video title. PageOne uses English captions to summarize each video’s main claims, arguments, evidence, and limitations, and to answer follow-up questions. It saves your summaries, questions, lists, and settings on your computer so you can return to them later.

## Before you start

You need a web browser such as Chrome or Safari and **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/). Python is the software that runs this app. On Windows, select **Add Python to PATH** if the installer offers it. Internet access is needed to install the app's packages, load new videos, and generate results; saved summaries can be read offline.

You also need an [OpenAI API key](https://platform.openai.com/api-keys) and access to API billing or credits. An API key is a private code that lets PageOne request summaries from OpenAI. [API usage is billed separately from ChatGPT](https://help.openai.com/en/articles/9039756). Keep your key private.

### Software installed with the app

The installation command below installs these packages for you:

| Package | Why PageOne needs it |
| --- | --- |
| Flask | Runs the pages you see in your browser. |
| openai | Requests summaries, topic labels, and answers. |
| yt-dlp | Reads YouTube titles and English captions. |
| pytubefix | Tries another way to read YouTube when yt-dlp fails. |

Flask also installs Jinja2, which builds the pages, and Werkzeug, which serves them on your computer. Other helper packages install automatically. Playwright is only needed for the optional developer browser checks, not for using PageOne.

## Open the app

If you do not have the app's files yet, [download them here](https://github.com/Shancypolo/ApolloChengai-lab-2026/archive/refs/heads/work.zip). Unzip the download, then open the **p1** folder inside it: that folder contains this README and a file named **run.py**. Do not double-click `run.py`; use the steps for your computer below.

<details>
<summary><strong>Windows</strong></summary>

1. In the p1 folder, click the address bar at the top of File Explorer, type `powershell`, and press Enter. This opens a window where you can paste commands.
2. Paste this command and press Enter. Wait for installation to finish:

   ```powershell
   py -m pip install -r requirements.txt
   ```

3. Paste this command and press Enter:

   ```powershell
   $env:OPENAI_API_KEY = Read-Host "Paste your OpenAI API key, then press Enter"
   ```

4. When asked, paste your actual key and press Enter. Put the key here, **not in any app file**.
5. Start PageOne:

   ```powershell
   py run.py
   ```

</details>

<details>
<summary><strong>Mac</strong></summary>

1. Open **Terminal** using Spotlight search. Type `cd `, including the space, drag the p1 folder into the Terminal window, and press Return. This tells Terminal which folder to use.
2. Paste this command and press Return. Wait for installation to finish:

   ```sh
   python3 -m pip install -r requirements.txt
   ```

3. Paste this command and press Return:

   ```zsh
   read -s "OPENAI_API_KEY?Paste your OpenAI API key, then press Return: "
   ```

4. Paste your actual key and press Return. It will not appear while you enter it. Put the key here, **not in any app file**.
5. Paste these commands to make the key available and start PageOne:

   ```sh
   export OPENAI_API_KEY
   python3 run.py
   ```

</details>

Leave that window open. In your web browser, open **[http://127.0.0.1:5000](http://127.0.0.1:5000)**. This address opens PageOne on your own computer.

To stop the app, return to the command window and press **Ctrl+C**. Next time, open a command window in the same folder, enter your key again, and run the start command; you do not need to reinstall the packages.

<details>
<summary>Only if Python refuses to install the packages</summary>

A “virtual environment” is a private folder for the app's packages. It is optional, but can help if Python reports an “externally managed environment” or a permissions problem.

On Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then follow the key steps above and start with `.\.venv\Scripts\python.exe run.py`.

On Mac:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Then follow the key steps above and start with `.venv/bin/python run.py`.

</details>

## Use PageOne

1. On YouTube, use **Share → Copy link** for a video or playlist. On PageOne's **Home**, paste that complete link, starting with `https://`, and press **Summarize**. A link that contains both a video and a playlist asks which one you mean.
2. Select the circles beside the videos you want. Clicking a video title opens YouTube. Long playlists have several pages; your selections carry across them.
3. Press **Summarize selected**, then open a summary to read it or ask a follow-up question, such as “What evidence supports the main claim?”
4. Open **Archive** to find saved work, create lists, or move and copy videos between lists.
5. Open **Settings** to change the writing instructions, text size, reading width, sorting, or automatic summaries for newly added playlist videos. For example, ask for “Short paragraphs that explain unfamiliar words.” Press **Save preferences**.

Use the **Save to** choice on Home to add a single video to an existing list. A playlist with several videos gets its own list. Saved summaries are reused; choose the replacement option only when you want to overwrite them.

## Your saved information

PageOne creates a **user data** folder beside `run.py`:

- **userdata.json** holds your summaries, saved questions and answers, lists, and all settings, including your summary-writing preferences.
- **error.log** records problems to help diagnose failures.

Your settings remain saved after you close and reopen the app. Back up `userdata.json` if you want to keep a spare copy. It is an ordinary, unencrypted text file, so protect it like your other personal notes. Your API key is not saved there. Titles, captions, writing preferences, and relevant saved questions, answers, and summaries are sent to OpenAI when needed; captions are not kept in your saved archive.

If you used an older version, PageOne copies its old saved files to these new names and keeps the originals. If it finds conflicting files, it stops rather than overwriting them; the error log explains the problem.

## Known limitations

- **YouTube access can fail.** Private, restricted, removed, or captionless videos may not work. YouTube can also block requests from some networks. The app reports a problem and offers **Try again** where available.
- **English captions are required.** Only the first 100,000 characters of captions are used, so a very long video may have later material omitted.
- **AI can be wrong.** Check important claims against the video. Topic labels use titles only; vague titles are grouped as **Other**. Dates or authors may appear as **Unknown**.
- **Your OpenAI account must allow the request.** An invalid key, missing credit, or unavailable model prevents AI requests; you can still read saved notes.
- **Requests can cost money even when an answer does not arrive.** The app makes one attempt per AI request; retrying is your choice. Large selections are split into separate groups. The session cost meter uses reported usage and may be incomplete; your OpenAI bill is the final record.
- **Keep the app running while work finishes.** Closing it stops unfinished work and clears the session counter. Completed summaries and settings remain saved. On refresh, return to Archive to find saved work.
- **This is for one person on one computer.** Do not run several copies against the same saved files or expose it to other computers. No account or password protects the local app.
- **A damaged save file is not overwritten.** Keep a backup; the app reports the problem instead of replacing your notes. If the address will not open, check the command window for an error, including whether another app is already using port 5000.

## What each file is for

You do not need to edit these files to use PageOne. Expand this list only if you want to understand the folder.

<details>
<summary>Show the individual file guide</summary>

| File | Purpose |
| --- | --- |
| `run.py` | Starts the app and explains missing software. |
| `app.py` | Connects the pages, buttons, and background work. |
| `youtube_source.py` | Reads YouTube titles and English captions. |
| `ai_summaries.py` | Requests summaries, topic labels, and follow-up answers. |
| `archive_storage.py` | Reads and safely saves notes and settings. |
| `data_paths.py` | Chooses save locations and preserves older saved files. |
| `usage_accounting.py` | Counts session tokens and estimates their cost. |
| `requirements.txt` | Lists the packages needed to use the app. |
| `requirements-dev.txt` | Adds the packages needed for developer checks. |
| `.gitignore` | Keeps local data and temporary files out of source control. |
| `README.md` | Explains installation and everyday use. |
| `HANDOFF.md` | Gives maintainers technical details and check results. |
| `projectFeatures.md` | Points readers to this guide and the maintenance guide. |
| `templates/base.html` | Supplies the shared navigation, answer area, and counter. |
| `templates/home.html` | Shows the YouTube link entry page. |
| `templates/ambiguity.html` | Asks whether a mixed link means a video or playlist. |
| `templates/source_results.html` | Shows titles, selection circles, search, and sorting. |
| `templates/inspection_progress.html` | Shows progress while titles are loading. |
| `templates/inspection_failure.html` | Offers another attempt when a source cannot load. |
| `templates/job_progress.html` | Shows progress while summaries are being written. |
| `templates/job_results.html` | Displays completed summaries and failed videos. |
| `templates/retry_result.html` | Displays the result of retrying one video. |
| `templates/archive.html` | Lists your saved playlists, lists, and videos. |
| `templates/archive_detail.html` | Opens one saved list and its video notes. |
| `templates/chat_progress.html` | Shows progress while a follow-up answer is written. |
| `templates/chat_answer.html` | Shows a follow-up answer or a retry option. |
| `templates/settings.html` | Shows writing and display preferences. |
| `templates/error_notice.html` | Provides the reusable problem notice. |
| `templates/notice.html` | Displays general error messages. |
| `templates/startup_error.html` | Explains why the app could not start. |
| `templates/workflow_steps.html` | Displays the three-step usage guide. |
| `static/css/pageone.css` | Sets the shared appearance and screen layouts. |
| `static/css/page_guides.css` | Styles the Home, Archive, and Settings task areas. |
| `static/js/local_requests.js` | Updates page sections without reloading the whole page. |
| `static/js/reading_position.js` | Keeps an opened summary heading from jumping. |
| `static/fonts/Newsreader.ttf` | Supplies the reading font. |
| `static/fonts/Newsreader-OFL.txt` | Contains the font's usage license. |
| `static/icons/navigation-ink.png` | Supplies the Home, Archive, and Settings icons. |
| `tests/test_pageone.py` | Checks pages, settings, storage, and AI rules offline. |
| `tests/test_api_attempts.py` | Checks that AI requests are attempted only once. |
| `tests/test_source_fallback.py` | Checks the alternative YouTube reader offline. |
| `tests/test_data_paths.py` | Checks save locations and preservation of older files. |
| `tests/test_inline_actions.py` | Checks retries and selections across list pages. |
| `tests/startup_smoke.py` | Checks normal startup and the missing-software notice. |
| `tests/visual_test.py` | Checks the full browser workflow and screen sizes. |
| `tests/inline_browser_test.py` | Checks in-page actions and recovery from failed requests. |
| `apiTests/live_diagnostic.py` | Checks real services; an AI check can incur charges. |
| `apiTests/test1_pytubefix.py` | Original video-summary experiment using pytubefix. |
| `apiTests/test1_yt_dlp.py` | Original video-summary experiment using yt-dlp. |
| `apiTests/test2_pytubefix.py` | Original playlist-title experiment using pytubefix. |
| `apiTests/test2_yt_dlp.py` | Original playlist-title experiment using yt-dlp. |
| `apiTests/testValues.md` | Lists public YouTube examples used for checks. |
| `user data/userdata.json` | Stores your notes, lists, and settings after saving. |
| `user data/error.log` | Stores diagnostic messages after the app runs. |
| `user data/archive-migration.json` | Records a completed transfer from older saved files. |

The files in `apiTests/` are experiments and checks, not part of normal use. Technical maintenance instructions are in [HANDOFF.md](HANDOFF.md).

</details>
