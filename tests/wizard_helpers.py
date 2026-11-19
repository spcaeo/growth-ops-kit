"""Shared helpers for the wizard tests: a fixture site (Astro files, a sitemap index with slashes, a language copy, redirects)
and a way to run `growth` with no access to the real home folder or global git config."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def env(tmp: Path, **extra) -> dict:
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    return {**os.environ, "HOME": str(home), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
            "GROWTH_CRONTAB": "", "GROWTH_LAUNCHD_DIRS": str(tmp / "none"), "PYTHONDONTWRITEBYTECODE": "1", **extra}


def growth(tmp: Path, *args, cwd=None, **extra):
    return subprocess.run([sys.executable, str(ROOT / "growth"), *args], capture_output=True, text=True, cwd=cwd or tmp, env=env(tmp, **extra))


def make_site(tmp: Path) -> tuple[Path, Path]:
    """(site repo folder, sitemap index file)."""
    repo = tmp / "site-repo"
    (repo / "src" / "content" / "blog").mkdir(parents=True)
    (repo / "public").mkdir()
    (repo / "astro.config.mjs").write_text("export default {};\n")
    (repo / "package.json").write_text(json.dumps({"scripts": {"build": "astro build", "preview": "astro preview"}}))
    (repo / "public" / "_redirects").write_text("/old/ /new/ 301\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env(tmp))
    smap = tmp / "sitemap"
    smap.mkdir()
    ns = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml"'
    (smap / "sitemap-index.xml").write_text(f'<?xml version="1.0"?><sitemapindex {ns}>'
                                            '<sitemap><loc>https://shop.example/sitemap-0.xml</loc></sitemap>'
                                            '<sitemap><loc>https://shop.example/sitemap-1.xml</loc></sitemap></sitemapindex>')
    (smap / "sitemap-0.xml").write_text(f'<urlset {ns}><url><loc>https://shop.example/</loc></url>'
                                        '<url><loc>https://shop.example/about/</loc><xhtml:link rel="alternate" hreflang="en-us" href="https://shop.example/en-us/about/"/></url>'
                                        '<url><loc>https://shop.example/blog/post-a/</loc></url></urlset>')
    (smap / "sitemap-1.xml").write_text(f'<urlset {ns}><url><loc>https://shop.example/en-us/about/</loc></url>'
                                        '<url><loc>https://shop.example/en-us/blog/post-a/</loc></url></urlset>')
    return repo, smap / "sitemap-index.xml"


def owner_approve(tmp: Path, *args, cwd, typed=None, timeout=60):
    """Run `growth approve ...` the way the owner does: in a real (pseudo) terminal, typing the code it shows back.
    typed: the words to type instead of the right ones. Returns (exit code, what the terminal showed)."""
    import pty
    import re
    import select
    pid, fd = pty.fork()
    if pid == 0:                                         # the child: its stdin, stdout and /dev/tty are the new terminal
        try:
            os.chdir(cwd)
            os.execve(sys.executable, [sys.executable, str(ROOT / "growth"), "approve", *args], env(tmp))
        finally:
            os._exit(127)
    out, sent = b"", False
    while True:
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            break
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
        m = re.search(rb"approve (\d{4})", out)
        if m and not sent:
            os.write(fd, ((typed if typed is not None else f"approve {m.group(1).decode()}") + "\n").encode())
            sent = True
    _, st = os.waitpid(pid, 0)
    os.close(fd)
    return os.waitstatus_to_exitcode(st), out.decode(errors="replace")
