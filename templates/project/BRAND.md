---
title: Brand, claims and positioning
version: 0.1.0
updated: <fill in: date>
owner: <fill in: who decides for the business>
---

# Brand, claims and positioning

**Fill this sheet with the owner at onboarding (flow stage A, step A2).** It holds the facts every page may state, in
one wording each, and what no page may claim. When this sheet and the page rulebook disagree on a **fact**, this sheet
wins; on **how a page is built**, the rulebook wins. Then fix the other one.

The rulebook points at section numbers of this sheet: section 1 (who we are; 1a holds the company and contact facts), section 4 (the one CTA and conversion),
section 5 (pricing words), section 6 (proof allowed), section 7 (what we never claim), section 10 (the permission
log). Keep the numbers.

Machine-readable words (the banned offer words, the words never to say, the old-brand words) also go in
`growth.json`, so the gate can check them. This sheet is the human version.

## 1. Who we are (one wording each, everywhere)

| Field | Wording |
| --- | --- |
| Business name | <fill in> |
| Category phrase | <fill in> |
| One-line hook | <fill in> |
| What it does | <fill in> |
| The author (rule 36l) | <fill in> |
| Origin story | <fill in> |

<!-- What goes in each <fill in> cell above (delete this comment when done):
  - Business name: the name as written on pages
  - Category phrase: what the business is, in the words buyers search, for example "Lawn care for homeowners"
  - One-line hook: one sentence a buyer would feel
  - What it does: two sentences, plain words
  - The author (rule 36l): the one named person every page shows in its byline: name, role, link to their author page
  - Origin story: only facts the owner approves, or leave empty
-->

## 1a. Company and contact facts

**Run `growth brand-scan` first** (it reads the terms, privacy, contact and about pages, the footer, llms.txt and the
JSON-LD, and writes `docs/brand-scan.md` with a draft of these lines). Copy what is right, keep the source in every row,
and ask the owner only for what the scan could not find or found twice with different values. A value the site does not
state stays "not found", never a guess. Source cell: the page path, or "owner, <date>".

| Field | Wording | Source |
| --- | --- | --- |
| Legal name | <fill in> | <fill in> |
| Registered or postal address | <fill in> | <fill in> |
| Governing law (terms of service) | <fill in> | <fill in> |
| Email, sales or new business | <fill in> | <fill in> |
| Email, support | <fill in> | <fill in> |
| Email, privacy or data protection | <fill in> | <fill in> |
| Email, legal | <fill in> | <fill in> |
| Email, careers or press | <fill in> | <fill in> |
| Other emails on the company's domain, and what each is for | <fill in> | <fill in> |
| Phone numbers | <fill in> | <fill in> |
| Booking link (Calendly, Cal.com, HubSpot meetings ...) | <fill in> | <fill in> |
| Social profiles (LinkedIn, X, Facebook, Instagram, YouTube, GitHub, Clutch, G2) | <fill in> | <fill in> |
| Terms of service last updated | <fill in> | <fill in> |
| Privacy policy last updated | <fill in> | <fill in> |
| Laws and standards the legal pages name (GDPR, HIPAA, SOC 2 ...) | <fill in> | <fill in> |

<!-- What goes in each <fill in> cell above (delete this comment when done):
  - Every email the scan found on the company's own domain is named here, or a line says why it is left out
    (`growth doctor` A2 checks this when docs/brand-scan.json exists).
  - Legal name: the entity named in the terms or privacy page ("... Pvt. Ltd."), not the trading name
  - Governing law: the place whose law governs the terms, as the page words it
  - Source: the page path it came from (for example /terms-of-use), or "owner, 2026-11-26"
-->

## 2. What we sell

- <fill in: the offer, one line each, in the words the site already uses>

## 3. Who we sell to

- <fill in: the buyer types, largest first: role, size, what they need>

## 4. How people buy (the one conversion)

| Field | Wording |
| --- | --- |
| The one CTA label | <fill in> |
| The one conversion path | <fill in> |
| The reason line | <fill in> |
| Call or step length | <fill in> |
| The market (also in `growth.json`) | <fill in> |
| Booking link | <fill in> |
| Other CTA wordings found on the site | <fill in> |

<!-- What goes in each <fill in> cell above (delete this comment when done):
  - The one CTA label: the exact button words, for example "Get a quote"
  - The one conversion path: the booking page, quote form or contact form the CTA goes to
  - The reason line: the one line beside the button that says what the reader gets (rule 32a)
  - Call or step length: for example "15-minute quote call"; one length everywhere (rule 4)
  - The market (also in `growth.json`): country and language, for example US, English
  - Booking link: the address a visitor books a call at, with its source page (a path), or "none"
  - Other CTA wordings found on the site: the other buttons that ask for action ("Get a free estimate", "Hire developers"), each with the pages it is on and its source (`growth brand-scan` lists them)
-->

## 5. Pricing words (state exactly these, nothing more)

- <fill in: how pricing works in words, with no amount unless the owner has approved one>
- Words that are not used until the owner says yes (for example "free", "no obligation"): <fill in>

## 6. Proof we may use

- <fill in: the proof the owner has approved, each with where it is already on the live site. If there is none, write
  "none yet".>

## 7. What we never claim

- <fill in: prices or amounts not on record, customer names, logos, quotes or results without a row in section 10,
  awards, guarantees the offer does not make, capabilities the site never states, places the business must not name
  (rule 36k).>
- Words never to use (also in `growth.json` `words`): <fill in>

## 8. Voice

- Plain, concrete, written by someone who does the work. Short sentences. No filler words (seamless, unlock, leverage,
  empower, streamline, cutting-edge, robust, world-class). <fill in: the owner's own voice notes>

## 8a. Illustration style and the brand kit

The colours, fonts, type scale, buttons, logo and tokens live in the brand kit, not here: run `growth brand-kit learn --base <preview address>`
and `growth brand-kit build`, then open `brand/brand-guidelines.html`. Change a value with `growth brand-kit set <path> <value>` (kept in
`brand/brand.overrides.json`); this sheet keeps the words and the owner's choices below.

<fill in: the style the owner picked from a board (rule 36g) and the one shared art set. Leave empty
until the owner has chosen.>

## 9. Open items for the owner

- <fill in or leave empty. Open questions also go in `docs/tasks.json` with a safe default.>

## 10. Permission log (customers we may name)

| Customer | What we may say | Who said yes | Date |
| --- | --- | --- | --- |
| <none yet> | | | |

## Claims already on the live site

<fill in at onboarding: the claims the live site already makes, each confirmed true by the owner in one answer. Rule 3
counts them as approved.>

## Change log

| Date | Version | What changed |
| --- | --- | --- |
| <fill in> | 0.1.0 | First sheet from the template. |

<!-- What goes in each <fill in> cell above (delete this comment when done):
  - <fill in: date>: date
-->
