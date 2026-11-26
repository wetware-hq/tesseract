# `pin-sources` — what may be cited, fetched or relied on

`type: resource.policy` · `spec: agent.policy` · subordinate to `docs/follow-agent-contract.md`, which governs on any conflict.

Every external input is pinned by a stable identifier — a DOI, or a repository commit and file sha256. Code under a licence this repository does not adopt is cited and pinned, never vendored. Machine rows in `tesseract.json` are design parameters, not vendor specifications: each one says what limit it stands for, and no row claims a named instrument's performance.

## Specification

```json { type: notebook.cell }
{
  "id": "docs/pin-sources.md",
  "type": "resource.policy",
  "role": "list the methods, data and code this repository may rely on",
  "reads": ["tesseract.json"],
  "writes": [],
  "must": ["pin code by commit and sha256", "never vendor GPL code", "cite papers, never copy them", "never present a machine row as a vendor claim"],
  "check": ["T2"]
}
```

## Graph

- ← [follow-agent-contract.md](follow-agent-contract.md)
- → [../skills/compile-chromosome.md](../skills/compile-chromosome.md)

## Theory

| Claim | Source |
|---|---|
| A sequence longer than a synthesizer's runlength can be built from shorter pieces joined in tiers, up to a whole designed chromosome | Richardson et al. (2017) Design of a synthetic yeast genome. *Science* 355(6329), 1040–1044. doi:10.1126/science.aaf4557 |
| Parent repository: media stored as the weights of a shallow network, written as synthetic DNA (`dna1`) and as indexed oligo pools (`pool1`) | `wetware-hq/web`, contract §9–§10 |
| Oligo pools with index and parity reconstruct a sequence from unordered, lossy reads | Goldman et al. (2013) Towards practical, high-capacity, low-maintenance information storage in synthesized DNA. *Nature* 494, 77–80. doi:10.1038/nature11875 |

The construction is a claim about software: the plan composes to the target. That a pot ligates, that a host carries an episome, or that a printed molecule matches the plan are not claimed here.

## Assembly

| Use | Source |
|---|---|
| Type IIS one-pot assembly fidelity measured for all 240 four-base overhangs; the data a fidelity-driven junction choice would use | Potapov et al. (2018) Comprehensive profiling of four base overhang ligation fidelity by T4 DNA ligase and application to DNA assembly. *ACS Synth. Biol.* 7(11), 2665–2674. doi:10.1021/acssynbio.8b00333 |
| Data-optimised overhang sets raise one-pot complexity well past what a distance rule allows | Pryor et al. (2020) Enabling one-pot Golden Gate assemblies of unprecedented complexity using data-optimized assembly design. *PLOS ONE* 15(9), e0238592. doi:10.1371/journal.pone.0238592 |
| Junction optimisation for scarless assembly of a target sequence; the design `omega1` is named after and deliberately simpler than | `RomeroLab/omega`, commit `160be2f7292676f64d54dad58902d5de557d9487`, `code/omega.py` sha256 `4287c1d29f27989d0f9a6ef9523d5f4e7e43356bd016e04699bf1e502f30534b`, `code/junctions.py` sha256 `2a1438cd850f054522b7df654fe36a756e471075abe33689ba8eae15c9fa4293`. GPL-3: **cited and pinned, never vendored.** |

`omega1` (contract §7) is a Hamming-distance rule over a deterministic set, with no ligation data in the repository. It is therefore conservative: it supports smaller pots than the measured sets above. Pinning a fidelity table would be a new format version, not an edit to this one.

## Synthesis

| Limit | Why it is a machine field | Source |
|---|---|---|
| Runlength ceiling of chemical synthesis, and the error accumulation that sets it | `ceil`, `floor` | Kosuri & Church (2014) Large-scale de novo DNA synthesis: technologies and applications. *Nat. Methods* 11, 499–507. doi:10.1038/nmeth.2918 |
| Enzymatic synthesis as the route to longer runs — the bet `m2-tdt` and `m3-bet` stand for | `ceil` | Palluk et al. (2018) De novo DNA synthesis using polymerase-nucleotide conjugates. *Nat. Biotechnol.* 36, 645–650. doi:10.1038/nbt.4173 |
| Writing to living genomes, the read-back end of the loop | out of scope here, pinned for the parent stack | Shipman et al. (2017) CRISPR–Cas encoding of a digital movie into the genomes of a population of living bacteria. *Nature* 547, 345–349. doi:10.1038/nature23017 |

## Samples

| Sample | How it is made |
|---|---|
| `samples/epi-12k.fa` | `ref/tess.py seed 12000` — `sha256(b"tess1" ‖ seed ‖ counter)` read two bits at a time, rejecting any base that would make a run of 4 or complete a machine enzyme site. Not a biological sequence and not derived from one. |
| `samples/site-2k.fa` | the same generator at `seed 7`, with two `GGTCTC` sites spliced in, so the enzyme choice of contract §3 has something to avoid. |

No third-party sequence is vendored, so no sequence in this repository carries anyone else's rights.

## Licence

MIT, see `LICENSE`.
