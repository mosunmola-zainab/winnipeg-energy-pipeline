"""Pull records from the Winnipeg Open Data Socrata API."""

import os
from sodapy import Socrata


def extract(limit: int = 500000) -> list[dict]:
    # Read connection details from environment
    domain = os.environ["SOCRATA_DOMAIN"]
    dataset_id = os.environ["SOCRATA_DATASET_ID"]
    app_token = os.environ.get("SOCRATA_APP_TOKEN")  # optional, raises rate limit

    # Connect and fetch rows
    client = Socrata(domain, app_token)
    try:
        results = client.get(dataset_id, limit=limit)
    finally:
        client.close()

    return results
