# Proof Artifacts

Generated Modal and live-deploy evidence is written here.

The JSON/TXT outputs are ignored by default so training runs can be repeated
without noisy diffs. For submission, paste the key metrics into `README.md` or
explicitly force-add a curated artifact if the hackathon requires files.

Recommended commands:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_modal_proof.ps1 -Stage smoke
powershell -ExecutionPolicy Bypass -File scripts\check_live_deploy.ps1 -WorkerUrl https://<worker-url>
```
