# `compose-plan` — rebuild and check a target from a plan

`type: resource.skill` · `spec: agent.skill` · subordinate to `docs/follow-agent-contract.md`, which governs on any conflict.

Walk a plan's tree, return the one sequence it builds, and check it against the target the plan names. This is the normative direction of the format.

## Specification

```json { type: notebook.cell }
{
  "id": "skills/compose-plan.md",
  "type": "resource.skill",
  "role": "compose a plan into its target and check both roots",
  "reads": ["*.tess", "FASTA"],
  "writes": ["FASTA"],
  "must": ["canonical bytes first", "check the target root", "refuse rather than return a partial sequence"],
  "check": ["T1", "T4", "T5", "T8"]
}
```

## Graph

- ← [compile-chromosome.md](compile-chromosome.md)
- → [../systems/order-pool.md](../systems/order-pool.md)
- → [../systems/commit-plan.md](../systems/commit-plan.md)

## Indications

- A plan arrived from somewhere else and must be trusted before anything is ordered.
- A plan root is cited on a `dna:` page and the citation must be verified against the page's `sequence-root`.

## Contraindications

- Never accept a plan whose bytes are not canonical (`bad_plan`); the plan root would not be the plan's identity.
- Never trust a plan's `shape` or `target.nt` without composing; they are summaries, not evidence.

## Algorithm

```text { type: notebook.cell }
python ref/tess.py compose <plan.tess> <out.fa>
python ref/tess.py check   <plan.tess> [--target target.fa] [--root <plan root>]

compose(plan):
  for each pot, deepest tier first:
    s := first child's sequence
    for each further child:
      if s[-k:] != child[:k]: fail(junction_mismatch)
      s := s + child[k:]
    check no overhang repeats in this pot and all are pairwise orthogonal   # bad_junction
    sequence[pot] := s
  s := sequence[root_part]
  if len(s) != target.nt or sha256(s) != target.root: fail(target_mismatch)
  return s
```

- `check` prints the plan root, machine, enzyme, target root, length and shape, and with `--target` verifies the composed sequence equals a FASTA target byte for byte.
- A plan that composes proves one thing: the parts it lists, joined as it says, are the target. It proves nothing about the physical build (`DISCLAIMER`).

## Sample

```sh
python ref/tess.py check samples/epi-12k.m0-chip.tess --target samples/epi-12k.fa
# <plan root> machine m0-chip enzyme BsaI target 560ca306…2608 nt 12000 parts 83 tiers 2 pots 10 min_hamming 2
```

## Falsification

- `compose` returns a sequence for a plan whose parts do not reconstruct its target root.
- A tampered base, a dropped part or a reordered pot composes without a refusal.

## Licence

MIT, see `LICENSE`.
