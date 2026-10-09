# Submission form answers (SerpApi India Hackathon 2026)

One section per field of the submission form, ready to paste. Fields marked **you** need your own details.

## Lead participant
- **Name:** PHILIP SIMON DEROCK (already filled)
- **Email:** already filled
- **Mobile number, occupation, years of experience:** you

## Project name
Quaoar

## Track
Commerce & Market Intelligence

The track covers finance tools for analysts. Among the public submissions found, no other entry checks IPOs or prospectuses. AI Agents also fits, through the two bounded agents. Either way, the overall prizes are judged across all tracks.

## Public GitHub repository
https://github.com/simon-derock/quaoar

## Demo video
**You:** the unlisted YouTube link to `results/video/quaoar-demo-1080p60.mp4`.

It meets every rule:
- **Length:** 2 min 12 s, under three minutes.
- **Running locally:** a screen recording of the project on this laptop. It shows the CLI installed with curl, a live scan, proof, the AI agent, a control case, then the local website and docs.
- **Core functionality:** all of it is shown working.
- **Subtitles:** yellow subtitles explain each step.
- **Music:** public domain (see the end of this file).

## Project description
Quaoar checks an SME IPO before you apply. It reads the company's prospectus, picks out the claims that can be checked, and checks each one against public search results:
- the vendor quoting for the IPO money: on the company registry, active, and with paid-up capital in proportion to the quote;
- the company's offices and factory;
- the lead manager's SEBI record;
- court matters the prospectus doesn't disclose;
- dated news.

Every line of the resulting card says checks out, doesn't match or couldn't find, with the source and its SerpApi search id. Fixed rules set every status. It never gives a verdict on the company and never gives investment advice.

It is for retail investors applying to SME IPOs on NSE Emerge and BSE SME. Applications there cost a lakh or more, and the companies are small and little known. It is also for the analysts and journalists who read these prospectuses.

Why it is useful: in 2024 an investors' group noticed, by hand, that the software vendor named in Trafiksol's prospectus had not filed accounts. SEBI found the vendor's office locked, and the IPO money was refunded. Quaoar flags that vendor automatically: it quoted ₹17.70 crore against ₹1 lakh of paid-up capital, 1,770 times.

Two AI agents work on a short leash:
- **The Investigator** fills evidence gaps during a scan.
- **The Analyst** answers plain-language questions about a card, citing its lines.

Code checks every citation and every number before an answer is shown. On three ordinary companies used as controls, one was flagged, over a real 2021 SEBI order about its lead manager.

You can use it four ways: a one-line install (`curl -fsSL quaoar.philipsimonderock.com/install | sh`), a terminal anyone can talk to, a web console, and an MCP server with an agent skill for your own agent. It has 950+ tests and CI.

## How the project uses SerpApi
SerpApi is the product's only window on the outside world; without it there is no check. Every search goes through one client with a query guard, a cache, a credit budget and key rotation, and every card line keeps its SerpApi search id so anyone can repeat it.

Engines used:
- **DuckDuckGo, site-restricted:** company-registry pages (Zauba, Tofler, InstaFinancials) for each vendor's CIN, status and paid-up capital; SEBI orders naming the lead manager or its past issues; Indian Kanoon and IBBI for court and insolvency matters. A probe showed Google ignoring `site:`, which is why these use DuckDuckGo.
- **Google Maps:** whether the vendor and the company's office or factory exist and are open, and whether a "factory" is listed as a residence.
- **Google News:** dated adverse coverage before the prospectus date. Evidence is read as of that date, so later news cannot change the card.
- **YouTube:** promotion volume around the IPO, shown as context, never counted.
- **Google:** the agents' last resort.

Why the data matters: a prospectus is the company's own account. Search results are the outside world's. A vendor whose registry page shows ₹1 lakh of capital, or an office Maps lists as closed, is a fact an investor can verify in seconds with the link. A fresh scan uses about 12 to 37 searches; repeats are free from the local cache.

## AI tools used
- **Claude Code (Anthropic):** helped write the code, tests and documentation, and design the website.
- **Cohere `command-a-03-2025` through PydanticAI:** used inside the product to read prospectus sections into structured claims and to run the two agents.

The models never set a status; fixed rules do.

## Additional team members
None.

## How did you hear about the hackathon?
**You:** pick the option that applies.

## Checkboxes
- **"This project existed before the hackathon":** leave unchecked. It is a new project; the first commit is on 2026-10-08.
- **Links tested in an incognito window:** tick only after opening the repository and the video link in a private window and confirming both play without asking for access.
- **Rules, Terms & Conditions:** tick after reading them.
- Then press **Submit project** (a draft doesn't count) before 10 October 2026, 23:59 IST.

## Credits for assets in the video and site
- **Music:** Beethoven, Symphony No. 1 in C, I. Adagio molto – Allegro con brio, performed by the Chamber Orchestra of the United States Marine Band (2019). Public domain as a work of the U.S. federal government; [Wikimedia Commons file](https://commons.wikimedia.org/wiki/File:Symphony_No._1_in_C_-_I._Adagio_molto,_Allegro_con_brio_-_Chamber_Orchestra_-_United_States_Marine_Band.opus).
- **Fonts:** Fraunces and Geist, under the SIL Open Font License.
- **Favicon dove:** Font Awesome Free, CC BY 4.0.
