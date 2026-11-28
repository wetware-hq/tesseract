# `benchmark-reasoning` — score a derivation without pretending it is a model

`type: resource.system` · `spec: agent.system` · subordinate to `docs/follow-agent-contract.md`, which governs on any conflict.

A `.doll` derivation is a reasoning system, not a language model: it emits a build plan, it is deterministic given a goal and a seed, and it carries no verdict. This file says how it is scored alongside models anyway — what is submitted, which numbers are honest, and what the scores do not mean. Attribution for any use of the Artificial Analysis API: <https://artificialanalysis.ai/>.

## Specification

```json { type: notebook.cell }
{
  "id": "systems/benchmark-reasoning.md",
  "type": "resource.system",
  "role": "define the benchmark envelope of a derivation and the four numbers reported with it",
  "reads": ["*.doll", "tesseract.json"],
  "writes": ["submission JSON", "receipt JSON"],
  "must": ["the grade comes from outside the file", "report the reflex baseline beside every score", "never submit a derivation that does not replay"],
  "check": ["T17", "T21"]
}
```

## Graph

- ← [../docs/distil-type-ii.md](../docs/distil-type-ii.md)
- ← [../skills/reason-build.md](../skills/reason-build.md)
- → [commit-plan.md](commit-plan.md)

## What is submitted

```text { type: notebook.cell }
python ref/doll.py submit <der.doll> --problem-id <id> [--proposer <model id>]
```

```json { type: notebook.cell }
{
  "problem_id": "<the problem the goal stands for>",
  "generated_code": "tess1:<plan root>",
  "model": "tesseract-doll1/d<depth>/<proposer>",
  "generation_config": {
    "doll_root": "...", "goal_root": "...", "head": "...",
    "objective": "fewest_tiers", "seed": 0, "theta_ppm": 1000000,
    "budget": {"acts": 16, "mbits": 64000},
    "spent": {"acts": 7, "backtracks": 1, "mbits": 15108, "pots": 28, "predicts": 28},
    "halt": "exhausted", "verdict": "unverified"
  }
}
```

The envelope is the field order of the Artificial Analysis batch evaluation endpoint (`POST /api/v2/critpt/evaluate`, key in `x-api-key`), so a run of derivations serialises into one batch. Two honest limits travel with it:

- **`generated_code` is a plan root, not code.** A grader that executes Python cannot grade it. Submitting to CritPt v2 is therefore only meaningful when a problem's expected artifact *is* a build plan; the endpoint is reused for its schema, rate limits and batch semantics, not to claim a place on a code-generation leaderboard. Grading access there is approved per account (`pin-sources.md` §Benchmarks), and this repository ships no key.
- **The free Data API is for context only.** Model and creator ids and the intelligence index give the baselines a derivation is reported *beside*; no number from it is ever written into a `.doll`.

## The four numbers

| Number | How it is computed | Why it is the honest one |
|---|---|---|
| **Solved** | the share of goals whose derivation emitted a plan that `compose` returns the target for | the only pass/fail this repository can compute itself, and it is exact |
| **Deliberation gain** | solved and objective value of the derivation minus the **reflex baseline**: one `compile` on the goal's first machine, 0 bits, no search (`distil-type-ii.md` D4) | a Type II system that does not beat the reflex has bought nothing with its bits |
| **Bits to pass** | median `spent.mbits` and `spent.acts` over solved goals | the cost side of the same ledger; a score without it is unreadable |
| **Halt calibration** | Brier score of the final gate (mapped to `[0, 1]`) against whether exhausting the search would have found a better plan | what a trained shell is for; with a fresh shell this is the number that shows it is untrained |

A **receipt** is the record of a graded run and lives outside the derivation: `{doll_root, goal_root, head, problem_id, grader, response, wall_ms, when}`, named by the sha256 of its canonical bytes. A receipt may cite a derivation; a derivation may never cite a receipt (`self_certified`).

## Procedure

1. Replay every derivation in the batch (`verify --target`), and drop any that refuses. A derivation that does not replay is not submitted.
2. Run the reflex baseline for each goal: `compile` on the goal's first machine with no search.
3. Serialise one submission per derivation, batch them, and send with `x-api-key`. Record `X-RateLimit-Remaining`; the default limit is 10 requests per 24 hours.
4. Write one receipt per graded derivation. Report all four numbers, or none.
5. If a shell is to be trained, train it on the receipts in `wetware-hq/web` (§15) and commit it there. Nothing in this repository fits a net.

## Not claimed

- That a derivation is comparable to a language model on a general benchmark. It solves one problem family — which machine builds this target best — and its score is a score on that family.
- That the gate of a fresh shell carries information. It does not; that is what halt calibration measures.
- That an accuracy number from a grader says a plan is buildable. `compose` says a plan returns its target; nothing more (§0 Contraindications).

## Licence

MIT, see `LICENSE`.
