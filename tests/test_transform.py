"""Unit tests for the transform module."""

from etl.transform import transform


def test_transform_returns_all_rows():
    # Should output the same number of rows it receives
    raw = [{"customer_name": "Zainab"}, {"customer_name": "Mosunmola"}]
    result = transform(raw)
    assert len(result) == 2


def test_transform_casts_numbers():
    # Socrata returns numbers as strings — transform should cast them
    raw = [{"hydro_gas_id": "12345", "amount_due": "99.50"}]
    result = transform(raw)
    assert result[0]["hydro_gas_id"] == 12345
    assert result[0]["amount_due"] == 99.50


def test_transform_handles_missing_fields():
    # An empty record should not crash, just return None for every field
    raw = [{}]
    result = transform(raw)
    assert result[0]["customer_name"] is None
    assert result[0]["hydro_gas_id"] is None
    assert result[0]["amount_due"] is None
