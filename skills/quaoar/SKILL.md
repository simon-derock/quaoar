---
name: quaoar
description: Check an Indian SME IPO prospectus against public evidence before anyone applies. Use when asked whether an IPO company, its vendor or its merchant banker looks real, or to read a recorded Quaoar case.
---

# Quaoar: check every IPO before you apply

Quaoar reads an SME IPO prospectus and checks what it claims against SerpApi evidence.
Every line says one of three things: **checks out**, **doesn't match**, **couldn't find**,
and links to its source. It never says fraud, buy or sell.

## Tools (MCP server `quaoar`)
- `list_replays` and `replay_card <name>`: recorded cases, no keys needed. Start here.
- `scan_prospectus <pdf path or https url>`: a live scan. Costs SerpApi credits (cap 25).
- `saved_card <scan_id>`, `ledger_stats`.

## Playbooks
**Investor quick check:** `scan_prospectus` with the PDF, then read the card out in plain words:
the counts first, then each "doesn't match" line with its proof link. Say what was *not* found
as "couldn't find", never as a problem.

**Journalist deep dive:** quote each signal with its source URL and the date it was seen.
A mismatch is a lead to verify, not a finding.

**Analyst:** use `ledger_stats` to report credits spent per engine, and replay cases to compare.

## Language rules
- Say "doesn't match" or "worth a closer look", never fraud, scam, fake, buy, sell, avoid.
- Never predict listing gains or a price. If asked, say Quaoar doesn't give investment advice.
- Absence of evidence is "couldn't find", not a mismatch.
- Always end with: Facts with sources. Not investment advice.
