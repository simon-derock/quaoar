# Quaoar demo video script (under 3 minutes, screen recording, running locally)

Setup before recording: `uv sync`, a filled `.env`, and one warm run so every search and model read is cached
(`uv run quaoar scan cases/pdfs/<trafiksol-rhp>.pdf`). Terminal at a large font. Nothing on screen may show a key.

**0:00 - 0:20 Hook (title card or the terminal, voice over)**
"In 2024 an investors' group caught a shell company hiding in an IPO prospectus, by hand. Trafiksol's software vendor had not filed accounts, and ₹44.87 crore went back to investors. Quaoar does that check for any SME IPO, with every line sourced."

**0:20 - 1:20 Live scan in the terminal**
```
uv run quaoar
› /scan cases/pdfs/<trafiksol-rhp>.pdf
```
Narrate as lines stream: sections found in milliseconds, claims read from the prospectus, then each SerpApi search with its engine, credits and time. Point at the `agent` lines: "When a search comes back empty, a ReAct investigator reformulates it, with a visible reason for every search and a hard budget. It only gathers evidence: fixed rules decide every verdict."

**1:20 - 1:55 The card**
Read the "doesn't match" line: "The vendor quoted ₹17.70 crore, but its paid-up capital on the registry is ₹1 lakh: 1,770 times." Then `› /proof 2`: the registry page, the date, the SerpApi search id. Say what "couldn't find" means and that it is never held against a company.

**1:55 - 2:20 It stays quiet when there is nothing to find**
`› /replay aelea` (a clean control from the same banker). "On three ordinary companies, Quaoar flagged one: a real SEBI order from 2022 naming the lead manager of TBI Corn. The first run flagged two; those were our own bugs, and the audit shows both runs." Figures: `docs/benchmark-audits/controls-2026-10-09.md`.

**2:20 - 2:45 Same core everywhere**
`› /comment` for the neutral public-comment letter, then the MCP tool from Claude Code (`replay_card trafiksol`), then the Netlify page replaying the same case.

**2:45 - 3:00 Close**
"Evidence as of the prospectus date, so later news can't change the card. Check every IPO before you apply. Pehle jaanch, phir apply."
