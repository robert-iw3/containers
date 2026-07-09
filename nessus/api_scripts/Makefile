.DEFAULT_GOAL := zip
.PHONY = clean

target_dir:
    mkdir -p target

copy_src: target_dir
    cp pipeline.py scan.toml nessus_config.toml standard_scan_template.json test_pipeline.py target

add_deps: target_dir
    pip install --upgrade pytenable requests boto3 toml validators tenacity python-jira pysnow pytest pytest-mock -t target

clean:
    rm -rf target *.egg-info .tox venv *.zip .pytest_cache htmlcov **/__pycache__

zip: add_deps copy_src
    cd target; zip -X -9 ../pipeline.zip -r .