# Winnipeg Utility Billing — Raw Grain Profiling Report

Snapshot pulled from Socrata (`49ge-5j9g`), cached at `analysis\data\raw_billing_snapshot.parquet`.
No transformation, casting, or deduplication was applied before profiling.

## 1. Total row count
- **Total rows: 464597**

## 2. `hydro_gas_id`
- Null count: 0
- Distinct (non-null) values: 464597
- Non-null row count: 464597
- Unique among non-null values: True
- **Globally unique key (unique + no nulls): True**

## 3. Duplicate-group counts for candidate keys

| Key | Total groups | Duplicate groups (size>1) | Rows in duplicate groups | Max group size |
|---|---|---|---|---|
| K1: account+meter+type+service_period | 354718 | 53718 | 163597 | 992 |
| K2: K1 + service_address | 354769 | 53760 | 163588 | 992 |
| K3: K2 + rate | 382257 | 26752 | 109092 | 992 |
| K4: K3 + billing_units | 404905 | 4350 | 64042 | 992 |
| K5: K4 + amount_due | 420921 | 4600 | 48276 | 744 |

## 4. Example duplicate groups (base key: account+meter+type+service_period)

### Group 1 — 6 rows
Key: `{'account_number': '79058146358503', 'meter_number': None, 'actual_service_type': 'OT', 'service_from_date': None, 'service_to_date': None}`
Columns that differ within this group: `['hydro_gas_id', 'primary_other', 'gst', 'amount_due']`

| hydro_gas_id | primary_other | gst | amount_due |
|---|---|---|---|
| 25711613 | 35 | 2.1 | 160.01 |
| 47983096 | 45 | 2.25 | 42.42 |
| 52928831 | 50 | 2.5 | 120.53 |
| 63456685 | 50 | 2.5 | -13.4 |
| 72088313 | 50 | 2.5 | 98.73 |
| 73113211 | 50 | 2.5 | 88.38 |

### Group 2 — 6 rows
Key: `{'account_number': '79856676456829', 'meter_number': None, 'actual_service_type': 'OT', 'service_from_date': None, 'service_to_date': None}`
Columns that differ within this group: `['hydro_gas_id', 'primary_other', 'city_tax', 'gst_on_city_tax', 'pst', 'gst', 'amount_due']`

| hydro_gas_id | primary_other | city_tax | gst_on_city_tax | pst | gst | amount_due |
|---|---|---|---|---|---|---|
| 23009107 | 0 | -1616.41 | -80.82 | 0 | 0 | 230.33 |
| 273924996 | 2791.69 | 0 | 0 | 195.42 | 139.58 | 3126.69 |
| 276152121 | 2791.69 | 0 | 0 | 195.42 | 139.58 | 3126.69 |
| 278185405 | 2791.69 | 0 | 0 | 195.42 | 139.58 | 3126.69 |
| 278185406 | 2791.69 | 0 | 0 | 195.42 | 139.58 | 3126.69 |
| 275283177 | 2791.69 | 0 | 0 | 195.42 | 139.58 | 3126.69 |

### Group 3 — 6 rows
Key: `{'account_number': '79113426359275', 'meter_number': None, 'actual_service_type': 'EL', 'service_from_date': '2006-01-31T00:00:00.000', 'service_to_date': '2006-02-28T00:00:00.000'}`
Columns that differ within this group: `['hydro_gas_id', 'billing_units', 'basic_charge', 'primary_other', 'pst', 'gst', 'amount_due']`

| hydro_gas_id | billing_units | basic_charge | primary_other | pst | gst | amount_due |
|---|---|---|---|---|---|---|
| 19854587 | 1 | 15.86 | 8.77 | 1.72 | 1.72 | 0 |
| 19854588 | 8 | 126.88 | 105.19 | 16.24 | 16.24 | 0 |
| 19854589 | 1 | 15.86 | 21.91 | 2.64 | 2.64 | 0 |
| 19854590 | 6 | 95.16 | 157.79 | 17.71 | 17.71 | 0 |
| 19854591 | 1 | 15.86 | 35.06 | 3.56 | 3.56 | 0 |
| 19854592 | 1 | 15.86 | 55.84 | 5.02 | 5.02 | 763.82 |

### Group 4 — 6 rows
Key: `{'account_number': '78734306356684', 'meter_number': None, 'actual_service_type': 'EL', 'service_from_date': '2015-12-31T00:00:00.000', 'service_to_date': '2016-01-31T00:00:00.000'}`
Columns that differ within this group: `['hydro_gas_id', 'rate', 'days_of_service', 'billing_units', 'basic_charge', 'primary_other', 'pst', 'gst', 'amount_due']`

| hydro_gas_id | rate | days_of_service | billing_units | basic_charge | primary_other | pst | gst | amount_due |
|---|---|---|---|---|---|---|---|---|
| 125014026 | KS01 | 0 | 1 | 20.51 | 14.1 | 2.77 | 1.74 | 0 |
| 125014027 | KS01 | 0 | 1 | 20.51 | 14.1 | 2.77 | 1.74 | 0 |
| 125014028 | None | 31 | 0 | 0 | 6377.24 | 175.62 | 318.87 | 0 |
| 125014029 | None | 31 | 0 | 0 | 51704.74 | 1096.49 | 2585.24 | 0 |
| 125014030 | None | 31 | 0 | 0 | 20211.08 | 884.22 | 1010.55 | 0 |
| 125014031 | None | 31 | 0 | 0 | 113.43 | 2.15 | 5.68 | 84563.55 |

### Group 5 — 6 rows
Key: `{'account_number': '86725396772529', 'meter_number': None, 'actual_service_type': 'OT', 'service_from_date': None, 'service_to_date': None}`
Columns that differ within this group: `['hydro_gas_id', 'primary_other', 'pst', 'gst', 'amount_due']`

| hydro_gas_id | primary_other | pst | gst | amount_due |
|---|---|---|---|---|
| 181833083 | -58.5 | -5.85 | -2.93 | 365.27 |
| 187767131 | -78.31 | -6.87 | -3.91 | 356.44 |
| 240547846 | -238.15 | -21.57 | -11.91 | 117.7 |
| 242666791 | -60.53 | -7.7 | -3.03 | 318.16 |
| 247382254 | -118.8 | -10.01 | -5.94 | 252.89 |
| 276335819 | -43.04 | -4.81 | -2.15 | 307.5 |

### Group 6 — 6 rows
Key: `{'account_number': '79113426359275', 'meter_number': None, 'actual_service_type': 'EL', 'service_from_date': '2005-12-30T00:00:00.000', 'service_to_date': '2006-01-31T00:00:00.000'}`
Columns that differ within this group: `['hydro_gas_id', 'billing_units', 'basic_charge', 'primary_other', 'pst', 'gst', 'amount_due']`

| hydro_gas_id | billing_units | basic_charge | primary_other | pst | gst | amount_due |
|---|---|---|---|---|---|---|
| 19851564 | 1 | 15.86 | 8.77 | 1.72 | 1.72 | 0 |
| 19851565 | 8 | 126.88 | 105.19 | 16.24 | 16.24 | 0 |
| 19851566 | 1 | 15.86 | 21.91 | 2.64 | 2.64 | 0 |
| 19851567 | 6 | 95.16 | 157.79 | 17.71 | 17.71 | 0 |
| 19851568 | 1 | 15.86 | 35.06 | 3.56 | 3.56 | 0 |
| 19851569 | 1 | 15.86 | 55.84 | 5.02 | 5.02 | 763.82 |

### Group 7 — 6 rows
Key: `{'account_number': '79112736400517', 'meter_number': None, 'actual_service_type': 'OT', 'service_from_date': None, 'service_to_date': None}`
Columns that differ within this group: `['hydro_gas_id']`

| hydro_gas_id |
|---|
| 273927112 |
| 278332084 |
| 273927316 |
| 276339565 |
| 277282499 |
| 277073034 |

### Group 8 — 6 rows
Key: `{'account_number': '78734306356684', 'meter_number': None, 'actual_service_type': 'EL', 'service_from_date': '2016-01-31T00:00:00.000', 'service_to_date': '2016-02-29T00:00:00.000'}`
Columns that differ within this group: `['hydro_gas_id', 'rate', 'days_of_service', 'billing_units', 'basic_charge', 'primary_other', 'pst', 'gst', 'amount_due']`

| hydro_gas_id | rate | days_of_service | billing_units | basic_charge | primary_other | pst | gst | amount_due |
|---|---|---|---|---|---|---|---|---|
| 126275776 | KS01 | 0 | 1 | 20.51 | 14.1 | 2.77 | 1.74 | 0 |
| 126275777 | KS01 | 0 | 1 | 20.51 | 14.1 | 2.77 | 1.74 | 0 |
| 126275778 | None | 29 | 0 | 0 | 6377.24 | 175.62 | 318.87 | 0 |
| 126275779 | None | 29 | 0 | 0 | 51704.74 | 1096.49 | 2585.24 | 0 |
| 126275780 | None | 29 | 0 | 0 | 20211.08 | 884.22 | 1010.55 | 0 |
| 126275781 | None | 29 | 0 | 0 | 113.43 | 2.15 | 5.68 | 84563.55 |

(Full 35-column rows for all example groups saved to `analysis\data\duplicate_group_examples.csv`.)

## 5. Are repeated records exact duplicates except for `hydro_gas_id`?
- Groups identical on all other 34 columns (differ at most by hydro_gas_id): 3970
- Rows involved in those groups: 40556
- Of those, groups where every row has a distinct hydro_gas_id (true exact-duplicate-except-id): 3970

## 6. How many `hydro_gas_id` values map to the same account/meter/type/service period?

| Distinct hydro_gas_id per (account, meter, type, service_period) group | Number of groups |
|---|---|
| 1 | 301000 |
| 2 | 51238 |
| 3 | 2037 |
| 4 | 143 |
| 5 | 120 |
| 6 | 8 |
| 7 | 7 |
| 8 | 3 |
| 10 | 1 |
| 12 | 3 |
| 13 | 3 |
| 14 | 4 |
| 15 | 4 |
| 16 | 6 |
| 17 | 1 |
| 20 | 1 |
| 22 | 1 |
| 28 | 1 |
| 31 | 2 |
| 37 | 1 |
| 38 | 1 |
| 44 | 2 |
| 48 | 3 |
| 52 | 1 |
| 66 | 1 |
| 72 | 2 |
| 108 | 1 |
| 122 | 1 |
| 140 | 1 |
| 141 | 1 |
| 144 | 1 |
| 146 | 1 |
| 150 | 1 |
| 154 | 1 |
| 160 | 1 |
| 187 | 1 |
| 206 | 1 |
| 215 | 1 |
| 227 | 1 |
| 228 | 1 |
| 233 | 1 |
| 244 | 1 |
| 248 | 11 |
| 249 | 1 |
| 250 | 1 |
| 252 | 1 |
| 254 | 2 |
| 259 | 1 |
| 288 | 1 |
| 296 | 1 |
| 300 | 1 |
| 312 | 1 |
| 340 | 2 |
| 341 | 1 |
| 342 | 1 |
| 374 | 7 |
| 376 | 1 |
| 400 | 1 |
| 405 | 1 |
| 440 | 1 |
| 450 | 1 |
| 456 | 1 |
| 475 | 1 |
| 478 | 1 |
| 484 | 1 |
| 492 | 9 |
| 493 | 1 |
| 494 | 1 |
| 496 | 39 |
| 497 | 4 |
| 498 | 2 |
| 586 | 1 |
| 596 | 1 |
| 652 | 1 |
| 660 | 1 |
| 738 | 1 |
| 741 | 1 |
| 828 | 1 |
| 990 | 1 |
| 992 | 3 |

## 7. Conclusion

**Source-record identity.** `hydro_gas_id` is unique and non-null across all 464597 rows (464597 distinct values, 0 nulls). It is the true row-level identity key in this raw feed -- every row is one `hydro_gas_id`, full stop. Despite its name, behaviorally it looks like a source-system surrogate/billing-line id rather than a customer or meter identifier (a real hydro/gas account or meter id would be expected to repeat across billing cycles for the same service point).

**Likely business grain.** `account_number + meter_number + actual_service_type + service_from_date + service_to_date` does NOT identify one business record -- 53718 groups (163597 rows) repeat on that key, with groups as large as 992 rows. Investigating the largest groups shows this is structural, not incidental: `actual_service_type = 'OT'` rows (non-metered flat fees/charges -- e.g. streetlights, directional signs) and a large share of `EL` rows carry a null `meter_number` and often null service dates, so many genuinely distinct billed items collapse onto the same key. Example: account `79113406359272` ('O/H DIRECTIONAL SIGNS') has 16 rows in one billing period, each a separate sign/fixture billed as its own line with its own `billing_units`/`basic_charge`, but sharing account, null meter, type, and period. The most plausible business grain is one row per billed line item (e.g. per fixture/charge component) per account per billing cycle, not one row per meter-read period. Adding `service_address`, `rate`, `billing_units`, and `amount_due` progressively narrows the duplication (K5 still has 4600 duplicate groups / 48276 rows) but never reaches uniqueness -- no combination of business columns tested fully replaces `hydro_gas_id`.

Separately, 3970 groups (40556 rows) are byte-identical across all 34 non-id columns and differ only by `hydro_gas_id` -- in every one of those groups each row still carries its own distinct id (3970 of 3970 groups). This is consistent with multiple identically-priced billed items (e.g. two signs with the same fixed monthly charge) rather than accidental re-ingestion, but that interpretation cannot be confirmed from this data alone.

**Unresolved ambiguity.**
- We cannot confirm from the data alone whether `hydro_gas_id` is a true source primary key or an artifact of how Socrata assigns row ids on publish. This needs confirmation from whoever owns the source extract on the City's side.
- It is unclear whether null `meter_number` always means "legitimately unmetered" (fixed-fee item) versus a data-capture gap for some metered services -- ~47% of `EL` rows have a null meter_number, which is a large share to attribute entirely to unmetered fixtures without source documentation.
- Duplicate groups mixing many $0 `amount_due` line items with one large non-zero `amount_due` row (seen in the 16-row example above) suggest some groups may blend item-level rows with an invoice-total row for the same period -- i.e. the grain may not be uniform across `actual_service_type` values. This should be verified against a data dictionary or source-system SME before choosing a dimensional grain, rather than assumed from pattern-matching alone.
