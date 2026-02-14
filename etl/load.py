"""Insert cleaned rows into the utility_billing table in PostgreSQL."""

import csv
import io
import os
import psycopg2


def get_connection():
    # Build connection from environment variables
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        sslmode="require",
    )


# All 35 columns in the same order as the table definition
COLUMNS = [
    "hydro_gas_id", "account_number", "customer_name",
    "ssc_number", "customer_information", "service_address",
    "town", "meter_number", "actual_service_type", "rate",
    "service_from_date", "service_to_date", "current_reading",
    "days_of_service", "billing_units", "read_code",
    "basic_charge", "primary_other", "supplemental",
    "transportation", "distribution", "frp_refund",
    "city_tax", "gst_on_city_tax", "carbon_charge",
    "pst", "gst", "adjustment", "amount_due",
    "demand_billing", "billed_kva", "measured_demand",
    "high_demand", "contract_demand", "multiplier",
]


def load(rows: list[dict]) -> int:
    conn = get_connection()
    cur = conn.cursor()

    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row.get(col, "") for col in COLUMNS)
    buf.seek(0)

    col_names = ", ".join(COLUMNS)
    copy_sql = f"COPY utility_billing ({col_names}) FROM STDIN WITH CSV"
    cur.copy_expert(copy_sql, buf)

    conn.commit()
    cur.close()
    conn.close()

    return len(rows)
