<p align="center">
  <img src="docs/assets/banner.png" alt="Quaoar. Check every IPO before you apply." width="100%">
</p>

<p align="center">
  <a href="https://github.com/simon-derock/quaoar/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/simon-derock/quaoar/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.13" src="https://img.shields.io/badge/python-3.13-c6c9cf">
  <img alt="Tests 900+" src="https://img.shields.io/badge/tests-900%2B-2ee59d">
  <img alt="MIT licence" src="https://img.shields.io/badge/licence-MIT-858a93">
  <img alt="Powered by SerpApi" src="https://img.shields.io/badge/powered%20by-SerpApi-2ee59d">
</p>

<p align="center">
  <b>Quaoar reads an SME IPO prospectus and checks what it claims against the outside world.</b><br>
  Every line of its card says <b>checks out</b>, <b>doesn't match</b> or <b>couldn't find</b>, with a source link.<br>
  No verdicts. No advice. <i>Facts with sources.</i>
</p>

<p align="center">
  <a href="#try-it-in-60-seconds">Try it</a> ·
  <a href="#what-it-checks">What it checks</a> ·
  <a href="#proof-that-it-works">Results</a> ·
  <a href="#use-it-from-your-own-agent">MCP</a> ·
  <a href="#honest-limits">Limits</a>
</p>

> Built for the SerpApi India Hackathon 2026, track Commerce & Market Intelligence.

## Why it exists

In 2024 an investors' group noticed that the software vendor named in Trafiksol's IPO prospectus had not filed accounts. SEBI then found the vendor's office locked, and the IPO money was refunded. The prospectus is *required* to name that vendor (ICDR Schedule VI clause 7(b)), so the check can be automated. Quaoar does that check, plus several more, in a few minutes.

## Four ways in

| | | |
|---|---|---|
| **Terminal** | `uv run quaoar` | A chat-style console. Plain language works, even if you know nothing about IPOs. |
| **CLI** | `quaoar scan rhp.pdf` | Scripted scans, `diff` between prospectus versions, ledger and key tools. |
| **Web console** | `quaoar serve` + `web/` | A product page that replays recorded scans. No keys, no uploads. |
| **Your agent** | `quaoar mcp` | Six MCP tools and a skill, so Claude Code can run the check for you. |

<p align="center">
  <img src="docs/assets/console.png" alt="The Quaoar console replaying the Trafiksol scan: terminal on the left, card with proof links on the right" width="100%">
</p>

## What it checks

| Check | What it looks at | SerpApi engines |
|---|---|---|
| **Vendor** | The company quoting for the IPO money: on the company registry, active, paid-up capital in proportion to the quote, any court or SEBI page naming it, on Maps | DuckDuckGo (site-restricted), Google Maps |
| **Premises** | The issuer's own registered office, factory or warehouse: is there a Maps listing, is it closed, is a "factory" listed as an apartment | Google Maps |
| **Merchant banker** | SEBI orders naming the banker or the issuers in its past-issues table | DuckDuckGo (site:sebi.gov.in) |
| **Litigation** | Court or SEBI matters naming the issuer that the prospectus does not list | DuckDuckGo (SEBI, Indian Kanoon, IBBI) |
| **News and hype** | Dated adverse coverage; promotion volume shown as context only, never as a verdict | Google News, YouTube |

Statuses come only from fixed rules. The language model reads the prospectus into claims, and every claim must be found on the page it cites or it is dropped.

### Evidence as of the prospectus date
By default Quaoar reads evidence **as of the date printed on the prospectus**, so later news cannot change the card. A Trafiksol scan dated before the SEBI action shows the vendor mismatch and nothing else; `--now` reads everything up to today. For the version an investor sees while the issue is open, scan the red herring prospectus (RHP), not the final prospectus filed after bidding closes.

### A bounded ReAct investigator
When a fixed search comes back empty, a ReAct investigator (PydanticAI on Cohere) reformulates it: it adds the registry city, tries the CIN, drops the legal suffix. It only **gathers evidence**; fixed rules still decide every verdict. Its design:

- the model chooses search *terms* and a one-sentence `why`; code builds the query, adds the site allowlist and applies the same cache, key pool and credit budget as every other search;
- at most 8 searches, 6 credits and 10 model requests per investigation; repeated searches are refused;
- text from the web is untrusted data in the prompt, and injection-shaped text is flagged in the event stream;
- the tool-call trace is stored, so re-running a scan replays it with no model call.

Prompt structure and the measured behaviour are in [ADR-0002](docs/decisions/ADR-0002-investigator-prompt.md). How much it actually helped is reported below, unvarnished.

## Proof that it works

The first test is Trafiksol, the case that made the news. Quaoar flags the vendor with no human help: Oasis Corpcare quoted ₹17.70 Cr against ₹1 lakh of paid-up capital (1,770 times), on the red herring prospectus and on the final one.

Then the question that matters: does it cry wolf? Three prospectuses with no known problem were scanned on the same rules, fixed in advance ([audit](docs/benchmark-audits/controls-2026-10-09.md)).

| Case | Flagged | Checks out / doesn't match / couldn't find |
|---|---|---|
| Trafiksol (red herring) | yes: vendor capital 1,770x | 8 / 1 / 1 |
| Aelea Commodities (control) | no | 4 / 0 / 9 |
| Indian Emulsifier (control) | no | 3 / 0 / 2 |
| TBI Corn (control) | yes: a 2021 SEBI order naming its lead manager | 3 / 1 / 7 |

**Controls flagged: 1 of 3.** The first run flagged 2 of 3, mostly from Quaoar's own bugs (matching a vendor to a same-named company, reading the lead manager as the issuer). Those were fixed as identity and parsing bugs, with the threshold untouched, and the audit shows both runs. The TBI flag is a true record about the banker, not the company, and the card says so.

**The ReAct investigator**, over the five scans: 15 investigations, 29 searches, 5 evidence gaps closed (1 registry, 4 Maps) and 17 left open. It helps at the margin and never changes a verdict.

**A scan costs** about 12 to 37 SerpApi searches on a fresh prospectus, 0 on a replay. Four companies is not an accuracy claim.

`quaoar diff earlier.pdf later.pdf` compares two versions of a prospectus (draft, red herring, final) and lists vendors, matters and lead managers that were added, removed or changed. It reads claims only, no searches. The promoter list is noisy when a draft lists promoter-group members.


## Try it in 60 seconds
No API keys needed.

```bash
git clone https://github.com/simon-derock/quaoar && cd quaoar
uv sync
uv run quaoar replay fixtures/replay/trafiksol
```
This replays a recorded scan of the Trafiksol red herring prospectus. Other recorded cases are in `fixtures/replay/` (`uv run quaoar` then `/cases`). `teamtech` is a prospectus never seen before, downloaded from sebi.gov.in and scanned live to test user documents; it has no ground truth and is not part of the evaluation.

## Inside the terminal
```
$ uv run quaoar
QUAOAR · check every IPO before you apply
› /replay trafiksol      watch a recorded case
› /proof 2               the evidence behind line 2: page, date, SerpApi search id
› /comment               a neutral public-comment letter from the lines that didn't match
› /scan path/to/rhp.pdf  a live scan (uses SerpApi credits; /mode, /budget)
› /trace  /credits  /help
```
Plain language works too ("show proof for 2"). A complete beginner can type "hi", "what is an SME IPO" or "where do I get a prospectus" and get a plain answer, in English or basic Hinglish. Advice questions ("should I apply?") get the facts and a plain disclaimer, not a view.

Other commands: `quaoar scan`, `card`, `comment`, `diff`, `doctor` (checks keys, model access and the ledger without spending credits), `ledger stats|verify`, `keys status`, `export`, `replay`, `serve`, `mcp`.

## Run a live scan on your own prospectus
```bash
cp .env.example .env     # add SERPAPI_API_KEYS and COHERE_API_KEYS
uv run quaoar doctor
uv run quaoar scan path/to/prospectus.pdf            # --mode fixed|agent, --now, --cutoff YYYY-MM-DD
uv run quaoar ledger stats                           # credits by engine and key, cache hit rate
```
Exchange sites (NSE, BSE) forbid automated downloads, so Quaoar refuses their URLs: download the PDF yourself, or use the lead manager's own website.

## Use it from your own agent
```bash
claude mcp add quaoar -- uvx --from git+https://github.com/simon-derock/quaoar quaoar mcp
```
Tools: `list_replays`, `replay_card`, `scan_prospectus`, `saved_card`, `draft_comment`, `ledger_stats`. Copy [`skills/quaoar/SKILL.md`](skills/quaoar/SKILL.md) into your agent's skills folder for the playbooks and language rules.

## How it is built
```mermaid
flowchart LR
    PDF[prospectus pdf] --> P[pages + sections]
    P --> C[claims, grounded on the page]
    C --> K[checks]
    K -->|every search| L[(ledger: cache, keys, budget)]
    L --> S[SerpApi]
    K -.gaps.-> A[ReAct investigator]
    A --> L
    K --> R[fixed rules] --> CARD[card + proof links]
```
- **One road to SerpApi.** Every search goes through one client: query guard, cache, credit budget, key rotation, response cleaning, provenance (`search_id`, hash, time).
- **Google ignores `site:`.** In a probe, Google returned results from other domains for `site:` queries (1 of 10 on the named site); DuckDuckGo returned 10 of 10. All site-restricted searches therefore use DuckDuckGo.
- **Guardrails.** Text from PDFs and search results is untrusted: control characters and bidi tricks are stripped, personal identifiers are masked before anything reaches the model, injection-shaped text is flagged, and the model can never set a status.
- **Same core everywhere.** The CLI, terminal, MCP server and web console run the same scan. The public site is replay only: no keys, no uploads, no live search.

Full design, specs and diagrams: [`PLAN_SPEC.md`](PLAN_SPEC.md). Decisions: [`docs/decisions`](docs/decisions). Audits with their raw method: [`docs/benchmark-audits`](docs/benchmark-audits).

## Honest limits
- **Absence is not a finding.** Small private companies often barely appear online, so "couldn't find" is common and is never counted against a company.
- **Identity is the hard part.** Early runs matched people and firms to unrelated namesakes. Fixes: a person's name alone is never enough; a vendor whose name carries no company form is never matched to a same-named registered company; cards never name individuals.
- **The 100x vendor-capital rule is a screen, not a verdict.** It was fixed before any control was scanned. A tiny vendor quoting a large amount is worth a look, but real small suppliers do this too.
- **Registry snippets are not live filings** and can lag the official records.
- **Point-in-time is partial.** Registry and Maps pages show today's state; strict "before listing" evidence relies on dated news, orders and court records.
- **Very small evaluation.** One positive (two versions) and three controls, all from one banker's website (exchange hosts forbid automated download). No accuracy claim is made.

## Development
```bash
uv sync --locked && ./scripts/gate.sh   # format, lint, strict types, tests, coverage, dead code, security
cd web && npm ci && npm test            # the console
```
Tests are written first and cite the spec they cover (`# spec: SPEC-...`). Timing budgets (parse a rupee amount, hash a request, hit the cache, locate sections in 300 pages) run in CI and print their medians in the job summary.

## Credits
Search data by [SerpApi](https://serpapi.com). Language model: Cohere. Agent framework: PydanticAI. MIT licence.

Built by Philip Simon Derock ([philipsimonderock.com](https://philipsimonderock.com)) for the SerpApi India Hackathon 2026.
