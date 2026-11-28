"""Reference `doll1` reasoner: the Type II half of the stack (docs/follow-agent-contract.md §11).

A doll is one derivation: a goal, a matryoshka of shallow `web`-shaped shells composed into one
deeper net, and a hash-chained trace of what the reasoner predicted, did and spent before it
emitted a plan. `compose` (§4) stays the only exactness check; a shell never grades a plan, and a
doll never carries an outcome from the world (§11, `verdict` is always "unverified").

Standard library only. Python 3.10+.
"""

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import tess
from tess import Refusal

TAG = b"doll1"
DEPTH_MAX = 8            # §11: more shells than this is depth_overflow
SHELL = (2, 64, 64, 3)   # a shell is a web of web §2 shape: 2 in, two hidden layers, 3 out
OMEGA0 = 30              # the sine frequency a web is fitted with (web §2)
PPM = 1_000_000
OBJECTIVES = {           # the key a goal orders candidates by, from the shape (§6)
    "fewest_tiers": lambda s: (s["tiers"], s["pots"], s["order_nt"]),
    "fewest_pots": lambda s: (s["pots"], s["tiers"], s["order_nt"]),
    "fewest_bases": lambda s: (s["order_nt"], s["tiers"], s["pots"]),
}
OPS = ("abstract", "branch", "predict", "act", "nest", "backtrack", "emit")


# ---------------------------------------------------------------- shells (the dolls)


def fresh_shell(seed, index):
    """A shell nobody trained: weights read off sha256(TAG || seed || index || counter).

    The shape and the initialisation bounds are a web's (SIREN: the first layer uniform on
    +-1/fan_in, the rest on +-sqrt(6/fan_in)/omega0), so a fresh shell and a shell fitted in
    `wetware-hq/web` are the same object; only the bytes differ. A fresh shell is a frozen
    surface, not a model of anything, and §11 says so.
    """
    stream, pos, blocks = bytearray(), 0, 0
    weights = []
    for fan_in, fan_out, first in ((SHELL[0], SHELL[1], True), (SHELL[1], SHELL[2], False), (SHELL[2], SHELL[3], False)):
        bound = 1.0 / fan_in if first else math.sqrt(6.0 / fan_in) / OMEGA0
        for count in (fan_in * fan_out, fan_out):
            row = []
            for _ in range(count):
                while pos + 2 > len(stream):
                    stream += hashlib.sha256(TAG + b"/shell" + seed.to_bytes(8, "big")
                                             + index.to_bytes(8, "big") + blocks.to_bytes(8, "big")).digest()
                    blocks += 1
                (raw,) = struct.unpack_from("<H", stream, pos)
                pos += 2
                value = bound * (2.0 * raw / 65535.0 - 1.0)
                row.append(struct.unpack("<e", struct.pack("<e", value))[0] + 0.0)  # binary16, as a web stores it
            weights.append(row)
    return shaped(weights)


def shaped(flat):
    """[w1, b1, w2, b2, w3, b3] flat lists -> the matrices a forward pass wants."""
    w1, b1, w2, b2, w3, b3 = flat
    return {
        "w1": [w1[i * SHELL[1]:(i + 1) * SHELL[1]] for i in range(SHELL[0])], "b1": b1,
        "w2": [w2[i * SHELL[2]:(i + 1) * SHELL[2]] for i in range(SHELL[1])], "b2": b2,
        "w3": [w3[i * SHELL[3]:(i + 1) * SHELL[3]] for i in range(SHELL[2])], "b3": b3,
    }


def shell_bytes(shell):
    """A shell's weights in a web's §2 order, binary16 little-endian: the shell root hashes these."""
    out = bytearray()
    for name in ("w1", "b1", "w2", "b2", "w3", "b3"):
        value = shell[name]
        rows = value if isinstance(value[0], list) else [value]
        for row in rows:
            out += struct.pack(f"<{len(row)}e", *row)
    return bytes(out)


def shell_root(shell):
    return hashlib.sha256(shell_bytes(shell)).hexdigest()


def web_shell(path):
    """A trained shell: a `web` tmap1 map (web §14) of the right shape, read for its six weights."""
    blob = Path(path).read_bytes()
    kind, tensors = read_map(blob)
    if kind != "web":
        raise Refusal("kind_mismatch", f"{kind!r} map, a web map is required")
    try:
        flat = [tensors[name][1] for name in ("w1", "b1", "w2", "b2", "w3", "b3")]
        grid = tensors["grid"][1]
    except KeyError as err:
        raise Refusal("bad_map", f"web map without {err}") from None
    want = [SHELL[0] * SHELL[1], SHELL[1], SHELL[1] * SHELL[2], SHELL[2], SHELL[2] * SHELL[3], SHELL[3]]
    if [len(v) for v in flat] != want or len(grid) != SHELL[0]:
        raise Refusal("bad_shell", f"a shell is {SHELL}, this map is not")
    return shaped(flat)


def read_map(blob):
    """Minimal tmap1 reader (web §14) for the dtypes a web map uses: float16, uint8, uint16."""
    fmt = {4: "B", 17: "H", 19: "e"}
    try:
        n = blob[5]
        kind = blob[6:6 + n].decode("ascii")
        (count,) = struct.unpack_from("<H", blob, 6 + n)
        pos, tensors = 8 + n, {}
        if blob[:5] != b"tmap1":
            raise Refusal("bad_map", "not tmap1 bytes")
        for _ in range(count):
            name = blob[pos + 1:pos + 1 + blob[pos]].decode("ascii")
            pos += 1 + blob[pos]
            code, rank = blob[pos], blob[pos + 1]
            shape = struct.unpack_from(f"<{rank}I", blob, pos + 2)
            pos += 2 + 4 * rank
            size = 1
            for dim in shape:
                size *= dim
            tensors[name] = (shape, list(struct.unpack_from(f"<{size}{fmt[code]}", blob, pos)))
            pos += size * struct.calcsize(fmt[code])
    except (IndexError, KeyError, UnicodeDecodeError, struct.error) as err:
        raise Refusal("bad_map", f"not a web-dtype tmap1 map: {err}") from None
    return kind, tensors


def forward(shell, x):
    """One shell: sin(omega0 * (x W1 + b1)) -> sin(omega0 * (h W2 + b2)) -> h W3 + b3."""
    h = [math.sin(OMEGA0 * (sum(x[i] * shell["w1"][i][j] for i in range(len(x))) + shell["b1"][j]))
         for j in range(SHELL[1])]
    h = [math.sin(OMEGA0 * (sum(h[i] * shell["w2"][i][j] for i in range(SHELL[1])) + shell["b2"][j]))
         for j in range(SHELL[2])]
    return [sum(h[i] * shell["w3"][i][j] for i in range(SHELL[2])) + shell["b3"][j] for j in range(SHELL[3])]


def nest(shells, alphas, state):
    """The matryoshka: D shallow shells composed into one 2D-layer residual net (§11).

    s_k = tanh(s_(k-1) + alpha_k * ds_k) with (ds_k, g_k) = shell_k(s_(k-1)); the last shell's
    g, squashed, is the halting gate. Nothing here touches a base, a part or a plan.
    """
    trail, gate = [], 0.0
    for shell, alpha in zip(shells, alphas):
        out = forward(shell, state)
        state = [math.tanh(state[i] + alpha * out[i]) for i in range(2)]
        gate = math.tanh(out[2])
        trail.append({"s_ppm": [round(v * PPM) for v in state], "gate_ppm": round(gate * PPM)})
    return state, trail


# ---------------------------------------------------------------- the goal


def goal_of(target_nt, target_root, machines, objective="fewest_tiers", floors=(None,),
            allow=(False, False), depth=3, seed=0, acts=16, mbits=64_000, theta_ppm=PPM, brief=""):
    if objective not in OBJECTIVES:
        raise Refusal("bad_goal", f"objective {objective!r}")
    if not machines:
        raise Refusal("bad_goal", "no machine offered")
    if not 1 <= depth <= DEPTH_MAX:
        raise Refusal("depth_overflow", f"depth {depth}, maximum {DEPTH_MAX}")
    if acts < 1 or mbits < 1:
        raise Refusal("bad_goal", "a budget of nothing")
    if not all(c in "0123456789abcdef" for c in target_root) or len(target_root) != 64:
        raise Refusal("bad_goal", "target root is not a sha256")
    if not brief.isascii() or len(brief) > 200:
        raise Refusal("bad_goal", "brief is not at most 200 ASCII characters")
    return {
        "brief": brief,
        "target": {"nt": int(target_nt), "root": target_root},
        "machines": sorted(machines),
        "floors": [None if f is None else int(f) for f in floors],
        "allow": {"small_episomes": bool(allow[0]), "small_fragments": bool(allow[1])},
        "objective": objective,
        "budget": {"acts": int(acts), "mbits": int(mbits)},
        "depth": int(depth),
        "seed": int(seed),
        "theta_ppm": int(theta_ppm),
    }


def goal_root(goal):
    return hashlib.sha256(canonical(goal)).hexdigest()


def candidates(goal, pins=None):
    """Every (machine, floor) the goal offers, in one fixed order. The search space, enumerated."""
    out = []
    for mid in goal["machines"]:
        row = tess.machine(mid, pins)
        for floor in goal["floors"]:
            if floor == row["floor"]:
                floor = None  # a machine's own floor under another name is its default, not a second candidate
            if floor is not None and not row["floor"] < floor <= row["ceil"]:
                continue
            cand = {"machine": mid, "floor": floor}
            if cand not in out:
                out.append(cand)
    if not out:
        raise Refusal("bad_goal", "no candidate machine and floor")
    if len(out) < 2:
        raise Refusal("unaccounted_cost", "one candidate is a reflex (`compile`), not a derivation")
    return out


def mbits(options):
    """The information it takes to name one option out of `options`, in millibits."""
    return 0 if options <= 1 else math.ceil(1000 * math.log2(options))


def surprise(predicted, actual):
    """How wrong the world model was about this candidate, in [0, 1]: the Type II signal."""
    bases = abs(actual["order_nt"] - predicted["order_nt"]) / max(1, predicted["order_nt"])
    tiers = abs(actual["tiers"] - predicted["tiers"]) / (predicted["tiers"] + 1)
    return min(1.0, bases + tiers)


# ---------------------------------------------------------------- the derivation


def reason(seq, goal, pins=None, shells=None):
    """Run one derivation and return a doll (§11). The only normative check is `compose` (§4)."""
    if tess.seq_root(seq) != goal["target"]["root"] or len(seq) != goal["target"]["nt"]:
        raise Refusal("goal_mutated", "the sequence is not the target the goal names")
    shells = shells or [fresh_shell(goal["seed"], k) for k in range(goal["depth"])]
    if len(shells) != goal["depth"]:
        raise Refusal("fake_nesting", f"{len(shells)} shells for depth {goal['depth']}")
    alphas = [1.0 / (k + 1) for k in range(goal["depth"])]
    key = OBJECTIVES[goal["objective"]]
    frontier = candidates(goal, pins)
    spent = {"acts": 0, "backtracks": 0, "mbits": 0, "pots": 0, "predicts": 0}
    frames = [{"op": "abstract", "goal_root": goal_root(goal), "candidates": len(frontier),
               "depth": goal["depth"], "s_ppm": [-PPM, -PPM]}]
    frames.append({"op": "branch", "candidates": frontier, "mbits": mbits(len(frontier))})
    spent["mbits"] += frames[-1]["mbits"]
    best, state, halted = None, [-1.0, -1.0], None
    open_set = list(frontier)
    while open_set:
        cost = mbits(len(open_set))
        if spent["acts"] >= goal["budget"]["acts"] or spent["mbits"] + cost > goal["budget"]["mbits"]:
            halted = "budget_exhausted"
            break
        ranked = []
        for cand in open_set:
            row = tess.machine(cand["machine"], pins)
            shape = tess.project(goal["target"]["nt"], row, cand["floor"])
            ranked.append((key(shape), hashlib.sha256(canonical(cand)).hexdigest(), cand, shape))
        ranked.sort()
        spent["predicts"] += len(ranked)
        _, _, cand, predicted = ranked[0]
        frames.append({"op": "predict", "candidate": cand, "shape": predicted, "ranked": len(ranked)})
        open_set.remove(cand)
        spent["mbits"] += cost
        spent["acts"] += 1
        row = tess.machine(cand["machine"], pins)
        try:
            plan = tess.compile_plan(seq, row, cand["floor"], goal["allow"]["small_fragments"], goal["allow"]["small_episomes"])
        except Refusal as err:
            frames.append({"op": "act", "candidate": cand, "mbits": cost, "outcome": f"refused:{err.code}"})
            frames.append({"op": "backtrack", "candidate": cand, "code": err.code, "open": len(open_set)})
            spent["backtracks"] += 1
            moved = [min(1.0, spent["acts"] / goal["budget"]["acts"]), 1.0]
        else:
            frames.append({"op": "act", "candidate": cand, "mbits": cost, "outcome": "plan",
                           "plan_root": tess.plan_root(plan), "shape": plan["shape"],
                           "surprise_ppm": round(surprise(predicted, plan["shape"]) * PPM)})
            spent["pots"] += plan["shape"]["pots"]
            if best is None or key(plan["shape"]) < key(best["shape"]):
                best = {"candidate": cand, "plan_root": tess.plan_root(plan), "shape": plan["shape"],
                        "enzyme": plan["enzyme"]["name"]}
            moved = [min(1.0, spent["acts"] / goal["budget"]["acts"]), surprise(predicted, plan["shape"])]
        state = [2.0 * moved[0] - 1.0, 2.0 * moved[1] - 1.0]
        state, trail = nest(shells, alphas, state)
        frames.append({"op": "nest", "depth": goal["depth"], "trail": trail})
        if trail[-1]["gate_ppm"] >= goal["theta_ppm"] and best is not None:
            halted = "gate"
            break
    if best is None:
        raise Refusal(halted or "unsat_search", "no candidate composed")
    frames.append({"op": "emit", "halt": halted or "exhausted", "plan_root": best["plan_root"],
                   "machine": best["candidate"]["machine"], "floor": best["candidate"]["floor"],
                   "shape": best["shape"], "verdict": "unverified"})
    doll = {
        "doll": 1,
        "goal": goal,
        "shells": [{"index": k, "source": "fresh", "seed": goal["seed"], "alpha_ppm": round(alphas[k] * PPM),
                    "root": shell_root(shells[k])} for k in range(goal["depth"])],
        "frames": frames,
        "spent": spent,
        "result": {"outcome": "plan", "halt": halted or "exhausted", "plan_root": best["plan_root"],
                   "machine": best["candidate"]["machine"], "floor": best["candidate"]["floor"],
                   "enzyme": best["enzyme"], "shape": best["shape"]},
        "verdict": "unverified",
    }
    doll["head"] = head(doll)
    return doll


def head(doll):
    """h_0 = sha256("doll1"), h_(j+1) = sha256(h_j || canonical frame j): 32 bytes name the trace."""
    chain = hashlib.sha256(TAG).digest()
    for frame in doll["frames"]:
        chain = hashlib.sha256(chain + canonical(frame)).digest()
    return chain.hex()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def doll_bytes(doll):
    return canonical(doll) + b"\n"


def doll_root(doll):
    return hashlib.sha256(doll_bytes(doll)).hexdigest()


def read_doll(path):
    try:
        blob = Path(path).read_bytes()
        doll = json.loads(blob.decode("ascii"))
    except (OSError, UnicodeDecodeError, ValueError) as err:
        raise Refusal("bad_doll", str(err)) from None
    if doll_bytes(doll) != blob:
        raise Refusal("bad_doll", "bytes are not canonical")
    for field in ("doll", "goal", "shells", "frames", "spent", "result", "verdict", "head"):
        if field not in doll:
            raise Refusal("bad_doll", f"no {field}")
    if doll["doll"] != 1:
        raise Refusal("bad_doll", f"tag {doll['doll']!r}")
    return doll


# ---------------------------------------------------------------- verification


def verify(doll, seq=None, pins=None):
    """Replay a derivation: its chain, its choices, its costs, its gates, its halt and its acts (§11).

    Everything but the acts replays without the target: the candidates come from the goal, each
    prediction from `project`, each cost from how many options were open, and each gate from running
    the regenerated shells on the state the trace says it reached. With `seq`, every act is compiled
    and composed again as well. A derivation grades nothing; this returns what the trace regenerates,
    and refuses where it does not.
    """
    goal = doll["goal"]
    if doll["verdict"] != "unverified":
        raise Refusal("self_certified", f"verdict {doll['verdict']!r}")
    for frame in doll["frames"]:
        if frame["op"] not in OPS:
            raise Refusal("bad_doll", f"op {frame['op']!r}")
        if "verdict" in frame and frame["verdict"] != "unverified":
            raise Refusal("self_certified", f"frame verdict {frame['verdict']!r}")
    if doll["frames"][0]["op"] != "abstract" or doll["frames"][0]["goal_root"] != goal_root(goal):
        raise Refusal("goal_mutated", "the trace does not open on this goal")
    if head(doll) != doll["head"]:
        raise Refusal("replay_divergence", "the head is not the chain over these frames")
    if len(doll["shells"]) != goal["depth"] or not 1 <= goal["depth"] <= DEPTH_MAX:
        raise Refusal("depth_overflow" if goal["depth"] > DEPTH_MAX else "fake_nesting", "depth")
    shells, alphas = [], []
    for k, shell in enumerate(doll["shells"]):
        if shell["alpha_ppm"] == 0:
            raise Refusal("fake_nesting", f"shell {k} moves the state by nothing")
        if shell["source"] != "fresh":
            raise Refusal("bad_shell", f"source {shell['source']!r} cannot be regenerated here")
        made = fresh_shell(shell["seed"], shell["index"])
        if shell_root(made) != shell["root"]:
            raise Refusal("replay_divergence", f"shell {k} is not the shell its root names")
        shells.append(made)
        alphas.append(shell["alpha_ppm"] / PPM)
    if seq is not None and (tess.seq_root(seq) != goal["target"]["root"] or len(seq) != goal["target"]["nt"]):
        raise Refusal("goal_mutated", "this sequence is not the target the goal names")

    key = OBJECTIVES[goal["objective"]]
    open_set = candidates(goal, pins)
    counted = {"acts": 0, "backtracks": 0, "mbits": 0, "pots": 0, "predicts": 0}
    acted, replayed, gates, armed, pending = [], 0, [], [], None
    if doll["frames"][1]["op"] != "branch" or doll["frames"][1]["candidates"] != open_set:
        raise Refusal("replay_divergence", "the branch is not the candidates the goal offers")
    for frame in doll["frames"][1:]:
        counted["mbits"] += frame.get("mbits", 0)
        if frame["op"] == "branch" and frame["mbits"] != mbits(len(open_set)):
            raise Refusal("unaccounted_cost", "the branch did not pay for naming one candidate")
        if frame["op"] == "predict":
            counted["predicts"] += frame["ranked"]
            if frame["ranked"] != len(open_set):
                raise Refusal("unaccounted_cost", f"a prediction over {frame['ranked']} of {len(open_set)} candidates")
            ranked = sorted((key(shape), hashlib.sha256(canonical(c)).hexdigest(), c, shape)
                            for c, shape in ((c, tess.project(goal["target"]["nt"], tess.machine(c["machine"], pins), c["floor"]))
                                             for c in open_set))
            if ranked[0][2] != frame["candidate"] or ranked[0][3] != frame["shape"]:
                raise Refusal("replay_divergence", f"{frame['candidate']} is not what `project` ranks first here")
            pending = frame
        if frame["op"] == "act":
            counted["acts"] += 1
            if pending is None or frame["candidate"] != pending["candidate"]:
                raise Refusal("replay_divergence", "an act without the prediction that chose it")
            if frame["mbits"] != mbits(len(open_set)):
                raise Refusal("unaccounted_cost", f"{frame['candidate']} cost {frame['mbits']} of {len(open_set)} options")
            open_set.remove(frame["candidate"])
            if counted["mbits"] > goal["budget"]["mbits"] or counted["acts"] > goal["budget"]["acts"]:
                raise Refusal("budget_exhausted", "an act outside the budget the goal set")
            if frame["outcome"] == "plan":
                counted["pots"] += frame["shape"]["pots"]
                acted.append(frame)
                if frame["surprise_ppm"] != round(surprise(pending["shape"], frame["shape"]) * PPM):
                    raise Refusal("replay_divergence", f"{frame['candidate']}: the recorded surprise is not the prediction's error")
            elif not frame["outcome"].startswith("refused:"):
                raise Refusal("bad_doll", f"outcome {frame['outcome']!r}")
            if seq is not None:
                row = tess.machine(frame["candidate"]["machine"], pins)
                try:
                    plan = tess.compile_plan(seq, row, frame["candidate"]["floor"],
                                             goal["allow"]["small_fragments"], goal["allow"]["small_episomes"])
                except Refusal as err:
                    got = f"refused:{err.code}"
                else:
                    got = "plan"
                    if tess.plan_root(plan) != frame["plan_root"] or plan["shape"] != frame["shape"]:
                        raise Refusal("replay_divergence", f"{frame['candidate']} gives another plan")
                if got != frame["outcome"]:
                    raise Refusal("replay_divergence", f"{frame['candidate']}: {got}, the doll says {frame['outcome']}")
                replayed += 1
        if frame["op"] == "backtrack":
            counted["backtracks"] += 1
            if pending is None or frame["open"] != len(open_set):
                raise Refusal("replay_divergence", "a backtrack over another frontier")
        if frame["op"] == "nest":
            if len(frame["trail"]) != goal["depth"]:
                raise Refusal("fake_nesting", "a nest that does not use every shell")
            if pending is None:
                raise Refusal("replay_divergence", "a nesting without an act before it")
            spend = min(1.0, counted["acts"] / goal["budget"]["acts"])
            act = doll["frames"][doll["frames"].index(pending) + 1]
            moved = 1.0 if act["outcome"] != "plan" else surprise(pending["shape"], act["shape"])
            _, trail = nest(shells, alphas, [2.0 * spend - 1.0, 2.0 * moved - 1.0])
            if trail != frame["trail"]:
                raise Refusal("replay_divergence", "the shells do not return the gates the trace records")
            if len({tuple(step["s_ppm"]) for step in frame["trail"]}) < goal["depth"]:
                raise Refusal("fake_nesting", "the state does not move between shells")
            gates.append(frame["trail"][-1]["gate_ppm"])
            if acted:  # a gate before any plan composed cannot halt the search (§11)
                armed.append(frame["trail"][-1]["gate_ppm"])
            pending = None
    if counted != doll["spent"]:
        raise Refusal("unaccounted_cost", f"{counted} against {doll['spent']}")
    if doll["spent"]["mbits"] <= 0 or doll["spent"]["acts"] <= 0:
        raise Refusal("unaccounted_cost", "a derivation that cost nothing is a reflex, not a thought")
    if not acted:
        raise Refusal("vacuous_doll", "no act composed a plan")
    best = min(acted, key=lambda f: key(f["shape"]))  # ties keep the plan the search found first, as `reason` does
    if doll["result"]["plan_root"] != best["plan_root"]:
        raise Refusal("replay_divergence", "the emitted plan is not the best plan the trace acted on")
    halt = doll["result"]["halt"]
    if halt == "gate" and (not armed or armed[-1] < goal["theta_ppm"]):
        raise Refusal("replay_divergence", f"a gate halt at {gates[-1]} below theta {goal['theta_ppm']}")
    if halt == "exhausted" and (open_set or any(g >= goal["theta_ppm"] for g in armed)):
        raise Refusal("replay_divergence", "an exhausted halt with a candidate left, or a gate that would have fired")
    if halt == "budget_exhausted" and not (
            doll["spent"]["acts"] >= goal["budget"]["acts"]
            or doll["spent"]["mbits"] + mbits(len(open_set)) > goal["budget"]["mbits"]):
        raise Refusal("replay_divergence", "a budget halt with budget left for another act")
    if halt not in ("gate", "exhausted", "budget_exhausted"):
        raise Refusal("bad_doll", f"halt {halt!r}")
    return {"root": doll_root(doll), "head": doll["head"], "acts": doll["spent"]["acts"],
            "mbits": doll["spent"]["mbits"], "replayed": replayed, "gates": gates,
            "halt": halt, "plan_root": doll["result"]["plan_root"],
            "verdict": doll["verdict"], "shells": [shell_root(s) for s in shells]}


# ---------------------------------------------------------------- benchmark envelope


def submission(doll, problem_id, proposer="none"):
    """One Artificial Analysis batch-evaluation submission for a derivation (§12).

    `generated_code` is the plan the derivation emitted, named by its root: a doll submits a build
    plan, never prose, and never the grade. Attribution: https://artificialanalysis.ai/
    """
    return {
        "problem_id": problem_id,
        "generated_code": f"tess1:{doll['result']['plan_root']}",
        "model": f"tesseract-doll1/d{doll['goal']['depth']}/{proposer}",
        "generation_config": {
            "doll_root": doll_root(doll), "goal_root": goal_root(doll["goal"]),
            "head": doll["head"], "objective": doll["goal"]["objective"],
            "seed": doll["goal"]["seed"], "theta_ppm": doll["goal"]["theta_ppm"],
            "budget": doll["goal"]["budget"], "spent": doll["spent"],
            "halt": doll["result"]["halt"], "verdict": doll["verdict"],
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="doll1: one Type II derivation over tess1 plans")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reason", help="target FASTA + goal -> .doll derivation")
    r.add_argument("fasta")
    r.add_argument("out")
    r.add_argument("--machines", default=None, help="comma-separated machine ids, default every machine")
    r.add_argument("--objective", default="fewest_tiers", choices=sorted(OBJECTIVES))
    r.add_argument("--floors", default="", help="comma-separated floors to offer as well as each machine's own")
    r.add_argument("--depth", type=int, default=3)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--acts", type=int, default=16)
    r.add_argument("--mbits", type=int, default=64000)
    r.add_argument("--theta-ppm", type=int, default=PPM, help="halt when the gate reaches this; default never")
    r.add_argument("--brief", default="")
    r.add_argument("--allow-small-fragments", action="store_true")
    r.add_argument("--allow-small-episomes", action="store_true")
    v = sub.add_parser("verify", help="replay a derivation: chain, gates, costs and every act")
    v.add_argument("doll")
    v.add_argument("--target", default=None, help="the target FASTA, to replay the acts as well")
    v.add_argument("--root", default=None, help="expected doll root")
    s = sub.add_parser("show", help="the trace, one line a frame")
    s.add_argument("doll")
    b = sub.add_parser("submit", help="an Artificial Analysis batch submission for a derivation (§12)")
    b.add_argument("doll")
    b.add_argument("--problem-id", required=True)
    b.add_argument("--proposer", default="none")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "reason":
            seq = tess.read_fasta(a.fasta)
            ids = a.machines.split(",") if a.machines else list(tess.machines())
            floors = [None] + [int(f) for f in a.floors.split(",") if f]
            goal = goal_of(len(seq), tess.seq_root(seq), ids, a.objective, floors,
                           (a.allow_small_episomes, a.allow_small_fragments), a.depth, a.seed,
                           a.acts, a.mbits, a.theta_ppm, a.brief)
            doll = reason(seq, goal)
            tess.write(a.out, doll_bytes(doll))
            res = doll["result"]
            print(f"{doll_root(doll)} halt {res['halt']} machine {res['machine']} plan {res['plan_root']} "
                  f"tiers {res['shape']['tiers']} pots {res['shape']['pots']} acts {doll['spent']['acts']} "
                  f"mbits {doll['spent']['mbits']}")
        elif a.cmd == "verify":
            doll = read_doll(a.doll)
            if a.root and doll_root(doll) != a.root:
                raise Refusal("root_mismatch", doll_root(doll))
            out = verify(doll, tess.read_fasta(a.target) if a.target else None)
            print(f"{out['root']} head {out['head']} acts {out['acts']} replayed {out['replayed']} "
                  f"mbits {out['mbits']} halt {out['halt']} plan {out['plan_root']} verdict {out['verdict']}")
        elif a.cmd == "show":
            doll = read_doll(a.doll)
            for i, frame in enumerate(doll["frames"]):
                rest = " ".join(f"{k}={json.dumps(v, separators=(',', ':'))}" for k, v in sorted(frame.items()) if k != "op")
                print(f"{i:3} {frame['op']:10} {rest}")
        elif a.cmd == "submit":
            print(json.dumps(submission(read_doll(a.doll), a.problem_id, a.proposer), indent=2, sort_keys=True))
    except Refusal as err:
        print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
