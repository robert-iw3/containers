## Wallarm gotestwaf

[github](https://github.com/wallarm/gotestwaf)

https://lab.wallarm.com/test-your-waf-before-hackers/

## Prerequisites
- Python 3.8+
- Install dependencies: `pip install ansible-runner pandas pyyaml openpyxl jinja2 yamllint tqdm psutil`
- Docker, Podman, or Kubernetes CLI installed
- Required files: `Dockerfile`, `config.yaml`, `deploy_gotestwaf.yml.j2`, `gotestwaf_k8s.yml`, `docker-compose.yml`, `deploy_config.yaml`

## Usage
1. **Prepare URLs**: Create a file (e.g., `waf_urls.txt`) with one URL per line, or use a single URL.
   Example `waf_urls.txt`:
   ```
   https://example.com
   https://api.example.org
   ```
2. **Run the Script**:
   ```bash
   python deploy_gotestwaf.py --urls <URL or file> --deploy-type <docker|podman|kubernetes> [--output-dir reports] [--parallel 10] [--dry-run]
   ```
   Example:
   ```bash
   python deploy_gotestwaf.py --urls waf_urls.txt --deploy-type docker --parallel 20
   ```
3. **For Docker/Podman with Compose**:
   ```bash
   docker-compose up --scale gotestwaf=20 -d
   ```
4. **View Reports**: Check the `reports/` directory for JSON, HTML, CSV, XLSX, YAML, and ZIP files.

## Configuration
Edit `deploy_config.yaml` to set defaults:
- `output_dir`: Report directory
- `parallel`: Number of parallel tasks
- `batch_size`: URLs per batch
- `retries`: Retry attempts for failed scans
- `report_fields`: Fields to include in CSV/XLSX reports

## Troubleshooting
- **No reports generated**: Check `deploy_gotestwaf.log` for errors.
- **Out of memory**: Reduce `parallel` or `batch_size` in `deploy_config.yaml`.
- **Image build fails**: Ensure `Dockerfile` is correct and dependencies are installed.
- **Kubernetes errors**: Verify `kubectl` is configured and the cluster is accessible.

## Notes
- All files must be in the same directory.
- Logs are saved to `deploy_gotestwaf.log`.
- Reports are timestamped and compressed into a ZIP file.
- Use `--dry-run` to validate setup without execution.