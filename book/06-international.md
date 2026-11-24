---
title: International sites
version: 3.0.0
updated: 2026-11-24
license: CC BY 4.0
---

# International sites: many languages, many countries (kit 3.0)

**Version 3.0.0 · 24 Nov 2026.** How one site serves several languages and countries "as Google asks": each copy has its own
address, tells Google who it is for, and points at its siblings. It adds one page rule (162) and changes nothing for a site
with one locale. Read it with [03-page-rulebook.md](03-page-rulebook.md) (rules 94 and 162) and [05-board.md](05-board.md).

The example: one business that wants English for the USA, English for Canada, French for Canada and Spanish for the USA.

## What a locale is

A **locale** is one language in one country: `en-US`, `en-CA`, `fr-CA`, `es-US`. Each locale has its own folder on the same
site, its own copy of every page, and its own Google search settings for research. The first is the **primary**: the
original, at the site's root.

| Locale | Folder | A page | Google research settings |
| --- | --- | --- | --- |
| `en-US` (primary) | `/` | `/pricing/` | `gl=us&hl=en&pws=0` |
| `en-CA` | `/en-ca/` | `/en-ca/pricing/` | `gl=ca&hl=en&pws=0` |
| `fr-CA` | `/fr-ca/` | `/fr-ca/pricing/` | `gl=ca&hl=fr&pws=0` |
| `es-US` | `/es-us/` | `/es-us/pricing/` | `gl=us&hl=es&pws=0` |

Folders on one domain are the kit's choice: one domain keeps all the site's links and trust together, and a folder is
cheap to add. (Google also accepts a country domain or a subdomain per locale; the rule below works for any of them if
the folders in `growth.json` match the real addresses.)

## Set it up, and change it later

The setup question about the market takes the old answer (one country and language) or a list of locales:

```
growth wizard answer market '{"locales": [{"locale": "en-US", "primary": true}, "en-CA", "fr-CA", "es-US"]}'
```

That is the whole change. Run the same command again with another list to add a language, drop one or change a folder:
the market is rewritten in `growth.json` straight away, in both forms (`market.locales`, and the old single-market fields
set to the primary locale's values). Every entry may carry `country`, `language`, `prefix` and `google_params`; what is left
out is worked out (the folder is `/<locale in lower case>/`, the Google settings are `gl=<country>&hl=<language>&pws=0`).
The rules the list must follow, each with a plain message when it breaks (`growth doctor`, step A14, prints them):

- every tag is a language tag with a dash (`fr-CA`, not `fr_CA`), and every locale has a country;
- exactly one locale is the primary, and its folder is `/`; no other locale has `/`;
- no two locales share a folder, and no folder sits inside another one;
- a locale's `google_params` carry its own country (`gl=ca`) and `pws=0` (results that are not personalised).

A site with no `market.locales` is one locale built from the old fields: nothing else to do, no new check runs.

## What every copy must say (rule 162)

Each copy is its own page: its own text, title and description, not a machine-translated mirror with the English
canonical. Google's two guides on this are Search Central, "Tell Google about localized versions of your page" and
"Managing multi-regional and multilingual sites". The gate (`intl.*`) checks the built page:

| Check | The page must | Why |
| --- | --- | --- |
| `intl.lang` | have `<html lang>` equal to its own locale (`fr-CA` on `/fr-ca/...`) | readers, screen readers and browsers get the right language |
| `intl.copies` | have every other locale's copy of the page | a missing copy is a **missing translation**, its own finding, never mistaken for a wrong tag |
| `intl.hreflang` | list itself, list each copy that exists, with absolute addresses to the same page in that locale's folder, be answered by a tag from each copy, and carry `x-default` | Google ignores a tag nobody answers |
| `intl.canonical` | be its own canonical, never the English page | a canonical to another language makes Google drop this copy |
| `intl.no-auto-redirect` | have no script, meta refresh or server rule that moves a visitor by language | a crawler sends no language and sees only one version; visitors lose the others |
| `intl.sitemap` | when the build has a sitemap, be listed with `xhtml:link` alternates for itself and each copy | the second way Google accepts hreflang |

The head of the English pricing page, written out:

```html
<html lang="en-US">
<link rel="canonical" href="https://example.com/pricing/">
<link rel="alternate" hreflang="en-US" href="https://example.com/pricing/">
<link rel="alternate" hreflang="en-CA" href="https://example.com/en-ca/pricing/">
<link rel="alternate" hreflang="fr-CA" href="https://example.com/fr-ca/pricing/">
<link rel="alternate" hreflang="es-US" href="https://example.com/es-us/pricing/">
<link rel="alternate" hreflang="x-default" href="https://example.com/pricing/">
```

The French-Canadian copy has the same six `alternate` lines, `lang="fr-CA"` and `https://example.com/fr-ca/pricing/` as its
canonical. In the sitemap, each `<url>` repeats the five addresses as `<xhtml:link rel="alternate" hreflang="..." href="..."/>`
(with `xmlns:xhtml="http://www.w3.org/1999/xhtml"` on `<urlset>`).

**A copy that does not exist yet.** The English page goes READY first, then its copies are written (below). Until a copy
exists, leave its hreflang out. The gate says "missing translation: the es-US copy of /pricing/ does not exist yet", as a
WARN, so the English page can be READY while its copies are being written. A project that wants it to block sets
`"missing_copy": "fail"` in `market` of `growth.json`.

## Choosing the language: suggest, never redirect

The owner asked for the site to pick the language from the visitor's browser. Google's advice is the opposite for a
redirect: do not send visitors to another version automatically by their language or country. A crawler sends no language, so
it would only ever see one version, and a visitor in the wrong country is locked out of the right page. So the kit does this:

1. The server answers every address the same, whatever the visitor's language.
2. A small script reads `navigator.language` and, only when it differs from the page's locale and a copy exists, shows a
   banner: "This page is also in Français (Canada)", with a plain link to that copy and a "No thanks".
3. The choice (a click on the link, or "No thanks") is kept in a cookie or `localStorage`, and the banner does not come back.
4. A language switcher in the header holds real links to the page's copies.

```js
// the banner only suggests: it never assigns to location (the gate fails a script that reads the language and moves the visitor)
const want = (navigator.languages || [navigator.language]).find((l) => copies[l]);   // copies: {"fr-CA": "/fr-ca/pricing/"}
if (want && want !== document.documentElement.lang && !localStorage.getItem("lang-choice")) showBanner(copies[want], want);
```

## Research for each market

Search settings differ by locale, so research is done per locale: `growth research ai ... --locale fr-CA`,
`growth research paa ... --locale fr-CA` and `growth journal run ... --locale fr-CA` record the locale on what they file
(`--locale` defaults to the primary locale; the market follows the locale's country) and `growth pace google --locale fr-CA`
prints the Google settings to use. **All locales share one Google door**: the pacer gives one turn every 20 to 30 seconds
to every agent together, so four locales never mean four times the searches. `growth doctor` (step A14) lists every locale.

## On the work board

When the project has two or more locales, `growth board add` (and `import`) makes, after the page's usual jobs:

- one **`localize`** job for each locale that is not the primary (so three for four locales). It carries its locale, needs
  the page's primary copy READY (the original is final before it is copied) and is done by a builder agent: it writes the
  copy at the locale's folder, with its own title, description, canonical, `lang` and hreflang set;
- one **`intl-check`** job (machine, runs side by side with others) that needs all the `localize` jobs and runs the six
  `intl.*` checks on the page.

A project with its own way of making copies can drop either with `pipeline_overrides.drop`. A one-locale project gets
neither. `growth work next --kinds localize` shows the job's locale and the folder to write to.

## Mistakes this chapter exists to prevent

| Mistake | What happens | The guard |
| --- | --- | --- |
| Every copy's canonical points at the English page | Google drops the other languages as duplicates | `intl.canonical` |
| The English page lists the French copy, the French page does not list the English one | Google ignores the pair | `intl.hreflang` (not reciprocal) |
| No `x-default` | visitors no locale fits get no page chosen for them | `intl.hreflang` |
| A script sends French browsers to `/fr-ca/` | a crawler never sees the French page from the English one; visitors cannot reach English | `intl.no-auto-redirect` |
| Relative hreflang addresses | Google ignores them | `intl.hreflang` |
| `<html lang="en">` on a French page | wrong screen reader voice, wrong hyphenation | `intl.lang` |
| Tags left in for a copy that was never written | a tag to a 404 | `intl.copies` (missing translation) |

## Change log

| Date | Version | What changed |
| --- | --- | --- |
| 2026-11-24 | 3.0.0 | First version: locales in `growth.json`, the wizard's two market answers, rule 162, the `localize` and `intl-check` jobs, research per locale. |
