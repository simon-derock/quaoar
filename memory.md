# memory (compact live state; PLAN_SPEC.md is canonical)
updated: 2026-10-09T02:05+05:30
phase: P3 checks (vendor x-ray live on Trafiksol); next card, scan, cli
deadline: 2026-10-10 23:59 IST (aim to submit by 21:00)

decisions:
- single agent; work only in Quaoar/ on main; gate && commit && push per micro-commit; no BOARD.md
- local pre-commit hook runs scripts/gate.sh (a red gate blocks the commit)
- commits: conventional micro-commits, no trailers, no co-author, no agent ids
- python 3.13 + uv 0.9.5; sqlite ledger; no graph database
- agent: pydantic-ai + serpapi-search-tools (json mode, google engine) (ADR-0001); mcp: fastmcp
- llm: cohere command-a-03-2025, tool output, retries 422/5xx, rotates keys on 429
- site-restricted searches on duckduckgo, results post-filtered (google ignores site:)
- claim spans cut from the page by code; values must be on the cited page
- prospectus pdfs from merchant-banker sites via our guarded intake, kept in cases/pdfs (ignored)

keys (.env, never printed): SERPAPI_API_KEYS x1 (Free), COHERE_API_KEYS x2

blocked:
- none (user said proceed; agent CLI design taken as approved)

next:
- card + scan orchestration + `quaoar scan` + replay bundle for Trafiksol
- BK banker track record, LT litigation diff, SV site visit
- mcp server, skill, api + web, backtest, README, video script

numbers:
- Trafiksol: sections located (375 pages, 23 ms), 15 llm calls, vendor quote 1,770x paid-up capital flagged, 2 credits
- probe: 20 credits, ledger count == SerpApi usage (docs/benchmark-audits/probe-2026-10-09.md)
- parse_inr 3.6 us, request hash 7.8 us, cache hit 0.12 ms, section locator 23.8 ms
