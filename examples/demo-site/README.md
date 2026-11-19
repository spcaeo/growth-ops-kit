# Demo site: Brightline Lawn Care

A small made-up website and its project folder. The kit's tests run the gate on it, and you can use it to try the tools
without touching a real site. Nothing here is real: the business, the address and the pages are invented.

```
site/      the website: plain HTML + one CSS file (home, lawn mowing, blog index, one post, about, contact,
           a deliberately weak page, sitemap.xml, robots.txt)
project/   its project folder: growth.json ("stack": "static"), a short BRAND.md, empty logs (steps log, tasks,
           journal) and the empty working folders
serve.py   serves site/ on 127.0.0.1 with clean addresses (/lawn-mowing), using only Python's http.server
```

## Try it

```
python3 examples/demo-site/serve.py 3801 &            # the site on http://127.0.0.1:3801
cd examples/demo-site/project
../../../growth gate page /lawn-mowing --url http://127.0.0.1:3801/lawn-mowing --type money --needs live
../../../growth gate page /lawn-offers --url http://127.0.0.1:3801/lawn-offers --type money --needs live
```

- `/lawn-mowing` is built to pass: 0 FAIL among the checks that read the live page. Checks that need a feature the site does
  not have (a sticky call bar, a call dialog) or an adapter for another stack (the Next.js code checks) are printed as
  `SKIP <id>: <why>`, never as OK.
- `/lawn-offers` is deliberately weak (two H1s, hype words, a TODO, a raw booking link, no meta description, no breadcrumbs,
  no structured data), so the tests can prove the checks fire. Its Fix lines show what each check wants.
- The home page, the post, the blog index, About and Contact are simple background pages. They are not built to pass the
  whole gate; build a page to the rulebook with the playbooks in `book/playbooks/`.

Stop the server when you are done (`kill %1`, or the pid you started).

The tests (`python3 -m pytest tests`) do the same on a free port, and stop their own server at the end.
