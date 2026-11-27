# `follow-agent-contract` — the tesseract contract

`type: resource.contract` · `spec: agent.contract` · normative. Every other file is subordinate to this one.

A **plan** is one DNA target compiled for one machine: a tree whose leaves are parts short enough for that machine to synthesize, whose nodes are one-pot assembly reactions, and whose root is the target. Any sequence a machine cannot write in one run can be written as a tree of pieces it can write, joined at junctions that fall on the target's own bases — so, as with the universal approximation theorem for a `web`, one fixed construction covers every target, and the machine's runlength only sets how deep the tree is. The target is never altered to suit the machine: a plan either composes back to it exactly or is refused.

## Specification

```json { type: notebook.cell }
{
  "id": "docs/follow-agent-contract.md",
  "type": "resource.contract",
  "role": "define the plan object, its bytes, composition, its roots, refusals and predicates",
  "reads": ["DISCLAIMER", "tesseract.json", "ooc/tesseract.og"],
  "writes": [],
  "must": ["one canonical byte form", "compose is the only normative direction", "never change a base of the target", "match codes, not prose"],
  "check": ["T1-T11"]
}
```

## Graph

- ← [read-repository.md](read-repository.md)
- → [pin-sources.md](pin-sources.md)
- → [vary-runlength.md](vary-runlength.md)
- → [../skills/compile-chromosome.md](../skills/compile-chromosome.md)
- → [../skills/compose-plan.md](../skills/compose-plan.md)
- → [../systems/order-pool.md](../systems/order-pool.md)
- → [../systems/commit-plan.md](../systems/commit-plan.md)

## Composition

```toml { type: notebook.cell }
format = "tesseract.md"          # the .tess file format: extension, media type, tag
store = "*.tess"                 # canonical plan bytes, §2
pins = "tesseract.json"          # machines, sample targets and plan roots
index = "ooc/tesseract.og"       # ObjectGraph traversal index
ref = "ref/tess.py"              # reference compose (normative) and compile (one valid plan)
tensors = "ref/tmap.py"          # tmap1 tensor map of a plan, §10 (web contract §14)
parent = "wetware-hq/web"        # dna1 sequences (web contract §9), pool1 oligos (§10)
up = "wetware-hq/helix"          # dna: pages, scratch plan claims (§9 here)
order = "systems/order-pool.md"
```

## Indications

- A target longer than a synthesizer's runlength must be built, and the build must be auditable base by base.
- Two machines must be compared before one is bought or booked: how many parts, how many tiers, how many pots, how many bases ordered.
- A `dna:` page in helix names a sequence nobody has printed yet, and an agent wants to propose how it would be built.

## Contraindications

- Not a wet-lab protocol. No buffer, enzyme unit, temperature, cycling or incubation time is specified or validated here.
- Not a fidelity model. `omega1` (§7) is a data-free combinatorial rule; it does not predict mis-ligation rates, and a plan that passes it can still fail in a pot.
- Not a biological designer. A plan does not check that a target is a viable chromosome, that it has an origin, a centromere or a selectable marker, or that a host tolerates it.
- Not a recoder. Where a target holds the only usable enzyme's site, the answer is a refusal, not a silent synonymous edit.

## §0 Objects

| Object | What it is | Exact? |
|---|---|---|
| **target** | one sequence over `ACGT`, length ≥ 1; the thing to be built | yes |
| **machine** | the limits of one synthesis and assembly setup (§3), a row of `tesseract.json` | yes |
| **part** | a leaf of the tree: a contiguous span of the target, floor ≤ length ≤ ceiling, ordered as DNA | yes |
| **pot** | one node: a single one-pot reaction joining its children at their shared junctions | yes |
| **junction** | a cut at base `p`: the `k` bases `target[p : p + k]`, shared by the parts either side as an overhang | yes |
| **plan** | the canonical bytes of one compiled target (§2) | yes |
| **target root** | `sha256` of the ASCII target, unsalted; *not* a helix `sequence-root` (§9) | yes |
| **plan root** | `sha256` of the canonical plan bytes; names the plan as `tess1:<root>` | yes |

A pot whose node is not the root builds an **episome**: an intermediate long enough to be carried in a host (`episome_floor`, §3). The root pot builds the target itself.

## §1 Flow

1. **Project** (optional). `project(nt, machine)` gives the shape a target of `nt` bases would take on each machine, without a sequence in hand (§6).
2. **Compile.** `compile(target, machine)` places junctions, cuts parts, and writes a plan — or refuses (§5). It never changes a base.
3. **Compose.** `compose(plan)` returns the sequence the tree builds, and must equal the target the plan names (§4). This is the normative direction.
4. **Order.** `order(plan)` writes the parts as FASTA, one record per part, with nothing but the target's bases ([`../systems/order-pool.md`](../systems/order-pool.md)).
5. **Build, then read back.** The physical steps are outside this contract. A plan becomes evidence only when a print reads the sequence back (§9).

A plan is immutable. A different machine, floor or allowance is a different plan with a different plan root, against the same target root.

## §2 Plan bytes

A plan is a JSON object written as canonical bytes: `sort_keys`, separators `,` and `:`, ASCII only, exactly one trailing newline (T1). Readers accept bytes `b` only if `canonical(read(b)) == b`.

| Key | Value |
|---|---|
| `tesseract` | `1` — the format tag |
| `machine` | the machine row, copied in full, so a plan is readable without `tesseract.json` |
| `enzyme` | the chosen Type IIS enzyme: `name`, `site`, `overhang` (§3) |
| `floor` | the floor part length in force for this plan (≥ `overhang + 1`, ≤ `ceil`) |
| `allow` | `{"small_episomes": bool, "small_fragments": bool}` — the two waived limits, recorded |
| `target` | `{"nt": int, "root": hex, "gc": float}` |
| `parts` | leaves in target order: `id`, `nt`, `span` `[start, end)`, `gc`, `seq` |
| `pools` | pots, deepest tier first: `id`, `tier`, `nt`, `span`, `children`, `junctions`, `min_hamming` |
| `root_part` | the id of the node whose sequence is the target |
| `shape` | `parts`, `tiers`, `pots`, `part_nt` `[min, max]`, `order_nt` (§6) |

Every base of the target appears in `parts`; a plan is self-contained. `span` is half-open and indexes the target. `junctions` lists the overhangs made inside that pot, left to right; `min_hamming` is the smallest pairwise distance among them (§7), or `null` below two.

## §3 Machine

A machine is data (T2). Each row of `tesseract.json` `machines` carries:

| Field | Meaning |
|---|---|
| `id` | machine name, used in plans and on the command line |
| `floor` | shortest part the machine will make, in bases |
| `ceil` | longest part the machine will make in one run (its **runlength**) |
| `pool` | most parts one pot may join |
| `episome_floor` | shortest intermediate that may be carried as an episome |
| `homopolymer_max` | longest run of one base allowed in a part |
| `gc` | `[min, max]` GC fraction allowed in a part |
| `enzymes` | Type IIS enzymes available: `name`, `site`, `overhang` length `k` |

One knob per physical limit, and no knob that is not a physical limit ([MCHU-91](https://linear.app/mchu001/issue/MCHU-91), minimum engineering idiot index). A machine must satisfy `floor < ceil` and must list at least one enzyme it fits: `overhang + 1 ≤ floor` and `pool + 1 ≤ |omega1(k)|` (§7), else `bad_machine`. A machine may list enzymes it does not fit — `SapI`'s 3-base overhang has only 6 orthogonal values, so a pool of 10 cannot use it — and they are passed over, not an error.

The enzyme is chosen by the target, not by the caller: the first enzyme the machine fits whose site is absent from both strands of the target (T3). If every such enzyme's site occurs, `forbidden_site`.

## §4 Compose

`compose(plan)` is the rule. For each pot, deepest tier first, concatenate the sequences of its children, left to right, overlapping each neighbouring pair by exactly one junction: the left child's last `k` bases must equal the right child's first `k` bases, else `junction_mismatch`. The sequence of `root_part` is the plan's result.

A plan is valid only if (T4):

- every part's `seq` is `ACGT`, matches its `nt`, and lies within floor and ceiling;
- every pot's children compose with matching overhangs, and no two junctions in one pot share an overhang or sit within Hamming distance 2 of each other or each other's complement (§7);
- the composed sequence's length equals `target.nt` and its `sha256` equals `target.root`, else `target_mismatch`.

Anything a plan asserts beyond this — that a machine exists, that a pot ligates, that a host carries an episome — is not checked and is not implied.

## §5 Refusal codes

Agents match the code, never the prose (T5).

| Code | Raised when |
|---|---|
| `bad_length` | the target is empty |
| `bad_base` | the target holds a character other than `ACGT` |
| `bad_machine` | a machine row is missing a field, is inconsistent, or is not in `tesseract.json` |
| `bad_floor` | the requested floor is below `overhang + 1` or above the ceiling |
| `forbidden_site` | every enzyme of the machine has its site in the target |
| `no_junction` | no orthogonal overhang set exists for the cuts the machine's limits allow |
| `above_ceiling` | a part is longer than the machine's runlength |
| `below_floor` | a part is shorter than the floor and `small_fragments` was not allowed |
| `small_episome` | an intermediate is shorter than `episome_floor` and `small_episomes` was not allowed |
| `pool_overflow` | a pot would join more parts than the pool width |
| `homopolymer` | a part holds a run of one base longer than `homopolymer_max` |
| `gc_window` | a part's GC fraction is outside the machine's window |
| `bad_plan` | the plan bytes are not canonical, or a required key is missing |
| `bad_junction` | an overhang is not `k` bases of `ACGT`, is a palindrome, or is a homopolymer |
| `junction_mismatch` | two children of a pot do not share their overhang |
| `target_mismatch` | the composed sequence is not the target the plan names |
| `root_mismatch` | a plan's root is not the one the caller expected |
| `kind_mismatch` | a tensor map of another kind is given where a `plan` map is required (§10) |
| `bad_map` | bytes are not one canonical `tmap1` map in the three plan dtypes (§10) |
| `exists` | the output path is already present |

A refusal never writes a partial plan or a partial sequence.

## §6 Shape

For a target of `n` bases, an overhang of `k` and a machine with runlength `ceil`, the fewest parts are `ceil((n - k) / (ceil - k))`; the tiers follow from the pool width, `tiers = ceil(log_pool(parts))`. The rule is **the fewest tiers the machine allows** (T6): fewest tiers is fewest one-pot reactions in series, and each tier is a day of work and a chance to lose the construct.

Within that tier count, parts are aimed at the middle of the machine's runlength, `(floor + ceil) / 2`, and capped at `pool ** tiers`. Ordering the theoretical minimum of parts would pin every cut to within a few bases of an even split and leave no room to move a junction onto an orthogonal overhang; the slack is what makes §7 solvable. So `parts` is `max(fewest, min(ceil((n - k) / (mid - k)), pool ** tiers))`.

`project(nt, machine)` computes `parts`, `tiers`, `pots` and `order_nt = nt + k * (parts - 1)` from this rule alone, and agrees with `compile` on every target that compiles (T7). A machine with a longer runlength never needs more tiers for the same target; when `ceil ≥ n` the tree is one part and no junction, no pot and no enzyme is used.

## §7 Junctions `omega1`

A junction is usable only if its overhang is `k` bases of `ACGT`, is not a palindrome (it must not anneal to itself), is not a single-base run, and holds at least one strong (`G`, `C`) and one weak (`A`, `T`) base, so no pot mixes an all-strong with an all-weak overhang (T8). Two overhangs in one pot are **orthogonal** when the Hamming distance between them, and between either and the reverse complement of the other, is at least 2 — a single mismatch anywhere must not turn one into another or into another's partner.

`omega1` is the pinned set the compiler draws from: take every usable overhang in alphabetical order and keep each one that is orthogonal to all already kept. The set is deterministic and data-free — 22 overhangs for `k = 4`, 6 for `k = 3` — so two agents reading one plan agree on which overhangs were available. A pot may present at most `|omega1(k)|` junctions, which is why §3 requires `pool + 1 ≤ |omega1(k)|` of the enzyme it uses.

Placement is deterministic. Junctions are placed left to right, each at the cut nearest an even split that the floor and ceiling allow and whose overhang is in `omega1` and unused in every pot the junction belongs to; a dead end backtracks to the previous junction's next-nearest cut. The first complete placement is the plan, so the same target and machine always give the same plan root (T9).

This is a combinatorial rule, not a fidelity model. Published ligation-fidelity data (`pin-sources.md` §Assembly) selects overhang sets by measured mis-ligation rates and supports larger pots than a distance rule does; `omega1` is the conservative, data-free stand-in, and a machine row may be narrowed or widened as data for it is pinned.

## §8 Predicates

| Id | Must hold |
|---|---|
| **T1** | A plan file's bytes are canonical; `canonical(read(b)) == b`. |
| **T2** | Every machine limit comes from `tesseract.json`; no limit is written in the code. |
| **T3** | The enzyme's site does not occur in the target, on either strand. |
| **T4** | `compose(plan)` equals the target, in length and `sha256`, or the plan is refused. |
| **T5** | Every refusal carries a code from §5. |
| **T6** | No plan uses more tiers than the machine's pool width requires for its part count. |
| **T7** | `project` agrees with `compile` on `parts`, `tiers` and `pots` for every target that compiles. |
| **T8** | In each pot, the junctions are pairwise orthogonal members of `omega1`, and none repeats. |
| **T9** | The same target, machine, floor and allowances give the same plan root. |
| **T11** | Every sample plan's tensor map is pinned, holds no base, and re-serializes to the same bytes (§10). |
| **T10** | No plan output contains a base the target does not have at that position; the compiler edits nothing. |

## §9 Up into helix

A helix `dna:` page fixes `sequence-root` and `length` at mint. Those two values are **not** a plan's two roots: a `dna:` page's `sequence-root` is the `Bases` token commitment `sha256(salt ‖ bases)`, salted so that a short sequence cannot be brute-forced from a public chain value, while a plan's `target.root` is the unsalted `sha256` of the target. Nobody without the salt can tell whether a plan's target is a page's sequence; a plan attaches to a page **by subject** — the `dna:<token id>` page an agent asserts it against — never by comparing a target root to a `sequence-root`.

What a page can check without the salt is the length: a plan whose `target.nt` differs from the page's `length` is not a claim about that chromosome. A holder of the sequence and its salt can check the rest, by recomputing both roots.

An agent proposing a build asserts a scratch `plan` claim on the `dna:` page, carrying the plan root, the machine id and the part count. It is a hypothesis and renders as one: it never becomes a `printed` receipt by itself. A print's read-back (web contract §10 `pool1`, helix `printed`) is what can agree with it.

Downward, a target may be any `ACGT` sequence, including one that carries a `dna1` payload from web (web contract §9): a web written as DNA can be compiled for a machine like any other target. tesseract does not interpret the payload.

## §10 Tensor map `tmap1`

A plan has exactly one tensor map, in the universal form `wetware-hq/web` contract §14 defines: named tensors, each a `TensorProto` (TensorFlow `DataType`, shape, row-major `tensor_content`), under the kind `plan`, named by a **tensor root** `sha256` of the map's bytes. `ref/tmap.py` is the reference: standard library only, it writes web's bytes record for record in three dtypes (float32, uint8, uint32). Any other map is read with web's `ref/tensor.py`.

| Tensor | dtype | Shape | What it holds |
|---|---|---|---|
| `allow` | uint8 | `[2]` | `small_episomes`, `small_fragments` as written in the plan |
| `floor` | uint32 | `[]` | the floor part length in force |
| `machine` | uint32 | `[5]` | `floor`, `ceil`, `pool`, `episome_floor`, `homopolymer_max` (§3) |
| `overhang` | uint8 | `[]` | the chosen enzyme's overhang length `k` |
| `part_gc` | float32 | `[p]` | each part's GC fraction, in target order |
| `part_span` | uint32 | `[p, 2]` | each part's half-open `[start, end)` in the target |
| `plan_root` | uint8 | `[32]` | the plan root |
| `pot_child` | uint32 | `[e, 2]` | one edge per child: `[pot node, child node]`, nodes being the `p` parts then the pots |
| `pot_hamming` | uint8 | `[n]` | each pot's `min_hamming`, 0 where the plan writes `null` (§7) |
| `pot_span` | uint32 | `[n, 2]` | each pot's span in the target |
| `pot_tier` | uint32 | `[n]` | each pot's tier, deepest tier first as in the plan |
| `root_node` | uint32 | `[]` | the node whose sequence is the target |
| `shape` | uint32 | `[6]` | `parts`, `tiers`, `pots`, `part_nt` min and max, `order_nt` (§6) |
| `target_nt` | uint32 | `[]` | the target's length in bases |
| `target_root` | uint8 | `[32]` | the unsalted target root (§0), never a helix `sequence-root` (§9) |
| `tesseract` | uint8 | `[]` | `1`, the format tag |

The map is a **view**, not an exact map: it holds no base, so a plan is not rebuilt from it (web §14, rule S4). It is the tree, the cuts and the two roots; the bases come from the target the map names, and `target[start:end]` is the part at that span. A part's own bases travel as a web `sequence` map of that part. An agent that wants the pot tree as a graph has `pot_child` as an edge list, ready for a network, without reading a base.

A plan is mapped only if it composes to the target it names (§4): `of_plan` runs `compose` first, so a tensor root never names a plan that does not build its target. The enzyme's name, the machine's id and the part ids are not tensors — they are strings, and §14 has no string dtype; a reader that needs them reads the plan.

| Id | Must hold |
|---|---|
| **T11** | Every sample plan's tensor map is the map `tesseract.json` pins, holds no base, and re-serializes to the same bytes. |

## Citations

See [`pin-sources.md`](pin-sources.md). Sources are cited and pinned, never vendored — in particular `RomeroLab/omega`, which is GPL-3 and is pinned by commit, not copied.

## Falsification

- A plan this repository ships does not compose back to its target.
- Two runs of the compiler on the same target and machine give different plan roots.
- A plan's part contains a base the target does not have at that position.
- `project` and `compile` disagree on the shape of a target that compiles.
- A pot in a shipped plan repeats an overhang, or holds two overhangs a single mismatch apart.
- A shipped plan's tensor map holds a base, or does not hash to the root `tesseract.json` pins.

## Licence

MIT, see `LICENSE`.
