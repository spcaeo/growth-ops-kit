---
title: Playbook - technical SEO
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: technical SEO

**Version 2.0.0 (generic edition) · 18 Nov 2026**

This is the one technical SEO standard. It holds about **150 checks**. Most of them are run by one command
(`growth tech_seo_check`, read-only, no browser). The rest need a browser, a production build or a search tool, and the
tables say which. The checks come from published guidance (Google Search Central, web.dev, WCAG), from the page
rulebook, and from real audits.

A "technical SEO check" asks: can a search engine (and an AI tool) reach the page, read it without running a script,
understand it, and trust it? It does not judge the writing. For writing and conversion see
[money-page](money-page.md) and [cro-audit](cro-audit.md). Rule 36d makes a clean run a release condition.

## 0. How to use it

| When | Run | Done when |
| --- | --- | --- |
| While building a page (dev server) | `growth tech_seo_check http://127.0.0.1:<port>/<path> --keyword "<main phrase>"` | 0 FAIL; every WARN fixed or explained in the pull request |
| Before the pull request, on a production build | build once in production mode, serve it, then `... --mode prod --build-dir <site>/<build folder> --ua facebookexternalhit` | 0 FAIL in `--mode prod`; metadata inside `<head>`; the page is indexable |
| Before launch, once per page type | Lighthouse and PageSpeed Insights (section 8 checks), Rich Results Test (SCH-16), share debuggers (SOC-09) | numbers in section 8 met |
| After go-live (owner's yes to merge first) | `... --allow-live` (fetches only that page, `robots.txt` and `sitemap.xml`), then Search Console URL Inspection (IDX-10) | indexed; canonical Google chose is ours |
| Sitewide, once a month | `... --site-scan` on a production build; compare the sitemap count (MAP-14) | no duplicate titles, no non-200 sitemap URL |

Options: `--mode dev|prod`, `--keyword`, `--type money|article|hub|other`, `--build-dir`,
`--ua googlebot|facebook|twitterbot|linkedinbot`, `--no-link-status`, `--site-scan`, `--md <file>`, `--allow-live`. The
checker prints one line per check: `OK`, `WARN`, `FAIL`, `INFO` (a fact, no action) or `SKIP` (it cannot check this
here, with the manual way). Each `WARN` and `FAIL` line carries a fix. It exits 1 when any `FAIL`. It never fetches the
real site unless `--allow-live` is given, and then only one page plus `robots.txt` and `sitemap.xml`.

**Two modes matter.** A dev or preview build is often `noindex` and `Disallow: /` on purpose, and some frameworks
stream page metadata into `<body>` in dev. In `--mode dev` those show as `INFO` or `WARN`. They must be proven fixed
with a production build in `--mode prod`, where the same facts are `FAIL`.

**Self-test.** `growth techseo selftest` serves one bad and one good page and proves the checker catches the bad one.

**Reading the tables.** **C** = the checker prints it. **M** = by hand or with the named tool. IDs are stable: the
checker prints the same IDs. A check with a letter after the number (SCH-04b) is a part of its parent. `<site>` is the
project's address from `growth.json`.

## 1. Crawl and index

Can a search engine reach the page, and is it allowed to keep it?

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| IDX-01 | **Status code.** The page answers 200 at its final address. | Only a 200 page can rank. | C |
| IDX-02 | **No redirect on the address we test.** If an old address redirects, it is one hop and permanent (301 or 308), never a chain. | Chains waste crawl budget and lose value. | C |
| IDX-03 | **Indexable.** No `noindex` in the meta robots tag or the X-Robots-Tag header on a page meant to rank. On a dev or preview build `noindex` is expected (INFO); in `--mode prod` it is a FAIL. | A stray noindex removes the page from Google. | C |
| IDX-04 | **Header and meta agree.** The X-Robots-Tag header says the same as the meta robots tag. | A hidden header can override the page. | C |
| IDX-05 | **robots.txt exists and names the sitemap.** `/robots.txt` answers 200 and has a `Sitemap:` line. | Crawlers read it first. | C |
| IDX-06 | **Page not blocked.** robots.txt does not disallow the page for Googlebot. A preview or dev build blocks everyone on purpose (INFO); in `--mode prod` a block is a FAIL. | A blocked page cannot be read. | C |
| IDX-07 | **Links followed.** The page's robots meta has no `nofollow`. | `nofollow` on a money page stops link value. | C |
| IDX-08 | **One robots meta.** At most one `<meta name=robots>`. | Two tags can disagree; the strictest wins. | C |
| IDX-09 | **Not an orphan.** Linked from the menu, a hub or a sibling, and listed in the sitemap. | A page nothing links to is rarely indexed. | M: link graph (LNK-09) and MAP-02 |
| IDX-10 | **Google has it.** After ship day: Search Console URL Inspection says "URL is on Google" and the canonical Google chose is ours. | Proof, not hope. | M: Search Console URL Inspection; request indexing |
| IDX-11 | **Right content type.** `text/html; charset=utf-8`. | A wrong type can stop indexing. | C |
| IDX-12 | **No soft 404.** Real copy (100+ words) and a real title; a missing page answers 404 or 410, not 200. | Google drops fake-200 error pages. | C |
| IDX-13 | **HTTPS and HSTS.** The live page is https and sends `Strict-Transport-Security`. | Trust and a ranking signal. | C (`--mode prod` on https) |
| IDX-14 | **Compression.** HTML is sent gzip or brotli. | Smaller, faster. | C (production build or live) |
| IDX-15 | **Cache headers.** A public page is not `no-store` (a dev server normally is). | CDN caching keeps the page fast. | C |

## 2. URL, canonical, redirects and status codes

One page, one address.

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| URL-01 | **Clean address.** Lowercase, words joined by hyphens, no underscores, spaces, query string or file extension, 115 characters or fewer (host included). | Readable, stable, no duplicates. | C |
| URL-02 | **One canonical.** Exactly one `<link rel=canonical>`. Missing is a FAIL. | Tells Google which address is the master. | C |
| URL-03 | **Absolute, https, site host.** `https://<site host>/...` in the site's one host style (no www or http unless that is the site's style, no relative path). | A wrong host splits the page. | C |
| URL-04 | **Self-referencing.** The canonical's path equals the page's own path. | A page that should rank names itself. | C |
| URL-05 | **One slash style.** The canonical and the sitemap use the same trailing-slash style. | Mixed styles make duplicate addresses. | C |
| URL-06 | **Canonical in `<head>`.** The canonical is inside `<head>` of the served HTML. Streamed into `<body>` is a WARN on a dev build, a FAIL in `--mode prod`. | Tags in the body can be ignored. | C |
| URL-07 | **Slash variant.** The other slash style redirects 301 or 308 to the real one (or answers 404). It must not answer 200 with its own canonical. | Duplicate address. | C |
| URL-08 | **http, www and apex.** `http://`, `www.` and the bare host each redirect in one step to the real address. | One home for the page. | M: `curl -sI` the 4 variants once after ship (the live site, owner approves) |
| URL-09 | **Tracking parameters.** `?utm_source=x` loads the page and its canonical is the clean address. | Campaign links must not make duplicates. | C |
| URL-10 | **Real 404.** An unknown address answers 404 or 410 (never 200), with helpful links. | Soft 404s waste crawling. | C |
| URL-11 | **No retired host.** The page, its schema and links never name an old host, an old IP or `localhost` (`growth.json` `old_hosts`). | Old hosts leak rankings. | C |
| URL-12 | **Moved pages.** A moved or merged page has one 301 straight to its final address; a removed one answers 410; internal links point at the final address. | Keeps rankings, no chains. | M: the redirect config; LNK-02 shows links through redirects |

## 3. Titles, meta, headings and language

What the result and the first screen say.

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| TTL-01 | **One title.** Exactly one `<title>`. | Two titles confuse the snippet. | C |
| TTL-02 | **Title length.** 30 to 60 characters and about 580px wide or less. 61+ characters is a WARN if it still fits 580px, a FAIL if it does not. Under 30 is a WARN. | A cut-off title loses clicks. | C (width is an estimate) |
| TTL-03 | **Keyword near the start.** With `--keyword`, the main phrase is in the first 35 characters. | Strongest place for the phrase. | C (`--keyword`) |
| TTL-04 | **Unique across the site.** No two pages share a title or a description. | Duplicates compete with each other. | C (`--site-scan`) |
| TTL-05 | **One meta description.** Exactly one. | | C |
| TTL-06 | **Description length and form.** 120 to 155 characters, a full sentence, no HTML or Markdown. Over 160 or under 70 is a FAIL. | Google may rewrite it, but a good one wins the click. | C |
| TTL-07 | **Description is its own.** Not the same as the title; not copied from another page. | | C |
| TTL-08 | **No placeholders or old year.** No lorem, TODO, `{{field}}`, `[Your ...]`, or a year before this one, in title, description or headings. | Embarrassing and untrusted. | C |
| TTL-09 | **One H1.** Exactly one `<h1>`. | The page's one topic line. | C |
| TTL-10 | **H1 is clear.** 1 to 70 characters; with `--keyword`, names the topic. | | C |
| TTL-11 | **Heading order.** The first heading is H1; no level is skipped (H2 then H4). | Structure for readers and tools. | C |
| TTL-12 | **No empty or repeated headings.** Every heading has words and no two share the same text. | | C |
| TTL-13 | **Heading ids kept.** Headings that were linked to keep their `id` so old `#section` links land. | Anchors are addresses. | C (counts them; INFO). Compare with the live page by hand |
| TTL-14 | **Language.** `<html lang="...">` with a valid code. | Screen readers, search language. | C |
| TTL-15 | **Charset.** `<meta charset=utf-8>` in the first 1024 bytes (or in the header). | Garbled text otherwise. | C |
| TTL-16 | **One spelling.** The project's chosen spelling (`growth.json` `spelling`) in title, description, alt and copy. | Consistent voice. | M: read it; spell check |

## 4. Content and links

Is there enough real copy, and do the links help?

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| CNT-01 | **Enough words.** 300 or more words of main copy is the floor (FAIL below); under 600 is a WARN for a money page. Counted in `<main>`, visible text only. | Thin pages do not rank. | C |
| CNT-03 | **No placeholder text.** No lorem, TODO, FIXME, `{{field}}`, `undefined`, `NaN`, `[object Object]` in the copy. | | C |
| CNT-04 | **Answer-first passage.** The first paragraph after the H1 is one self-contained answer of 40 to 60 words (WARN outside 30 to 70). | AI answers quote this passage. | C |
| CNT-05 | **Visible date.** The page shows "Updated <date>" (and `dateModified` in schema). | Freshness signal for people and AI. | C |
| LNK-01 | **Link inventory.** Reported: total, unique, internal, external, other. | Know what the page links to. | C |
| LNK-02 | **Internal links work.** Every unique internal link answers 200. A link that goes through a redirect is a WARN; a broken link is a FAIL. | Broken links hurt users and crawling. | C (HEAD requests to the local server) |
| LNK-03 | **Every link has a name.** Visible text, `aria-label`, or an image alt. An icon-only link with no name is a FAIL. | Crawlers read anchor text only. | C |
| LNK-04 | **Anchor text says where it goes.** No "click here", "read more", "learn more", "here", "more". | Anchor text is a ranking hint. | C |
| LNK-05 | **No `utm_` on internal links.** None. | Restarts analytics, makes duplicate URLs. | C |
| LNK-06 | **No placeholder links.** No `href="#"`, empty href, `javascript:`; no `<a>` without `href`. | Not crawlable. | C |
| LNK-07 | **External links safe.** `target=_blank` links carry `rel=noopener`; add `nofollow` or `sponsored` to any link you do not vouch for or that is paid. The checker lists the external hosts for a human decision. | Security and link value. | C |
| LNK-07b | **External links we pass value to.** Listed for a human decision: each followed external link is one you vouch for. | | C (INFO) |
| LNK-08 | **No old or wrong host.** No internal link to `http://`, an unwanted `www.` or an old host. | | C |
| LNK-09 | **Contextual internal links.** Three or more internal links inside the main copy (not menu or footer): up to the hub, across to siblings. | Passes value and shows topic depth. | C |
| LNK-10 | **One anchor, one target.** The same anchor text does not point at two different pages. | Ambiguous. | C |
| LNK-12 | **In-page anchors land.** Every `#section` link has a matching `id`. | | C |
| LNK-13 | **No internal nofollow.** None. | Wastes link value. | C |

## 5. Images and media

Fast, described, and not a layout jump.

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| IMG-01 | **Inventory.** Reported: images, with alt, decorative (`alt=""`), missing alt. | | C |
| IMG-02 | **Alt text.** Every image has an `alt`. `alt=""` only for pure decoration; an image that is a link's only content, or 200px wide or more, needs a real alt. | Accessibility and image search. | C |
| IMG-03 | **Alt quality.** 125 characters or fewer, no "image of", not a file name. | | C |
| IMG-04 | **Width and height.** Every `<img>` has width and height (or aspect-ratio). | Stops layout shift (CLS). | C |
| IMG-05 | **First screen not lazy.** The first image is not `loading=lazy` (FAIL); the second is a WARN. The main picture has `fetchpriority=high`. | Lazy hero = slow LCP. | C |
| IMG-06 | **Later images lazy.** Images after the sixth are `loading=lazy`. | Saves bandwidth. | C |
| IMG-07 | **Modern format.** No PNG or JPEG over 150 KiB; use WebP or AVIF (SVG for drawings). | Smaller files. | C |
| IMG-08 | **File size.** No image over 200 KiB (WARN 200 to 300, FAIL above). | Page weight and LCP. | C (HEAD) |
| IMG-09 | **Extension and type.** The file name keeps its extension and is served as `image/*`. | A file without a type may not show. | C |
| IMG-10 | **No broken images.** Every image answers 200. | | C |
| IMG-11 | **Responsive.** Pictures 600px or wider carry `srcset` (the framework's image component does it). | Phones get small files. | C |
| IMG-12 | **Descriptive file names.** Not `IMG_1234.jpg`. | Image search hint. | C |
| IMG-13 | **Not bigger than shown.** Natural size is no more than 2x the displayed size. | Wasted bytes. | M: Lighthouse "Properly size images" |
| IMG-14 | **A main picture.** A picture 480px wide or more on a hub or money page (or a clear reason it is drawn in SVG). | | C |
| IMG-15 | **Video.** `<video autoplay>` is `muted` and `playsinline`, has a `poster`. | Autoplay rules, LCP. | C |
| IMG-16 | **Nothing on a picture only.** Words that appear only inside a picture also exist as text. | AI and search cannot read pictures. | M: read the page; compare with the JSR-02 word count |

## 6. Structured data (JSON-LD)

Markup says what the page shows, and nothing else.

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| SCH-01 | **JSON-LD parses.** Every `<script type=application/ld+json>` is valid JSON. | A broken block is ignored. | C |
| SCH-02 | **Context and type.** Each block has `@context` schema.org and each node a `@type`. | | C |
| SCH-02b | **Types found.** Lists the types on the page (INFO). | Know what Google sees. | C |
| SCH-03 | **Right types for the page.** Money page: the page's main type (Service, SoftwareApplication or Product, as fits; never only the site's Organization), FAQPage, BreadcrumbList. Article: Article or BlogPosting + BreadcrumbList. Hub: CollectionPage or WebPage + BreadcrumbList. | Rich results and AI understanding. | C (`--type`) |
| SCH-03b | **Publisher and page node.** Organization named, and a WebPage node for the page (WARN if missing). | Says who is behind the page. | C |
| SCH-04 | **Required properties.** Every known node has its required properties (table in section 9), including `Offer` with `price` and `priceCurrency`. Missing = FAIL; missing recommended = WARN (SCH-04b). | Google needs them for the rich result. | C |
| SCH-04b | **Recommended properties.** Recommended properties present when they are true and shown (WARN if missing). | Richer results. | C |
| SCH-04c | **Rich-result needs by design.** If the site shows no public price and no ratings (`BRAND.md`), the markup carries no offers, ratings or reviews: INFO. Never add them to look complete. | | C (INFO) |
| SCH-05 | **FAQ equals the page.** FAQPage questions and answers are the visible ones, word for word, in the same order; no empty answer; no near-duplicate question. | A mismatch can cost the rich result and misleads readers. | C |
| SCH-06 | **Says what the page shows.** The main node's `url` equals the canonical; it has a name (or headline) and a description. | | C |
| SCH-07 | **Breadcrumbs.** BreadcrumbList positions 1..n, each step has name and URL, the last step is this page, and the same crumbs are visible in a `nav aria-label="Breadcrumb"`. Markup and visible trail come from the same data. | Visible and marked-up trail must match. | C |
| SCH-08 | **`@id` references resolve.** Every `{"@id": ...}` points at a node on the page. | | C |
| SCH-09 | **Right host.** All URLs in the markup use the site's address; none name localhost, an unwanted www or an old host. | | C |
| SCH-10 | **Dates are ISO.** `datePublished`, `dateModified`, etc. are ISO 8601. | | C |
| SCH-11 | **No invented proof.** Ratings or reviews in the markup only when the page shows them. | Never claim what you cannot show. | C |
| SCH-13 | **Microdata.** If microdata is also present, it agrees with the JSON-LD. | | C |
| SCH-14 | **JSON-LD is never the page's first node (Next.js adapter).** JSON-LD sits inside an empty block `<div>` (in the shared JsonLd component), never directly in `<main>` or `<body>`. | A first `<script>` node leaves a page navigation half way down. | C; plus a browser test that `scrollY === 0` after navigation |
| SCH-15 | **No duplicate nodes.** One Organization and one WebSite node per page. | | C |
| SCH-16 | **Rich result test.** Google's Rich Results Test and validator.schema.org show no errors. | Final proof. | M: search.google.com/test/rich-results, validator.schema.org |

## 7. Social cards

What a shared link looks like.

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| SOC-01 | **Open Graph set.** `og:title`, `og:description`, `og:url`, `og:type`, `og:site_name`, `og:image` all present. | Link previews on LinkedIn, Facebook, Slack, WhatsApp. | C |
| SOC-02 | **Share image is real.** `og:image` is absolute https on your host, answers 200 as an image (not GIF or SVG), 1200x630 or close (1.91:1), under 5 MB, and `og:image:width` and `height` equal the file. | A broken share image once reached an owner. | C (reads the file header) |
| SOC-03 | **Image alt.** `og:image:alt` present. | | C |
| SOC-04 | **og:url = canonical.** Identical. | | C |
| SOC-05 | **Text follows meta.** `og:title` and `og:description` follow the meta text, or there is a reason (INFO). | | C |
| SOC-06 | **X (Twitter) card.** `twitter:card` = `summary_large_image`, `twitter:image` = `og:image`, title and description present. | | C |
| SOC-07 | **Locale.** `og:locale` only if set correctly. Optional on a one-language site. | | C (INFO) |
| SOC-08 | **Text length.** `og:title` 70 or fewer, `og:description` 200 or fewer. | Cut-off previews. | C |
| SOC-09 | **One wording on every network.** A set `twitter:title` or `twitter:description` equals the `og:` one (or is left out, so X falls back to og). | The same share reads two ways on X and LinkedIn. | C |
| SOC-09 | **Look at it.** Open the page in the Facebook Sharing Debugger and the LinkedIn Post Inspector; read the preview. | Tools do not see ugly. | M |

## 8. Performance and Core Web Vitals

Fast on a phone. Needs a production build and a browser; the checker only reads what the HTML and headers show.

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| PERF-01 | **LCP (largest paint).** 75th percentile is 2.5 s or less (good); over 4 s is poor. | Ranking signal and conversion. | M: PageSpeed Insights or CrUX for field data; Lighthouse on a production build for lab data |
| PERF-02 | **INP (interaction).** 200 ms or less (good); over 500 ms poor. | | M: same |
| PERF-03 | **CLS (layout shift).** 0.1 or less (good), over 0.25 poor. Target 0.05 or less; a static site can hold 0.002 or less. | Pages that jump lose trust. | M: same; browser test with sticky bars and popups |
| PERF-04 | **Lighthouse scores.** Mobile and desktop: Performance 90 or more, SEO 100, Accessibility 95 or more, Best practices 95 or more. | Single score to compare releases. | M: Lighthouse on a production build |
| PERF-05 | **HTML weight.** HTML of 250 KB or less unpacked (WARN above, FAIL above 500 KB). Dev HTML is larger and only an INFO. | Lean markup, fast parse. | C (`--mode prod` or `--build-dir`) |
| PERF-06 | **Render-blocking.** No synchronous `<script src>` in `<head>`; 3 or fewer blocking stylesheets. | Delays first paint. | C |
| PERF-07 | **Fonts.** Self-hosted, 3 or fewer preloaded files, no run-time Google Fonts CSS. | Font requests slow the first paint. | C |
| PERF-08 | **Third-party tags.** No blocking third-party script in `<head>`; the tag manager loads after the page is idle. | Mobile LCP was 7.6 to 8.2 s with tags running at start. | C |
| PERF-09 | **Resource hints.** 3 or fewer `preconnect` or `dns-prefetch`. | | C |
| PERF-11 | **TTFB.** Server answers in 0.8 s or less. | | M: PageSpeed Insights; `curl -w` on a production build |
| PERF-12 | **Asset caching.** Static files cache for a year (immutable). | Repeat visits are instant. | C (`--mode prod`) |
| PERF-13 | **Total page weight.** Lighthouse "Total byte weight" passes; no single image over 200 KiB. | | M: Lighthouse |
| PERF-14 | **Nothing moves the layout.** Sticky bar, exit dialog, hints and cookie banners add no layout shift. | | M: browser CLS check on a production build |
| PERF-15 | **No long main-thread work.** Total Blocking Time 200 ms or less (lab). | INP proxy. | M: Lighthouse |

## 9. Mobile, accessibility, sitemap, robots and the rest

### Mobile and accessibility that affect SEO (Google indexes the phone page)

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| MOB-01 | **Viewport.** `width=device-width, initial-scale=1`; zoom is not blocked (no `user-scalable=no`, no `maximum-scale=1`). | Mobile-first indexing; accessibility. | C |
| MOB-02 | **Tap targets and text.** Tap targets 24px or more, body text 16px, no mono label under 12px on phones. | Usability. | M: Lighthouse; `growth phone_check` |
| MOB-03 | **No sideways scroll.** Nothing wider than the screen at 360, 390, 820 and 1024px. | | M: browser overflow sweep |
| MOB-04 | **Same content on phone and desktop.** A phone user agent sees the same words, H1 and canonical (within 3%). | Google indexes the mobile version. | C |
| MOB-05 | **Landmarks.** One `<main>`, a header or nav, a footer, and a skip link. | Structure for assistive tools and crawlers. | C |
| MOB-06 | **Names on controls.** Buttons and form fields have a name or label. | Lighthouse SEO and accessibility. | C |
| MOB-07 | **Contrast.** Text meets 4.5:1. | | M: Lighthouse; `growth contrast_check` |
| MOB-08 | **No intrusive popups.** Nothing covers the first screen on a phone; the exit dialog opens only after real engagement, once per session. | Google's interstitial rule. | M: browser at 390px |
| MOB-09 | **Reduced motion.** Animations stop under `prefers-reduced-motion`. | | M: browser with reduced motion |

### Sitemap, robots, llms.txt, feeds and icons

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| MAP-01 | **Sitemap works.** `/sitemap.xml` answers 200 as valid XML. | | C |
| MAP-02 | **Page is listed.** An indexable page's canonical is in the sitemap; a noindex page is not. | | C |
| MAP-03 | **Sitemap clean.** All URLs absolute https on your host, unique, no query, `.md` or JSON, under 50,000. | | C |
| MAP-04 | **Every listed URL is a 200.** Each sitemap URL answers 200. | | C (`--site-scan`) |
| MAP-05 | **lastmod.** This page has a real `lastmod` date; not every page has the same one. Priority and changefreq are ignored by Google. | | C |
| MAP-06 | **robots.txt does not block assets.** No Disallow on CSS, JS, images or the framework's build folder. | Google must render the page. | C |
| MAP-08 | **llms.txt.** The owner decides (rule 148). If present: starts with `# Name`, a `>` summary, then link lists. | Not a ranking factor. | C (INFO) |
| MAP-10 | **Feed link.** The RSS link answers 200. | | C |
| MAP-11 | **Icons.** favicon and apple-touch-icon files answer 200. | | C |
| MAP-14 | **Sitemap count.** Reported before and after a change. | Catches pages lost or added by accident. | C (INFO) |

### International

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| INT-01 | **hreflang.** None is right for one language. If ever added: reciprocal, absolute, self entry, `x-default`. | A lone hreflang is wrong. | C |

### JavaScript rendering: is the content in the HTML?

Crawlers and AI tools often read the raw HTML only.

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| JSR-01 | **Key tags in raw HTML.** Title, description, canonical and `og:title` are in the HTML as served, no JavaScript needed. | Non-rendering crawlers. | C |
| JSR-02 | **Copy in raw HTML.** The H1 and 300+ words of main copy are in the served HTML. | | C |
| JSR-03 | **Real links.** Navigation uses `<a href>`, not click handlers. | Crawlers follow links, not clicks. | C |
| JSR-05 | **Metadata in `<head>`.** In the served HTML the metadata tags are inside `<head>`. Some dev servers stream them into `<body>` (WARN on dev, FAIL in `--mode prod`). Social bots get `<head>` metadata (test `--ua facebook`). | Prove it on a production build. | C (`--mode prod`, `--ua`, `--build-dir`) |
| JSR-06 | **No hidden streaming.** No large copy sits in hidden streaming containers that need JavaScript to appear. | | C |
| JSR-08 | **Rendered equals raw.** The browser's rendered text matches the raw HTML text (no big copy added only by script). | | M: compare `curl` text with the browser's `innerText` |
| JSR-09 | **Navigation lands at the top.** From a scrolled page, client navigation to several routes and a logo click ends at `scrollY === 0`; a hash link lands on its heading. | Known Next.js bug (SCH-14). | M: browser regression test (rule 107) |
| JSR-10 | **Images have a real `src`.** Not only `data-src` filled by script. | | C |

### Delivery and security headers

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| SEC-01 | **Baseline headers.** `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy` present. | Trust, basic hardening. | C |
| SEC-02 | **CSP.** A `Content-Security-Policy` or report-only one that allows the tags the site really uses. | | C (INFO) |
| SEC-03 | **No mixed content.** No `http://` resources on an https page. | Browsers block them. | C |
| SEC-04 | **No software name.** No `X-Powered-By` or server version. | Less to attack. | C |

### The built page (production build)

Reads the static HTML a build wrote, with no server.

| ID | Check and pass line | Why | How |
| --- | --- | --- | --- |
| BLD-01 | **Built HTML found.** The build folder holds the page's HTML for a static page. | | C (`--build-dir`) |
| BLD-02 | **Metadata in built `<head>`.** Title, description, canonical and og:image are inside `<head>` of the built HTML. | | C |
| BLD-03 | **Built page indexable.** No noindex (build in production mode). | | C |
| BLD-04 | **Built HTML weight.** 250 KB or less. | | C |

## 10. Reference tables

### Lengths and sizes

| Thing | Pass | Warn or fail |
| --- | --- | --- |
| Title | 30 to 60 characters, about 580px or less | over 60 and wider than 580px = FAIL |
| Meta description | 120 to 155 characters, one full sentence | over 160 or under 70 = FAIL |
| H1 | exactly one, 70 characters or fewer | none or more than one = FAIL |
| Main copy | 600 words or more on a money page | under 300 = FAIL, under 600 = WARN |
| First answer paragraph | 40 to 60 words | outside 30 to 70 = WARN |
| Share image | 1200x630 (1.91:1), JPEG, PNG or WebP, under 5 MB | GIF, SVG, under 1200x600 = FAIL |
| Any picture | 200 KiB or less | 200 to 300 WARN, over 300 FAIL |
| HTML | 250 KB unpacked or less | over 250 WARN, over 500 FAIL |
| URL | lowercase, hyphens, 115 characters or fewer, no query | any other = WARN |
| Contextual internal links | 3 or more in the main copy | fewer = WARN |
| Sitemap | under 50,000 URLs, all 200, all indexable | |

### Core Web Vitals (75th percentile on phones)

| Metric | Good | Needs work | Poor |
| --- | --- | --- | --- |
| LCP (largest paint) | up to 2.5 s | 2.5 to 4 s | over 4 s |
| INP (response to a tap) | under 200 ms | 200 to 500 ms | over 500 ms |
| CLS (layout shift) | under 0.1 | 0.1 to 0.25 | over 0.25 (target 0.05 or less) |

### Required and recommended schema properties

The checker applies these. A pipe `a|b` means one of the two.

| Type | Required | Recommended |
| --- | --- | --- |
| Organization | name, url | logo, sameAs, contactPoint |
| WebSite | url | name, potentialAction |
| WebPage | name, url | description, isPartOf, datePublished, dateModified |
| Article, BlogPosting | headline, image, datePublished, author | dateModified, publisher |
| SoftwareApplication | name, applicationCategory, operatingSystem | offers, aggregateRating, review |
| Product | name, image | offers, aggregateRating, review |
| FAQPage | mainEntity | |
| Question | name, acceptedAnswer | |
| Answer | text | |
| QAPage | mainEntity | |
| BreadcrumbList | itemListElement | |
| ListItem | position, name, item (the last step may leave out item) | |
| ItemList | itemListElement | |
| HowTo | name, step, description | |
| HowToStep, HowToSection | text or itemListElement (+ name for a section) | |
| LocalBusiness | name, address | geo, aggregateRating |
| Review | author, itemReviewed, reviewRating | |
| AggregateRating | ratingValue, ratingCount or reviewCount, itemReviewed | bestRating, worstRating |
| Offer | price, priceCurrency | |
| VideoObject | name, description, thumbnailUrl, uploadDate | contentUrl, duration |
| Event | name, startDate, location | description, endDate |
| Course, Dataset | name, description | |
| Person | name | |
| JobPosting | title, description, datePosted, validThrough, hiringOrganization, jobLocation | |

## 11. Traps we already know

- **A first `<script>` node (Next.js).** On a client-side navigation Next.js scrolls the new page's top-level nodes
  into view, last to first. If the first node is JSON-LD (hidden), the window stops part-way down. Keep JSON-LD inside
  an empty `<div>` (SCH-14) and add the browser `scrollY === 0` test (JSR-09).
- **Dev server metadata.** In dev, some frameworks stream `<title>`, description, canonical and og tags into `<body>`
  and move them with a script. Bots that do not run scripts see no `<head>` metadata there. A production build of a
  static page writes them inside `<head>`. Always prove it with a production build before launch (JSR-05, BLD-02).
- **Preview is noindex on purpose.** Run `--mode prod` only against a build made in production mode.
- **A visible breadcrumb is part of the schema.** Markup without the visible trail fails SCH-07. Use the shared
  breadcrumb component so both come from one list (rule 50).
- **Never invent proof for markup.** If the business quotes price on the call and shows no ratings, the markup carries
  no `offers` or `aggregateRating` (SCH-04c, SCH-11).
- **Do not run Lighthouse on the dev server.** Dev bundles are not the real weight; measure on a production build.

## 12. Limits of the checker

- It reads HTML and headers only. It cannot measure LCP, INP, CLS, contrast, tap size or scrolling; those are the `M`
  checks.
- Title width is an estimate (Arial 20px averages), not a measurement.
- Link and image status checks send read-only HEAD requests (GET if HEAD fails) to the local server, three at a time,
  at most 80 links and 40 images. A cold dev server compiles each page it is asked for, so use `--no-link-status`
  when the server is busy.
- `--site-scan` fetches every sitemap page from the local server; run it on a production build, not a busy dev server.
- It does not render JavaScript. JSR-08 (rendered text equals raw text) is a manual comparison.
