# LABRA-AGU — Source document for an explainer video (NotebookLM, English)

> **How to use:** upload this file as a *source* in NotebookLM and generate a
> **Video Overview** (or Audio Overview). Suggested focus prompt: *"Explain in
> accessible terms what LABRA-AGU is, the problem of asset shielding, how the
> agent cross-references multiple sources to uncover fraud, and why the
> change-log (history of edits) is the key differentiator. Audience: lawyers and
> public-sector decision-makers, not programmers. Tone: clear, with analogies,
> about 8 minutes."*

---

## 1. One-line pitch

**LABRA-AGU** is an AI agent that hunts **asset shielding** — the maneuvers
debtors use to hide property and avoid paying what they owe to the State. It
reads data scattered across many databases and documents, joins
the pieces nobody saw together, and pinpoints the fraud **with traceable proof**.

## 2. The problem: fraud lives in the gaps between sources

Picture a debtor who owes millions to the Treasury. He doesn't hide the money in
one place — that would be easy to find. He **slices the scheme** across many:

- at the **commercial registry**, he sells his company's shares to an *offshore*;
- at a **notary**, that offshore appoints his brother-in-law as attorney "with
  full powers" — so the brother-in-law controls everything while, on paper, the
  debtor owns nothing;
- at the **financial-intelligence unit**, three transfers of about R$ 9,000
  appear — each just below the R$ 10,000 reporting threshold (this is called
  *structuring* or *smurfing*);
- and all of it happens **days before a seizure** he knew was coming.

Look at each source **in isolation** and you see no crime: selling shares is
legal, a power of attorney is legal, small transfers are legal. **The fraud only
exists when you put it all together.** No human can do that, at scale, across
millions of records. That is LABRA-AGU's job.

## 3. The big idea: a "river" of events that never forgets

At the core is a special database called **HeraclitusDB**. Think of it as a
**river** that only flows forward: everything that enters becomes a **permanent,
immutable event** — nothing is deleted, nothing is rewritten. If something was
wrong, you **append** a correction; the original stays visible.

This gives three powers, all crucial for the justice system:

1. **Chain of custody.** Every conclusion points, via a unique fingerprint (a
   *ULID*), to the exact documents that support it. No guesswork: every
   accusation has proof traceable to its origin.
2. **Time travel ("AS OF" queries).** You can ask "how did this look on such a
   date?" and reconstruct the past exactly as it was.
3. **Full auditability.** Even *reading* personal data is logged (who queried
   what, and why) — essential for data-protection law.

The name fits: Heraclitus is the philosopher of *"everything flows."* Truth
isn't edited; it accumulates.

## 4. The architecture: three roles that only speak through the river

The system strictly separates duties — as in any serious investigation, whoever
collects the evidence is not whoever judges:

- **The Senses (ingestion)** — pull data from **any** source: government SQL
  databases (Oracle, SQL Server, Postgres…), case PDFs, Word contracts,
  spreadsheets, and even **audio and video** from wiretaps and testimony
  (transcribed locally, so nothing leaves the machine). They **ingest without
  opining**.
- **The Brain (the live daemon)** — the agent that "listens to the river" and,
  with each new document, re-evaluates the whole case. It **investigates without
  touching the original sources**: it only knows the river.
- **The Prosecutor (directives)** — the prosecutor can issue **orders** ("focus
  on offshores", "prioritize this taxpayer ID"). But even an order is an
  auditable event in the river: it records *who asked to investigate what*.

None of the three talks directly to another. Every interaction goes through the
river; every interaction is auditable.

## 5. How the agent thinks, step by step

1. **Read the chaos.** A document arrives. The agent extracts entities (taxpayer
   IDs, company IDs), relationships (who sold what to whom), transactions, dates,
   and **judicial milestones** (seizure, summons, freeze). For clean text, a
   rules-based extractor handles it; for messy text (a scanned, OCR'd case file),
   a **large language model** steps in — and if it fails, the system falls back
   to the rules. It is never left without analysis.
2. **Resolve identities.** The same ID appears in a thousand forms. The agent
   **merges them into a single node**, validating check digits. Without this, the
   fraud would hide among duplicates.
3. **Build the case graph.** Document by document, the agent accumulates a **map
   of relationships** — people, companies, assets, and money, all linked. This is
   where pieces from different sources finally meet.
4. **Run the detectors over the whole graph** — not one document at a time, but
   the consolidated case. That's how it sees a triangulation split across four
   places.
5. **Focus its attention (ACT-R).** Inspired by cognitive science, the agent
   weights entities that appear often and recently — and those the prosecutor
   flagged. It's the focus of a seasoned investigator, expressed as math.
6. **Conclude with proof and with the law.** Each alert carries the narrative,
   the **severity**, the IDs of **all** supporting sources, and the **legal
   basis** (which criminal/civil statute). It even drafts a **theory of the
   case** for the prosecutor to review.

## 6. The fraud catalog

The agent combines two ways of thinking. **Deductive** (known schemes):
offshore triangulation, family front-man, structuring/smurfing, asset
dissipation on the eve of seizure, bribery, cross-donations, holding-with-usufruct,
cascading offshores, hidden ultimate beneficiary, rigged public contracts,
crypto off-ramps, money mules. **Inductive** (finds what *stands out*, even with
no known pattern): using graph analysis and statistics, it spots suspicious hubs,
collector accounts, and the **articulation point** — the one node whose removal
splits the scheme in two: the irreplaceable link of concealment.

## 7. The key differentiator: the change-log (CDC)

Here is the innovation that sets LABRA-AGU apart from a mere database query.

Most systems look only at the **current state** of the tables — the snapshot of
now. LABRA-AGU also reads the **change-log**: the *history of edits* (what was
created, modified, or deleted, by whom and when).

Why it matters — a real example from the system:

> A share sale, in the database, is dated **May 1st** — before the June 5th
> seizure. It looks perfectly legitimate.
>
> But the **change-log** reveals the truth: that date was **edited on June 10th**
> — *after* the seizure — from "June 8th" to "May 1st." The deal was
> **back-dated** to pretend it happened before the execution. And two days later,
> a financial record was **deleted**.

The fraud — **back-dating** and **destruction of evidence** — is **invisible in
the current snapshot**. It only appears when you cross the **database** with the
**log**. LABRA-AGU does exactly that, and the proof it generates points to both
sources at once. *The truth is in the changes, not just the final state.*

## 8. How we know it's right (the science)

A system that "finds fraud" but never measures whether it's correct is
dangerous. So LABRA-AGU has an **evaluation harness**: a set of **labeled
scenarios** — fraud cases *and* legitimate ones — with the right answer known in
advance. It is measured by **precision, recall, and F1**. The legitimate cases
matter as much as the fraudulent ones: they verify the agent **doesn't raise
false alarms** about innocent citizens. Today it scores perfectly with zero false
positives, and this measurement runs automatically on every code change, so no
"improvement" can quietly degrade quality.

## 9. Why it matters

- **Recovers public money.** Every dismantled shielding scheme is an asset
  returned to the State.
- **Turns weeks into seconds.** What a forensic expert would take weeks to
  cross-reference, the agent does continuously, at scale, without tiring.
- **It's proof, not a hunch.** Everything is traceable to source, auditable, and
  arrives with the legal basis attached — ready for the case file.
- **Respects law and privacy.** Sensitive data is processed locally, every read
  is logged, and the immutable history is itself the guarantee of integrity.

LABRA-AGU doesn't replace the prosecutor. It does what machines do best —
cross-reference mountains of data without missing a detail — so the prosecutor
can do what only a human can: judge and act.

## 10. Suggested narrative arc (for the video)

1. **Hook** (15s): "How does a debtor of millions end up owning nothing, on paper?"
2. **The problem** (1m): fraud sliced across sources; no one sees the whole.
3. **The river idea** (1m): event sourcing — truth that cannot be erased.
4. **The three roles** (1m): senses, brain, prosecutor.
5. **The agent in action** (2m): read → resolve identities → graph → detect →
   prove with the law. Use the triangulation case as the throughline.
6. **The differentiator** (1.5m): the change-log and back-dating — the snapshot
   lies, the history doesn't.
7. **Trust** (1m): how we measure correctness; no false alarms.
8. **Close** (30s): recover, at scale, with proof. The machine cross-references;
   the human decides.
