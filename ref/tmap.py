"""`tmap1` tensor maps (wetware-hq/web contract §14) of this repository's two objects.

A `plan` map is a tess1 plan's tree as named tensors; a `doll` map is a doll1 derivation's trace as
named tensors (§11). Both are **views**: roots, spans, the tree, the trace and the shape, never a
base (§10, web S4).
Standard library only; it writes web's bytes record for record, using three TensorFlow DataTypes.
Any other map, or any other dtype, is read with web's `ref/tensor.py`.
"""

import argparse
import hashlib
import math
import struct
import sys

import doll
import tess
from tess import Refusal

F32, U8, U32 = 1, 4, 22  # TensorFlow DataType (tensorflow/core/framework/types.proto)
FMT = {F32: "f", U8: "B", U32: "I"}


def pack(kind, tensors):
    """{name: (dtype, flat values, shape)} -> canonical tmap1 bytes, names ascending."""
    out = [b"tmap1", bytes([len(kind)]), kind.encode("ascii"), struct.pack("<H", len(tensors))]
    for name in sorted(tensors):
        code, values, shape = tensors[name]
        if code == F32:
            if not all(math.isfinite(v) for v in values):
                raise Refusal("bad_plan", f"{name}: not a finite float")
            try:  # round to float32 first, so a value that underflows to -0.0 is written +0.0 (§14)
                values = [struct.unpack("<f", struct.pack("<f", v))[0] + 0.0 for v in values]
            except (struct.error, OverflowError) as err:
                raise Refusal("bad_plan", f"{name}: {err}") from None
        out += [bytes([len(name)]), name.encode("ascii"), bytes([code, len(shape)]), struct.pack(f"<{len(shape)}I", *shape)]
        try:
            out.append(struct.pack(f"<{len(values)}{FMT[code]}", *values))
        except (struct.error, OverflowError) as err:
            raise Refusal("bad_plan", f"{name}: {err}") from None
    return b"".join(out)


def unpack(blob, kind=None):
    """tmap1 bytes in the three dtypes this repository writes -> (kind, {name: (dtype, shape, values)})."""
    try:
        n = blob[5]
        k = blob[6 : 6 + n].decode("ascii")
        (count,) = struct.unpack_from("<H", blob, 6 + n)
        pos, tensors = 8 + n, {}
        for _ in range(count):
            name = blob[pos + 1 : pos + 1 + blob[pos]].decode("ascii")
            pos += 1 + blob[pos]
            code, rank = blob[pos], blob[pos + 1]
            shape = struct.unpack_from(f"<{rank}I", blob, pos + 2)
            pos += 2 + 4 * rank
            size = 1
            for d in shape:
                size *= d
            tensors[name] = (code, shape, list(struct.unpack_from(f"<{size}{FMT[code]}", blob, pos)))
            pos += size * struct.calcsize(FMT[code])
    except (IndexError, KeyError, UnicodeDecodeError, struct.error) as err:
        raise Refusal("bad_map", f"not a plan-dtype tmap1 map: {err}") from None
    try:
        canonical = pack(k, {t: (c, v, s) for t, (c, s, v) in tensors.items()}) == blob
    except Refusal:
        canonical = False
    if blob[:5] != b"tmap1" or pos != len(blob) or list(tensors) != sorted(tensors) or not canonical:
        raise Refusal("bad_map", "not one canonical tmap1 map")
    if kind is not None and k != kind:
        raise Refusal("kind_mismatch", f"{k}, wanted {kind}")
    return k, tensors


def root(blob):
    """The tensor root: sha256 of the map's bytes, cited tmap1:<root>."""
    return hashlib.sha256(blob).hexdigest()


def digest(hexroot):
    try:
        b = bytes.fromhex(hexroot)
    except (TypeError, ValueError):
        b = b""
    if len(b) != 32:
        raise Refusal("bad_plan", f"not a sha256 digest: {hexroot}")
    return (U8, list(b), (32,))


def of_plan(plan):
    """A plan as named tensors: its roots, its parts' spans, its pot tree and its shape. No base (S4)."""
    try:
        return plan_map(plan)
    except (KeyError, IndexError, TypeError, ValueError) as err:
        raise Refusal("bad_plan", f"{type(err).__name__}: {err}") from None


def plan_map(plan):
    target = tess.compose(plan)  # a plan is mapped only if it composes to the target it names (§4)
    m, sh, parts, pools = plan["machine"], plan["shape"], plan["parts"], plan["pools"]
    for x in parts + pools:
        span = x["span"]
        if not (isinstance(span, list) and len(span) == 2 and all(type(v) is int for v in span)):
            raise Refusal("bad_plan", f"{x['id']} span {span} is not [start, end]")
    spans = {p["id"]: tuple(p["span"]) for p in parts}
    for p in parts:  # compose checks the bases, not the coordinates the map exports
        if target[slice(*spans[p["id"]])] != p["seq"]:
            raise Refusal("bad_plan", f"{p['id']} span {list(p['span'])} is not its bases in the target")
    for pot in pools:
        spans[pot["id"]] = tuple(pot["span"])
        if spans[pot["id"]] != (spans[pot["children"][0]][0], spans[pot["children"][-1]][1]):
            raise Refusal("bad_plan", f"{pot['id']} span {list(pot['span'])} is not its children's")
    if spans[plan["root_part"]] != (0, len(target)):
        raise Refusal("bad_plan", f"{plan['root_part']} does not span the target")
    node = {x["id"]: i for i, x in enumerate(parts + pools)}
    edges = [[node[pot["id"]], node[c]] for pot in pools for c in pot["children"]]

    def vec(code, values):
        return (code, list(values), (len(values),))

    def mat(rows):
        return (U32, [v for r in rows for v in r], (len(rows), 2))

    return pack("plan", {
        "allow": vec(U8, [int(plan["allow"]["small_episomes"]), int(plan["allow"]["small_fragments"])]),
        "floor": (U32, [plan["floor"]], ()),
        "machine": vec(U32, [m["floor"], m["ceil"], m["pool"], m["episome_floor"], m["homopolymer_max"]]),
        "overhang": (U8, [plan["enzyme"]["overhang"]], ()),
        "part_gc": vec(F32, [p["gc"] for p in parts]),
        "part_span": mat([p["span"] for p in parts]),
        "plan_root": digest(tess.plan_root(plan)),
        "pot_child": mat(edges),
        "pot_hamming": vec(U8, [pot["min_hamming"] or 0 for pot in pools]),
        "pot_span": mat([pot["span"] for pot in pools]),
        "pot_tier": vec(U32, [pot["tier"] for pot in pools]),
        "root_node": (U32, [node[plan["root_part"]]], ()),
        "shape": vec(U32, [sh["parts"], sh["tiers"], sh["pots"], sh["part_nt"][0], sh["part_nt"][1], sh["order_nt"]]),
        "target_nt": (U32, [plan["target"]["nt"]], ()),
        "target_root": digest(plan["target"]["root"]),
        "tesseract": (U8, [1], ()),
    })


def of_doll(der):
    """A derivation as named tensors: its roots, its trace, its gates and what it spent. No base, no plan.

    The map is a view of the trace (§11): the ops, the information each act cost, the gate each
    nesting of the shells returned, and the three roots a reader needs to find the goal, the plan
    and the derivation itself. The candidates, the machine ids and the refusal codes are strings,
    and §14 has no string dtype; a reader that needs them reads the `.doll` file.
    """
    try:
        return doll_map(der)
    except (KeyError, IndexError, TypeError, ValueError) as err:
        raise Refusal("bad_doll", f"{type(err).__name__}: {err}") from None


def doll_map(der):
    doll.verify(der)  # a derivation is mapped only if its chain, gates and costs replay (§11)
    goal, shells, frames, spent = der["goal"], der["shells"], der["frames"], der["spent"]
    shape = der["result"]["shape"]
    gates = [f["trail"][-1]["gate_ppm"] / doll.PPM for f in frames if f["op"] == "nest"]

    def vec(code, values):
        return (code, list(values), (len(values),))

    return pack("doll", {
        "alpha_ppm": vec(U32, [s["alpha_ppm"] for s in shells]),
        "budget": vec(U32, [goal["budget"]["acts"], goal["budget"]["mbits"]]),
        "depth": (U8, [goal["depth"]], ()),
        "doll": (U8, [1], ()),
        "doll_root": digest(doll.doll_root(der)),
        "frame_mbits": vec(U32, [f.get("mbits", 0) for f in frames]),
        "frame_op": vec(U8, [doll.OPS.index(f["op"]) for f in frames]),
        "gate": vec(F32, gates),
        "goal_root": digest(doll.goal_root(goal)),
        "head": digest(der["head"]),
        "plan_root": digest(der["result"]["plan_root"]),
        "shape": vec(U32, [shape["parts"], shape["tiers"], shape["pots"], shape["part_nt"][0], shape["part_nt"][1], shape["order_nt"]]),
        "shell_root": (U8, [b for s in shells for b in bytes.fromhex(s["root"])], (len(shells), 32)),
        "spent": vec(U32, [spent["acts"], spent["backtracks"], spent["mbits"], spent["pots"], spent["predicts"]]),
        "target_nt": (U32, [goal["target"]["nt"]], ()),
        "target_root": digest(goal["target"]["root"]),
        "theta": (F32, [goal["theta_ppm"] / doll.PPM], ()),
        "verdict": (U8, [0], ()),  # 0 is "unverified", the only verdict a derivation may carry (§11)
    })


def main(argv=None):
    ap = argparse.ArgumentParser(description="tmap1: a tess1 plan or a doll1 derivation as named tensors (web §14)")
    ap.add_argument("cmd", choices=["map"])
    ap.add_argument("plan", help="a .tess plan or a .doll derivation")
    ap.add_argument("out")
    ap.add_argument("--root", default=None, help="expected tensor root")
    a = ap.parse_args(argv)
    try:
        if str(a.plan).endswith(".doll"):
            blob = of_doll(doll.read_doll(a.plan))
        elif str(a.plan).endswith(".tess"):
            blob = of_plan(tess.read_plan(a.plan))
        else:
            raise Refusal("kind_mismatch", "a map is written for a .tess plan or a .doll derivation")
        if a.root and root(blob) != a.root:
            raise Refusal("root_mismatch", root(blob))
        tess.write(a.out, blob)
        print(root(blob), len(blob))
    except Refusal as err:
        print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
