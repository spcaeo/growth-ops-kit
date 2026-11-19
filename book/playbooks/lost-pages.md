---
title: Playbook - lost pages and redirects
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: lost pages and redirects

**Version 2.0.0 (generic edition) · 18 Nov 2026**

## When to use it

- An old address people or search engines still ask for answers 404.
- A page is taken down, or a post is pulled.
- Search Console lists "not found" or "page with redirect" addresses.
- `growth link_map check --all` flags `to-redirect`, `to-gone` or `to-unknown`.

## How redirects work (find the project's own place in `SETUP.md`)

A site keeps one list of removed and redirected addresses: addresses that answer **410** ("gone for good"), addresses
that answer **301** to a new page, and any pattern rules. Two rules hold on every site:

- **410, not 404,** for content that is gone for good (rule 77); **301 only to a relevant page, never to the home page**
  (rule 75); a redirect to a planned page ships together with that page.
- A draft post is never built, so its old address is a 404 unless it is listed.

## Before you start

- Find what the address was: search the source for the old slug, and `git log --oneline -S"<old slug>"`.
- **Pick the page that took its topic**, not the home page. Search engines treat a mass redirect to the home page like
  a 404. Use a 410 when nothing covers the topic.
- An address only a bot ever asked for gets nothing.
- Every redirect or 410 needs the owner's yes: it changes what the live site does for search engines.

## Steps

1. **Worktree:** branch `fix/redirects-<topic>`.
2. Add one line to the right list, with a one-line comment saying why and who decided and when.
3. If the page is also being pulled, mark it as a draft in the same commit.
4. Fix every internal link that points at the old address (`growth link_map check --all` lists them) so no page links
   to a redirect (rule 75).
5. One hop only: the target must itself be a live page that does not redirect.

## Checks

```
growth checks
growth link_map check --all --include-scheduled --repo <worktree>   # no to-redirect, to-gone or to-unknown
```

After release, request each old address once on the live site:
`curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' <site>/<old>` must print `301` and the new address (or `410`).

## Traps we already fell into

- A target that is itself redirected (a chain). Keep one hop.
- A redirect to a page that was not live yet.
- An internal link left pointing at the old address.
- A pulled cluster whose posts were all sent to the home page: it looked like a mass 404 to search engines.
- More in [../lessons.md](../lessons.md).

## Done when

Each old address answers 301 or 410 on the live site, `growth link_map check --all` shows no moved links, and the run
is noted in the task step.
