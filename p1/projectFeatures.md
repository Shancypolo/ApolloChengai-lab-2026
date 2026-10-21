Some features below probably wont make it to the final product.

1. sort or group videos by publish date, author, and topic
2. optionally extend chats for more information about a video
3. customizable summary preferences
4. store past video summary of playlist
5. support multiple playlists
6. automatic fetch new videos added to playlist and summarize on startup

create a web app using python, Flask + Jinja2 + HTMX + css. 
goal: summarize youtube playlists and youtube videos. features include list all video titles from the playlist. sort or group videos by publish date, author, and topic
2. optionally extend chats for more information about a video
3. customizable summary preferences
4. store past video summary of playlist

visuals: a collapsable sidebar with pages settings, archive, and home.
    Home: homepage 


code must maximize readability for absolute beginner coders. use object oriented and functional programming paradigms. prefer functional programming over object oriented but you may use both. write a vs code readable comment under each function and class that explains usage and method with minimal words. write atleast 2 python files. locate html files outside of python files instead of embedding it. maximize flexibility on windows and mac newest version. use browser, computer control, cloud browser and subagents to visually test on extreme aspect ratios for correct display and correct functionality.## 5. Engineering constraints
- Use functional programming for transformations, validation, normalization, and rendering.
- Use object-oriented programming only through small concrete objects that own real state. Do not add abstract base classes, factories, inheritance trees, generic framework layers, or templates.
- Keep control nesting at four levels or fewer.
- Use straightforward native Python, descriptive names, focused functions, and a clear constants section.
- Preserve user-owned files and unrelated edits. Do not use destructive resets or broad deletion.
- Read the handoff and repository documentation carefully before making related changes.
- Keep README short and practical. Keep HANDOFF detailed and technically precise.
- Update all relevant documentation whenever behavior, prompts, context, tools, domains, tests, dependencies, or output contracts change.
- Research industry standards before writing or materially revising a handoff. Record the sources used and distinguish documented facts from assumptions.
- Handoff must cover setup, files, runtime flow, AI contracts, minimal context, source policy, security boundary, privacy, failure handling, test evidence, ownership, maintenance, and acceptance criteria.
- Use the handoff's prior checks and tests as the starting regression suite.
- Run compile checks, offline fake-client tests, relevant live diagnostics, and an end-to-end CLI smoke test when authorized.
- Debug failures until the main program, public functions, and relevant edge cases work.
- Keep offline tests network-free. Keep live API diagnostics separate and clearly identified because they consume quota.
- Cover dynamic questions, preference persistence, no-repeat behavior, early search, ambiguous-input progression, tool configuration, source allowlisting, HTTPS validation, malformed responses, injection handling, blank input, EOF, Unicode, missing credentials, output contract, and nesting depth.
- Report failures and fixes precisely. Do not claim a check passed unless it ran successfully.