# memory (compact live state; PLAN_SPEC.md is canonical)
updated: 2026-10-09T05:00+05:30
phase: P1 foundation done (domain, guard G1-G3/G5-G8, events, serp client + ledger), P0 probe done
deadline: 2026-10-10 23:59 IST (aim to submit by 21:00)

decisions:
- single agent; work only in Quaoar/ on main; gate && commit && push per micro-commit; no BOARD.md
- commits: conventional micro-commits, no trailers, no co-author, no agent ids
- python 3.13 + uv 0.9.5; sqlite ledger; no graph database
- agent: pydantic-ai + serpapi-search-tools (json mode, google engine) (ADR-0001); mcp: fastmcp
- llm: cohere command-a-plus-05-2026 locked per scan, 2 keys rotate
- site-restricted searches on duckduckgo, results post-filtered (google ignores site:)
- public site is replay only (api on render, web on netlify)
- history rewritten once (2026-10-09) to drop a real email from a test; force-pushed with lease

keys (.env, never printed): SERPAPI_API_KEYS x1 (Free, 230 left), COHERE_API_KEYS x2

blocked:
- agent CLI design waits for user confirmation ([ORCHESTRA:AGENT_CLI])
- case prospectus PDFs (manual download, kept local)

next:
- P2 prospectus: acquire (url/path guards), pdf pages, section locator, grounded extraction
- P3 checks VX, BK, LT, SV on top of LedgerClient

numbers:
- probe: 20 credits, ledger count == SerpApi usage (docs/benchmark-audits/probe-2026-10-09.md)
- parse_inr 3.6 us, request hash 7.8 us, cache hit 0.12 ms (tests/perf)
- guards and parsers linear on 200 KB adversarial input
