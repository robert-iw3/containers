<p align="center">
    <a href="https://github.com/robert-iw3/apps/actions/workflows/anchore-ghcr.yml" alt="Docker CI">
          <img src="https://github.com/robert-iw3/apps/actions/workflows/anchore-ghcr.yml/badge.svg" /></a>
</p>

<p align="center">
  <img src="https://sdtimes.com/wp-content/uploads/2020/10/3229fe16208c1b2a76cceeb6c1c5a3b2.png" />
</p>

https://anchore.com/opensource/

---

# Anchore Scanner Usage Guide

## Prerequisites
- Podman or Kubernetes (kubectl configured)
- Python 3.8+ with `tqdm` and `pyyaml` (`pip install tqdm pyyaml`)
- Dockerfile from the provided configuration
- Container images accessible to Podman/Kubernetes

## Setup
1. Save `Dockerfile`, `deploy_anchore.py`, and `scan_config.json` in the same directory.
2. Edit `scan_config.json` to list your container images:
   ```json
   {
       "images": [
           {"repo": "your_repo/image:tag", "name": "image_name"},
           ...
       ]
   }
   ```

## Running Scans
### Podman
```bash
python deploy_anchore.py --deploy-type podman --config scan_config.json --output-dir ./scan_results
```

### Kubernetes
1. Ensure a PersistentVolumeClaim named `anchore-scan-results` exists in the `anchore` namespace.
2. Run:
```bash
python deploy_anchore.py --deploy-type kubernetes --config scan_config.json --output-dir ./scan_results
```

## Output
- Results are saved in `./scan_results` with SBOMs (`json`, `csv`) and vulnerability reports.
- A `scan_summary.json` file details the scan results.
- Logs are saved with timestamps in `anchore_scan_YYYYMMDD_HHMMSS.log`.

## Notes
- Adjust `--max-workers` (default: 4) for performance tuning with large image sets.
- Ensure images are accessible to your Podman/Kubernetes environment.