# `reason-build` — derive a build the hard way

`type: resource.skill` · `spec: agent.skill` · subordinate to `docs/follow-agent-contract.md`, which governs on any conflict.

One target, several machines and floors offered, one objective: search the offers, pay for each try, and emit the plan the search settled on as a `.doll` derivation (contract §11). The derivation is the reasoning; the plan it names is still checked only by `compose`.

## Specification

```json { type: notebook.cell }
{
  "id": "skills/reason-build.md",
  "type": "resource.skill",
  "role": "run one doll1 derivation over the machines a goal offers, and replay it",
  "reads": ["FASTA", "tesseract.json", "*.doll"],
  "writes": ["*.doll"],
  "must": ["predict before acting", "account every act", "emit verdict unverified", "replay before citing"],
  "check": ["T12", "T13", "T14", "T15", "T16", "T17", "T18", "T19", "T20"]
}
```

## Graph

- ← [../docs/distil-type-ii.md](../docs/distil-type-ii.md)
- ← [compose-plan.md](compose-plan.md)
- → [../systems/benchmark-reasoning.md](../systems/benchmark-reasoning.md)

## Indications

- Several machines, floors or allowances could build a target, and which one is best under an objective is not obvious from the machine rows.
- A compile refused and the question is whether any offer in the space composes at all.
- A build decision has to be auditable later: what was tried, what it cost, why it stopped.

## Contraindications

- One machine, one floor, no objective: that is `compile` (`compile-chromosome.md`), 0 bits, and a derivation would be `unaccounted_cost` theatre.
- Not a designer of targets. A goal names a target by root and length; nothing here proposes a sequence, and the reasoner cannot edit one.
- Not a fidelity or cost model. The objective ranks `tiers`, `pots` and `order_nt` — the three numbers `project` gives — and nothing about money, time or success rate.

## Algorithm

```text { type: notebook.cell }
python ref/doll.py reason <target.fa> <out.doll> [--machines m0-chip,m1-column] [--objective fewest_tiers]
                          [--floors 120,250] [--depth 3] [--seed 0] [--acts 16] [--mbits 64000]
                          [--theta-ppm 15000] [--brief "..."]
python ref/doll.py show   <out.doll>                       # the trace, one line a frame
python ref/doll.py verify <out.doll> --target <target.fa>  # chain, gates, costs, every act replayed
```

1. **Abstract.** Fix the goal: target root and length, the machines and floors offered, the objective, the budget, the depth and the seed. The goal root is the first frame; nothing may change it afterwards (`goal_mutated`).
2. **Branch.** Enumerate every (machine, floor) the goal offers, and pay `ceil(1000·log2(candidates))` millibits for the choice the search is about to make among them.
3. **Predict.** Rank the open candidates by `project` (§6) under the objective, ties broken by the sha256 of the candidate. No base is read; this is the cheap model.
4. **Act.** `compile` the best-predicted candidate and `compose` the result (§4). A refusal is an outcome, not an error: its code is recorded and the candidate is dropped.
5. **Nest.** Move the search state to `(budget spent, surprise)`, run it through the `D` shells, and read the deepest shell's gate.
6. **Halt.** Stop when the gate reaches the goal's `theta_ppm` and a plan has composed, when the budget is out, or when the frontier is empty. Emit the best composed plan under the objective, with `verdict: "unverified"`.
7. **Replay before citing.** `verify` regenerates the shells from the seed, re-runs every act, checks the chain, the gates and the sums, and refuses on any divergence. Never cite a derivation that has not been replayed with its target in hand.

## Worked example

```text { type: notebook.cell }
$ python ref/doll.py reason samples/epi-12k.fa out.doll --objective fewest_tiers --floors 120,250
9dd4222f42fa277c4baba391904b9d7d315597bcb110deb55f89a246a76af8bf halt exhausted machine m3-bet
  plan 87626317b6358aaacde6dda2e55e3fdd89e616cefc4f063c69522ae7a6932a12 tiers 0 pots 0 acts 7 mbits 15108
```

Seven candidates — four machines, plus the two extra floors each machine accepts. The search spends 15,108 millibits over 7 acts, finds that `m1-column` at a floor of 250 cannot be cut at all (`no_junction`: the slack contract §6 leaves is what makes junction placement solvable, and a floor near the ceiling removes it), and settles on the one-part `m3-bet` plan, 0 tiers.

`samples/epi-12k.halt.doll` is the same target with only the two machines that could exist today, the `fewest_bases` objective and `theta_ppm` 15,000: the gate fires after 2 acts and it emits the same plan the exhaustive search would have — one compile saved, with a frozen shell, on one target.

## Falsification

- `verify` on a shipped derivation refuses, or prints a root or head other than the one `tesseract.json` pins.
- `reason` twice on one goal and seed gives two doll roots.
- A derivation's emitted plan is not the best composed plan among its own acts (`replay_divergence`).

## Licence

MIT, see `LICENSE`.
