"""A doll1 derivation (contract §11): canonical bytes, a chain that replays, a cost that sums, no verdict."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ref"))

import doll  # noqa: E402
import tess  # noqa: E402
import tmap  # noqa: E402

PINS = json.loads((ROOT / "tesseract.json").read_text())
TARGET = tess.read_fasta(ROOT / "samples/epi-12k.fa")


def goal(**over):
    base = {"target_nt": len(TARGET), "target_root": tess.seq_root(TARGET), "machines": ["m0-chip", "m1-column"],
            "objective": "fewest_tiers", "floors": (None,), "depth": 2, "seed": 3}
    return doll.goal_of(**(base | over))


def refused(code):
    def check(test, call):
        with test.assertRaises(tess.Refusal) as ctx:
            call()
        test.assertEqual(ctx.exception.code, code)
    return check


class Samples(unittest.TestCase):
    def test_every_sample_derivation_is_pinned(self):  # T12, T13, T14
        self.assertEqual(sorted(d["path"] for d in PINS["dolls"]),
                         sorted(f"samples/{p.name}" for p in (ROOT / "samples").glob("*.doll")))
        for pin in PINS["dolls"]:
            with self.subTest(doll=pin["path"]):
                der = doll.read_doll(ROOT / pin["path"])
                self.assertEqual(doll.doll_root(der), pin["root"])
                self.assertEqual(der["head"], pin["head"])
                self.assertEqual(len(doll.doll_bytes(der)), pin["bytes"])
                self.assertEqual(der["spent"], pin["spent"])
                self.assertEqual(der["result"]["halt"], pin["result"]["halt"])
                self.assertEqual(der["result"]["plan_root"], pin["result"]["plan_root"])
                self.assertEqual(der["verdict"], "unverified")

    def test_every_act_replays_against_the_target(self):  # T15
        for pin in PINS["dolls"]:
            der = doll.read_doll(ROOT / pin["path"])
            out = doll.verify(der, TARGET)
            self.assertEqual(out["replayed"], pin["spent"]["acts"])
            self.assertEqual(out["plan_root"], pin["result"]["plan_root"])

    def test_the_emitted_plan_composes_to_the_target(self):  # T15, T16, contract §4
        for pin in PINS["dolls"]:
            der = doll.read_doll(ROOT / pin["path"])
            acts = [f for f in der["frames"] if f["op"] == "act" and f["outcome"] == "plan"]
            key = doll.OBJECTIVES[der["goal"]["objective"]]
            self.assertEqual(der["result"]["plan_root"], min(acts, key=lambda f: key(f["shape"]))["plan_root"])
            row = tess.machine(der["result"]["machine"])
            plan = tess.compile_plan(TARGET, row, der["result"]["floor"])
            self.assertEqual(tess.plan_root(plan), der["result"]["plan_root"])
            self.assertEqual(tess.compose(plan), TARGET)

    def test_a_derivation_holds_no_base(self):  # T20, web S4
        for pin in PINS["dolls"]:
            blob = (ROOT / pin["path"]).read_bytes()
            for start in range(0, len(TARGET) - 24, 997):
                self.assertNotIn(TARGET[start:start + 24].encode("ascii"), blob)
            self.assertNotIn(b'"seq"', blob)

    def test_a_refusal_is_recorded_as_an_outcome(self):  # §5, D2
        der = doll.read_doll(ROOT / "samples/epi-12k.doll")
        codes = {f["code"] for f in der["frames"] if f["op"] == "backtrack"}
        self.assertEqual(codes, {"no_junction"})
        self.assertTrue(any(f["outcome"] == "refused:no_junction" for f in der["frames"] if f["op"] == "act"))

    def test_the_benchmark_envelope(self):  # §12
        der = doll.read_doll(ROOT / "samples/epi-12k.doll")
        sub = doll.submission(der, "demo", "none")
        self.assertEqual(sub["generated_code"], f"tess1:{der['result']['plan_root']}")
        self.assertEqual(sub["generation_config"]["verdict"], "unverified")
        self.assertEqual(sub["generation_config"]["doll_root"], doll.doll_root(der))
        self.assertEqual(sub["model"], "tesseract-doll1/d3/none")
        self.assertNotIn("accuracy", json.dumps(sub))  # a grade never comes from inside a derivation


class Search(unittest.TestCase):
    def test_the_same_goal_and_seed_give_the_same_derivation(self):  # T14
        g = goal()
        first, second = doll.reason(TARGET, g), doll.reason(TARGET, g)
        self.assertEqual(doll.doll_root(first), doll.doll_root(second))
        self.assertNotEqual(doll.doll_root(first), doll.doll_root(doll.reason(TARGET, goal(seed=4))))

    def test_the_shells_are_the_shells_their_roots_name(self):  # T19
        der = doll.reason(TARGET, goal())
        self.assertEqual([s["root"] for s in der["shells"]],
                         [doll.shell_root(doll.fresh_shell(3, k)) for k in range(2)])
        self.assertEqual(len(doll.shell_bytes(doll.fresh_shell(0, 0))), 2 * 4547)

    def test_the_state_moves_through_every_shell(self):  # T19, D5
        der = doll.reason(TARGET, goal(depth=4))
        for frame in (f for f in der["frames"] if f["op"] == "nest"):
            self.assertEqual(len(frame["trail"]), 4)
            self.assertEqual(len({tuple(step["s_ppm"]) for step in frame["trail"]}), 4)

    def test_cost_is_the_sum_over_the_frames(self):  # T18, D4
        der = doll.reason(TARGET, goal())
        self.assertEqual(der["spent"]["mbits"], sum(f.get("mbits", 0) for f in der["frames"]))
        self.assertGreater(der["spent"]["mbits"], 0)
        self.assertEqual(der["spent"]["acts"], sum(1 for f in der["frames"] if f["op"] == "act"))

    def test_a_prediction_precedes_every_act(self):  # D3
        der = doll.reason(TARGET, goal())
        ops = [f["op"] for f in der["frames"]]
        self.assertTrue(all(ops[i - 1] == "predict" for i, op in enumerate(ops) if op == "act"))
        self.assertTrue(any("surprise_ppm" in f for f in der["frames"] if f["op"] == "act"))

    def test_the_gate_halts_the_search_early(self):  # D6
        der = doll.reason(TARGET, goal(machines=["m0-chip", "m1-column", "m2-tdt", "m3-bet"], theta_ppm=-doll.PPM))
        self.assertEqual(der["result"]["halt"], "gate")
        self.assertEqual(der["spent"]["acts"], 1)

    def test_the_budget_halts_a_search_that_found_nothing(self):
        refused("budget_exhausted")(self, lambda: doll.reason(TARGET, goal(machines=["m1-column"], floors=(250, 260), acts=1)))

    def test_a_space_in_which_nothing_composes(self):
        refused("unsat_search")(self, lambda: doll.reason(TARGET, goal(machines=["m1-column"], floors=(250, 260))))

    def test_one_candidate_is_a_reflex(self):  # D4: a free derivation is `compile`
        refused("unaccounted_cost")(self, lambda: doll.reason(TARGET, goal(machines=["m1-column"], floors=(None,))))

    def test_a_machines_own_floor_is_not_a_second_candidate(self):
        g = goal(machines=["m0-chip", "m1-column"], floors=(None, 150, 250))
        self.assertEqual(doll.candidates(g), [{"machine": "m0-chip", "floor": None},
                                              {"machine": "m0-chip", "floor": 150},
                                              {"machine": "m1-column", "floor": None},
                                              {"machine": "m1-column", "floor": 250}])  # 150 is m1-column's own floor

    def test_a_tie_keeps_the_plan_the_search_found_first(self):  # §11, replay agrees with reason
        der = doll.read_doll(ROOT / "samples/epi-12k.doll")
        key = doll.OBJECTIVES[der["goal"]["objective"]]
        acts = [f for f in der["frames"] if f["op"] == "act" and f["outcome"] == "plan"]
        tied = [f for f in acts if key(f["shape"]) == (1, 1, 12036)]
        self.assertEqual(len(tied), 2)
        self.assertGreater(tied[1]["plan_root"], tied[0]["plan_root"])
        best = min(acts, key=lambda f: key(f["shape"]))
        self.assertEqual(doll.verify(der)["plan_root"], best["plan_root"])

    def test_a_goal_whose_target_is_another_sequence(self):
        refused("goal_mutated")(self, lambda: doll.reason(TARGET[:-1], goal()))

    def test_bad_goals(self):
        for over, code in ((dict(objective="cheapest"), "bad_goal"), (dict(machines=[]), "bad_goal"),
                           (dict(depth=0), "depth_overflow"), (dict(depth=9), "depth_overflow"),
                           (dict(acts=0), "bad_goal"), (dict(target_root="z" * 64), "bad_goal"),
                           (dict(brief="x" * 201), "bad_goal"), (dict(floors=(10_000,)), "bad_goal")):
            with self.subTest(goal=over):
                refused(code)(self, lambda over=over: doll.reason(TARGET, goal(**over)))


class Replay(unittest.TestCase):
    def setUp(self):
        self.der = doll.read_doll(ROOT / "samples/epi-12k.halt.doll")

    def tampered(self, edit):
        der = copy.deepcopy(self.der)
        edit(der)
        return der

    def test_bytes_must_be_canonical(self):  # T12
        path = ROOT / "samples/epi-12k.halt.doll"
        for bad in (path.read_bytes() + b"\n", path.read_bytes().replace(b'"doll":1', b'"doll": 1'),
                    path.read_bytes().replace(b'"doll":1', b'"doll":2'), b"{}\n"):
            with self.subTest(bad=bad[:24]):
                probe = ROOT / "tests" / "probe.doll"
                probe.write_bytes(bad)
                try:
                    refused("bad_doll")(self, lambda: doll.read_doll(probe))
                finally:
                    probe.unlink()

    def test_a_changed_frame_changes_the_head(self):  # T13
        der = self.tampered(lambda d: d["frames"][2].__setitem__("ranked", 9))
        self.assertNotEqual(doll.head(der), der["head"])
        refused("replay_divergence")(self, lambda: doll.verify(der))

    def test_a_derivation_may_not_grade_itself(self):  # T17, D7
        for edit in (lambda d: d.__setitem__("verdict", "correct"),
                     lambda d: d["frames"][-1].__setitem__("verdict", "passed")):
            der = self.tampered(edit)
            der["head"] = doll.head(der)
            refused("self_certified")(self, lambda: doll.verify(der))

    def test_a_cost_that_does_not_sum(self):  # T18
        der = self.tampered(lambda d: d["spent"].__setitem__("mbits", d["spent"]["mbits"] + 1))
        refused("unaccounted_cost")(self, lambda: doll.verify(der))

    def test_nesting_that_does_nothing(self):  # T19
        der = self.tampered(lambda d: d["shells"][0].__setitem__("alpha_ppm", 0))
        der["head"] = doll.head(der)
        refused("fake_nesting")(self, lambda: doll.verify(der))
        der = self.tampered(lambda d: d["frames"].__setitem__(5, d["frames"][5] | {"trail": d["frames"][5]["trail"][:1]}))
        der["head"] = doll.head(der)
        refused("fake_nesting")(self, lambda: doll.verify(der))

    def test_a_shell_that_is_not_the_shell_its_root_names(self):  # T14, T19
        der = self.tampered(lambda d: d["shells"][1].__setitem__("root", "0" * 64))
        der["head"] = doll.head(der)
        refused("replay_divergence")(self, lambda: doll.verify(der))

    def test_a_trace_that_opens_on_another_goal(self):  # T17, §11
        der = self.tampered(lambda d: d["goal"].__setitem__("seed", 11))
        refused("goal_mutated")(self, lambda: doll.verify(der))
        refused("goal_mutated")(self, lambda: doll.verify(self.der, TARGET[:-1]))

    def test_an_emitted_plan_no_act_composed(self):  # T16
        der = self.tampered(lambda d: d["result"].__setitem__("plan_root", "1" * 64))
        refused("replay_divergence")(self, lambda: doll.verify(der))

    def test_an_act_whose_plan_is_another_plan(self):  # T15
        act = next(i for i, f in enumerate(self.der["frames"]) if f["op"] == "act" and f["outcome"] == "plan")
        der = self.tampered(lambda d: d["frames"][act].__setitem__("plan_root", "2" * 64))
        der["head"] = doll.head(der)
        der["result"]["plan_root"] = "2" * 64
        refused("replay_divergence")(self, lambda: doll.verify(der, TARGET))

    def test_a_gate_that_the_shells_do_not_return(self):  # T14: the gates are recomputed, not read
        act = next(i for i, f in enumerate(self.der["frames"]) if f["op"] == "nest")
        der = self.tampered(lambda d: d["frames"][act]["trail"][-1].__setitem__("gate_ppm", 999_999))
        der["head"] = doll.head(der)
        refused("replay_divergence")(self, lambda: doll.verify(der))

    def test_an_act_that_did_not_pay_for_its_options(self):  # T18
        act = next(i for i, f in enumerate(self.der["frames"]) if f["op"] == "act")
        for edit in (lambda d: d["frames"][act].__setitem__("mbits", 1),
                     lambda d: d["frames"][act - 1].__setitem__("ranked", 9),
                     lambda d: d["frames"][1].__setitem__("mbits", 7)):
            der = self.tampered(edit)
            der["head"] = doll.head(der)
            refused("unaccounted_cost")(self, lambda: doll.verify(der))

    def test_a_choice_project_does_not_rank_first(self):  # T15, D3
        act = next(i for i, f in enumerate(self.der["frames"]) if f["op"] == "predict")
        der = self.tampered(lambda d: d["frames"][act].__setitem__("candidate", {"floor": None, "machine": "m0-chip"}))
        der["head"] = doll.head(der)
        refused("replay_divergence")(self, lambda: doll.verify(der))

    def test_a_branch_that_is_not_the_space_the_goal_offers(self):
        der = self.tampered(lambda d: d["frames"][1].__setitem__("candidates", d["frames"][1]["candidates"][:2]))
        der["head"] = doll.head(der)
        refused("replay_divergence")(self, lambda: doll.verify(der))

    def test_a_halt_the_gate_does_not_support(self):  # D6
        der = self.tampered(lambda d: d["result"].__setitem__("halt", "exhausted"))
        refused("replay_divergence")(self, lambda: doll.verify(der))

    def test_an_unknown_op(self):
        der = self.tampered(lambda d: d["frames"][1].__setitem__("op", "guess"))
        der["head"] = doll.head(der)
        refused("bad_doll")(self, lambda: doll.verify(der))


class Shells(unittest.TestCase):
    def test_a_fresh_shell_is_binary16_and_finite(self):
        shell = doll.fresh_shell(0, 0)
        for name in ("w1", "b1", "w2", "b2", "w3", "b3"):
            rows = shell[name] if isinstance(shell[name][0], list) else [shell[name]]
            for row in rows:
                self.assertTrue(all(abs(v) <= 1.0 for v in row))
        out = doll.forward(shell, [0.0, 0.0])
        self.assertEqual(len(out), 3)
        self.assertEqual(out, doll.forward(doll.fresh_shell(0, 0), [0.0, 0.0]))

    def test_a_trained_shell_is_a_web_map_of_this_shape(self):
        sizes = {"w1": (2, 64), "b1": (64,), "w2": (64, 64), "b2": (64,), "w3": (64, 3), "b3": (3,)}
        shell = doll.fresh_shell(1, 0)
        tensors = {"grid": (17, [64, 64], (2,)), "omega0": (17, [30], ()), "activation": (4, [0], ())}
        flat = {"w1": [v for r in shell["w1"] for v in r], "b1": shell["b1"],
                "w2": [v for r in shell["w2"] for v in r], "b2": shell["b2"],
                "w3": [v for r in shell["w3"] for v in r], "b3": shell["b3"]}
        for name, shape in sizes.items():
            tensors[name] = (19, flat[name], shape)
        blob = webmap(tensors)
        path = ROOT / "tests" / "probe.tmap"
        path.write_bytes(blob)
        try:
            self.assertEqual(doll.shell_root(doll.web_shell(path)), doll.shell_root(shell))
            path.write_bytes(webmap({k: v for k, v in tensors.items() if k != "w3"}))
            refused("bad_map")(self, lambda: doll.web_shell(path))
            path.write_bytes(webmap(tensors, kind="plan"))
            refused("kind_mismatch")(self, lambda: doll.web_shell(path))
            path.write_bytes(webmap(tensors | {"b3": (19, shell["b3"][:2], (2,))}))
            refused("bad_shell")(self, lambda: doll.web_shell(path))
        finally:
            path.unlink()


def webmap(tensors, kind="web"):
    """A web tmap1 map (web §14) written by hand: this repository reads one, it never writes one."""
    import struct
    out = [b"tmap1", bytes([len(kind)]), kind.encode("ascii"), struct.pack("<H", len(tensors))]
    fmt = {4: "B", 17: "H", 19: "e"}
    for name in sorted(tensors):
        code, values, shape = tensors[name]
        out += [bytes([len(name)]), name.encode("ascii"), bytes([code, len(shape)]),
                struct.pack(f"<{len(shape)}I", *shape), struct.pack(f"<{len(values)}{fmt[code]}", *values)]
    return b"".join(out)


class Tensors(unittest.TestCase):
    def test_every_sample_derivation_map_is_pinned(self):  # T21
        pins = PINS["tensors"]["doll_maps"]
        self.assertEqual(sorted(m["doll"] for m in pins), sorted(d["path"] for d in PINS["dolls"]))
        for pin in pins:
            with self.subTest(doll=pin["doll"]):
                blob = tmap.of_doll(doll.read_doll(ROOT / pin["doll"]))
                self.assertEqual(tmap.root(blob), pin["root"])
                self.assertEqual(len(blob), pin["bytes"])
                kind, t = tmap.unpack(blob, "doll")
                self.assertEqual(kind, "doll")
                self.assertEqual(tmap.pack(kind, {n: (c, v, s) for n, (c, s, v) in t.items()}), blob)

    def test_the_map_names_the_goal_the_plan_and_the_derivation(self):  # §10
        der = doll.read_doll(ROOT / "samples/epi-12k.doll")
        t = tmap.unpack(tmap.of_doll(der), "doll")[1]
        self.assertEqual(bytes(t["doll_root"][2]).hex(), doll.doll_root(der))
        self.assertEqual(bytes(t["goal_root"][2]).hex(), doll.goal_root(der["goal"]))
        self.assertEqual(bytes(t["plan_root"][2]).hex(), der["result"]["plan_root"])
        self.assertEqual(bytes(t["head"][2]).hex(), der["head"])
        self.assertEqual(t["spent"][2], [der["spent"][k] for k in ("acts", "backtracks", "mbits", "pots", "predicts")])
        self.assertEqual(t["frame_op"][1], (len(der["frames"]),))
        self.assertEqual(t["verdict"][2], [0])
        self.assertEqual(t["shell_root"][1], (der["goal"]["depth"], 32))

    def test_a_derivation_that_does_not_replay_is_not_mapped(self):  # T21
        der = doll.read_doll(ROOT / "samples/epi-12k.doll")
        der["spent"]["acts"] += 1
        refused("unaccounted_cost")(self, lambda: tmap.of_doll(der))

    def test_no_base_in_a_derivation_map(self):  # T20, web S4
        blob = tmap.of_doll(doll.read_doll(ROOT / "samples/epi-12k.doll"))
        self.assertNotIn(TARGET[:16].encode("ascii"), blob)
        self.assertLessEqual({c for c, _, _ in tmap.unpack(blob)[1].values()}, {tmap.U8, tmap.U32, tmap.F32})


if __name__ == "__main__":
    unittest.main()
