# `distil-type-ii` — the operating system of a Type II machine

`type: resource.design` · `spec: agent.design` · subordinate to `docs/follow-agent-contract.md`, which governs on any conflict.

Dual-process theory splits behaviour into a fast, automatic Type I process and a slow, deliberate Type II one (`pin-sources.md` §Reasoning). The Type I half of this stack is already written down as the seven principles of a reflex machine: present percept only, a fixed table, same percept → same act, no model, a narrow envelope, delegated authority, zero bits per act (`wetware-hq/tulip`, `docs/distil-type-i.md`). This page is the other half: what a Type II machine must do to earn the name, as rules a reader can check against a `.doll` file, each with the refusal code that catches its violation.

## Specification

```json { type: notebook.cell }
{
  "id": "docs/distil-type-ii.md",
  "type": "resource.design",
  "role": "state the operating principles of a Type II machine as checkable rules",
  "reads": ["DISCLAIMER", "../reason.md", "tesseract.json"],
  "writes": [],
  "must": ["one rule, one refusal code", "never call a net's output evidence", "contrast with the Type I principles, never restate them"],
  "check": ["T12-T20"]
}
```

## Graph

- ← [follow-agent-contract.md](follow-agent-contract.md)
- → [../skills/reason-build.md](../skills/reason-build.md)
- → [../systems/benchmark-reasoning.md](../systems/benchmark-reasoning.md)

## The seven principles

| Id | Type II must | Type I (`distil-type-i` P1–P7) | Refusal if broken |
|---|---|---|---|
| **D1** | **Carry a trace.** The act depends on the whole derivation so far, not on the present percept: the frames are hash-chained and the 32-byte `head` names all of them. | P1 present percept only | `replay_divergence` |
| **D2** | **Search, and be able to be wrong.** Candidates are enumerated, tried in an order, and a refused one is abandoned and returned from — not looked up. | P2 a fixed table | `unsat_search` |
| **D3** | **Model the world before paying for it.** Every act is preceded by a prediction from a cheaper model — here `project` (§6), which gives a shape without touching a base — and the error of that prediction is recorded as `surprise_ppm`. | P4 no model | `vacuous_doll` |
| **D4** | **Pay, and say what it paid.** Each choice costs the millibits it takes to name, `ceil(1000·log2(options))`, plus the acts, pots and predictions it consumed. The reflex pays 0 bits; a derivation that reports 0 is lying or is a reflex. | P7 zero bits per act | `unaccounted_cost` |
| **D5** | **Deliberate in depth, and compose that depth.** The shells nest: `D` shallow `web`-shaped nets become one `2D`-layer residual net, and every shell moves the state (§11). Depth that does nothing is not depth. | P5 a narrow envelope | `fake_nesting`, `depth_overflow` |
| **D6** | **Stop on its own, inside a budget.** The gate of the deepest shell decides when the search has had enough, and the budget stops it when the gate does not. Both halts are recorded, so an early stop can be scored against what exhausting the search would have found. | P6 delegated authority | `budget_exhausted` |
| **D7** | **Never grade itself.** The only exactness check is `compose` (§4); the only verdict in the file is `"unverified"`; a score from the world is a separate object that cites the derivation's roots (§12). | P3 same percept → same act | `self_certified` |

D3 and D7 are the two that matter. A system that predicts nothing is a generator with extra steps; a system that grades itself is an oracle, and an oracle cannot be benchmarked.

## What the shells are, and are not

A shell is a `web`: 2 inputs, two hidden layers of 64 sine units, 3 outputs, the shape `wetware-hq/web` fits images with (contract §11, web §2). Composition is residual: `s_k = tanh(s_(k-1) + α_k · Δs_k)` with `(Δs_k, g_k) = shell_k(s_(k-1))`, so `D` shallow nets are one deeper net whose every layer is still a committed object with a root — the matryoshka ([MCHU-95](https://linear.app/mchu001/issue/MCHU-95)).

The two inputs are search dynamics, not semantics: how much of the act budget is spent, and how wrong the world model just was. This is deliberate. A 4,547-parameter sine net over two coordinates can hold a smooth halting surface; it cannot read a DNA target, a junction or a machine row, and nothing here asks it to. A fresh shell is a frozen pseudo-random surface derived from the goal's seed, so a derivation with untrained shells is an exhaustive best-first search with a published stopping rule — and that is the honest baseline a trained shell has to beat.

Training a shell is the outer loop's job, not this repository's: fit a web on the `receipt` records a benchmark run leaves (§12) with `wetware-hq/web` §15 (`fit`, `optim_step`, LoRA `adapter` maps), commit it, and name it by its web root. Nothing in a `.doll` changes when a shell is trained except which bytes its root names.

## Hypotheses

- **Best-first plus an early halt is cheap.** Ordering candidates by the projected objective and stopping on the gate found the same plan as exhausting the search on the sample, at 2 acts instead of 7 (`samples/epi-12k.halt.doll` against `samples/epi-12k.doll`). On one target with one frozen shell this is a demonstration of the mechanism, not a measured gain.
- **Surprise is the signal worth training on.** `project` and `compile` disagree whenever the first enzyme listed is not the enzyme chosen or the floor moves a cut; that disagreement, not the plan, is what a halting surface can learn from.
- **The cheap-generator/strong-reranker split of the seed (`pin-sources.md` §Reasoning) is a hypothesis here, not a rule.** The format allows `depth = 1` and an untrained shell precisely so that "deeper dolls are worth their bits" can be refuted by ablation.

## Not claimed

- That a shell reasons. It ranks nothing and proves nothing; it emits one number that decides whether to keep searching.
- That a derivation's plan is better than a reflex's plan. The reflex — `compile` on a default machine — is the baseline the benchmark reports against (§12).
- That any of this is dual-process theory as psychology. The two names are borrowed to split one engineering problem; no claim about human cognition is made or needed.

## Falsification

- `python ref/doll.py verify samples/epi-12k.doll --target samples/epi-12k.fa` refuses, or prints a head or root other than the one `tesseract.json` pins.
- A derivation in this repository emits a plan that `compose` does not return the target for.
- Two runs of `reason` on the same goal and seed give different doll roots.
- A shipped derivation reports a cost its frames do not sum to, or a verdict other than `unverified`.

## Licence

MIT, see `LICENSE`. Sources are cited and pinned, not vendored.
