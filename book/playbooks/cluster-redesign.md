---
title: Playbook - rebuilding a cluster
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: rebuilding a cluster

**Version 2.0.0 (generic edition) · 18 Nov 2026**

A **cluster** is one topic's pages: its main page (the money page or hub), its feature pages and its posts. For
Brightline Lawn Care, the aeration cluster is `/lawn-aeration` plus every post under `/lawn-aeration/blog`. This
playbook is for rebuilding a whole cluster so it reads as one planned set: research first, a design brief per page,
then build and release one page at a time. It also covers one guide, a "best software" list, a comparison or a hub.

The project's clusters are listed in its `SETUP.md` and `growth.json`. Posts carry original covers (one distinct
composition each); a rebuild keeps that rule. A rebuild never renames an address (rule 73).

## The order, every cluster

1. **Look at what the cluster does today.** `growth link_map check --all` for orphans and missing links, the site map
   for the list of pages (see [site-map](site-map.md)), Search Console for the cluster's searches. Write the findings
   in one page.
2. **Research before design.** One researcher per page, read only, writes `research/<slug>-research-<date>.md` (the file `ev.research-check` reads; the same name rule is in the gate, with `<slug>-audit-<date>.md` or `<slug>-review-<date>.md` for the independent review): who
   searches and why; what the top 20 results offer and the gaps none fill; a fact base read from the sources' own
   pages (claim, URL, date, confidence); every claim of the old page judged; real pain points in the readers' own
   words; ideas for interactive elements; an outline. No page is built without it (rule 27).
3. **A design brief per page**, written by the lead from that research: the reader's job, the one thing the page must
   let them do, the signature element, the layout, what is cut. Two pages of one cluster never share a signature
   element by default (rule 157).
3b. **Pre-flight per page** (rule 0a; from a real project): `growth preflight` PASS for every page before its build
   lane starts; shared problems are fixed once, for the whole cluster, first. The gate runs after every commit in each
   lane.
4. **Build** (one lane per page, see [04-lanes-and-releases.md](../04-lanes-and-releases.md)), **independent check**,
   **fix**, **release one page at a time**.
5. **The cluster's main page last, or in step.** A cluster is not done until its main page links to every rebuilt page
   and shows each one's cover (rule 144). (A lesson: a cluster's posts were all rebuilt and the hub was forgotten.)
6. **After release:** measure from the release date (day 7, 14, 28, 56).

## Rules that carry over from every cluster (never relaxed)

- Checked facts with sources and dates; never an invented number; "quote only" or "not published" is an answer
  (rules 1, 5).
- Fair to every other provider: say where a rival, or doing nothing, wins (rule 16).
- Buyer-stage order, one fact in one place, a main path a reader finishes, detail in folds (rule 28).
- One closing ask: the project's one CTA label.
- No price or amount that is not approved; no customer or result that is not approved.
- Every rebuilt page keeps its address, its date gate and its place in the sitemap.

## Rules that are new for a redesign

1. **The signature element answers the reader's real question,** in their words, before any long text.
2. **One theme per page, from the site's own look:** a page may change its section rhythm and its components, never
   the brand, the header, the footer or the logo lockup (rules 42, 43).
3. **Depth over length.** Depth means the reader's exact situation is covered, the hidden costs and traps are named,
   and the steps are real. Length is cut.
4. **The gaps list is the plan.** Each gap from the research that we can fill becomes a section or an element, or is
   written down as not filled, and why.
5. **A shared component built for one page is general** (no page names inside) and has a test (rule 52).

## Journey and conversion: written for every page before design

1. **Why they are here:** the trigger that made them search today and the job they must finish.
2. **Who they are:** the reader types, largest first, with role, size and skill.
3. **Buyer stage per type:** problem-aware, comparing, deciding, or doing a task (some readers are not buying; say so
   and serve them anyway, rule 22).
4. **The ideal customer on this page:** which type the business can really help and sell to. Name who is not a fit,
   and still serve them well.
5. **The top of the page:** the answer in the reader's words, the one control that tailors the page to them, nothing
   else.
6. **The conversion path:** the small steps (read, use a check, open the matching guide) and where the one ask
   appears, tied to the answer the page just gave. Every step is a link or a tracked click so the funnel can be
   measured (landed, used the check, reached the ask, converted).

## Guards

- The research file exists before the first build commit of a redesigned page (the lead checks).
- The page's design brief is quoted in the writer's brief.
- The tests and the build pass on every page ([release](release.md)).
