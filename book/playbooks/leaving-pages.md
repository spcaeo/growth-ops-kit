---
title: Playbook - pages people leave
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: pages people leave

**Version 2.0.0 (generic edition) · 18 Nov 2026**

## When to use it

Analytics show a page where many visitors leave without a next step, or the owner asks why a page does not bring
conversions. Diagnosis first; changes second.

## Evidence first

1. The page's numbers: Search Console for the search side; your analytics connector for the visit side; a session
   recording tool, if the site has one, for how people move. Note dates and the length of the window.
2. Where visitors come from, how far they read, where they go next.
3. The page itself, in a browser at phone and desktop widths: how many words, where the asks sit (first screen,
   middle, end), which links lead on, whether a box is off topic for the reader's question.
4. Does the page answer the question it ranks for? Compare its title with the searches it shows for (rule 18).

Analytics are read only. Never change tracking settings without the owner.

## The proposal (what the owner approves)

One row per page: the page, the evidence (numbers with dates), what you think is wrong, the proposed change in exact
words, and which file it touches. Put it in the task list under "waiting for the owner".

## Once approved

- Wording on pages: [change-a-page](change-a-page.md); on posts: [update-post](update-post.md).
- A new component or a new pattern: test it on one page first.
- Measure again two to four weeks after the release with the same sources, and write the before and after in the task
  step.

### Before the edit (rule 0a)

Run `growth preflight` on the page and fix what it lists first; gate after every commit; the owner sees it only when
`growth ready` says READY.

## Done when

The proposal is in the task list with its evidence. After approval and release, the before and after numbers are
written down.
