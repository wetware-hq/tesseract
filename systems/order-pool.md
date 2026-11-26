# `order-pool` — turn a plan into an oligo order

`type: resource.system` · `spec: agent.system` · subordinate to `docs/follow-agent-contract.md`, which governs on any conflict.

A plan's leaves are the order. This file fixes what is sent to a synthesizer and what must be checked before and after. Nothing here is a wet-lab protocol: no vendor, queue, buffer or incubation is specified.

## Specification

```json { type: notebook.cell }
{
  "id": "systems/order-pool.md",
  "type": "resource.system",
  "role": "write a plan's parts as an order and bound what the order proves",
  "reads": ["*.tess"],
  "writes": ["FASTA"],
  "must": ["compose before ordering", "order the parts verbatim", "re-check every delivered part against the plan"],
  "check": ["T4", "T10"]
}
```

## Graph

- ← [../skills/compose-plan.md](../skills/compose-plan.md)
- → [commit-plan.md](commit-plan.md)

## Indications

- A plan has composed to its target and the parts are to be synthesized.

## Contraindications

- Never order from a plan that has not composed (contract §4). A plan is cheap to check and an order is not.
- Never order a part a vendor has silently rewritten. A delivered sequence that differs from the plan is a different part, and its plan is no longer the build record.
- Never add vector, primer, barcode or adaptor bases to a part in this file. A part is exactly a span of the target; anything else changes the composed sequence and makes the plan false.

## Algorithm

```text { type: notebook.cell }
python ref/tess.py order <plan.tess> <order.fa>

order(plan):
  compose(plan)                                  # refuse to write an order for an invalid plan
  for each part, in target order:
    write ">" part.id " nt=" part.nt " span=" start "-" end
    write part.seq                               # the target's own bases, nothing added

receive(delivered, plan):
  for each part: if delivered[part.id] != part.seq: fail(target_mismatch)
```

- The order carries `shape.order_nt` bases in total: the target's length plus `overhang` bases for every junction, because each junction's bases are in both neighbouring parts (contract §6).
- Flanking sequence a method needs — enzyme sites, vector arms, primer sites — belongs to the physical protocol, not to the plan. The plan stays the record of the target's bases.
- The parts of one pot can be ordered and delivered as a pooled mixture; the plan's `pools` say which parts share a reaction, and the junctions in that pot are pairwise orthogonal (contract §7).

## Cost

For `samples/epi-12k.fa` (12,000 nt) the order is 12,328 bases in 83 parts on `m0-chip`, and 12,000 bases in 1 part on `m3-bet` — a 2.7% junction overhead against 0% (`docs/vary-runlength.md`).

## Falsification

- An order file contains a base at a position where the target has another.
- The order's total length is not `shape.order_nt`.

## Licence

MIT, see `LICENSE`.
