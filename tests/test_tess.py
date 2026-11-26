"""`tess1` is exact: every plan composes back to its target, byte for byte, or it is not a plan."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ref"))

import tess  # noqa: E402

EPI = ROOT / "samples" / "epi-12k.fa"
SITE = ROOT / "samples" / "site-2k.fa"
EPI_ROOT = "560ca3068f3491d4b7686c337a68a32b67f6a5383cba0db18e6a49db31c62608"
SITE_ROOT = "1e5bf84b1a3ed793553c8e6e195375ec7ba9088a7e59e2dd008e9347ff28f925"


def plans():
    return sorted((ROOT / "samples").glob("*.tess"))


class Samples(unittest.TestCase):
    def test_sample_targets_are_pinned(self):
        self.assertEqual(tess.seq_root(tess.read_fasta(EPI)), EPI_ROOT)
        self.assertEqual(tess.seq_root(tess.read_fasta(SITE)), SITE_ROOT)

    def test_seed_is_deterministic(self):
        sites = tuple(sorted({e["site"] for m in tess.machines().values() for e in m["enzymes"]}))
        self.assertEqual(tess.seeded(12000, 0, sites), tess.read_fasta(EPI))

    def test_every_sample_plan_composes_to_its_target(self):
        targets = {tess.seq_root(tess.read_fasta(p)): tess.read_fasta(p) for p in (EPI, SITE)}
        for path in plans():
            with self.subTest(plan=path.name):
                plan = tess.read_plan(path)
                self.assertEqual(tess.compose(plan), targets[plan["target"]["root"]])

    def test_sample_plans_are_canonical_on_disk(self):
        for path in plans():
            with self.subTest(plan=path.name):
                self.assertEqual(path.read_bytes(), tess.canonical(tess.read_plan(path)))

    def test_sample_plans_are_what_the_compiler_writes(self):
        for path in plans():
            with self.subTest(plan=path.name):
                plan = tess.read_plan(path)
                target = tess.read_fasta(EPI if plan["target"]["root"] == EPI_ROOT else SITE)
                again = tess.compile_plan(target, tess.machine(plan["machine"]["id"]))
                self.assertEqual(tess.plan_root(again), tess.plan_root(plan))


class Exactness(unittest.TestCase):
    def test_compile_compose_round_trip(self):
        for mid in ("m1-column", "m2-tdt", "m3-bet"):
            seq = tess.seeded(3000, 3, ("GGTCTC", "CGTCTC", "GCTCTTC"))
            with self.subTest(machine=mid):
                plan = tess.compile_plan(seq, tess.machine(mid))
                self.assertEqual(tess.compose(plan), seq)
                self.assertEqual(plan["target"]["root"], tess.seq_root(seq))

    def test_parts_overlap_by_exactly_one_overhang(self):
        plan = tess.read_plan(ROOT / "samples" / "epi-12k.m0-chip.tess")
        k = plan["enzyme"]["overhang"]
        for left, right in zip(plan["parts"], plan["parts"][1:]):
            self.assertEqual(left["seq"][-k:], right["seq"][:k])

    def test_a_changed_base_is_caught(self):
        plan = tess.read_plan(ROOT / "samples" / "epi-12k.m2-tdt.tess")
        part = plan["parts"][2]
        part["seq"] = part["seq"][:50] + ("A" if part["seq"][50] != "A" else "C") + part["seq"][51:]
        with self.assertRaises(tess.Refusal) as caught:
            tess.compose(plan)
        self.assertEqual(caught.exception.code, "target_mismatch")

    def test_a_dropped_part_is_caught(self):
        plan = tess.read_plan(ROOT / "samples" / "epi-12k.m2-tdt.tess")
        plan["pools"][-1]["children"] = plan["pools"][-1]["children"][:-1]
        with self.assertRaises(tess.Refusal):
            tess.compose(plan)

    def test_plan_root_is_the_canonical_bytes(self):
        import hashlib
        for path in plans():
            plan = tess.read_plan(path)
            self.assertEqual(tess.plan_root(plan), hashlib.sha256(tess.canonical(plan)).hexdigest())


class Junctions(unittest.TestCase):
    def test_orthogonal_set_is_pinned(self):
        self.assertEqual(len(tess.orthogonal_set(4)), 22)
        self.assertEqual(tess.orthogonal_set(3), ["AAC", "ACA", "AGG", "CAA", "CTC", "GGA"])
        self.assertEqual(tess.orthogonal_set(4)[:3], ["AAAC", "AACA", "AAGG"])

    def test_set_members_are_pairwise_orthogonal(self):
        for k in (3, 4):
            members = tess.orthogonal_set(k)
            for i, a in enumerate(members):
                for b in members[i + 1:]:
                    self.assertTrue(tess.orthogonal(a, b), (a, b))

    def test_no_pot_reuses_an_overhang(self):
        for path in plans():
            for pool in tess.read_plan(path)["pools"]:
                hs = pool["junctions"]
                with self.subTest(plan=path.name, pool=pool["id"]):
                    self.assertEqual(len(set(hs)), len(hs))
                    if len(hs) > 1:
                        self.assertGreaterEqual(pool["min_hamming"], 2)

    def test_palindromes_and_homopolymers_are_not_junctions(self):
        self.assertFalse(tess.junction_ok("GGCC"))
        self.assertFalse(tess.junction_ok("AAAA"))
        self.assertTrue(tess.junction_ok("AAAC"))


class Machines(unittest.TestCase):
    def test_machines_are_described(self):
        for mid, m in tess.machines().items():
            with self.subTest(machine=mid):
                tess.check_machine(m)
                self.assertLess(m["floor"], m["ceil"])
                self.assertLessEqual(m["pool"] + 1, len(tess.orthogonal_set(m["enzymes"][0]["overhang"])))

    def test_project_agrees_with_compile(self):
        seq = tess.read_fasta(EPI)
        for mid in tess.machines():
            with self.subTest(machine=mid):
                plan = tess.compile_plan(seq, tess.machine(mid))
                row = tess.project(len(seq), tess.machine(mid))
                self.assertEqual(row["parts"], plan["shape"]["parts"])
                self.assertEqual(row["tiers"], plan["shape"]["tiers"])
                self.assertEqual(row["pots"], plan["shape"]["pots"])

    def test_a_longer_runlength_never_costs_more_tiers(self):
        rows = [tess.project(316617, tess.machine(mid)) for mid in tess.machines()]
        rows.sort(key=lambda r: r["ceil"])
        self.assertEqual([r["tiers"] for r in rows], sorted((r["tiers"] for r in rows), reverse=True))
        self.assertEqual(rows[-1]["tiers"], 1)

    def test_enzyme_avoids_sites_in_the_target(self):
        plan = tess.read_plan(ROOT / "samples" / "site-2k.m1-column.tess")
        self.assertEqual(plan["enzyme"]["name"], "BsmBI")
        seq = tess.read_fasta(SITE)
        site = plan["enzyme"]["site"]
        self.assertNotIn(site, seq)
        self.assertNotIn(tess.revcomp(site), seq)


class Refusals(unittest.TestCase):
    def refusal(self, code, fn, *args, **kw):
        with self.assertRaises(tess.Refusal) as caught:
            fn(*args, **kw)
        self.assertEqual(caught.exception.code, code)

    def test_sequence_must_be_acgt(self):
        self.refusal("bad_base", tess.check_sequence, "ACGTN")
        self.refusal("bad_length", tess.check_sequence, "")

    def test_floor_must_sit_under_the_ceiling(self):
        seq = tess.seeded(3000, 1, ("GGTCTC",))
        self.refusal("bad_floor", tess.compile_plan, seq, tess.machine("m1-column"), 400)

    def test_target_shorter_than_the_floor_is_refused(self):
        seq = tess.seeded(600, 2, ("GGTCTC",))
        self.refusal("below_floor", tess.compile_plan, seq, tess.machine("m3-bet"))
        plan = tess.compile_plan(seq, tess.machine("m3-bet"), small_fragments=True)
        self.assertEqual(tess.compose(plan), seq)

    def test_a_target_full_of_sites_is_refused(self):
        m = tess.machine("m1-column")
        seq = tess.seeded(3000, 4) + "".join(e["site"] for e in m["enzymes"])
        self.refusal("forbidden_site", tess.compile_plan, seq, m)

    def test_small_episomes_need_the_flag(self):
        m = dict(tess.machine("m1-column"), episome_floor=12000)
        seq = tess.read_fasta(EPI)
        self.refusal("small_episome", tess.compile_plan, seq, m)
        plan = tess.compile_plan(seq, m, small_episomes=True)
        self.assertEqual(tess.compose(plan), seq)

    def test_machines_must_be_described(self):
        self.refusal("bad_machine", tess.check_machine, {"id": "x"})
        self.refusal("bad_machine", tess.machine, "no-such-machine")

    def test_a_plan_without_a_target_is_refused(self):
        plan = json.loads(tess.canonical(tess.read_plan(plans()[0])).decode())
        del plan["target"]
        self.refusal("bad_plan", tess.compose, plan)


class Pins(unittest.TestCase):
    def test_tesseract_json_pins_every_sample(self):
        pins = json.loads((ROOT / "tesseract.json").read_text())
        by_path = {row["path"]: row for row in pins["plans"]}
        for path in plans():
            row = by_path[f"samples/{path.name}"]
            plan = tess.read_plan(path)
            with self.subTest(plan=path.name):
                self.assertEqual(row["root"], tess.plan_root(plan))
                self.assertEqual(row["bytes"], len(path.read_bytes()))
                self.assertEqual(row["machine"], plan["machine"]["id"])
                self.assertEqual(row["shape"], plan["shape"])
        for row in pins["targets"]:
            seq = tess.read_fasta(ROOT / row["path"])
            with self.subTest(target=row["name"]):
                self.assertEqual(row["root"], tess.seq_root(seq))
                self.assertEqual(row["nt"], len(seq))

    def test_machines_in_plans_match_the_pins(self):
        pinned = {m["id"]: m for m in json.loads((ROOT / "tesseract.json").read_text())["machines"]}
        for path in plans():
            plan = tess.read_plan(path)
            self.assertEqual(plan["machine"], pinned[plan["machine"]["id"]])

    def test_objectgraph_checksum(self):
        import hashlib
        import re
        text = (ROOT / "ooc" / "tesseract.og").read_text()
        body = "\n".join(l for l in text.splitlines() if not l.startswith("checksum:")) + "\n"
        self.assertIn(f"checksum: sha256:{hashlib.sha256(body.encode()).hexdigest()}", text)
        for plan in (tess.read_plan(p) for p in plans()):
            if plan["shape"]["parts"] > 1:
                self.assertIn(tess.plan_root(plan), text)


if __name__ == "__main__":
    unittest.main()
