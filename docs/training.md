# Training And Dataset Contract

## Separate learning problems

Perception and coordination are trained independently. Image datasets do not
become RL trajectories, and simulator ground truth never becomes a deployed
policy observation.

## Perception lanes

| Source | V1 role | Headline evaluation |
| --- | --- | --- |
| Sen1Floods11 hand labels | TerraMind S1GRD flood segmentation | Event-held-out IoU, F1, calibration |
| Sen1Floods11 weak masks | Optional auxiliary pretraining only | Never used for headline metrics |
| SpaceNet 8 | Separate flooded road/building accessibility | Cross-AOI evaluation |
| FloodNet | Optional low-altitude scene segmentation | Flight/spatial-group split |
| SeaDronesSee | Small-person detector initialization | Mission/video-group split only |
| OSM, DEM, GPM Early/Late | Runtime context and simulation conditioning | Provenance and freshness checks |
| Copernicus EMS, GPM Final | Offline reference | Never presented as real-time input |

TerraMind is pinned to `ibm-esa-geospatial/TerraMind-1.0-tiny` revision
`2b5ac0a`. The intended exported flood path is S1-only; S1+S2 is an upper-bound
experiment because cloud-free optical imagery is not guaranteed.

Training starts with a frozen backbone and new flood/projection heads. Only the
last encoder blocks may then be unfrozen at a lower learning rate. The exported
artifact includes preprocessing, bands, units, normalization, calibration,
validity masks, and model revision.

The drone detector is a separate compact model. Maritime people-in-water data
is useful initialization but does not prove urban flood generalization.

## Colab training dependencies

The repository lockfile intentionally covers only the lightweight API,
simulation, contract, and command-center development path. GPU perception and
MARL training dependencies are installed explicitly inside Colab so default
repository scans do not inherit large optional stacks that are not needed to run
the demo.

Use current Colab-compatible wheels for the active runtime, then record exact
resolved versions in the exported model card. The intended training stack is:

- TerraTorch for TerraMind flood segmentation experiments.
- PyTorch and TorchVision for perception heads and detector fine-tuning.
- Gymnasium, PettingZoo, and Ray RLlib for scalable MARL training.
- Weights & Biases or Trackio for experiment tracking.

The lightweight notebook entrypoints in `notebooks/` are import-safe in the
default dev environment and should fail fast in Colab if a required training
package is missing.

## RL observation adapter

The policy receives compact semantic features:

- flood probabilities and projected overhead embeddings,
- victim hypotheses with confidence,
- data age and validity masks,
- battery, pose quality, role, and communication state,
- nearby hazards and task assignments.

The procedural simulator first creates latent truth. A calibrated observation
adapter then applies perception false positives/negatives, localization error,
latency, stale data, and complete dropout. Oracle observations are permitted
only as a diagnostic evaluation condition.

## MARL curriculum

1. Validate rewards and action masks with two drones and deterministic scripts.
2. Train shared local policies with two and four active drones.
3. Add the slower global assignment policy.
4. Train randomized active masks from four to eight drones.
5. Freeze training and evaluate zero-shot transfer at 16 drones.

PPO updates must use clipping, normalized advantages, gradient clipping, an
entropy bonus, centralized value baselines, and logged reward components.
Safety violations are tracked separately from shaped reward so a policy cannot
hide unsafe behavior behind higher mission score.

## Evaluation splits

- Split Sen1Floods11 by complete flood event, never neighboring chips.
- Split SpaceNet 8 by AOI.
- Split FloodNet by flight or spatial cluster.
- Split SeaDronesSee by mission/video/camera.
- Split RL by generator family and seed, never transitions.
- Lock test seeds before policy tuning.

Each policy condition uses at least three training seeds and 100 locked
evaluation missions when compute permits. Reports include bootstrap confidence
intervals and label reduced runs honestly.
