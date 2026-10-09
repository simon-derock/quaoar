# Demo video

The recorded video is `results/video/quaoar-demo-1080p60.mp4` (2 min 12 s, 1080p at 60 fps, yellow subtitles burned in; the lossless master is `quaoar-demo-master.mkv` in the same folder, both git-ignored). Everything in it ran locally on one laptop:

| Time | What runs |
|---|---|
| 0:00 | Title card |
| 0:07 | `curl -LsSf …/install.sh \| sh`: the CLI installed from GitHub |
| 0:17 | `quaoar`, then `hi`: the built-in beginner answer |
| 0:30 | `/scan trafiksol-rhp.pdf`: a live scan of the Trafiksol red herring prospectus. It costs 0 credits because every search was already in the local ledger. |
| 0:43 | `/proof 2`: the registry page, date and SerpApi search id behind the 1,770x line |
| 0:50 | "why was this flagged?" and the lead-manager question: the Analyst agent, with citations |
| 1:10 | "is this IPO safe?": no verdict, no advice |
| 1:16 | `/replay aelea`: a control company where nothing fails to match |
| 1:25 | The website: the recorded scan, the "How a check works" sequence, the beginner chat, the docs |
| 2:06 | Closing card |

How it was made: the terminal is the real CLI driven in a pseudo-terminal with typed input, recorded with timestamps and rendered in xterm.js. Pauses before each step were lengthened so the output can be read; nothing on screen was edited. The website is the real site, captured from the browser while a script scrolls and clicks.
