---
title: Playbook - new blog post
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: new blog post

**Version 2.0.0 (generic edition) · 18 Nov 2026**

Every post is a content file on a branch of the site repo. The steps below wrap that, plus the extra files a post may
need so the site's tests pass (cover entries, hub lists). `SETUP.md` of the project says where each lives. The queue
route is in [release](release.md).

## When to use it

A post that does not exist yet. A post that exists gets [update-post](update-post.md); one wrong fact alone is
[fix-a-fact](fix-a-fact.md).

## Before you start

- A task line: working title, the cluster (for Brightline Lawn Care: mowing, aeration or leaf clean-up), the search it
  answers, its sources, and the pages it links to and from. **The owner approved the topic.**
- Search the site first for the main keyword. If a post already covers the topic, this is an update. Two posts on one
  question compete with each other (rule 19).
- Pick the cluster. A new post goes in its cluster's address group (rule 73). A post that fits no cluster goes to the
  owner first.
- The date: today, or the day it should go live. The project's daily limit (for example two a day) is in `SETUP.md`.

## Step 0b: pre-flight, then check as you go (rule 0a)

Before the first edit, `growth preflight <path> --type post --key <key>` must say PASS (see
[update-post](update-post.md) step 0b). After **every** commit, run the gate on the preview and fix its FAILs before
the next edit. Nothing goes to the owner until `growth ready` says READY.

## Steps

1. **Worktree:** branch `article/<slug>`. The slug is part of the address and is frozen once live: lower case, hyphens,
   no dates, short and descriptive.
2. **Front matter** (copy a recent post): title, slug, cluster, author and role (rule 36l), `date` (quoted
   `'YYYY-MM-DD'`), `updated` (same as `date` at first), excerpt, tags, cover and its alt text, `draft: false`, meta
   title, meta description (rules 81, 82), share image; the rest empty. Keep `canonical` empty unless the owner says
   otherwise.
3. **Body.** The reader's question answered in the first paragraph (rule 18). Headings are `##` (each becomes a
   contents entry and an anchor, rule 53). Every fact about another company comes from that company's own page, with
   the month and year read ("as of August 2026"), and the post says plainly where a rival or "do nothing" wins. Every
   fact about the business comes from `BRAND.md` in its wording. **No price, customer name, result or number without
   the owner's approval** (rules 1, 2, 3). Finish with one ask through the shared component (rule 136), using the
   project's one CTA label.
4. **FAQ (optional).** A FAQ section with one heading per question becomes FAQ structured data. The answers must be the
   visible text of the page (rule 96); never the same question twice.
5. **Links** ([internal-linking](internal-linking.md)): a link up to the cluster's main page, two or three links to
   sibling posts of the same cluster, and the ask. Link from sentences that already talk about the target (rule 89).
   A link to a post that is not live yet shows as plain text until it is, so check the order things go live in.
6. **The files a post needs besides the content file.** Check the project's tests. Typically:
   - an artwork entry and the pictures (rule 61, [images](images.md)): every post owns its own picture;
   - a cover entry, and the generated cover and share card;
   - the post added to its cluster's main page list, so that page links to it (rule 54). Update that page's "last
     modified" date when its page changes.
7. **Hand over** the list of sibling changes: older posts that should link to the new one
   ([internal-linking](internal-linking.md) part C).

## Checks

```
growth checks
growth link_map check /<cluster>/blog/<slug> --repo <your worktree>   # exit 1 on any link flag
growth gate page /<cluster>/blog/<slug> --url <local URL> --repo <worktree> --type post
```

Then open the page on the local server at the widths of rule 106 (360 to 1920) and read it. The page must show its
cover, contents, FAQ and the ask. Close the browser.

## Traps we already fell into

- "Missing original artwork" in the tests: the post had no artwork entry or pictures. Add them in the same commit.
- An unquoted date. Quote it. `updated` before `date` fails the build.
- A `date` in the future on a post that should be live: the date gate hides it.
- A post merged to the queue branch without its pictures: the day's publish fails and that day's post waits.
- A slug typed wrong and published: the address is frozen. Fix it only with the owner, with a redirect
  ([lost-pages](lost-pages.md)).
- More in [../lessons.md](../lessons.md).

## Done when

The post is live at its address, it is in the sitemap, its cluster page lists it, two older posts link to it, the task
step is ticked, and the day-7 look is booked ([release](release.md) "Measure").
