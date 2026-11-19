---
title: Playbooks
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbooks

**Version 2.0.0 (generic edition) · 18 Nov 2026**

One file per repeatable job. Every playbook follows the five stages in [agent-steps](agent-steps.md) (audit, write,
test, release, measure). Each one adds what is special to its job: the files, the checks, the traps we already know,
and who approves. Commands are written as `growth <tool> ...` and run in the project folder; the commands that read
the site's code run inside the site repo or a worktree of it.

| Playbook | The job | Who approves |
| --- | --- | --- |
| [agent-steps](agent-steps.md) | The steps for any agent that changes a page, in order, with stop points | the lead |
| [cro-audit](cro-audit.md) | Audit a page for conversion, the same way and depth for every page, then fix | lead |
| [money-page](money-page.md) | A service page, pricing or home: the questioning guide, one page at a time with two owner check-ins, measuring after go-live | lead; owner at both check-ins |
| [cluster-redesign](cluster-redesign.md) | Rebuild one topic's whole set of pages, or one guide, list, comparison or hub, after research | lead; owner sees each page |
| [new-post](new-post.md) | Write and publish a new blog post | owner approves the topic; a reviewer the post |
| [update-post](update-post.md) | Refresh an existing post: new facts, new sections, a new cover | reviewer; owner if a claim about the business changes |
| [fix-a-fact](fix-a-fact.md) | Correct a wrong or old fact, or a fact about the business that reads two ways | reviewer; owner for facts about the business |
| [change-a-page](change-a-page.md) | Change a heading, stat, card, link or alt text on a page | owner for wording and design; reviewer for the rest |
| [internal-linking](internal-linking.md) | The link plan for a page you optimize: which pages link to it, with which search words, from which sentence (`growth link_map`), filed in the journal on each source page | lead; owner for links on the owner's pages |
| [link-graph](link-graph.md) | The map of every internal link on the site, built at onboarding from the rendered pages: orphans, weak pages, anchors, cluster health | lead |
| [lost-pages](lost-pages.md) | Old addresses still asked for, 404s, redirects, pulled pages | owner (it changes what search engines see) |
| [leaving-pages](leaving-pages.md) | A page people leave quickly | owner |
| [images](images.md) | A cover or a page picture | owner looks at new art |
| [site-map](site-map.md) | The address map, the XML sitemap, redirects | lead |
| [release](release.md) | Put work live (branch and PR, or the queue), check it, undo it | lead only; owner's yes to merge |
| [technical-seo](technical-seo.md) | The technical SEO standard (about 150 checks) and its checker `growth tech_seo_check`: run it on every page before the pull request, on a production build before launch, and after go-live | lead |

Which playbook for which job, and the owner check-ins: [01-flow.md](../01-flow.md) stage C.

## Writing a new playbook

Copy the shape of an existing one: **When to use it**, **Before you start**, **Steps**, **Checks**, **Traps we already
fell into**, **Done when**. Add it to the table above and bump the version of this file.

**Every page playbook starts with the pre-flight** (rule 0a; from a real project: "when you start a new page the
planning and preparation should be done in depth and all checkpoints clear set as part of that playbook and
workflow"): `growth preflight` PASS before any edit, the gate after every commit, `growth ready` READY before the owner
sees a URL. A new playbook copies that step.

## How to change the playbooks

Every file starts with the same header (`title`, `version`, `updated`, `license`). **PATCH** = a typo or clearer
sentence; **MINOR** = a new step, rule or playbook; **MAJOR** = the flow changes so old hand-overs are wrong. Whenever
the owner corrects something, add the lesson to [lessons](../lessons.md) and the rule to the
[page rulebook](../03-page-rulebook.md) in the same change.
