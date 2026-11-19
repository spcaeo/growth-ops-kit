---
title: Playbook - update a post
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: update a post

**Version 2.0.0 (generic edition) · 18 Nov 2026**

## When to use it

A post that is live needs new facts, a new section, a removed section, a new cover, or a full refresh. One wrong fact
alone is [fix-a-fact](fix-a-fact.md).

## Before you start

- **The address stays the same.** The slug and its group never change (rule 73). The title, the meta title, the
  description and the canonical of a live page change only with the owner's OK (rule 74).
- Read the file's history so you build on it: `git log --oneline -- <file>`.
- Re-check every fact about another company on its official page today, not only the one you came to change.
  Comparison posts carry "as of <month year>" dates; refresh the dates you re-checked (rule 5).
- Run `growth link_map inbound <path> --repo <worktree>` so you know who links in and with which words. Keep those
  words working.

## Step 0b: pre-flight, then check as you go (rule 0a)

Before the first edit, `growth preflight <path> --type post --key <key>` must say PASS: shared site problems that
would fail the page are fixed first (their own commit), the planning evidence for this page type exists, and
`research/<key>-checkpoints.md` lists every check by when it runs. Give the helper that file with its generated brief
(`growth brief`). After **every** commit, run the gate on the preview and fix its FAILs before the next edit; the end
is a confirmation, not a repair. Nothing goes to the owner until `growth ready` says READY (the golden rule).

## Steps

1. **Worktree:** branch `article/<slug>-update` (or `fix/` for a small correction).
2. Edit the content. Set `updated` to today: it drives the byline date, the structured data and the sitemap
   `lastmod` (rule 12). **Never change `date`** (the publish day) on a live post: moving it forward can hide the post
   at the next build.
3. A removed section: check no other page links to its heading (`#anchor`). A heading's anchor is its text, lower
   case, with hyphens (rule 85).
4. A new cover: [images](images.md).
5. A post taken down: mark it as a draft and add its old address to the redirect list (a 301 to the page that took its
   topic, or a 410). See [lost-pages](lost-pages.md). That needs the owner's yes.

## Checks

Everything in [new-post](new-post.md), plus: search the whole site source for the old wording; nothing is left.

## Traps we already fell into

- Moving `date` forward to "refresh" a post: it disappears. Use `updated`.
- Moving a post to another group changes its address. That is a redirect job with the owner's yes.
- A post refreshed but its excerpt and meta description still describe the old version.
- More in [../lessons.md](../lessons.md).

## Done when

The live page shows the change, `updated` shows the day it was released, every check passes, and the task step is
ticked.
