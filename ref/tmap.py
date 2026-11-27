"""`tmap1` tensor maps (wetware-hq/web contract §14) for a tess1 plan: the plan's tree as named tensors.

The plan map is a **view**: it carries roots, spans, the pot tree and the shape, and never a base.
A part's bases travel as a web `sequence` map of that part, by its own sequence root (§14, S4).
Standard library only, like the rest of this repository; the bytes are web's, record for record.
"""

import argparse
import hashlib
import re
import struct
import sys

import tess
from tess import Refusal

MAGIC = b"tmap1"
MAX_BYTES = 1 << 30
MAX_RANK = 8
MAX_TENSORS = 1024
KIND = re.compile(rb"[a-z][a-z0-9-]{0,31}")
NAME = re.compile(rb"[a-z][a-z0-9_]{0,63}")

# TensorFlow DataType (tensorflow/core/framework/types.proto), as web contract §14 lists them.
U8, F32, U32 = 4, 1, 22
NAMES = {1: "float32", 2: "float64", 3: "int32", 4: "uint8", 5: "int16", 6: "int8", 9: "int64", 10: "bool",
         17: "uint16", 19: "float16", 22: "uint32", 23: "uint64"}
FMT = {1: "f", 2: "d", 3: "i", 4: "B", 5: "h", 6: "b", 9: "q", 10: "B", 17: "H", 19: "e", 22: "I", 23: "Q"}
SIZE = {c: struct.calcsize("<" + f) for c, f in FMT.items()}
FLOATS = {1, 2, 19}
SIGNED = {3, 5, 6, 9}


def flat(values, shape):
    """Row-major values of a nested list, checked against `shape`."""
    if not shape:
        return [values]
    if shape[0] == 0 and values == []:
        return []
    if not isinstance(values, (list, tuple)) or len(values) != shape[0]:
        raise Refusal("bad_shape", f"{shape[0]} expected, got {len(values) if isinstance(values, (list, tuple)) else values}")
    out = []
    for v in values:
        out += flat(v, shape[1:])
    return out


def shape_of(values):
    """The shape of a rectangular nested list; a scalar has shape ()."""
    shape = []
    while isinstance(values, (list, tuple)):
        shape.append(len(values))
        values = values[0] if values else None
    return tuple(shape)


def pack(kind, tensors):
    """Serialize {name: (dtype, values[, shape])} under `kind` to canonical tmap1 bytes, names ascending.

    The shape is read from the nested values unless given; give it when a dimension can be 0.
    """
    k = kind.encode("ascii")
    if not KIND.fullmatch(k):
        raise Refusal("bad_kind", kind)
    if not 1 <= len(tensors) <= MAX_TENSORS:
        raise Refusal("bad_count", str(len(tensors)))
    out = [MAGIC, bytes([len(k)]), k, struct.pack("<H", len(tensors))]
    for name in sorted(tensors, key=lambda s: s.encode("ascii")):
        n = name.encode("ascii")
        if not NAME.fullmatch(n):
            raise Refusal("bad_name", name)
        code, values, *given = tensors[name]
        if code not in FMT:
            raise Refusal("bad_dtype", f"{name}: DataType {code}")
        shape = tuple(given[0]) if given else shape_of(values)
        if len(shape) > MAX_RANK or any(d >= 1 << 32 for d in shape):
            raise Refusal("bad_shape", name)
        vs = flat(values, shape)
        check(name, code, vs)
        out += [bytes([len(n)]), n, bytes([code, len(shape)]), struct.pack(f"<{len(shape)}I", *shape)]
        out.append(struct.pack(f"<{len(vs)}{FMT[code]}", *vs) if vs else b"")
    blob = b"".join(out)
    if len(blob) > MAX_BYTES:
        raise Refusal("too_large", f"{len(blob)} bytes")
    unpack(blob)
    return blob


def check(name, code, values):
    """§14: a float is finite and not negative zero; an integer fits its dtype."""
    for v in values:
        if code in FLOATS:
            if v != v or v in (float("inf"), float("-inf")):
                raise Refusal("bad_value", f"{name}: not finite")
            if v == 0.0 and str(v)[0] == "-":
                raise Refusal("bad_value", f"{name}: negative zero")
            f = "<" + FMT[code]
            try:
                fits = struct.unpack(f, struct.pack(f, v))[0] == v
            except (OverflowError, struct.error):
                fits = False
            if not fits:
                raise Refusal("bad_value", f"{name}: {v} is not a {NAMES[code]}")
        else:
            bits = 1 if code == 10 else 8 * SIZE[code]
            lo, hi = (-(1 << (bits - 1)), 1 << (bits - 1)) if code in SIGNED else (0, 1 << bits)
            if isinstance(v, bool) or not isinstance(v, int) or not lo <= v < hi:
                raise Refusal("bad_value", f"{name}: {v}")


def unpack(blob, kind=None):
    """Parse tmap1 bytes into (kind, {name: (dtype, shape, values)}); refuse what would not re-serialize."""
    if len(blob) > MAX_BYTES:
        raise Refusal("too_large", f"{len(blob)} bytes")
    if blob[:5] != MAGIC:
        raise Refusal("bad_magic")
    pos = 5

    def take(n):
        nonlocal pos
        if pos + n > len(blob):
            raise Refusal("truncated")
        pos += n
        return blob[pos - n : pos]

    k = take(take(1)[0])
    if not KIND.fullmatch(k):
        raise Refusal("bad_kind", k.decode("ascii", "replace"))
    (count,) = struct.unpack("<H", take(2))
    if not 1 <= count <= MAX_TENSORS:
        raise Refusal("bad_count", str(count))
    tensors, last = {}, b""
    for _ in range(count):
        n = take(take(1)[0])
        if not NAME.fullmatch(n):
            raise Refusal("bad_name", n.decode("ascii", "replace"))
        if n <= last:
            raise Refusal("bad_order", n.decode("ascii"))
        last = n
        code, rank = take(2)
        if code not in FMT:
            raise Refusal("bad_dtype", f"{n.decode()}: DataType {code}")
        if rank > MAX_RANK:
            raise Refusal("bad_shape", n.decode())
        shape = struct.unpack(f"<{rank}I", take(4 * rank))
        size = 1
        for d in shape:
            size *= d
        values = list(struct.unpack(f"<{size}{FMT[code]}", take(size * SIZE[code]))) if size else []
        check(n.decode(), code, values)
        tensors[n.decode("ascii")] = (code, shape, values)
    if pos != len(blob):
        raise Refusal("trailing_bytes")
    kind_s = k.decode("ascii")
    if kind is not None and kind_s != kind:
        raise Refusal("kind_mismatch", f"{kind_s}, wanted {kind}")
    return kind_s, tensors


def root(blob):
    """The tensor root: sha256 of the map's bytes, cited tmap1:<root>."""
    unpack(blob)
    return hashlib.sha256(blob).hexdigest()


def digest(hexroot):
    """A 32-byte root as the uint8 [32] tensor §14 requires."""
    if not re.fullmatch(r"[0-9a-f]{64}", hexroot or ""):
        raise Refusal("bad_plan", f"not a sha256 digest: {hexroot}")
    return list(bytes.fromhex(hexroot))


def of_plan(plan):
    """A plan as named tensors: its roots, its parts' spans, its pot tree and its shape. No base (S4)."""
    tess.compose(plan)  # a plan is mapped only if it composes to the target it names (§4)
    m, sh = plan["machine"], plan["shape"]
    parts, pools = plan["parts"], plan["pools"]
    index = {p["id"]: i for i, p in enumerate(parts)}
    for i, pot in enumerate(pools):
        index[pot["id"]] = len(parts) + i
    edges = [[len(parts) + i, index[c]] for i, pot in enumerate(pools) for c in pot["children"]]
    return pack("plan", {
        "allow": (U8, [int(plan["allow"]["small_episomes"]), int(plan["allow"]["small_fragments"])]),
        "floor": (U32, plan["floor"]),
        "machine": (U32, [m["floor"], m["ceil"], m["pool"], m["episome_floor"], m["homopolymer_max"]]),
        "overhang": (U8, plan["enzyme"]["overhang"]),
        "part_gc": (F32, [struct.unpack("<f", struct.pack("<f", p["gc"]))[0] for p in parts]),
        "part_span": (U32, [list(p["span"]) for p in parts], (len(parts), 2)),
        "plan_root": (U8, digest(tess.plan_root(plan))),
        "pot_child": (U32, edges, (len(edges), 2)),
        "pot_hamming": (U8, [pot["min_hamming"] or 0 for pot in pools]),
        "pot_span": (U32, [list(pot["span"]) for pot in pools], (len(pools), 2)),
        "pot_tier": (U32, [pot["tier"] for pot in pools]),
        "root_node": (U32, index[plan["root_part"]]),
        "shape": (U32, [sh["parts"], sh["tiers"], sh["pots"], sh["part_nt"][0], sh["part_nt"][1], sh["order_nt"]]),
        "target_nt": (U32, plan["target"]["nt"]),
        "target_root": (U8, digest(plan["target"]["root"])),
        "tesseract": (U8, 1),
    })


def show(blob):
    """kind, root and each tensor's dtype and shape, one line each."""
    kind, tensors = unpack(blob)
    lines = [f"{kind} tmap1:{root(blob)} bytes {len(blob)} tensors {len(tensors)}"]
    for name, (code, shape, _) in tensors.items():
        lines.append(f"  {name:12} {NAMES[code]:8} [{', '.join(str(d) for d in shape)}]")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="tmap1: a tess1 plan as named tensors (web contract §14)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("map", help="plan -> .tmap")
    m.add_argument("plan")
    m.add_argument("out")
    m.add_argument("--root", default=None, help="expected tensor root")
    s = sub.add_parser("show", help="a .tmap's kind, root and tensors")
    s.add_argument("tmap")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "map":
            blob = of_plan(tess.read_plan(a.plan))
            if a.root and root(blob) != a.root:
                raise Refusal("root_mismatch", root(blob))
            tess.write(a.out, blob)
            print(root(blob), len(blob))
        else:
            with open(a.tmap, "rb") as fh:
                print(show(fh.read()))
    except Refusal as err:
        print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
