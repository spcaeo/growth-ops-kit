---
title: Playbook - fix a fact
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: fix a fact

**Version 2.0.0 (generic edition) · 18 Nov 2026**

## When to use it

- A fact about another company on the site is wrong or out of date: a price, a plan, a limit, a feature.
- A fact about the business reads two ways across the site.
- A reviewer, an audit or the owner flagged a claim.

## Before you start

- **A fact about another company:** open its official page today. Copy the exact wording and the URL (rule 5).
- **A fact about the business:** the only wording allowed is in `BRAND.md`. If it is not there, stop and ask the owner
  through the lead (rules 1, 3, 9). Never grow a capability claim, and never bring back a price the owner removed.
- **Find every place, not only the one reported.** The fact may sit in posts, pages, shared page text and components:
  search the whole site source for the wording. Check the content files and any file that holds page text in code.

## Step 0b: pre-flight, then check as you go (rule 0a)

Before the first edit, `growth preflight <path> --type <type of each page> --key <key>` must say PASS (see
[update-post](update-post.md) step 0b). After **every** commit, run the gate on the preview and fix its FAILs before
the next edit. Nothing goes to the owner until `growth ready` says READY.

## Steps

1. **Worktree:** branch `fix/<topic>`.
2. Edit each file. In a post, the FAQ is part of the body, so one edit fixes the text and the FAQ data (rule 96). On a
   page whose FAQ lives in code, edit the answer there.
3. Set `updated` on every content file you changed (rule 12).
4. **Add a guard so the old wording cannot come back** when the same fact keeps going wrong: a small test that fails if
   a banned phrase appears in the content (rule 110). Add the rule to the page rulebook (or the project's own rules)
   in the same change.

## Checks

```
growth checks                          # only the checks this change touches (rule 105)
grep -rn "<old wording>" <site source>   # must print nothing
```

After release, search the live page: fetch it and count the old wording; it must be 0.

## Traps we already fell into

- Fixing the page that was reported and missing the same fact on others.
- A scripted find-and-replace that changed a second, different line. After any scripted replace, run `git diff` and
  read every changed line.
- Choosing between two figures yourself. Ask the owner (rule 9).
- More in [../lessons.md](../lessons.md).

## Done when

The search finds no old wording in the repo or on the live page, a guard exists, and the release is confirmed live.
