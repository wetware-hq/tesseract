# `vary-runlength` — what a longer write changes

`type: resource.design` · `spec: agent.design` · subordinate to `docs/follow-agent-contract.md`, which governs on any conflict. **Hypotheses only; nothing here is evidence.**

The machine is data (contract §3), so the same target can be compiled against a synthesizer that does not exist yet and the cost of that machine can be read off. This file collects what the shape numbers suggest, and what they do not.

## Specification

```json { type: notebook.cell }
{
  "id": "docs/vary-runlength.md",
  "type": "resource.design",
  "role": "record what varying the machine does to a plan, as hypotheses",
  "reads": ["tesseract.json"],
  "writes": [],
  "must": ["label every claim a hypothesis", "never state a shape that project does not print"],
  "check": ["T6", "T7"]
}
```

## Graph

- ← [follow-agent-contract.md](follow-agent-contract.md)

## The shape of the bet

`ref/tess.py project 316617` — the length of yeast chromosome III, the first chromosome designed and built synthetically (`pin-sources.md` §Theory):

| Machine | Runlength | Parts | Tiers | Pots | Bases ordered |
|---|---|---|---|---|---|
| `m0-chip` | 200 | 2,169 | 4 | 243 | 325,289 |
| `m1-column` | 300 | 1,433 | 4 | 162 | 322,345 |
| `m2-tdt` | 2,000 | 289 | 3 | 33 | 317,769 |
| `m3-bet` | 50,000 | 10 | 1 | 1 | 316,653 |

Tiers are reactions in series: each one is a transformation, a growth, a prep and a check. Pots are reactions in parallel. The ordered-base overhead is the only thing the junctions cost in material — `k` bases per junction, 2.7% of the target at 150-base parts and 0.01% at 50,000.

## Hypotheses

- **Runlength buys tiers, not bases.** Every machine orders about the same number of bases; what a longer write removes is serial reactions. If a build's cost is dominated by the calendar rather than the oligos, runlength is the only parameter worth buying.
- **Depth is the risk, not length.** Each tier is an opportunity to lose the construct, and a failure at tier 3 discards the work of tiers 1 and 2. A one-tier plan either works or fails once.
- **The junction rule is what limits the pot, not the pot.** `omega1` supports 10-way pots; measured fidelity sets support far more (`pin-sources.md` §Assembly). Pinning a fidelity table would cut tiers at the same runlength — the cheapest improvement available here, and the one that needs data this repository does not have.
- **Slack is required.** Ordering the fewest parts the ceiling allows leaves a junction a few bases of freedom and the placement fails (contract §6). A machine whose floor is near its ceiling is hard to compile for even when it is long.
- **The target is the invariant.** Because `target.root` is fixed and `compose` is exact, a plan can be rewritten for a new machine at any time and compared to the old one by the same root. Nothing in a plan is worth preserving once a better machine exists.

## Not claimed

- That `m2-tdt` or `m3-bet` corresponds to any instrument, now or later. They are the limits in the design space, named so the bet can be priced.
- That a 50,000-base part is synthesizable, or that a 10-part pot of 32,000-base fragments assembles.
- That a plan says anything about viability: origin, centromere, marker, copy number and host tolerance are all outside this repository.

## Falsification

- A machine with a longer runlength needs more tiers for the same target (contract T6).
- The table above disagrees with `ref/tess.py project 316617`.

## Licence

MIT, see `LICENSE`.
