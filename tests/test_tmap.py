"""A plan's tensor map (web contract §14) is one byte form, pinned, and holds no base."""

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ref"))

import tess  # noqa: E402
import tmap  # noqa: E402

PINS = json.loads((ROOT / "tesseract.json").read_text())["tensors"]


def mapped(path):
    return tmap.of_plan(tess.read_plan(ROOT / path))


def nest(values, shape):
    return [list(values[i : i + shape[1]]) for i in range(0, len(values), shape[1])]


def repack(blob):
    kind, t = tmap.unpack(blob)
    return tmap.pack(kind, {n: (c, v, s) for n, (c, s, v) in t.items()})


class Samples(unittest.TestCase):
    def test_every_sample_plan_map_is_pinned(self):  # T11
        self.assertEqual(sorted(m["plan"] for m in PINS["maps"]), sorted(f"samples/{p.name}" for p in (ROOT / "samples").glob("*.tess")))
        for m in PINS["maps"]:
            with self.subTest(plan=m["plan"]):
                blob = mapped(m["plan"])
                self.assertEqual(tmap.root(blob), m["root"])
                self.assertEqual(len(blob), m["bytes"])
                self.assertEqual(repack(blob), blob)

    def test_map_names_the_plan_and_its_target(self):
        for m in PINS["maps"]:
            plan = tess.read_plan(ROOT / m["plan"])
            kind, t = tmap.unpack(mapped(m["plan"]), "plan")
            self.assertEqual(bytes(t["plan_root"][2]).hex(), tess.plan_root(plan))
            self.assertEqual(bytes(t["target_root"][2]).hex(), plan["target"]["root"])
            self.assertEqual(t["target_nt"][2], [plan["target"]["nt"]])
            self.assertEqual(t["shape"][1], (6,))
            spans = nest(t["part_span"][2], t["part_span"][1])
            self.assertEqual(spans, [p["span"] for p in plan["parts"]])
            self.assertEqual(t["pot_child"][1][0], sum(len(p["children"]) for p in plan["pools"]))

    def test_spans_rebuild_the_parts_from_the_target(self):  # T10: the map cuts, the target supplies bases
        targets = {tess.seq_root(tess.read_fasta(p)): tess.read_fasta(p) for p in (ROOT / "samples").glob("*.fa")}
        for m in PINS["maps"]:
            plan = tess.read_plan(ROOT / m["plan"])
            t = tmap.unpack(mapped(m["plan"]))[1]
            seq = targets[bytes(t["target_root"][2]).hex()]
            spans = nest(t["part_span"][2], t["part_span"][1])
            self.assertEqual([seq[a:b] for a, b in spans], [p["seq"] for p in plan["parts"]])

    def test_no_base_in_a_plan_map(self):  # web S4, §14 T6
        for m in PINS["maps"]:
            blob = mapped(m["plan"])
            for part in tess.read_plan(ROOT / m["plan"])["parts"]:
                self.assertNotIn(part["seq"][:16].encode("ascii"), blob)
            codes = {c for c, _, _ in tmap.unpack(blob)[1].values()}
            self.assertLessEqual(codes, {tmap.U8, tmap.U32, tmap.F32})


class Format(unittest.TestCase):
    def setUp(self):
        self.blob = tmap.pack("probe", {"b": (tmap.U32, [1, 2, 3, 4], (2, 2)), "a": (tmap.F32, [1.5], ()), "c": (tmap.U8, [], (0, 2))})

    def refused(self, blob, code, kind=None):
        with self.assertRaises(tess.Refusal) as ctx:
            tmap.unpack(blob, kind)
        self.assertEqual(ctx.exception.code, code)

    def test_canonical_bytes(self):
        self.assertEqual(self.blob[:13], b"tmap1\x05probe\x03\x00")
        self.assertEqual(self.blob[13:21], b"\x01a\x01\x00" + struct.pack("<f", 1.5))
        self.assertEqual(repack(self.blob), self.blob)

    def test_refusals(self):
        self.refused(self.blob, "kind_mismatch", "plan")
        for bad in (b"tmap2" + self.blob[5:], self.blob[:-1], self.blob + b"\0",
                    self.blob.replace(b"\x01a", b"\x01d", 1), self.blob[:15] + b"\x07" + self.blob[16:]):
            self.refused(bad, "bad_map")
        with self.assertRaises(tess.Refusal) as ctx:
            tmap.pack("probe", {"x": (tmap.U8, [256], ())})
        self.assertEqual(ctx.exception.code, "bad_plan")

    def test_a_plan_that_does_not_compose_is_not_mapped(self):
        plan = tess.read_plan(ROOT / PINS["maps"][0]["plan"])
        plan["target"]["root"] = "0" * 64
        with self.assertRaises(tess.Refusal) as ctx:
            tmap.of_plan(plan)
        self.assertEqual(ctx.exception.code, "target_mismatch")

    def test_stale_coordinates_are_not_mapped(self):
        for path, edit in (("parts", lambda p: p.__setitem__("span", [p["span"][0] + 1, p["span"][1] + 1])),
                           ("pools", lambda p: p.__setitem__("span", [0, p["span"][1] - 1]))):
            plan = tess.read_plan(ROOT / PINS["maps"][0]["plan"])
            edit(plan[path][0])
            tess.compose(plan)  # still composes: compose reads bases, not spans
            with self.assertRaises(tess.Refusal) as ctx:
                tmap.of_plan(plan)
            self.assertEqual(ctx.exception.code, "bad_plan")

    def test_missing_metadata_is_bad_plan(self):
        for drop in (lambda p: p["parts"][0].pop("gc"), lambda p: p.pop("floor"), lambda p: p["enzyme"].pop("overhang")):
            plan = tess.read_plan(ROOT / PINS["maps"][0]["plan"])
            drop(plan)
            with self.assertRaises(tess.Refusal) as ctx:
                tmap.of_plan(plan)
            self.assertEqual(ctx.exception.code, "bad_plan")


if __name__ == "__main__":
    unittest.main()
