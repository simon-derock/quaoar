# memory (compact live state; PLAN_SPEC.md is canonical)
updated: 2026-10-09T03:10+05:30
phase: P1 foundation (domain + guard G1/G2/G5-G8 done, CI green)
deadline: 2026-10-10 23:59 IST (aim to submit by 21:00)

decisions:
- single agent; work only in Quaoar/ on main; gate && commit && push per micro-commit; no BOARD.md
- commits: conventional micro-commits, no trailers, no co-author, no agent ids
- python 3.13 + uv 0.9.5; sqlite ledger; no graph database
- agent: pydantic-ai + serpapi-search-tools (ADR-0001); mcp: fastmcp
- llm: cohere command-a-plus-05-2026 locked per scan, 2 keys rotate
- public site is replay only (api on render, web on netlify)
- fresh code; stellium/lunarbit lend patterns only
- track: commerce & market intelligence; varyaa never a positive label

keys (.env, never printed): SERPAPI_API_KEYS x1 (Free, 250/month), COHERE_API_KEYS x2

blocked:
- agent CLI design waits for user confirmation ([ORCHESTRA:AGENT_CLI])
- case prospectus PDFs (manual download, kept local)

next:
- P1: serp client (G3 query guard), ledger, key pools, replay, sanitizer
- P0 probe through the ledger (budget 30 searches)

numbers:
- parse_inr median 2.6-3.6 us (budget 20 us), tests/perf
- guards linear on 200 KB adversarial input (tests/unit/guard/test_redos.py)
- CI run 37832935578: gates, perf, privacy green
