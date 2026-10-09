---
name: quaoar
description: Check an Indian SME IPO prospectus against public evidence before anyone applies. Use when asked whether an IPO company, its vendor or its merchant banker looks real, to draft a public comment, or to read a recorded Quaoar case.
---

# Quaoar: check every IPO before you apply

Quaoar reads an SME IPO prospectus and checks what it claims against SerpApi evidence.
Every line says one of three things: **checks out**, **doesn't match**, **couldn't find**,
and links to its source. It never says fraud, buy or sell.

## What it checks
- **Vendor named in the objects of the issue**: on the company registry? paid-up capital in proportion to the quote? active? on Maps? any court or SEBI page naming it?
- **Issuer's own premises**: a Maps listing for the registered office, factory or warehouse; a factory listed as an apartment or co-working space is flagged.
- **Merchant banker**: SEBI orders naming the banker or the issuers in its past-issues table.
- **Litigation**: court or SEBI matters naming the issuer (or a promoter, with the issuer) that the prospectus does not list.
- **News**: dated adverse coverage. Promotion volume (YouTube, news) is shown as context only.
- By default evidence is read **as of the prospectus date**, so later news cannot change the card. `--now` reads it as of today.

## Tools (MCP server `quaoar`)
- `list_replays` and `replay_card <name>`: recorded cases, no keys needed. Start here.
- `scan_prospectus <pdf path or https url>`: a live scan. Costs SerpApi credits (cap 25). `mode` is `agent` (a bounded ReAct investigator fills evidence gaps) or `fixed`.
- `ask_card <name or scan_id> <question>`: a plain-language answer about a card, citing its lines (L<n>) and any follow-up search results (S<n>). Quote the answer with its citations; it never changes a status.
- `saved_card <scan_id>`, `draft_comment <scan_id>`, `ledger_stats`.

## Playbooks
**Investor quick check:** `scan_prospectus` with the PDF, then read the card in plain words (follow-up questions go to `ask_card`):
the counts first, then each "doesn't match" line with its proof link. Say what was *not* found
as "couldn't find", never as a problem.

**Journalist deep dive:** quote each signal with its source URL and date. A mismatch is a lead to
verify, not a finding. Use `draft_comment` only if the user wants to write to the exchange.

**Analyst:** use `ledger_stats` for credits per engine, and replay cases to compare. Report the
control results with their interval, not just the hits.

## Language rules
- Say "doesn't match" or "worth a closer look", never fraud, scam, fake, buy, sell, avoid.
- Never predict listing gains or a price. If asked, say Quaoar doesn't give investment advice.
- Absence of evidence is "couldn't find", not a mismatch.
- Never name an individual as the subject of a court matter.
- Always end with: Facts with sources. Not investment advice.
