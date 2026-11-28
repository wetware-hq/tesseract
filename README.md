# tesseract

**Any chromosome, built from parts a machine can actually make — and checked base by base before anything is ordered.**

> tesseract is academic research material. A plan is a build record an agent can check in software, not a validated protocol or an assembly that has been performed. (Full text: [`DISCLAIMER`](DISCLAIMER).)

## What is this?

A **plan** (a `.tess` file, defined in [`tesseract.md`](tesseract.md)) is one DNA sequence compiled for one machine: the tree of parts short enough for that machine to synthesize, the one-pot reactions that join them, and the junctions they are joined at. Composing the tree returns the target byte for byte, or the plan is not a plan.

A synthesizer has a runlength — the longest strand it will write in one go. Any sequence longer than that can be written as a tree of pieces it can write, joined at junctions that fall on the target's own bases. So one fixed construction covers every target, the way one fixed network shape covers every image in the parent repository [`wetware-hq/web`](https://github.com/wetware-hq/web); the machine's runlength only sets how deep the tree is.

Why compile a chromosome this way:

- **The target is never edited.** No domestication, no recoding, no padding. Where a machine cannot build the sequence as given, the compiler refuses with a code ([contract §5](docs/follow-agent-contract.md)).
- **The plan is the audit.** Every base of every part is in the file, so `compose` reconstructs the target and checks its SHA-256 (its **target root**) without trusting the compiler.
- **The machine is data.** Floor, ceiling, pool width, episome floor, GC and homopolymer limits, Type IIS enzymes — all in [`tesseract.json`](tesseract.json). A machine that does not exist yet can be priced today.

## Try it

```sh
python ref/tess.py project 316617                                             # every machine, no sequence needed
python ref/tess.py compile samples/epi-12k.fa out.tess --machine m0-chip      # 12 kb -> 83 parts
python ref/tess.py check   samples/epi-12k.m0-chip.tess --target samples/epi-12k.fa
python ref/tess.py compose samples/epi-12k.m2-tdt.tess back.fa                # the tree -> the target
python ref/tess.py order   samples/epi-12k.m0-chip.tess order.fa              # the parts to synthesize
python ref/tmap.py map   samples/epi-12k.m0-chip.tess out.tmap   # the plan as named tensors (web §14)
python ref/doll.py reason samples/epi-12k.fa out.doll --objective fewest_tiers  # search the machines (Type II)
python ref/doll.py verify samples/epi-12k.doll --target samples/epi-12k.fa      # replay the whole derivation
python -m unittest discover -s tests
```

Python 3.10+, standard library only. No third-party packages.

## What a longer write buys

`ref/tess.py project 316617` — the length of yeast chromosome III, the first chromosome designed and built synthetically:

| Machine | Runlength | Parts | Tiers | Pots | Bases ordered |
|---|---|---|---|---|---|
| `m0-chip` | 200 | 2,169 | 4 | 243 | 325,289 |
| `m1-column` | 300 | 1,433 | 4 | 162 | 322,345 |
| `m2-tdt` | 2,000 | 289 | 3 | 33 | 317,769 |
| `m3-bet` | 50,000 | 10 | 1 | 1 | 316,653 |

Every machine orders about the same number of bases. What a longer runlength removes is **tiers** — reactions in series, each one a day of work and a chance to lose the construct. At a runlength past the target length the tree collapses to a single part and no enzyme is used at all. `m2-tdt` and `m3-bet` are not instruments; they are the bet on enzymatic synthesis, priced ([`docs/vary-runlength.md`](docs/vary-runlength.md)).

## How a plan is built

| Step | What happens |
|---|---|
| **Enzyme** | Take the first Type IIS enzyme the machine fits whose site is absent from both strands of the target. If every one occurs, refuse — never recode. |
| **Parts** | Fewest tiers the machine's pool width allows; within that, parts aimed at the middle of its runlength, so junctions have room to move. |
| **Junctions** | Cut at the base nearest an even split whose 4-base overhang is in the pinned `omega1` set and is unused in every pot that junction belongs to; a dead end backtracks. |
| **Compose** | Walk the tree, overlap each neighbouring pair by exactly one overhang, and check the result's length and SHA-256 against the target. This is the only normative step. |

Junctions are **scarless**: neighbouring parts overlap by the target's own bases, so nothing is inserted. Overhangs in one pot are pairwise orthogonal — at least 2 mismatches apart from each other and from each other's reverse complement — after `RomeroLab/omega`, which is GPL-3 and is [pinned, never vendored](docs/pin-sources.md).

## Thinking about a build: `doll1`

Everything above is Type I: one target and one machine in, one plan out, no search and nothing spent. A **derivation** ([`reason.md`](reason.md), [contract §11](docs/follow-agent-contract.md)) is the Type II half — given several machines, floors and an objective, it predicts each candidate's shape with `project` before paying for it, compiles and composes the best guess, backtracks on a refusal, and stops when it has had enough:

```text
goal    = target root + nt, machines and floors offered, objective, budget in acts and millibits, depth, seed
predict = project(nt, machine)                  # the cheap world model: a shape, no base read
act     = compile + compose                     # the only exactness check in the system (§4)
nest    = D shallow webs -> one 2D-layer net    # s_k = tanh(s_(k-1) + a_k * ds_k), gate = tanh(g_D)
halt    = gate >= theta | budget out | frontier empty        # verdict is always "unverified"
```

The nesting is the matryoshka: a shell is a `web` of web's own shape (2 in, two hidden layers of 64 sine units, 3 out), and `D` of them compose into one net of `2D` layers whose every layer is still a committed object with a root. Its two inputs are search dynamics — the share of the act budget spent, and how wrong the last prediction was — and nothing else, because a 4,547-number sine net can hold a halting surface and cannot read a sequence. A fresh shell is derived from the goal's seed and fitted by nobody; training one is `wetware-hq/web` §15's job, not this repository's.

```sh
python ref/doll.py reason samples/epi-12k.fa out.doll --objective fewest_tiers --floors 120,250
# 7 candidates, 7 acts, 15,108 millibits, one no_junction backtrack -> the one-part m3-bet plan
python ref/doll.py show   samples/epi-12k.doll          # the trace, one line a frame
python ref/doll.py verify samples/epi-12k.doll --target samples/epi-12k.fa   # chain, gates, costs, acts
python ref/doll.py submit samples/epi-12k.doll --problem-id demo             # the benchmark envelope (§12)
```

A derivation is a record of a search, not evidence about the world: it never grades itself ([`docs/distil-type-ii.md`](docs/distil-type-ii.md) D7), and what a score of one means is fixed in [`systems/benchmark-reasoning.md`](systems/benchmark-reasoning.md) — solved share, gain over the 0-bit reflex baseline, bits to pass, and how badly calibrated the halting gate was.

## Up into helix

A `dna:` page in [`wetware-hq/helix`](https://github.com/wetware-hq/helix) fixes a chromosome's `sequence-root` and length at mint. A plan's target root is *not* that value — the chain commitment is salted, `sha256(salt ‖ bases)`, so only a holder of the salt can link the two — so a plan attaches to a page by subject, and what a reader without the salt can check is the length. It attaches as a **scratch `plan` claim**: the plan root, the machine and the part count an agent proposes. It is a hypothesis and renders as one, until a print's read-back agrees with it ([`systems/commit-plan.md`](systems/commit-plan.md)).

## What is in this repository

| Path | What it covers |
|---|---|
| [`DISCLAIMER`](DISCLAIMER) | The one-line notice. Agents read it first. |
| [`tesseract.md`](tesseract.md) | The `.tess` file format: extension, media type, tag and axioms. |
| [`reason.md`](reason.md) | The `.doll` derivation format: what a Type II search writes down, and its axioms. |
| [`docs/read-repository.md`](docs/read-repository.md) | Where to start: which file to read for which task. |
| [`docs/follow-agent-contract.md`](docs/follow-agent-contract.md) | The rulebook: objects, plan bytes, machines, composition, refusals, junctions, predicates. It wins if files disagree. |
| [`docs/pin-sources.md`](docs/pin-sources.md) | The papers, code and samples, each pinned. |
| [`docs/vary-runlength.md`](docs/vary-runlength.md) | What varying the machine does to a plan (hypotheses only). |
| [`docs/distil-type-ii.md`](docs/distil-type-ii.md) | The operating principles of a Type II machine, D1–D7, against the Type I reflex. |
| [`skills/compile-chromosome.md`](skills/compile-chromosome.md) | Cutting a target into parts. |
| [`skills/compose-plan.md`](skills/compose-plan.md) | Rebuilding and checking a target from a plan. |
| [`skills/reason-build.md`](skills/reason-build.md) | Searching the machines a goal offers, and replaying the search. |
| [`systems/order-pool.md`](systems/order-pool.md) | Turning a plan into an oligo order. |
| [`systems/commit-plan.md`](systems/commit-plan.md) | Attaching a plan to a chromosome page, and on chain. |
| [`systems/benchmark-reasoning.md`](systems/benchmark-reasoning.md) | Scoring a derivation beside models, and the four numbers that are honest. |
| [`ref/tess.py`](ref/tess.py) | The reference compiler (one valid plan) and `compose` (normative). |
| [`ref/tmap.py`](ref/tmap.py) | The `tmap1` tensor maps of a plan and of a derivation, contract §10. |
| [`ref/doll.py`](ref/doll.py) | The reference Type II reasoner: search, nesting, replay, benchmark envelope, contract §11–§12. |
| [`tesseract.json`](tesseract.json) | Machines, sample targets, plan roots and pinned sources. |
| [`ooc/tesseract.og`](ooc/tesseract.og) | ObjectGraph index for traversal without prose. |
| [`samples/`](samples) | A 12 kb target compiled at four machines, a 2 kb target that forces the enzyme to fall through, and two derivations over them. |
| [`tests/`](tests) | Exactness, canonical bytes, junction orthogonality, machine projection, derivation replay, every refusal. |

## Licence

MIT, see [`LICENSE`](LICENSE). Sources are cited and pinned, not vendored.
