---
title: Playbook - CRO audit of a page
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: CRO audit of a page

**Version 2.0.0 (generic edition) · 18 Nov 2026**

CRO means conversion rate optimization: finding why visitors do not take the next step, and fixing it. The next step
is the project's one conversion (for Brightline Lawn Care, the "Get a quote" form). Every page that should convert
gets this audit, the same way and at the same depth, then a separate fix pass, then the normal test and release.

## Step 0: inventory and snapshot (always first)

1. `growth inventory`: the full inventory must be current (today). It says which page group, pillar and cluster the
   page belongs to and how it compares with its siblings.
2. Money pages first: pick from the "Money pages" table in `inventory/INVENTORY.md` unless the owner names a page.
3. `growth page_snapshot <path> --task <T#> --action "<what>"`: page elements plus all its Search Console data (every
   query with clicks, impressions, click rate, position; daily; countries) and analytics data. This is the baseline;
   take it again after the change goes live.

## Order

Audit the pages in the order of their readers (visits first, from analytics), starting with the money pages. The audit
is **read only**. The fix pass is a separate job on its own branch.

## The audit, in nine steps

1. **What is on the page now.** Title, description, H1, headings, structured data, dates, length (words, screens at
   1280 and 390), images and product pictures, forms, every call to action with its place, and fold by fold (what each
   screen shows, its ask, its proof). Use the page on the local server or the live page, at both widths.
2. **The business behind it.** What the business sells that fits this page and the proof allowed, from `BRAND.md` and
   `SETUP.md`. What may not be claimed (`BRAND.md` "never claim" list, and below).
3. **Why people land here.** The searches that show this page (Search Console), with impressions, clicks, click rate
   and position for the last 28 and 90 days; the top 10 results for the main search and what type of page each is;
   where we rank; the promise of the search against the first screen. Paid search-result tools: check your saved
   results first and price the call before making it (never pay twice for the same data).
4. **Who the visitors are.** Three or four types of reader with role, size, what they need, how far along they are,
   their questions, their doubts, and the next step each is ready for. Say which type is the most common and which is
   the most valuable. Back each with evidence (search words, a real forum quote with its link), never a guess.
5. **CRO diagnosis.** A 1 to 5 score for: intent match, value in 5 seconds, relevance to this reader, scannability,
   fit of the ask to the reader's readiness, trust and proof, friction (clicks to convert), objection handling, phone.
   The top five reasons it does not convert.
6. **Competitors.** The pages that win the searches: their angle, depth, proof and ask; what we lack against them;
   what none of them answers (our opening). Read each page in full, one at a time. A page behind a bot check is not
   read by any route; note it and move on.
7. **Gaps and freshness.** Each gap with today's fact and its source (read today).
8. **The rebuilt page, fold by fold.** The order and why; per fold the job, headline options, the component, the ask
   and the proof.
9. **Action plan.** Quick wins, medium jobs, big bets; what to measure afterwards.

Output: a file in the project's `research/` folder, named `<page>-cro-audit-<date>.md`.

## What a fix pass may take from an audit

Take: putting the search promise on the first screen; routing by situation (which service, which reader); an ask that
fits the reader's readiness; direct answers that AI answers can quote; fresher dates; corrections with sources.

## Never take (whatever an audit suggests)

Invented customers, reviewers, credentials or logos; case studies, names or results the owner has not approved; rating
or review structured data when there are no real ratings on the pages; prices or time ranges the owner has not
approved; promises the offer does not make (a free trial, "no obligation", a guarantee) until `BRAND.md` allows them;
capability claims beyond `BRAND.md`; facts read through a bot check; other companies' prices shown as if they were
yours.

## Done when

The audit file is written, every number has its date and source, the top five fixes are in the task list with who
approves, and nothing on the site was changed.
