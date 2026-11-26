"""Reference `tess1` compiler: one DNA target as a tree of synthesizable parts, and back.

Needs only Python 3.10+ (no third-party packages). `compose` is normative and exact
(docs/follow-agent-contract.md §4): compose(compile(seq, machine)) == seq for every plan this
compiler writes. The compiler never changes a base of the target; where the machine cannot
build it, the compiler refuses with a code (§5).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

BASES = "ACGT"
COMPLEMENT = str.maketrans("ACGT", "TGCA")
LINE = 80  # FASTA line width; layout only, never part of the sequence
TAG = b"tess1"
PINS = Path(__file__).resolve().parent.parent / "tesseract.json"


class Refusal(Exception):
    """A refusal carries a stable code (§5). Agents match the code, never the message."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- sequence helpers


def revcomp(seq):
    return seq.translate(COMPLEMENT)[::-1]


def gc(seq):
    return (seq.count("G") + seq.count("C")) / len(seq) if seq else 0.0


def longest_run(seq):
    best = run = 0
    prev = ""
    for b in seq:
        run = run + 1 if b == prev else 1
        prev = b
        best = max(best, run)
    return best


def seq_root(seq):
    """A target is named by the sha256 of its bases as ASCII, as in `wetware-hq/web` §9."""
    return hashlib.sha256(seq.encode("ascii")).hexdigest()


def hamming(a, b):
    return sum(x != y for x, y in zip(a, b))


# ---------------------------------------------------------------- the machine


def machines(path=None):
    """Machine descriptions are data, not code: `tesseract.json` `machines`."""
    try:
        pins = json.loads(Path(path or PINS).read_text())
    except (OSError, ValueError) as err:
        raise Refusal("bad_machine", str(err)) from None
    return {m["id"]: m for m in pins["machines"]}


def machine(mid, path=None):
    found = machines(path).get(mid)
    if found is None:
        raise Refusal("bad_machine", f"no machine {mid!r}")
    check_machine(found)
    return found


def check_machine(m):
    need = ("id", "floor", "ceil", "pool", "episome_floor", "homopolymer_max", "gc", "enzymes")
    for key in need:
        if key not in m:
            raise Refusal("bad_machine", f"missing {key}")
    if not m["enzymes"]:
        raise Refusal("bad_machine", "no enzyme")
    if not 1 <= m["floor"] <= m["ceil"]:
        raise Refusal("bad_machine", f"floor {m['floor']} ceil {m['ceil']}")
    if m["pool"] < 2:
        raise Refusal("bad_machine", f"pool {m['pool']} cannot join two parts")
    lo, hi = m["gc"]
    if not 0.0 <= lo <= hi <= 1.0:
        raise Refusal("bad_machine", f"gc window {m['gc']}")
    if not any(fits(enz, m) for enz in m["enzymes"]):
        raise Refusal("bad_machine", f"no enzyme of {m['id']} has {m['pool'] + 1} orthogonal overhangs")


def fits(enz, m):
    """Whether one enzyme can serve a machine's pool width and floor (§3)."""
    return (enz["overhang"] + 1 <= m["floor"]
            and m["pool"] + 1 <= len(orthogonal_set(enz["overhang"])))


def enzyme_for(seq, m):
    """The first enzyme the pool width fits whose recognition site is absent, either strand.

    The compiler never edits the target, so a target carrying every machine site is refused
    rather than domesticated (§4 axiom 1).
    """
    usable = [enz for enz in m["enzymes"] if fits(enz, m)]
    for enz in usable:
        site = enz["site"]
        if site not in seq and revcomp(site) not in seq:
            return enz
    sites = ", ".join(f"{e['name']} {e['site']}" for e in usable)
    raise Refusal("forbidden_site", f"target carries every site of {m['id']}: {sites}")


# ---------------------------------------------------------------- junctions (omega1)


def junction_ok(h, _=None):
    """A scarless overhang is usable on its own: not a palindrome, not all-strong, not all-weak."""
    if len(h) < 2 or any(b not in BASES for b in h):
        return False
    if h == revcomp(h):  # ligates to itself, so it is never orthogonal
        return False
    strong = h.count("G") + h.count("C")
    if strong == 0 or strong == len(h):
        return False
    return longest_run(h) < len(h)


def orthogonal_set(k):
    """The pinned `omega1` overhang set: greedy over all usable overhangs in alphabetical order.

    Deterministic, so two agents reading one plan agree on which overhangs were available.
    22 overhangs for k = 4, 6 for k = 3. A pot may present at most that many (§7).
    """
    out = []
    for i in range(4 ** k):
        h = "".join(BASES[(i >> (2 * (k - 1 - j))) & 3] for j in range(k))
        if junction_ok(h, None) and all(orthogonal(h, other) for other in out):
            out.append(h)
    return out


def orthogonal(a, b):
    """`omega1`: two overhangs are orthogonal if neither strand of one mis-ligates to the other.

    Data-free and deterministic: two mismatches apart on both strands. Weaker than OMEGA's
    fidelity-data optimisation (docs/pin-sources.md §Assembly); it bounds nothing, it only
    excludes the pairs every ligation data set shows cross-ligating.
    """
    return min(hamming(a, b), hamming(a, revcomp(b))) >= 2


def place_junctions(seq, enz, nparts, floor, ceil, reactions):
    """Cut positions whose overhangs come from the `omega1` set and stay orthogonal in every pot.

    Deterministic: junctions are placed left to right, each as near as the machine allows to an
    even split, and a dead end backtracks to the previous junction's next-nearest cut. The first
    plan found is the one returned, so the same target and machine always give the same plan.
    """
    k, n = enz["overhang"], len(seq)
    allowed = set(orthogonal_set(k))
    pots_of = {j: [r for r in reactions if j in r] for j in range(1, nparts)}

    def candidates(j, prev):
        nominal = round(j * (n - k) / nparts)
        lo = max(prev + floor - k, j * (floor - k), n - k - (nparts - j) * (ceil - k))
        hi = min(prev + ceil - k, j * (ceil - k), n - k - (nparts - j) * (floor - k))
        out = [p for p in range(lo, hi + 1) if seq[p:p + k] in allowed]
        return sorted(out, key=lambda p: (abs(p - nominal), p))

    budget, cuts, overhangs = 400_000, [0], []
    stack = [iter(candidates(1, 0))]
    while stack:
        if budget <= 0:
            raise Refusal("no_junction", f"gave up placing {nparts - 1} junctions under {enz['name']}")
        budget -= 1
        p = next(stack[-1], None)
        if p is None:
            stack.pop()
            if cuts[1:]:
                cuts.pop()
                overhangs.pop()
            continue
        j, h = len(stack), seq[p:p + k]
        if any(not orthogonal(h, overhangs[i - 1]) for r in pots_of[j] for i in r if i < j):
            continue
        cuts.append(p)
        overhangs.append(h)
        if j == nparts - 1:
            return cuts, overhangs
        stack.append(iter(candidates(j + 1, p)))
    raise Refusal("no_junction", f"no orthogonal {k}-nt overhangs exist for {nparts} parts")


def tree(nparts, width):
    """Group parts into pots of at most `width` children, bottom up, left to right.

    Deterministic and as shallow as the machine allows (§6): the fewest tiers, and at each
    tier groups whose sizes differ by at most one.
    """
    tiers = []
    nodes = [(i, i + 1) for i in range(nparts)]  # (first part, last part + 1)
    while len(nodes) > 1:
        groups = -(-len(nodes) // width)
        tier, start = [], 0
        for g in range(groups):
            end = (g + 1) * len(nodes) // groups
            kids = nodes[start:end]
            tier.append({"span": (kids[0][0], kids[-1][1]), "children": kids})
            start = end
        tiers.append(tier)
        nodes = [node["span"] for node in tier]
    return tiers


def pots(tiers, nparts):
    """For each pot, the junction indices present in that one reaction.

    A junction `j` separates part `j - 1` from part `j`. In a pot it is either internal, made
    by that reaction, or a flank the pot presents to its parent.
    """
    out = []
    for tier in tiers:
        for node in tier:
            a, b = node["span"]
            inside = [kid[1] for kid in node["children"][:-1]]
            flanks = [j for j in (a, b) if 0 < j < nparts]
            out.append(sorted(set(inside + flanks)))
    return out


# ---------------------------------------------------------------- compile


def part_count(n, k, floor, ceil, pool):
    """How many base parts to order (§6).

    The fewest tiers the machine allows is the rule; within that tier count, parts are aimed at
    the middle of the machine's runlength so junctions have room to move to an orthogonal
    overhang. Ordering the fewest possible parts would pin every cut to within a few bases.
    """
    fewest = max(1, -(-(n - k) // (ceil - k)))
    if fewest == 1:
        return 1
    tiers = len(tree(fewest, pool))
    mid = (floor + ceil) // 2
    return max(fewest, min(-(-(n - k) // (mid - k)), pool ** tiers))


def compile_plan(seq, m, floor=None, small_fragments=False, small_episomes=False):
    """Target sequence -> a `tess1` plan (§3). Refuses rather than alter a base."""
    check_sequence(seq)
    enz = enzyme_for(seq, m)
    k, n = enz["overhang"], len(seq)
    floor = m["floor"] if floor is None else floor
    if not k + 1 <= floor <= m["ceil"]:
        raise Refusal("bad_floor", f"floor {floor} outside {k + 1}-{m['ceil']}")
    nparts = part_count(n, k, floor, m["ceil"], m["pool"])
    cuts, overhangs = [0], []
    if nparts > 1:
        reactions = pots(tree(nparts, m["pool"]), nparts)
        cuts, overhangs = place_junctions(seq, enz, nparts, floor, m["ceil"], reactions)
    bounds = cuts + [n - k]
    parts = []
    for j in range(nparts):
        start, end = bounds[j], bounds[j + 1] + k
        frag = seq[start:end]
        last = j == nparts - 1
        if len(frag) > m["ceil"]:
            raise Refusal("above_ceiling", f"part {j} is {len(frag)} nt, ceiling {m['ceil']}")
        if len(frag) < floor and not (last and small_fragments):
            raise Refusal("below_floor", f"part {j} is {len(frag)} nt, floor {floor}")
        if longest_run(frag) > m["homopolymer_max"]:
            raise Refusal("homopolymer", f"part {j} has a run of {longest_run(frag)}")
        if not m["gc"][0] <= gc(frag) <= m["gc"][1]:
            raise Refusal("gc_window", f"part {j} is {gc(frag):.4f} GC, window {m['gc']}")
        parts.append({"id": f"p{j}", "nt": len(frag), "span": [start, end], "gc": round(gc(frag), 4), "seq": frag})
    pools, tiers = [], tree(nparts, m["pool"]) if nparts > 1 else []
    index = {(i, i + 1): f"p{i}" for i in range(nparts)}
    for t, tier in enumerate(tiers, start=1):
        for g, node in enumerate(tier):
            a, b = node["span"]
            start, end = bounds[a], bounds[b] + k
            root = t == len(tiers) and len(tier) == 1
            pid = "chr" if root else f"e{t}-{g}"
            inside = [overhangs[kid[1] - 1] for kid in node["children"][:-1]]
            nt = end - start
            if not root and nt < m["episome_floor"] and not small_episomes:
                raise Refusal("small_episome", f"{pid} is {nt} nt, episome floor {m['episome_floor']}")
            if len(node["children"]) > m["pool"]:
                raise Refusal("pool_overflow", f"{pid} joins {len(node['children'])} parts, pool {m['pool']}")
            pools.append({
                "id": pid, "tier": t, "nt": nt, "span": [start, end],
                "children": [index[kid] for kid in node["children"]],
                "junctions": inside,
                "min_hamming": min_hamming(inside) if len(inside) > 1 else None,
            })
            index[node["span"]] = pid
    plan = {
        "tesseract": 1,
        "machine": m,
        "enzyme": enz,
        "floor": floor,
        "allow": {"small_episomes": bool(small_episomes), "small_fragments": bool(small_fragments)},
        "target": {"nt": n, "root": seq_root(seq), "gc": round(gc(seq), 4)},
        "parts": parts,
        "pools": pools,
        "root_part": pools[-1]["id"] if pools else parts[0]["id"],
        "shape": {
            "parts": nparts, "tiers": len(tiers), "pots": len(pools),
            "part_nt": [min(p["nt"] for p in parts), max(p["nt"] for p in parts)],
            "order_nt": sum(p["nt"] for p in parts),
        },
    }
    compose(plan)  # a plan this compiler writes always composes back to its target (§4)
    return plan


def min_hamming(overhangs):
    return min(min(hamming(a, b), hamming(a, revcomp(b)))
               for i, a in enumerate(overhangs) for b in overhangs[i + 1:])


def check_sequence(seq):
    if not seq:
        raise Refusal("bad_length", "empty target")
    bad = [b for b in seq if b not in BASES]
    if bad:
        raise Refusal("bad_base", f"{bad[0]!r} at {seq.index(bad[0])}")


# ---------------------------------------------------------------- compose (normative)


def compose(plan):
    """Plan -> the one sequence it builds (§4). Every junction is checked, nothing is guessed."""
    if not isinstance(plan, dict) or plan.get("tesseract") != 1:
        raise Refusal("bad_plan", "not a tess1 plan")
    for key in ("enzyme", "parts", "pools", "root_part", "target"):
        if key not in plan:
            raise Refusal("bad_plan", f"missing {key}")
    k = plan["enzyme"].get("overhang")
    if not isinstance(k, int) or k < 2:
        raise Refusal("bad_plan", f"overhang {k}")
    built = {}
    for part in plan["parts"]:
        if part["id"] in built:
            raise Refusal("bad_plan", f"duplicate id {part['id']}")
        check_sequence(part.get("seq", ""))
        if len(part["seq"]) != part["nt"]:
            raise Refusal("bad_plan", f"{part['id']} says {part['nt']} nt, holds {len(part['seq'])}")
        built[part["id"]] = part["seq"]
    for pot in plan["pools"]:
        kids = pot.get("children") or []
        if len(kids) < 2:
            raise Refusal("bad_plan", f"{pot['id']} joins {len(kids)} parts")
        if pot["id"] in built:
            raise Refusal("bad_plan", f"duplicate id {pot['id']}")
        if len(pot.get("junctions", [])) != len(kids) - 1:
            raise Refusal("bad_plan", f"{pot['id']} has {len(pot.get('junctions', []))} junctions for {len(kids)} parts")
        seq, present = built.get(kids[0]), []
        if seq is None:
            raise Refusal("bad_plan", f"{pot['id']} joins unbuilt {kids[0]}")
        for h, kid in zip(pot["junctions"], kids[1:]):
            nxt = built.get(kid)
            if nxt is None:
                raise Refusal("bad_plan", f"{pot['id']} joins unbuilt {kid}")
            if seq[-k:] != h or nxt[:k] != h:
                raise Refusal("junction_mismatch", f"{pot['id']} at {kid}: {seq[-k:]} | {h} | {nxt[:k]}")
            if not junction_ok(h, None):
                raise Refusal("bad_junction", f"{pot['id']}: {h}")
            present.append(h)
            seq += nxt[k:]
        for i, a in enumerate(present):
            for b in present[i + 1:]:
                if not orthogonal(a, b):
                    raise Refusal("bad_junction", f"{pot['id']}: {a} and {b} are not orthogonal")
        built[pot["id"]] = seq
    out = built.get(plan["root_part"])
    if out is None:
        raise Refusal("bad_plan", f"no part {plan['root_part']}")
    if seq_root(out) != plan["target"]["root"] or len(out) != plan["target"]["nt"]:
        raise Refusal("target_mismatch", f"{seq_root(out)} {len(out)} nt")
    return out


# ---------------------------------------------------------------- plan bytes


def canonical(plan):
    """One byte form: RFC 8785-style JSON, keys sorted, no space, one trailing newline."""
    return (json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def plan_root(plan):
    return hashlib.sha256(canonical(plan)).hexdigest()


def read_plan(path):
    try:
        blob = Path(path).read_bytes()
    except OSError as err:
        raise Refusal("bad_plan", str(err)) from None
    try:
        plan = json.loads(blob)
    except ValueError as err:
        raise Refusal("bad_plan", str(err)) from None
    if canonical(plan) != blob:
        raise Refusal("bad_plan", "not the canonical byte form")
    return plan


def write(path, blob):
    if Path(path).exists():
        raise Refusal("exists", str(path))
    with open(path, "xb") as f:
        f.write(blob)


# ---------------------------------------------------------------- projection


def project(nt, m, floor=None):
    """The shape a target of `nt` bases takes on a machine, without cutting it (§6).

    Agrees with `compile` on shape for every target that compiles, so an agent can compare
    machines before it has a sequence in hand.
    """
    check_machine(m)
    k = m["enzymes"][0]["overhang"]
    floor = m["floor"] if floor is None else floor
    parts = part_count(nt, k, floor, m["ceil"], m["pool"])
    tiers = tree(parts, m["pool"]) if parts > 1 else []
    return {"machine": m["id"], "ceil": m["ceil"], "parts": parts, "tiers": len(tiers),
            "pots": sum(len(t) for t in tiers), "order_nt": nt + k * (parts - 1)}


# ---------------------------------------------------------------- sample targets


def seeded(nt, seed=0, sites=()):
    """A deterministic pseudo-random target: sha256(TAG || seed || counter) read two bits a time.

    Rejects a base that would make a run of 4 or complete a forbidden site, so the sequence is
    a stand-in for a synthesizable construct, not a biological one.
    """
    out = []
    i = 0
    while len(out) < nt:
        block = hashlib.sha256(TAG + seed.to_bytes(8, "big") + i.to_bytes(8, "big")).digest()
        i += 1
        for byte in block:
            for shift in (6, 4, 2, 0):
                if len(out) == nt:
                    break
                b = BASES[(byte >> shift) & 3]
                tail = "".join(out[-7:]) + b
                if len(tail) >= 4 and tail[-4:] == b * 4:
                    continue
                if any(tail.endswith(s) or tail.endswith(revcomp(s)) for s in sites):
                    continue
                out.append(b)
    return "".join(out)


# ---------------------------------------------------------------- FASTA


def read_fasta(path):
    try:
        text = Path(path).read_text(encoding="ascii")
    except UnicodeDecodeError as err:
        raise Refusal("bad_base", f"non-ASCII byte at {err.start}") from None
    except OSError as err:
        raise Refusal("bad_base", str(err)) from None
    if not text.startswith(">"):
        raise Refusal("bad_base", "not a FASTA record")
    body = text.split("\n", 1)[1] if "\n" in text else ""
    if ">" in body:
        raise Refusal("bad_base", "more than one FASTA record")
    seq = "".join(body.split()).upper()
    check_sequence(seq)
    return seq


def write_fasta(path, seq, header):
    if Path(path).exists():
        raise Refusal("exists", str(path))
    with open(path, "x", encoding="ascii") as f:
        f.write(f">{header}\n")
        for i in range(0, len(seq), LINE):
            f.write(seq[i:i + LINE] + "\n")


def write_order(path, plan):
    """The oligo order: every tier-0 part, one FASTA record each, in plan order."""
    if Path(path).exists():
        raise Refusal("exists", str(path))
    with open(path, "x", encoding="ascii") as f:
        for part in plan["parts"]:
            f.write(f">{part['id']} nt={part['nt']} span={part['span'][0]}-{part['span'][1]}\n")
            f.write(part["seq"] + "\n")


# ---------------------------------------------------------------- CLI


def main(argv=None):
    ap = argparse.ArgumentParser(description="tess1: compile a DNA target into a part tree, and compose it back")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compile", help="target FASTA -> .tess plan")
    c.add_argument("fasta")
    c.add_argument("out")
    c.add_argument("--machine", required=True)
    c.add_argument("--floor", type=int, default=None, help="set the floor part length")
    c.add_argument("--allow-small-fragments", action="store_true")
    c.add_argument("--allow-small-episomes", action="store_true")
    s = sub.add_parser("compose", help="plan -> the sequence it builds")
    s.add_argument("plan")
    s.add_argument("out")
    k = sub.add_parser("check", help="compose a plan and report its shape")
    k.add_argument("plan")
    k.add_argument("--target", default=None)
    k.add_argument("--root", default=None, help="expected plan root")
    o = sub.add_parser("order", help="plan -> the oligo pool to order, as FASTA")
    o.add_argument("plan")
    o.add_argument("out")
    p = sub.add_parser("project", help="the shape a target of n bases takes on each machine")
    p.add_argument("nt", type=int)
    p.add_argument("--machine", default=None)
    sub.add_parser("machines", help="list machine descriptions")
    d = sub.add_parser("seed", help="write a deterministic sample target")
    d.add_argument("nt", type=int)
    d.add_argument("out")
    d.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "compile":
            seq = read_fasta(a.fasta)
            plan = compile_plan(seq, machine(a.machine), a.floor, a.allow_small_fragments, a.allow_small_episomes)
            write(a.out, canonical(plan))
            sh = plan["shape"]
            print(f"{plan_root(plan)} parts {sh['parts']} tiers {sh['tiers']} pots {sh['pots']} "
                  f"part_nt {sh['part_nt'][0]}-{sh['part_nt'][1]} order_nt {sh['order_nt']}")
        elif a.cmd == "compose":
            plan = read_plan(a.plan)
            seq = compose(plan)
            write_fasta(a.out, seq, f"tess1 nt={len(seq)} plan={plan_root(plan)}")
            print(seq_root(seq), len(seq))
        elif a.cmd == "check":
            plan = read_plan(a.plan)
            seq = compose(plan)
            if a.root and plan_root(plan) != a.root:
                raise Refusal("root_mismatch", plan_root(plan))
            if a.target and read_fasta(a.target) != seq:
                raise Refusal("target_mismatch", a.target)
            sh = plan["shape"]
            hams = [p["min_hamming"] for p in plan["pools"] if p["min_hamming"] is not None]
            print(f"{plan_root(plan)} machine {plan['machine']['id']} enzyme {plan['enzyme']['name']} "
                  f"target {plan['target']['root']} nt {plan['target']['nt']} parts {sh['parts']} "
                  f"tiers {sh['tiers']} pots {sh['pots']} min_hamming {min(hams) if hams else None}")
        elif a.cmd == "order":
            plan = read_plan(a.plan)
            compose(plan)
            write_order(a.out, plan)
            print(f"parts {len(plan['parts'])} nt {plan['shape']['order_nt']}")
        elif a.cmd == "project":
            ms = machines()
            ids = [a.machine] if a.machine else list(ms)
            for mid in ids:
                row = project(a.nt, machine(mid))
                print(f"{row['machine']:10} ceil {row['ceil']:6} parts {row['parts']:7} "
                      f"tiers {row['tiers']} pots {row['pots']:6} order_nt {row['order_nt']}")
        elif a.cmd == "machines":
            for mid, m in machines().items():
                print(f"{mid:10} floor {m['floor']:5} ceil {m['ceil']:6} pool {m['pool']:3} "
                      f"episome_floor {m['episome_floor']:6} enzymes {','.join(e['name'] for e in m['enzymes'])}")
        elif a.cmd == "seed":
            sites = [e["site"] for m in machines().values() for e in m["enzymes"]]
            seq = seeded(a.nt, a.seed, tuple(sorted(set(sites))))
            write_fasta(a.out, seq, f"tess1 sample nt={a.nt} seed={a.seed}")
            print(seq_root(seq), len(seq), f"gc {gc(seq):.4f} run {longest_run(seq)}")
    except Refusal as err:
        print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
