"""A tiny Astro-shaped repository for the any-stack tests (2.6.0): src/pages, src/components, src/lib, src/styles and tests/.
Made in the test's temp folder with `git init` and its own identity (never the machine's). Main branch `main`, then a
branch `fix/tiny` with one commit, so the branch checks have something to compare."""
import subprocess
from pathlib import Path

FILES = {
    "package.json": '{"name": "tiny-astro", "private": true, "dependencies": {"astro": "5.0.0"}}\n',
    "astro.config.mjs": "export default {};\n",
    "src/styles/base.css": ":root { --link: #1a5fd0; --yes: #1f7a3d; }\nhtml { scroll-padding-top: 5rem; }\n"
                           "a { color: var(--link); text-decoration: underline; }\n",
    "src/components/frame/CopyOpen.astro": '---\nconst { value } = Astro.props;\n---\n<span><button data-copy={value} aria-label="Copy">c</button></span>\n'
                                           "<script>import '../../lib/copy-open';</script>\n",
    "src/lib/copy-open.ts": "export function wire() { document.addEventListener('click', (e) => navigator.clipboard.writeText('x')); }\n",
    "src/components/frame/StickyCta.astro": '---\n---\n<div class="sticky-cta"><a href="/contact-us/">Book a call</a></div>\n',
    "src/components/frame/LinkCard.astro": '---\n---\n<span class="lc" data-lc><span class="lc__title"></span></span>\n',
    "src/components/frame/Logo.astro": '---\nconst head = \'<svg aria-label="Old name">\';\n---\n<Fragment set:html={head} />\n',
    "src/components/frame/Tick.astro": '---\n---\n<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="7"/><path d="M4 8l3 3 5-6"/></svg>\n',
    "src/components/blocks/Hero.astro": '---\n---\n<section><h1>Lawn mowing</h1></section>\n',
    "src/layouts/Base.astro": "---\nimport StickyCta from '../components/frame/StickyCta.astro';\nimport CopyOpen from '../components/frame/CopyOpen.astro';\n"
                              "import '../styles/base.css';\n---\n<html><body><slot /><StickyCta /><CopyOpen value=\"a\" /></body></html>\n",
    "src/pages/index.astro": "---\nimport Base from '../layouts/Base.astro';\n---\n<Base><main><h1>Home</h1></main></Base>\n",
    "src/pages/lawn-mowing.astro": "---\nimport Base from '../layouts/Base.astro';\nimport Hero from '../components/blocks/Hero.astro';\n---\n"
                                   "<Base><main><Hero /></main></Base>\n",
    "tests/copy-open.test.mjs": "import { test } from 'node:test';\ntest('copy open', () => {});\n",
}


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args], cwd=repo, check=True, capture_output=True)


def make_astro_repo(dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    for rel, text in FILES.items():
        f = dest / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    git(dest, "init", "-q", "-b", "main")
    git(dest, "add", "-A")
    git(dest, "commit", "-qm", "First commit")
    git(dest, "checkout", "-qb", "fix/tiny")
    return dest


def commit(repo, msg="Change", email="test@example.com"):
    """Commit everything with one identity (author and committer both `email`)."""
    git(repo, "add", "-A")
    subprocess.run(["git", "-c", "user.name=Test", "-c", f"user.email={email}", "commit", "-qm", msg], cwd=repo, check=True, capture_output=True)
