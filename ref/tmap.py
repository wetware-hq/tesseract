"""`tmap1` tensor map (wetware-hq/web contract §14) of a tess1 plan: the plan's tree as named tensors.

The plan map is a **view**: roots, spans, the pot tree and the shape, never a base (§10, web S4).
Standard library only; it writes web's bytes record for record, using three TensorFlow DataTypes.
Any other map, or any other dtype, is read with web's `ref/tensor.py`.
"""

import argparse
import hashlib
import math
import struct
import sys

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
            values = [v + 0.0 for v in values]  # -0.0 is written +0.0 (§14), so unpack refuses it as non-canonical
        out += [bytes([len(name)]), name.encode("ascii"), bytes([code, len(shape)]), struct.pack(f"<{len(shape)}I", *shape)]
        try:
            out.append(struct.pack(f"<{len(values)}{FMT[code]}", *values))
        except (struct.error, OverflowError) as err:
            raise Refusal("bad_plan", f"{name}: {err}") from None
    return b"".join(out)


def unpack(blob, kind=None):
    """tmap1 bytes in the three plan dtypes -> (kind, {name: (dtype, shape, flat values)})."""
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
    if blob[:5] != b"tmap1" or pos != len(blob) or list(tensors) != sorted(tensors) or pack(k, {t: (c, v, s) for t, (c, s, v) in tensors.items()}) != blob:
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


def main(argv=None):
    ap = argparse.ArgumentParser(description="tmap1: a tess1 plan as named tensors (web contract §14)")
    ap.add_argument("cmd", choices=["map"])
    ap.add_argument("plan")
    ap.add_argument("out")
    ap.add_argument("--root", default=None, help="expected tensor root")
    a = ap.parse_args(argv)
    try:
        blob = of_plan(tess.read_plan(a.plan))
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
