# Analysis grading rubric

How to fill in `analysis_worksheet.csv`. The point of this file is that the same
claim gets the same grade regardless of when you grade it — the first pass on
run `20260827_173336` produced 19 claims marked supported whose own notes
described an unsupported element, which made the headline support rate an
artifact of where the line drifted rather than a measurement.

Grade one claim at a time, against its own citation only. Do not credit a claim
because you know it to be true of the company, or because a neighbouring
paragraph of the filing would support it. The question is always: **does this
quoted text, on its own, establish this claim?**

---

## `citation_found_in_filing` — pre-filled, override rarely

Auto-filled by `grade_analysis.py --emit` via substring search, after
normalising whitespace, case, and PDF line-break hyphenation (`non- GAAP` →
`non-GAAP`).

- Leave it TRUE when the check found the quote.
- Set it FALSE only if the "quote" is actually a paraphrase — words the filing
  does not contain, presented as a quotation.
- Set it TRUE if the check said FALSE but you can find the passage yourself
  (the matcher tolerates case and hyphenation artifacts, but not every PDF
  quirk).

This column measures only *does this text exist in the filing*. It is the
mechanical half, and on this run it passed 100% while a sixth of the claims
were still unsupported — so it is not evidence of grounding on its own.

---

## `claim_supported_by_citation` — the load-bearing column

**FALSE if the claim asserts any material element the quoted text does not
state.** A material element is a fact, named entity, causal mechanism, scope, or
consequence that a reader would rely on.

Specifically, mark FALSE when the claim:

- **names something absent from the quote** — competitors, products, categories,
  time periods, dollar figures
- **adds a causal mechanism** the quote does not give ("larger competitors …
  *by responding faster to technological change, undercutting on price, or
  bundling*", where the quote lists only size and resources)
- **adds a consequence** the quote does not state ("… *which could result in
  significant monetary penalties and forced changes to its business practices*")
- **generalises from a single instance** to a pattern ("*persistent and
  sophisticated* cyberattacks" from a quote describing one incident)
- **rests on a bare number** where the claim is interpretive — a cash-flow line
  such as `Stock-based compensation expense 3,509 3,183 2,787` establishes the
  amount, not that it "understates cash profitability relative to GAAP earnings"

Mark TRUE, and record the reservation in `notes`, when the only gap is:

- **tone or confidence** — the claim is more assertive than the quote, but
  asserts nothing additional
- **omission** — the claim is *narrower* than the quote, dropping detail it
  does not need. Everything claimed is still in the quote, so it is supported.
- **peripheral elaboration** — the claim's central assertion is supported and
  the unsupported material is a consequence a reader would draw from the quoted
  fact rather than a new fact about the business. A quote describing a DOJ
  complaint supports a claim that mentions exposure to penalties; a quote
  describing investment ahead of revenue supports a claim that mentions
  underutilised capacity.

The dividing line is **added content, not attitude** — and among added content,
whether the addition is load-bearing. Ask: if the unsupported element were
struck out, would the claim still say the same thing? If yes, TRUE with a note.
If the reader would act differently without it — a named competitor, a distinct
market, a causal mechanism the quote never gives — FALSE.

This is the softer of two possible standards, and deliberately so. It is also
harder to apply consistently than a strict every-element test, which is why the
worked examples below matter more than the wording above: when a new case is
genuinely unclear, match it to the closest example rather than re-deriving the
rule.

---

### Worked examples (run `20260827_173336`)

| Verdict | Case | Quote gives | Claim adds |
|---|---|---|---|
| TRUE | ADBE `business_model_risks`#1 | DOJ complaint and its allegations | exposure to penalties — a consequence of being sued |
| TRUE | MSFT `business_model_risks`#0 | investment at scale, ahead of revenue | underutilised capacity, margin compression — consequences of that |
| TRUE | CRM `business_model_risks`#2 | breach risk incl. third parties | *nothing* — claim is narrower than the quote |
| FALSE | MSFT `competitive_threats`#1 | vertical integration succeeded in PCs, tablets, phones | **PC operating systems** — a distinct market |
| FALSE | TEAM `competitive_threats`#1 | competitors have greater resources | **they respond more quickly to new technology** — a mechanism |
| FALSE | NOW `business_model_risks`#2 | one sentence: breaches have material effect | **cloud delivery, sensitive data, renewal revenue** — facts about the business |
| FALSE | CRM `profitability_quality`#1 | `Stock-based compensation expense 3,509 3,183 2,787` | that SBC **understates cash profitability** — interpretation on a bare number |

The two closest calls on the FALSE side are MSFT `business_model_risks`#2
(generalising one intrusion into a pattern) and NOW `business_model_risks`#2
(a very thin quote). Both were failed because the additions are facts, not
implications — but they sit nearest the line, so revisit them first if the
standard shifts again.

---

## `material` — is this claim worth a reader's attention?

TRUE by default. Mark FALSE when the claim is filler:

- **it restates its own citation** with no added synthesis. If you can delete
  the claim and lose nothing the quote didn't already say, it is not material —
  the model has retrieved, not analysed.
- it is generic enough to apply to any company in the sector without the filing
- it is a trivial or immaterial point relative to the question asked

A claim can be supported and immaterial at the same time; a faithful
restatement is exactly that case. If this column comes back 100% TRUE across a
whole run, suspect the bar rather than the model.

---

## `notes` — free text

Write why, in a phrase. The notes drive the failure taxonomy in `report.py`,
and on the first pass they carried more signal than the booleans did.

**Formatting:** commas are fine, but if you edit the CSV in a text editor you
must quote any field containing one. Two hand-edited CSVs in this project have
been corrupted this way. Editing in a spreadsheet application and exporting to
CSV handles the quoting for you.

---

## What this rubric cannot catch

The columns ask whether a claim is *supported*, never whether it is *correct*.
A confidently wrong claim backed by a valid quote passes. One example from run
`20260827_173336`: a claim that stock-based compensation "inflates GAAP net
income relative to cash economics" is backwards — SBC is an expense that
reduces GAAP net income and is added back to reach operating cash flow. It was
marked FALSE, but for the citation being a bare number, not for being wrong.
If factual accuracy matters for your use case, that needs its own column.
