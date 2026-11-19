---
title: The site link graph
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# The site link graph

**Version 2.0.0 (generic edition) · 18 Nov 2026**

## Why at onboarding

From a real project: build our own map first when onboarding, like the sitemap: every internal link in and out, the
anchor words, the clusters. The sitemap lists pages. It does not say which pages are linked, from where, or with what
words. A page nobody links to, or one linked only from the menu, is weak, and you cannot see that by reading one page.

The graph is built from the **rendered HTML** of every page in the sitemap, not from the site's source code. So it
works the same for any site, and for a site of 1,000 pages: each page is read once (about 4 minutes at 8 at a time),
and inbound links are simply the outbound links turned around.

## Run it

All commands run in the project folder. Plain requests only: no browser, polite (a few at a time, a short pause,
robots.txt respected). Run it only as the setup step, a weekly refresh, or after a release.

| Job | Command |
| --- | --- |
| Map the whole live site | `growth link_graph crawl` (`--concurrency 4 --delay 0.3` is gentler) |
| Map a branch before release | `growth link_graph crawl --base http://127.0.0.1:<port>` (paths come from the live sitemap) |
| The report | `growth link_graph report --out research/link-graph-<date>.md` |
| One page: links in and out, with Search Console words | `growth link_graph page /pricing` |
| After a page changed | `growth link_graph update /pricing /blog/x` (also on every page that got a new link) |
| Before and after for a page | `growth link_graph history /pricing` |
| For the tracker dashboard | `growth link_graph export --json` (writes `inventory/link-graph.json`) |

Data: `inventory/link-graph.db` (SQLite): `pages`, `links` (source, target, anchor, zone, rel, nearest heading),
`targets` (redirect and broken checks), `links_history` (the snapshots for before and after).

## Read the report

- **Zone** says where a link sits: *body* (the page's own text), *related* (a "related" box or side box),
  *breadcrumb*, *nav*, *header*, *footer*. Only body links count for rule 88: menu and footer links are on every page
  and say nothing about this page.
- **Orphan**: no body link from another page. Split into "nothing at all" and "only menu, footer or related". **Weak**:
  only one. Fix by adding links from the strongest related pages (`growth link_map suggest <path>`).
- **Redirects linked** and **broken links**: change the link to the final address, or remove it (rule 75).
- **Same anchor words, two pages** (rule 90) and **one short anchor used by most pages** (exact-match overuse): give
  each page its own words, taken from the page's real searches.
- **Cluster health** per cluster (labels from `inventory/inventory.json`): do the spokes link up to the hub, does the
  hub link every spoke, do spokes link two siblings. Counted on body and related links only.
- The **fix list by source page** is what goes in the journal: every fix is an edit on the page that sends the link
  (`growth journal add --page <src> --tag internal-link --recheck <date> ...`).

## How it feeds the money-page job

- **Step 26a** of [money-page](money-page.md) and rule **88a**: before the link plan, run `growth link_graph page
  <path>`. It shows every link in by zone with the anchor, the source's cluster, and the page's top Search Console
  queries next to the anchors: do the anchors use what people really search?
- After release, run `growth link_graph update <path>` on the page and on each page that received a new link. The
  history keeps before and after, so the gain in body links in can be shown.
- Rebuild the whole graph weekly, or after each release (`growth doctor` row A7b turns TODO when it is 8 days old).

## Known limits

- Links added by JavaScript after the page loads are not in the HTML and are not seen. That is also what Google sees
  first, so it is the right view.
- Query strings and fragments are dropped, so `/x?cta=nav` and `/x` are one target.
- A card link takes its own heading as the anchor; a link with only an image uses the image's alt text.
- The cluster label of a page comes from the inventory (page group and pillar). Without it the first folder of the
  address is used.
