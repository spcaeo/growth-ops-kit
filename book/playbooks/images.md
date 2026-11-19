---
title: Playbook - covers and pictures
version: 2.0.0
updated: 2026-11-18
license: CC BY 4.0
---

# Playbook: covers and pictures

**Version 2.0.0 (generic edition) · 18 Nov 2026**

A site's pictures are original illustrations or its own photos: no stock photos and no other company's art. This
playbook covers how a picture fits into publishing. The project's `SETUP.md` says where pictures live and how the
current set was made (the generator, the prompt, the export size).

## The two kinds of post picture

| Kind | Used for | What to record |
| --- | --- | --- |
| **Article artwork** (the blog's editorial illustrations) | cards on the blog list and the article page | file names (a full-size and a small version), the alt text, a provenance note (tool, prompt, date) |
| **Cover and share card** | the page's main picture, and the share image (rule 65) | the art without the title drawn in it (rule 61), and a share card that carries the title |

Every post owns one distinct composition. There is no shared fallback image. A test should fail on a missing entry, a
missing file, a repeated name or a copied file (page rulebook rules 61, 62, 63, 64).

## Steps

1. Look at two or three existing covers first: the look, the colours, the level of detail, one idea per picture (the
   subject of the post, in one scene). Rule 36g: it must read in 3 seconds.
2. Make the picture with the image tool the owner has approved. **A paid image call is spent only after the owner
   agrees to the cost.** Ask for the right shape (for example 16:9) with no text baked in. Never copy another
   company's art or layout.
3. **Look at every image yourself.** Automatic checks catch some faults only: wrong subject, odd hands, stray text, a
   copy of another cover.
4. Export at the sizes the site uses (for example 1280 px and 640 px wide, in a modern format). Resize and compress
   only; do not redraw. Name the files after the composition and keep the file extension (rule 64).
5. Register the picture where the site registers pictures, with an `alt` that describes the scene in one plain
   sentence (what a screen reader should say), and a provenance entry (name, files, prompt, date).
6. Set the cover, its alt text and the share image in the post's data (rules 62, 65). The page draws the title, so the
   art never has the title inside it.

## Rules

- Keys and tokens never go in the repo, a commit or a message.
- One house look. Never a stock photo.
- Product pictures and films belong to design jobs, not to a post, and need the owner's yes ([change-a-page](change-a-page.md)).
  A product screenshot carries its capture date (rule 159).
- No picture is heavier than 200 KiB, and each has width and height (rule 63).
- The owner looks at new art before it ships.

## Checks

```
growth checks            # only the checks this change touches (rule 105)
growth gate page <path> --url <local URL> --repo . --type post
```

Then open the post and the blog list at phone and desktop widths (rule 106): the cover is sharp, not cropped through
the subject, and the alt text is there (view source).

## Done when

The tests pass, the owner has seen new art, and the pictures are live on the post and on the list page.
