---
title: Playbook - change a page
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: change a page

**Version 2.0.0 (generic edition) · 18 Nov 2026**

## Step 0: inventory and snapshot (always first)

1. `growth inventory`: the full inventory must be current (today). It says which page group, pillar and cluster the
   page belongs to and how it compares with its siblings.
2. Money pages first: pick from the "Money pages" table in `inventory/INVENTORY.md` unless the owner names a page.
3. `growth page_snapshot <path> --task <T#> --action "<what>"`: page elements plus all its Search Console data (every
   query with clicks, impressions, click rate, position; daily; countries) and analytics data. This is the baseline;
   take it again after the change goes live.

## When to use it

A page needs one value changed, added or removed: a heading, a stat, a card, a link, a button label, an alt text. The
page is a content page, a page whose text lives in code, or a coded route (home, pricing, booking, contact). The
project's `SETUP.md` says which file renders which kind.

## Before you start

- Wording, design, the menu, the logo lockup and new sections are the owner's.
- Find the file that renders the page.
- **Design and layout files:** check first that no other agent has them open (`git branch -r`, open worktrees). Two
  agents on one file clash (rule 40).
- The conversion path stays: the project's one CTA label goes to the one conversion path (rules 32, 33). Do not change
  the CTA wording without the owner.

## Step 0b: pre-flight, then check as you go (rule 0a)

Before the first edit, `growth preflight <path> --type money|core|hub|post --key <key>` must say PASS (see
[update-post](update-post.md) step 0b). After **every** commit, run the gate on the preview and fix its FAILs before
the next edit. Nothing goes to the owner until `growth ready` says READY.

## Steps

1. **Worktree:** branch `page/<page>-<topic>`.
2. Make the one edit. Keep the structure; do not "improve" nearby text (rule 121).
3. If the page's `updated` or a hub's "last modified" date shows the change date, update it (rule 12).
4. Removing a card or a list item: check the layout does not leave a gap (count-based grids), at the widths of rule
   106 (360 to 1920).

## Checks

Only the checks the change touches (`growth checks`, rule 105), then look at the page at the widths of rule 106 (360
to 1920). Click the CTA: it must open the booking path.

## Traps we already fell into

- A heading changed and a link elsewhere used its `#anchor`.
- A price put back on a page after the owner removed it.
- More in [../lessons.md](../lessons.md).

## Done when

The live page shows the change, and the task step is ticked.
