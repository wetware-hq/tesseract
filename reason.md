# `.doll`

A `.doll` file is one **derivation**: a goal over this repository's machines, a matryoshka of shallow `web`-shaped shells composed into one deeper net, and the hash-chained trace of what a reasoner predicted, did, refused and spent before it emitted a plan. It holds no base and no plan — only roots, shapes, refusal codes and counters — and it never holds a verdict about the world. This page names the file format. [`docs/follow-agent-contract.md`](docs/follow-agent-contract.md) §11 defines it and governs on any conflict.

```toml
[doll]
media_type = "application/vnd.tesseract.doll+json"   # vendor tree, not registered with IANA
extension  = ".doll"
tag        = "doll1"                                 # the "doll": 1 key of the derivation object
version    = "1.0.0"
spec       = "docs/follow-agent-contract.md"
reference  = "ref/doll.py"

[pipeline]
input   = "goal --target root + nt, machines offered, objective, budget, depth, seed { no sequence is named }"
process = "search { predict with project, act with compile+compose, nest the shells, backtrack on a refusal }"
output  = "derivation --fileformat .doll { canonical JSON, doll root = sha256(bytes), head = frame chain }"
```

## Axioms

1. **One byte form.** A derivation is canonical JSON: sorted keys, no spaces, ASCII, one trailing newline (contract §2 bytes, §11). A parser accepts bytes `b` only if `canonical(read(b)) == b`.
2. **Replay is normative.** A derivation is valid only if its frames regenerate: the same goal and seed give the same candidates, the same predictions, the same costs, the same shells, the same gates, the same acts and the same `head` (§11). Reasoning is one way to reach a derivation; replaying it is the rule.
3. **Exactness is `compose`, never a shell.** The plan a derivation emits is checked by contract §4 and nothing else. A shell orders candidates and decides when to stop; it never says a plan is correct, and no net's output is evidence.
4. **A derivation costs something.** Every act is paid for in millibits of the choice it names and recorded in `spent`. A derivation that spent nothing is a reflex, not a thought (`unaccounted_cost`).
5. **A derivation never grades itself.** `verdict` is `"unverified"`, always. A result from the world — a benchmark score, a print read-back — lives outside the file and cites its roots (§12).
6. **The goal is never edited.** The target root, the machines offered and the budget are fixed at the first frame; a trace that changes them is `goal_mutated`. As with a target in a plan, the way to a different goal is a different derivation.
7. **Nesting is real or it is refused.** Every shell moves the search state and is named by its own root. A shell with a zero step, a depth that does not use every shell, or a state that does not move is `fake_nesting`.
