"""A minimal Next.js-shaped repository for the adapter tests: a few files, made in the test's temp folder with `git init`
(no npm install, no network). It is deliberately plain: no content folder, no middleware rules, no redirect file, no
remote and a branch called `trunk`, so a check that assumes one particular site's layout shows up as a false FAIL."""
import subprocess
from pathlib import Path

FILES = {
    "package.json": '{"name": "brightline-site", "private": true, "dependencies": {"next": "15.0.0", "react": "19.0.0"}}\n',
    "app/layout.tsx": 'import "./globals.css";\nexport default function Layout({ children }: { children: React.ReactNode }) {\n'
                      '  return <html lang="en"><body><main>{children}</main></body></html>;\n}\n',
    "app/globals.css": ":root { --color-ink: #1a1a1a; --color-link: #1a5fd0; }\nhtml { scroll-padding-top: 5rem; }\nbody { color: var(--color-ink); }\n",
    "app/page.tsx": 'export default function Home() { return <section data-fold="hero"><h1>Brightline Lawn Care</h1></section>; }\n',
    "app/lawn-mowing/page.tsx": 'import Link from "next/link";\nexport default function Page() {\n'
                                '  return <section data-fold="hero"><h1>Lawn mowing</h1><Link href="/contact">Get a quote</Link></section>;\n}\n',
    "app/contact/page.tsx": 'export default function Page() { return <section data-fold="form"><h1>Contact</h1></section>; }\n',
    "lib/posts.ts": 'export const posts = [{ slug: "best-mowing-height", title: "Best mowing height" }];\n',
    "middleware.ts": "export function middleware() {}\n",
}


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args], cwd=repo, check=True, capture_output=True)


def make_repo(dest: Path) -> Path:
    """Create the fixture repo in `dest` (one commit on a branch named trunk, no remote) and return it."""
    dest.mkdir(parents=True, exist_ok=True)
    for rel, text in FILES.items():
        f = dest / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    git(dest, "init", "-q", "-b", "trunk")
    git(dest, "add", "-A")
    git(dest, "commit", "-qm", "First commit")
    git(dest, "checkout", "-qb", "page/lawn-mowing")        # a page branch with one change, as the gate expects
    (dest / "app/lawn-mowing/page.tsx").write_text(FILES["app/lawn-mowing/page.tsx"].replace("Lawn mowing", "Lawn mowing, weekly"))
    git(dest, "commit", "-qam", "Change the heading")
    return dest
