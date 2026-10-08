# memory (compact live state; PLAN_SPEC.md is canonical)
updated: 2026-10-09T01:10+05:30
phase: P1 foundation (worktree ../wt-quaoar-foundation, branch feat/foundation)
deadline: 2026-10-10 23:59 IST (aim to submit by 21:00)

decisions:
- single agent; one worktree per task (../wt-quaoar-<slug>), ff-only merges; no BOARD.md
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
- P1 scaffold: pyproject, gate.sh, ci.yml, domain, guard, ledger, key pools
- P0 probe through the ledger (budget 30 searches)

numbers: none measured yet
