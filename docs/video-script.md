# Quaoar demo video script (under 3 minutes, screen recording, running locally)

Record at a readable font size, light or dark terminal. Warm the ledger first with one live scan so the replay and cache lines show.

**0:00 – 0:20 Hook (voice over a plain title card)**
"In 2024, an investors' group caught a shell company hiding in an IPO prospectus, by hand. Trafiksol's vendor had not filed accounts, and ₹44.87 crore was refunded. Quaoar does that check for every SME IPO, in about two minutes."

**0:20 – 1:20 Live scan**
```
uv run quaoar scan cases/pdfs/<trafiksol>.pdf --cutoff 2024-09-03
```
Narrate as lines stream: pages, sections found in milliseconds, claims read, then each SerpApi search with its engine, credits and time. "Four searches. Everything else came from the prospectus."

**1:20 – 1:55 The card**
Read the "doesn't match" line out loud: "The vendor quoted ₹17.70 crore, but its paid-up capital is ₹1 lakh: the quote is 1,770 times its capital." Show the proof link and the SerpApi search id. Point at "couldn't find" and say it is never held against a company.

**1:55 – 2:25 Trust**
Run it again: "0 credits, same card." Show `quaoar ledger stats`. Say: "The model only reads the document. Every verdict comes from a fixed rule."

**2:25 – 2:50 Everywhere**
Show the MCP tool from Claude Code (`replay_card trafiksol`), then the Netlify page replaying the same case.

**2:50 – 3:00 Close**
"Check every IPO before you apply. Pehle jaanch, phir apply."
