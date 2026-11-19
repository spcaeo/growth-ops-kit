---
title: Playbook - the address map and the sitemap
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: the address map and the sitemap

**Version 2.0.0 (generic edition) · 18 Nov 2026**

What addresses a site has, where each kind of page comes from in the site repo, how the XML sitemap is built, how
redirects work, and what to do when an address changes. Every project writes this down once, in its own `SETUP.md`
(or a `site-map/` note), and keeps it current. The numbers in it come from commands, never from memory.

## 1. Write the short version down (once, at onboarding)

For Brightline Lawn Care the short version could read:

- **N addresses** are in https://brightline.example/sitemap.xml (date): the home page, the blog list, pricing, the
  booking page, the contact page, the service pages, the content pages, the posts. One language, no regions.
- The sitemap is **one file** or an index, built by `<file>` from the content files.
- Addresses have **no trailing slash** (or always one: the site's one style, rule 80). The scheme is **frozen**
  (rule 73): posts at `/<cluster>/blog/<slug>`, service pages at `/<slug>`.
- `robots.txt` allows everything on production and points to the sitemap. On any preview it disallows everything.
- Whether an `llms.txt` exists (the owner decides, rule 148).
- A page is in the sitemap only when it is live: not a draft, and its `date` has arrived.

## 2. The map of the site

Make one table of page types: the page type, its address, the file that makes it, and where its content comes from.

| Page type | Address | Made by | Content comes from |
| --- | --- | --- | --- |
| Home | `/` | the home route | the code |
| Service page (hub, money page) | `/<service>` | the page route | the content file or the page's data file |
| Post | `/<cluster>/blog/<slug>` | the post route | a content file with its cluster |
| Core content page | `/<slug>` | the page route | a content file |
| Blog list | `/blog` (later pages `/blog/page/<n>`) | the list route | all live posts |
| Booking, contact | `/book`, `/contact` | their routes | an embed or a form |
| HTML sitemap, feed | `/sitemap`, `/rss.xml` | their routes | the content |

Also record: which key in the front matter decides the address (`slug`, a cluster key), which decides whether the page
is live (`draft`, `date`), and the one module that reads the content files (rule 104).

## 3. The XML sitemap

- What it lists, in order, and how each page's `lastmod` is set. The rule for writers: **the `updated` date is the
  sitemap's `lastmod`** (rule 12). Change it when you change a page for real; do not touch it for a typo. A hub's
  "last modified" that is set by hand must be bumped when the hub changes.
- It lists only pages you want as search landing pages (rule 87): status 200, indexable, its own canonical.
- Check it: `growth tech_seo_check --site-scan` (MAP-01 to MAP-14) and compare the count before and after a change.

## 4. Redirects

One list holds the removed and moved addresses (rules 75, 76, 77). The mechanics (which file, which middleware) go in
`SETUP.md`. How to change one: [lost-pages](lost-pages.md).

## 5. When an address changes

1. Do not, unless the owner says so (rule 73).
2. If it must: one 301 to the final address, every internal link updated, the sitemap checked, the old address
   requested once on the live site, and the journal told.

## 6. Refresh the list

Rebuild the map after any release that adds or removes a page: `growth inventory` (every URL with its page group,
type and numbers) and `growth link_graph crawl`. A drift between the sitemap count and the inventory count is a
finding.
