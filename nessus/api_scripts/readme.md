### Scan Automation via Nessus API
---

Install Dependencies:
```bash
pip install pytenable requests boto3 toml validators tenacity python-jira pysnow pytest pytest-mock
```

Run Pipeline:
```bash
python pipeline.py --phase all --config scan.toml --nessus-config nessus_config.toml --min-severity 1
```

Run Tests:
```bash
pytest test_pipeline.py -v
```
