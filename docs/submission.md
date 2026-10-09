# Submission text (SerpApi India Hackathon 2026)

Ready to paste into the submission form. Fields marked *you* need your own details.

**Project name:** Quaoar

**Tagline:** Check every IPO before you apply.

**Track:** Commerce & Market Intelligence. It turns finance search results into a tool for retail investors and analysts. AI Agents also fits, through the two bounded agents.

**Repository:** https://github.com/simon-derock/quaoar

**Website:** https://quaoar.philipsimonderock.com (docs at /docs.html)

**Demo video:** *you*: the unlisted YouTube or Drive link to `results/video/quaoar-demo-1080p60.mp4`

## What it does
Quaoar reads an Indian SME IPO prospectus and checks what it claims against the outside world before anyone applies:
- the vendor quoting for the IPO money;
- the company's offices and factory;
- the lead manager's SEBI record;
- court matters the prospectus doesn't list;
- dated news.

Every line of its card says *checks out*, *doesn't match* or *couldn't find*, with the source and its SerpApi search id. Fixed rules set every status. It never gives a verdict on the company and never gives investment advice.

## Who it helps
- Retail investors applying to SME IPOs on NSE Emerge and BSE SME. Applications cost a lakh or more, and the companies are little known.
- The analysts and journalists who read these prospectuses for a living.

In 2024 an investors' group caught, by hand, that the software vendor in Trafiksol's prospectus had not filed accounts. The IPO money was refunded. Quaoar flags the same vendor automatically: it quoted ₹17.70 Cr against ₹1 lakh of paid-up capital, 1,770 times.

## How it uses SerpApi
SerpApi is the product's only window on the outside world. Every search goes through one client with a query guard, a cache, a credit budget and key rotation.

| Engine | Used for |
|---|---|
| DuckDuckGo (site-restricted) | registry pages, SEBI orders, court and insolvency records |
| Google Maps | vendor and premises listings |
| Google News | dated coverage |
| YouTube | promotion volume, shown as context |
| Google | the agents' last resort |

Every line of the card keeps its SerpApi search id so anyone can repeat the check. A fresh scan costs about 12 to 37 searches. Re-runs are free from the local ledger.

## AI agents
**Investigator.** It fills evidence gaps during a scan: at most 8 searches and 6 credits per investigation.

**Analyst.** It answers plain-language questions about a finished card. It plans from the related card lines and runs follow-up searches only when the card can't answer: at most 3 searches and 3 credits. Its answer is shown only if every citation exists, every number appears in a cited source, and the wording and advice guards pass.

**Evaluation** ([audit](benchmark-audits/analyst-2026-10-09.md)):
- Offline: 40/40 questions cite the expected line.
- Live: 23/24.
- Every answer passed the wording guard.

## Running it locally
```bash
curl -LsSf https://raw.githubusercontent.com/simon-derock/quaoar/main/install.sh | sh
quaoar            # then: /replay trafiksol, /proof 2, "why was this flagged?"
```
No keys are needed to replay recorded cases. A live scan needs SerpApi and Cohere keys in `.env`.

## Disclosures
**Prior work:** none. This is a new project, first commit on 2026-10-08.

**AI tools used:**
- Claude Code (Anthropic) helped write the code, tests and docs.
- Cohere `command-a-03-2025`, through PydanticAI, is used inside the product to read prospectus text into claims and to run the two agents.

**Third-party assets:**
- Fonts: Fraunces and Geist, under the SIL Open Font License.
- Favicon dove: Font Awesome Free, CC BY 4.0.

## Before pressing Submit (*you*)
- [ ] Open the repository and the video link in a private window; both must open without asking for access.
- [ ] Fill in the participant details: name, email, phone, occupation, years of experience.
- [ ] Press **Submit project**. A saved draft doesn't count. The deadline is 10 October 2026, 23:59 IST.
