"""Main entrypoint — runs the full extract-transform-load sequence."""

from dotenv import load_dotenv

# Load .env
load_dotenv()

from etl.extract import extract
from etl.transform import transform
from etl.load import get_connection, load


def run():
    # Pull raw data from Socrata API
    raw = extract()
    print(f"Extracted {len(raw)} records")

    # Clean and type-cast the raw records
    rows = transform(raw)
    print(f"Transformed {len(rows)} rows")

    # Truncate to avoid duplicates on re-runs
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE utility_billing")
    conn.commit()
    cur.close()
    conn.close()
    print("Truncated utility_billing table")

    # Insert into PostgreSQL
    inserted = load(rows)
    print(f"Loaded {inserted} rows into database")


if __name__ == "__main__":
    run()
