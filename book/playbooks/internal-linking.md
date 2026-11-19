---
title: Playbook - internal links
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: internal links (structure, rules, checks, and the link plan for a page)

**Version 2.0.0 (generic edition) · 18 Nov 2026**

From a real project: "Based on clusters and semantic SEO principles, you have not optimized internal linking from GSC
data, prompts and content ... these need to be documented for each page we want to optimize, so when we reach that
page we have it."

This is the one home for internal links: how a site links (part A), the rules and the checks that guard them (part B),
how to make any link edit (part C), the job for one page you want to rank: which pages should link to it, with which
words, from which sentence, filed on the page it must be added to (part D). Every check is a command:
`growth link_map check <path>` (one page) or `check --all` (the site) exits 1 on any flag, and the rule gate
(`growth gate page`, rules 75, 88, 88a, 90) runs it.

## In short

- A **cluster** is one topic: a **hub** (the main page, which is often also the money page) and its **spokes** (the
  posts and feature pages of that topic). The clusters are in `growth.json` (`silos`). For Brightline Lawn Care: hub
  `/lawn-aeration`, spokes `/lawn-aeration/blog/<slug>`.
- Spokes link **up** to the hub, in their text. The hub links **down** to every spoke. Spokes link **across** to two
  or three siblings. Links to another cluster only where the reader needs that other topic.
- A money page needs **links written in the text of other pages** ("body links"). The menu, footer and breadcrumbs are
  on every page and count for little. Rule 88: at least two content links in; for a money page, every spoke of its
  cluster plus the strongest pages outside it that talk about its subject.
- **Link words come from what people search.** Each link uses one of the page's real search phrases from Search
  Console, and **no two pages use the same words** for it (rule 90). Vary them.
- **Strongest pages first.** A link from a page Google already shows a lot (impressions, clicks) passes more than one
  from a page nobody sees.
- **The plan is stored in the journal** on every source page, so whoever opens that page later finds the link waiting.

## Words used here

| Word | Plain meaning |
| --- | --- |
| Internal link | A link from one page of the site to another page of the same site. |
| Anchor text (link words) | The words a reader clicks. Search engines read them as "what the target page is about". |
| Hub | The main page of a cluster. |
| Spoke | A post or feature page of the cluster. |
| Orphan, weak page | An orphan has no links in from other pages. A weak page has only one. |
| Redirect (301), gone (410) | An old address that sends the visitor to a new one, or says the page was removed for good. |
| nofollow | A label on a link that says "we do not vouch for this site". |
| Date gate | A page whose `date` is in the future does not exist on the live site until its day. |

## A. How a site links

### A.1 Links the templates add by themselves

You do not write these, and they cannot fix a weak page.

| Where | What it links |
| --- | --- |
| Top menu and footer | the main pages, pricing, blog, the booking page, about, legal |
| HTML sitemap (if any) | every hub and page |
| Breadcrumbs | home, the hub, the page |
| A hub's guide list | the posts of that cluster, hand-ordered |
| Related stories at the end of a post | a few posts, ranked by cluster, shared topics and nearness in date |
| Blog list | every post, with filters |

The project's `SETUP.md` says which files build these.

### A.2 Links written in the text

These you control. Posts write them in Markdown, `[words](/path)`. Count them with `growth link_map check --all` and
`growth link_graph report`. Flags to know: orphan, weak, no-hub, not-on-hub, siblings under 2, dead-end links,
`dup-anchor` (the same words linking to two pages).

## B. The rules and the checks that guard them

| Rule | What it says | Guarded by |
| --- | --- | --- |
| Hub | A post links up to its hub, in its text: `[words](/<hub>)`. | the site's hub test (if the hub is marked "spokes linked"); `link_map check` `no-hub` |
| Hub list | Every post of a cluster is in its hub's guide list. | `link_map check` `not-on-hub` |
| Siblings | A post links to two or three sibling posts of its own cluster, in sentences that already talk about them. | `link_map check` `siblings<2` |
| Both ways | A new post gets links in from older posts. Every post has at least two other pages that link to it (a hub list counts). | `link_map check` `orphan`, `weak` (rule 88) |
| The ask | Posts end with one link through the shared ask card. | review (rule 136) |
| One words, one page | The same words never link to two different pages. | `link_map check` `dup-anchor` (rule 90) |
| No dead ends | Never link to a redirect, a removed page or a draft. | `link_map check` `to-redirect`, `to-gone`, `to-not-live`, `to-unknown` (rule 75) |
| Frozen addresses | Link to a page by its current address. The URL scheme never changes. | rule 73 |
| Outside links | Name the source in the words ("the agency's guidance"), never "source" or "click here". Outside links carry `rel="noopener"` and, where you do not vouch for them, `nofollow` (rule 91); let the site's code add it, never by hand. | the build |
| Facts | Check a page is true before you link to it, and cite the other company's own page when a post states a fact about it. | review |

### Links to posts that are not live yet

Many sites turn a link to a post that exists but is not live (a draft, or dated for later) into **plain text** on the
live site, and back into a link once the target is live. So you may write the link early, but until the target is
live the reader sees no link. Link order matters when you publish a set of posts over several days.

### B.1 Outside links

- Do not add `rel` or `target` by hand, unless the owner decides a particular outside link should be followed.
- Cite the other company's own pages for facts about it (price pages, help pages), with the month and year read.
- A link to a government or standards page is wanted in a post that states a rule or interval.

### B.2 Anchor text, how many links, and where

- **Words.** Words that already sit in a sentence about the target. Describe the target ("lawn aeration prices",
  "when to aerate a lawn in autumn"). Never "here", "read more", "click here" or a bare URL.
- **One set of words, one page.** Before you link words, search for them in the content. If they already link to
  another page, choose other words. `growth link_map inbound <path>` prints every link in with its words; `check
  --all` lists every shared anchor (`dup-anchor`).
- **Vary the words** for one target. If most links to a page use the same words, reword some.
- **How many.** No fixed number in the code. The plan: one link up to the hub, two or three to siblings, one ask.
- **Where.** In body text, early enough to be read, in a sentence that is already about the target. Not in a heading.
  Do not stack links in one sentence.
- **Address style.** The site's own links are paths in the site's one style (rule 80), no full domain.
- **No tracking tags** (`utm_...`) on internal links (rule 34).

### B.3 Never link to a redirected or removed address

Old addresses are listed in the site's redirect config. A link to one works for the reader but wastes search value and
may end on the home page. Before you link an address, check it is not in that list. `growth link_map check <path>`
does it for you and flags `to-redirect` or `to-gone`. How to add one: [lost-pages](lost-pages.md).

## C. Making any link change

1. **Worktree and branch** `fix/links-<topic>` ([agent-steps](agent-steps.md)).
2. Edit the content file (or the hub's guide list). Link words that already exist; add one short sentence only when no
   sentence fits.
3. A link-only edit keeps `updated` and `date` as they are (a new link is not a content change; the sitemap date must
   not move for it). Change `updated` only when the text itself changes.
4. Run the checks (C.1). Open the page and click the new link.
5. A change on another lane's page goes on that lane's "sibling changes" list ([04-lanes-and-releases.md](../04-lanes-and-releases.md)).

**Worked example (not applied).** `link_map check` flags `/lawn-mowing/blog/mowing-height-guide` as `no-hub`: it never
links to `/lawn-mowing`. Find a sentence in that post that already names the service, for example "weekly lawn mowing
schedules", and link those words: `[weekly lawn mowing schedules](/lawn-mowing)`. Make sure those words do not
already link to another page.

### C.1 The checks that guard links

| Check | Command | What fails | Time |
| --- | --- | --- | --- |
| Link flags, one page | `growth link_map check <path> [--repo <worktree>]` | exit 1 on any flag: orphan, weak, no-hub, not-on-hub, siblings<2, to-redirect, to-gone, to-not-live, to-unknown, dup-anchor | 0.1 s |
| Link flags, the site | `growth link_map check --all [--repo <worktree>]` | the same, for every live page | 0.1 s |
| Links in and out of one page | `growth link_map inbound <path>` / `outbound <path>` | nothing fails; every link with its words and where it sits | 1 s |
| The rule gate | `growth gate page <path> --url <local url> --repo <worktree> --type <type>` | rules 75, 88, 88a, 88b, 89, 90 among all the page rules | seconds |
| The site's own tests | the project's test command | a hub missing from the sitemap; a spoke-linked hub with a post that does not link back | seconds |
| The whole site builds | the project's build command | bad front matter, a missing cover | minutes |

`orphan` and `weak` count content links only (body text and hub guide lists), not the menu, footer, breadcrumbs or
related cards, so a page can be reachable and still be weak. That is the point: it shows what the writing does for a
page. Only live posts count (not drafts, not future-dated) unless you add `--include-scheduled`.

### C.2 Small link jobs

#### C.2.1 Link a new post in

1. **Place it.** Its cluster. Search first for a post on the same question: update it instead.
2. **Links out, in the new post's own text:** one to the hub, two or three to siblings, one ask.
3. **Check each target and its words.** The target is live and is not a redirect (B.3). The words are not already used
   for another page (B.2). The target is true today.
4. **Add it to the hub's guide list.**
5. **Links in from older posts** (both ways): for the hub's most relevant posts, find a sentence that already talks
   about the new post's subject. List these as sibling changes; the lead makes them as one `fix/links-<new-slug>`
   change, because they touch other lanes' files.
6. **Check:** `growth link_map check <new path>` exits 0 (links in from at least 2 pages, no flags); then the tests and
   the build.

#### C.2.2 Fix a weak or orphan page

1. Find them: `growth link_map check --all` (orphan, weak).
2. Decide whether the page should rank. About, privacy and terms pages are reached through the menu and footer by
   design. A post or feature page needs written links in.
3. See who links to it now: `growth link_map inbound <path>`.
4. Find two or three posts whose text already talks about it: same cluster first, then another cluster only where the
   reader needs it.
5. Edit each, part C. Re-run `check <path>`.

#### C.2.3 Fix a missing hub, hub list or sibling link

Same as C.2.2, but the edit goes on the flagged page itself (`no-hub`, `siblings<2`) or on the hub's guide list
(`not-on-hub`).

### C.3 Do and don't

| Do | Don't |
| --- | --- |
| Link words that already sit in a sentence about the target. | Link "here", "read more", "source" or a bare URL. |
| Link up to the hub, across to 2 or 3 siblings, and end on the ask. | Leave a new post with no links in from older posts. |
| Use the target's current address, in the site's one style. | Link an old address, a redirect, or the full domain. |
| Search the words first; one set of words for one page. | Reuse the same words for two pages. |
| Name an outside source in the link words. | Write `rel` or `target` by hand. |
| Run `link_map check`, the tests and the build. | Trust "in 1" as proof a page is fine; read its links. |

## D. The link plan for one page

### The tool: `growth link_map`

Read-only on the site, standard library only, about 1 second. Run it in the project folder. `--repo` points at a
branch worktree when the page is being rebuilt there (the default is `growth.json` `site_repo`).

```
growth link_map inbound  /lawn-aeration [--repo ../wt-lawn-aeration-v2]
growth link_map outbound /lawn-aeration
growth link_map orphans                     # pages with fewer than 2 content links in (rule 88)
growth link_map suggest  /lawn-aeration [--limit 25] [--research 'research/*aeration*']
growth link_map check    /lawn-aeration     # exit 1 on any flag (C.1)
growth link_map check --all
(--json on any command; --include-scheduled counts future-dated posts)
```

What it reads: the content files, the coded pages and the components they import, the menu, the footer, the
breadcrumbs and the "related stories" box. Redirects come from the redirect config: a page that now 301s somewhere is
gone (never a source, never a target), and a link to an old address counts for its final page. Search Console data
comes from the page tracker's database, read-only (when connected).

Every link gets a **where**: `body` (the page's own text), `hub-list` (a hub's guide list or shelves), `nav`,
`footer`, `breadcrumb`, `related`.

How `suggest` scores a page that does not link yet (the scores are printed, so a person can check them):

| Signal | What it looks at | Points |
| --- | --- | --- |
| (a) cluster | same cluster as the target; an old generic post in the topic | 3; 1 |
| (b) Search Console | the source ranks for the target's own searches (overlapping words) | log2(1 + impressions/5), max 4 |
| | the source's own strength, 90-day impressions | log10(1 + impressions)/1.5, max 2 |
| (c) the text | it already says a target search phrase without a link; or names the business and a topic word | 3; 1.5; topic word only 1 |
| (d) buyer questions | AI prompts and buyer questions in the research files that the source's title and headings answer | 0.5 each, max 2 |

The target's search phrases are its Search Console queries **plus the queries of pages that now 301 into it** (their
searches move with them), plus the dossier's "Own" list. Anchors are handed out most impressions first; a phrase
already used for the target, or used for any other page, is skipped.

It also prints **anchor fixes** (links already there with repeated words or no search phrase) and **outbound gaps**
(a hub's spokes it does not link; a spoke's missing hub and siblings).

The tool finds candidates; a person decides. It cannot judge meaning: a word that means two things matched the wrong
topic once. Read every sentence it prints.

### Steps for one page

1. **Measure.** `inbound <page>` on the live clone and on the branch. Write down body links (distinct pages), the
   different link words, and the repeats. Menu, footer and breadcrumbs separately.
2. **Plan.** `suggest <page> --repo <worktree>`. Read the research first: the dossier (search words, the "Own" list),
   the AI-answers check and the GEO search check (buyer prompts).
3. **Choose, best first.** In this order:
   - every spoke of the cluster links up in its text;
   - pages outside the cluster that already rank for the target's searches (the strongest signal: Google already ties
     them to the topic);
   - repeated or generic link words on existing links, moved to unused search phrases;
   - other clusters, only where the reader needs it.
   Never link from or to an address in the redirect config, a draft or a future-dated post.
4. **Write it in the journal, on the source page**, one entry per link, before editing:
   ```
   growth journal add --page <source> --page <target> --kind finding --tag internal-link \
     --recheck <day 28> --title "Link to <target> from <source>: anchor '<words>'" \
     --text "<the exact sentence, where it sits, and why, with the Search Console numbers>"
   ```
   Plus one summary entry on the target with the counts before and after. A link that waits for the owner (their page,
   or a decision on the source) stays open with the reason in the text.
5. **Edit** (content files only unless the brief says otherwise; one natural sentence; words the page already uses;
   `BRAND.md` claims only, never a banned word). Link-only edits do not change `updated`.
6. **Check.** The content tests the change touches (rule 105, `growth checks`), including the link-card tests because
   the "+" previews read the links. Re-run `inbound` and `check <page>` (exit 0): the counts went up and the repeats
   went down.
7. **Close.** Commit only the files you edited. `growth journal done <id> "applied in <commit>"`.
8. **Re-check at day 28** (`growth journal due`): `inbound` again (a later edit can drop a link), and in Search
   Console the position of each anchor phrase for the target.

### The "+" previews (rule 36c)

Every internal text link gets the "+" preview card by itself, built from the site's own content. Nothing to add per
link. A link to a redirect or a draft gets no card, which is one more reason never to write one.

### Where the plans are

- `journal/pages/<page>.md`: every link waiting on that page (tag `internal-link`), open or done.
- `research/<page>-internal-links-<date>.md`: the full report per target page.
