# `commit-plan` — attach a plan to a chromosome, and read it back

`type: resource.system` · `spec: agent.system` · subordinate to `docs/follow-agent-contract.md`, which governs on any conflict.

A plan root is a 32-byte commitment to a complete build record for one exact target. This file fixes how a plan attaches to a helix `dna:` page and what makes it evidence. No contract is deployed yet: `tesseract.json` `chain` is `null`, so nothing can be committed.

## Specification

```json { type: notebook.cell }
{
  "id": "systems/commit-plan.md",
  "type": "resource.system",
  "role": "commit a plan root and bind it to a chromosome page as a hypothesis",
  "reads": ["*.tess", "tesseract.json"],
  "writes": ["chain (once a contract is pinned)", "helix dna: scratch claims"],
  "must": ["bind by target root", "claim as scratch, never as a receipt", "never rewrite a committed plan root"],
  "check": ["T1", "T4", "T9"]
}
```

## Graph

- ← [../skills/compose-plan.md](../skills/compose-plan.md)
- ← [order-pool.md](order-pool.md)

## Indications

- A `dna:` page in helix names a chromosome and an agent wants to propose, on the record, how it would be built.
- Two agents propose different builds for the same chromosome and the proposals must be compared without trusting either.

## Contraindications

- Never assert a plan as a `printed` receipt. A plan is a hypothesis until a print reads the sequence back (helix contract; web contract §10 `pool1`).
- Never publish a salt, or a target whose sequence a page's holder keeps private. Compiling someone's chromosome is their business; a plan root reveals the whole sequence to anyone holding the plan bytes.
- Never attach a plan whose `target.nt` differs from the page's `length`. It is not a claim about that chromosome. (The roots cannot be compared: a page's `sequence-root` is salted, a plan's target root is not.)
- Never sign a chain transaction while `tesseract.json` `chain` is `null`.

## Algorithm

```text { type: notebook.cell }
commit(plan):
  P := sha256(canonical(plan))            # the plan root
  T := plan.target.root                   # unsalted sequence root, not the chain commitment
  publish (P, T, machine.id, shape.parts, shape.tiers)
  store the canonical bytes keyed by P    # calldata, or a content-addressed store

attach(page, plan):                       # page is dna:<token id>; the subject is the binding
  if page.length != plan.target.nt: fail(target_mismatch)
  assert scratch claim: plan(page) = tess1:<P>, machine, parts

link(plan, salt, seq):                    # only a holder of the sequence and its salt
  sha256(seq) == plan.target.root and sha256(salt || seq) == page.sequence_root
```

- A chromosome page may carry many plans: one per machine, floor or allowance. They do not conflict, because each is a claim about a build, not about the sequence, and the sequence is fixed at mint.
- A plan becomes evidence only by agreement with a receipt: a print whose read-back sequence root equals `target.root`. Until then it renders under hypotheses.
- The plan bytes are small enough to publish in full — the 12,000-base sample's plan is about 13 kB — so a reader can compose it themselves rather than trust the shape.

## Falsification

- A plan is rendered as a receipt, or a plan whose target root is not the page's `sequence-root` appears on that page.
- The same plan root is published with different bytes.

## Licence

MIT, see `LICENSE`.
