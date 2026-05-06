#!/usr/bin/env python3
"""
Sanity check: verify mneme-hq-prod BigQuery access and expected datasets exist.
Run before any pipeline work that touches BQ.

Usage:
    python scripts/bq_healthcheck.py
"""

import os
import sys
from pathlib import Path

REQUIRED_DATASETS = {"analytics_raw", "searchconsole", "growth_ops", "staging"}


def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def main():
    load_env()

    project = os.environ.get("MNEME_BQ_PROJECT")
    key_file = os.environ.get("MNEME_GOOGLE_APPLICATION_CREDENTIALS")

    if not project:
        print("FAIL: MNEME_BQ_PROJECT not set")
        sys.exit(1)
    if not key_file or not Path(key_file).exists():
        print(f"FAIL: key file not found: {key_file}")
        sys.exit(1)

    try:
        from google.oauth2 import service_account
        from google.cloud import bigquery
    except ImportError:
        print("FAIL: google-cloud-bigquery not installed")
        print("      pip install google-cloud-bigquery")
        sys.exit(1)

    creds = service_account.Credentials.from_service_account_file(
        key_file,
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    client = bigquery.Client(project=project, credentials=creds)

    print(f"Project : {project}")
    print(f"Key file: {key_file}")

    datasets = {ds.dataset_id for ds in client.list_datasets()}
    print(f"Datasets: {sorted(datasets)}")

    missing = REQUIRED_DATASETS - datasets
    if missing:
        print(f"FAIL: missing datasets: {missing}")
        sys.exit(1)

    result = list(client.query("SELECT 1 AS ok").result())
    if result[0].ok != 1:
        print("FAIL: test query returned unexpected result")
        sys.exit(1)

    ga4_datasets = [d for d in datasets if d.startswith("analytics_") and d != "analytics_raw"]
    if ga4_datasets:
        print(f"GA4 export dataset(s): {ga4_datasets}")
    else:
        print("GA4 export dataset: not yet created (expected within 24h of link setup)")

    print("OK: all checks passed")


if __name__ == "__main__":
    main()
