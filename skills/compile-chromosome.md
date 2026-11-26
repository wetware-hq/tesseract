# `compile-chromosome` — cut a target into parts a machine can make

`type: resource.skill` · `spec: agent.skill` · subordinate to `docs/follow-agent-contract.md`, which governs on any conflict.

Compile one `ACGT` target against one machine into a canonical `.tess` plan, or refuse.

## Specification

```json { type: notebook.cell }
{
  "id": "skills/compile-chromosome.md",
  "type": "resource.skill",
  "role": "turn a target sequence and a machine into plan bytes",
  "reads": ["FASTA", "tesseract.json"],
  "writes": ["*.tess"],
  "must": ["never change a base of the target", "refuse with a code", "compose before writing"],
  "check": ["T2", "T3", "T6", "T8", "T9", "T10"]
}
```

## Graph

- ← [../docs/follow-agent-contract.md](../docs/follow-agent-contract.md)
- ← [../docs/pin-sources.md](../docs/pin-sources.md)
- → [compose-plan.md](compose-plan.md)

## Indications

- A target is longer than the machine's runlength, or is about to be ordered and the order must be auditable.
- The same target must be priced against several machines (`project` first, then compile against the one chosen).

## Contraindications

- Never edit, recode or domesticate a target to make it compile. A `forbidden_site` refusal is the answer.
- Never overwrite a plan that has been pinned in `tesseract.json` or claimed on a `dna:` page; a new machine or floor is a new plan.
- Never relax a machine row to make one target fit. The row is a physical limit, not a knob per target.

## Algorithm

```text { type: notebook.cell }
python ref/tess.py compile <target.fa> <out.tess> --machine <id>
                           [--floor N --allow-small-fragments --allow-small-episomes]

compile(seq, m, floor):
  check seq is ACGT and non-empty                      # bad_base, bad_length
  enz := first enzyme m fits whose site is absent, both strands   # forbidden_site
  nparts := part_count(n, k, floor, ceil, pool)        # contract §6
  cuts := place_junctions(...)                         # omega1, backtracking; no_junction
  parts := spans between cuts, overlapping by k        # above_ceiling, below_floor,
                                                       # homopolymer, gc_window
  pools := tree(nparts, pool), deepest tier first      # small_episome, pool_overflow
  plan := { machine, enzyme, floor, allow, target, parts, pools, root_part, shape }
  compose(plan)                                        # §4, before anything is written
  write canonical(plan)
```

- The compiler is not normative; any plan that composes to the target under a machine's limits is valid. `compose` is the rule (contract §4).
- Placement is deterministic, so the same inputs give the same plan root. Changing the floor or an allowance changes the plan root.
- `--allow-small-fragments` waives the floor for the last part only; `--allow-small-episomes` waives `episome_floor` for intermediates. Both are recorded in the plan's `allow`, so a reader sees what was waived.

## Sample

| Target | Machine | Parts | Tiers | Pots | Part bases | Plan root |
|---|---|---|---|---|---|---|
| `samples/epi-12k.fa`, 12,000 nt | `m0-chip` | 83 | 2 | 10 | 111–189 | `tesseract.json` `plans` |
| `samples/epi-12k.fa` | `m1-column` | 55 | 2 | 7 | 193–256 | — |
| `samples/epi-12k.fa` | `m2-tdt` | 10 | 1 | 1 | 1,171–1,219 | — |
| `samples/epi-12k.fa` | `m3-bet` | 1 | 0 | 0 | 12,000 | — |
| `samples/site-2k.fa`, 2,000 nt with two `GGTCTC` sites | `m1-column` | 10 | 1 | 1 | 193–214 | enzyme falls through to `BsmBI` |

## Falsification

- A written plan does not compose back to its target, or the same inputs give two plan roots.
- A part's bases differ from the target at that span.

## Licence

MIT, see `LICENSE`.
