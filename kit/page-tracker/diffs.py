"""What changed, read-only from the site repo:
- per change (changes table): the content file's before/after between the change's commit and the commit before it
  that touched the same file (git show <sha>:<file>),
  as readable blocks (headings, paragraphs, list items) with added/removed text, and the frontmatter fields that
  changed (title, description first). Written to diffs/<page>.json, one file per page, fetched by the dashboard only
  when a change is opened.
- editor saves: not used for this site (no editor saves on its own); the table stays empty.
  python3 diffs.py
"""
import difflib, json, os, re, sqlite3, subprocess
import repo_meta

import config
HERE = config.HERE      # the project's page-tracker data folder
OUT = os.path.join(HERE, "diffs")
FIRST_FIELDS = ("title", "metaTitle", "metaDescription", "excerpt", "description", "summary")


def page_file_name(path):
    return (path.strip("/").replace("/", "__") or "home") + ".json"


def show(sha, rel):
    try:
        return repo_meta.git("show", f"{sha}:{rel}")
    except subprocess.CalledProcessError:
        return None


def flat(d, pre=""):
    out = {}
    for k, v in (d or {}).items():
        key = pre + str(k)
        if isinstance(v, dict) and key in ("seo",):
            out.update(flat(v, key + "."))
        elif isinstance(v, (str, int, float, bool)) or v is None:
            out[key] = v
        else:
            out[key] = json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)[:400]
    return out


def blocks(body):
    """Split a body into readable blocks: headings, paragraphs, list items (markdown), trimmed."""
    out = []
    for chunk in re.split(r"\n\s*\n", body or ""):
        chunk = chunk.strip()
        if not chunk:
            continue
        if re.match(r"^([-*]|\d+\.) ", chunk) and "\n" in chunk:
            out += [ln.strip() for ln in chunk.split("\n") if ln.strip()]
        else:
            out.append(re.sub(r"\s*\n\s*", " ", chunk))
    return out


def word_diff(a, b):
    sm = difflib.SequenceMatcher(None, a.split(), b.split(), autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.append(["=", " ".join(a.split()[i1:i2])])
        else:
            if i2 > i1:
                out.append(["-", " ".join(a.split()[i1:i2])])
            if j2 > j1:
                out.append(["+", " ".join(b.split()[j1:j2])])
    return out


def diff(before, after, rel):
    fb, bb = repo_meta.parse(before or "", rel)
    fa, ba = repo_meta.parse(after or "", rel)
    xb, xa = flat(fb), flat(fa)
    skip = {"modified", "date", "wpId"}
    keys = [k for k in sorted(set(xb) | set(xa)) if xb.get(k) != xa.get(k) and k not in skip]
    keys.sort(key=lambda k: (FIRST_FIELDS.index(k) if k in FIRST_FIELDS else 99, k))
    fields = [dict(key=k, before=xb.get(k), after=xa.get(k)) for k in keys]
    A, B = blocks(bb), blocks(ba)
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    out, added, removed = [], 0, 0
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.append(dict(t="same", n=i2 - i1, first=A[i1][:120]))
        elif op == "replace" and i2 - i1 == j2 - j1:
            for a, b in zip(A[i1:i2], B[j1:j2]):
                wd = word_diff(a, b)
                added += sum(len(x[1].split()) for x in wd if x[0] == "+"); removed += sum(len(x[1].split()) for x in wd if x[0] == "-")
                out.append(dict(t="mod", words=wd))
        else:
            for a in A[i1:i2]:
                removed += len(a.split()); out.append(dict(t="del", text=a))
            for b in B[j1:j2]:
                added += len(b.split()); out.append(dict(t="add", text=b))
    return dict(fields=fields, blocks=out, added_words=added, removed_words=removed)


def write_diffs(c):
    os.makedirs(OUT, exist_ok=True)
    ref = repo_meta.branch_ref() if repo_meta.repo_ok() else None
    n = 0
    for path, rel in c.execute("SELECT path, file FROM pages").fetchall():
        rows = c.execute("SELECT sha, live_at FROM changes WHERE path=? ORDER BY live_at", (path,)).fetchall()
        out = {}
        if rel and ref and rows:
            hist = repo_meta.git("log", ref, "--format=%H", "--", rel).split()  # newest first
            for sha, live in rows:
                i = hist.index(sha) if sha in hist else -1
                if i < 0 or i + 1 >= len(hist):
                    continue
                prev_sha = hist[i + 1]  # the commit before it that touched the file
                before, after = show(prev_sha, rel), show(sha, rel)
                if after is None or before is None:
                    continue
                d = diff(before, after, rel)
                d.update(sha=sha, prev_sha=prev_sha, live_at=live, file=rel)
                out[sha] = d
                n += 1
        config.save_json(os.path.join(OUT, page_file_name(path)), out, ensure_ascii=False, separators=(",", ":"))
    print(f"diffs: {n} changes written to diffs/")


def editor_saves(c):
    """A site with no editor that saves on its own (content changes are git commits on a branch) has no
    editor saves to list. The table stays so the dashboard's code path is the same."""
    c.execute("""CREATE TABLE IF NOT EXISTS editor_saves(path TEXT, sha TEXT, at TEXT, role TEXT, fields TEXT,
        PRIMARY KEY(path, sha))""")
    c.commit()


def export_saves(c, path):
    c.execute("""CREATE TABLE IF NOT EXISTS editor_saves(path TEXT, sha TEXT, at TEXT, role TEXT, fields TEXT, PRIMARY KEY(path, sha))""")
    return [dict(sha=r[0], at=r[1], role=r[2], fields=json.loads(r[3] or "[]"))
            for r in c.execute("SELECT sha, at, role, fields FROM editor_saves WHERE path=? ORDER BY at", (path,))]


if __name__ == "__main__":
    con = sqlite3.connect(__import__("config").DB)
    write_diffs(con); editor_saves(con)
