# Independent review checklist (rule 109)

The fixed list every independent review answers before READY, for every content change. The reviewer is a different
model from the builder. `growth review new <key>` writes `research/<key>-review-<date>.md` from this list; `ev.review`
passes only when the file answers every item (`R1 pass`, `R1 fixed`, or `R1 n/a: <reason>`, then what was seen) and names a
reviewer who is not the builder. Do not edit the ids; add project items in the review file, not here.

- **R1 Like for like.** Every price sum, saving or "cheaper" claim compares the same feature on both sides. Name the feature the sum is about, then price the cheapest plan on each side that has it. A plan that lacks the feature never stands against one that has it.
- **R2 Head numbers appear in the body.** Every number in the first screen and the verdict (money, percent, count, minutes) appears in the body with its source and date, and the body's figure is the same. A head figure the body never states is a claim the page does not back. (The gate's `claims.head-figures` checks money figures; the reviewer checks the rest.)
- **R3 No two answers contradict.** Compare the FAQ answers with each other, with the body, with the verdict and with the table: the same plan, limit or price is never given two ways, and an answer that holds only "on a paid plan" or "for one user" says so.
- **R4 Every claim has its source.** Each price, limit, feature-by-plan claim and date was read from the vendor's own page and is cited; each worked sum was recomputed.
- **R5 Fairness.** No rival shaded, the business not flattered beyond what its own site says, no limit hidden where it "wins".
- **R6 The first screen answers the reader's question.** It gives the same answer the body proves, and a repeat of it does not fill the page.
- **R7 Held fields.** Every held-field proposal (`growth held list <key>`) that quotes a fact this review changed is rewritten or marked stale.
