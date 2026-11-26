# `.tess`

A `.tess` file is one DNA target compiled for one machine: the tree of parts a synthesizer can make, the pots they are joined in, and the junctions they are joined at. It holds every base of every part, so composing the tree returns the target byte for byte. This page names the file format. [`docs/follow-agent-contract.md`](docs/follow-agent-contract.md) defines it and governs on any conflict.

```toml
[tess]
media_type = "application/vnd.tesseract+json"   # vendor tree, not registered with IANA
extension  = ".tess"
tag        = "tess1"                            # the "tesseract": 1 key of the plan object
version    = "1.0.0"
spec       = "docs/follow-agent-contract.md"
reference  = "ref/tess.py"

[pipeline]
input   = "target --ACGT sequence { any length, no edit allowed }"
process = "cut { Type IIS junctions, omega1 orthogonal overhangs, fewest tiers the machine allows }"
output  = "plan --fileformat .tess { canonical JSON, plan root = sha256(bytes) }"
```

## Axioms

1. **One byte form.** A plan is canonical JSON: sorted keys, no spaces, ASCII, one trailing newline (contract §2). A parser accepts bytes `b` only if `canonical(read(b)) == b`.
2. **Compose is normative.** `compose(plan)` walks the tree and returns one sequence; a plan is valid only if that sequence's sha256 and length equal the `target` it names (contract §4). Compiling is one valid way to reach a plan; composing is the rule.
3. **Two roots.** The **target root** is `sha256` of the ASCII target sequence, the unsalted sequence root of the parent specbase. The **plan root** is `sha256` of the canonical plan bytes, and names the plan: `tess1:<plan root>`. A helix `dna:` page's `sequence-root` is a *salted* commitment, `sha256(salt ‖ bases)`, so it is a different value: only a holder of the salt can link the two (contract §9).
4. **No base is ever changed.** The compiler does not domesticate, recode or pad a target. Where the machine cannot build the sequence as given, it refuses with a code (contract §5) — `no_junction`, `forbidden_site`, `below_floor`, `above_ceiling`, `gc_window`, `homopolymer`, `small_episome`, `pool_overflow`.
5. **Scarless junctions.** Every cut falls on native bases: neighbouring parts overlap by exactly one overhang, which is the `k` bases of the target at the cut. Nothing is inserted, so the assembled sequence carries no scar.
6. **The machine is data.** Floor, ceiling, pool width, episome floor, homopolymer limit, GC window and Type IIS enzymes live in [`tesseract.json`](tesseract.json), not in the code (contract §3). The same target compiles shallower on a machine with a longer runlength, down to one part when the ceiling reaches the target length.
7. **A plan is a hypothesis.** A plan asserts nothing about the physical world. It becomes evidence only when a print reads back the sequence it claims — in helix, a scratch `plan` claim against a `dna:` page until a `printed` receipt agrees (contract §9).
