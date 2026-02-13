"""Clean and type-cast raw Socrata records for PostgreSQL."""


# Safely convert a value to float, return None if it can't be parsed
def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# Safely convert a value to int, return None if it can't be parsed
def _safe_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


# All 35 columns grouped by type for clarity
TEXT_FIELDS = [
    "customer_name", "ssc_number", "customer_information",
    "service_address", "town", "meter_number",
    "actual_service_type", "rate", "read_code",
]

INT_FIELDS = [
    "hydro_gas_id", "account_number", "days_of_service",
]

FLOAT_FIELDS = [
    "current_reading", "billing_units", "basic_charge",
    "primary_other", "supplemental", "transportation",
    "distribution", "frp_refund", "city_tax",
    "gst_on_city_tax", "carbon_charge", "pst",
    "gst", "adjustment", "amount_due",
    "demand_billing", "billed_kva", "measured_demand",
    "high_demand", "contract_demand", "multiplier",
]

TIMESTAMP_FIELDS = [
    "service_from_date", "service_to_date",
]


def transform(records: list[dict]) -> list[dict]:
    cleaned = []

    for rec in records:
        row = {}

        # Keep text fields as-is (already strings from the API)
        for field in TEXT_FIELDS:
            row[field] = rec.get(field)

        # Cast integer fields
        for field in INT_FIELDS:
            row[field] = _safe_int(rec.get(field))

        # Cast numeric/money fields to float
        for field in FLOAT_FIELDS:
            row[field] = _safe_float(rec.get(field))

        # Pass timestamp strings through — PostgreSQL handles ISO format
        for field in TIMESTAMP_FIELDS:
            row[field] = rec.get(field)

        cleaned.append(row)

    return cleaned
