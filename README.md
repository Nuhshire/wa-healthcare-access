# Washington Healthcare Access Analysis

Which Washington counties have the highest uninsured rates, and do counties with a
federal "medically underserved" designation have worse health outcomes?

## Data
- **CDC PLACES** county-level health estimates (long format, one row per county x measure)
- **HRSA MUA/P** Medically Underserved Area / Population designations

Both are downloaded automatically by `etl.py` into `data/raw/` (not committed).

## Pipeline (`etl.py`)
1. Download both sources.
2. Reshape PLACES from long to wide (one row per county).
3. Reduce HRSA to one flag per county, reconciling duplicate and many-to-one
   records (several designations can cover the same county).
4. Join on county FIPS code across all 39 Washington counties and load into SQLite.

## Analysis (`analysis.py`)
- SQL window function (`RANK() OVER`) ranking counties by % uninsured adults.
- Grouped comparison of average health outcomes for counties with vs. without a
  federal underserved-area designation.

## Run
```
pip install -r requirements.txt
python etl.py
python analysis.py
```

## Notes
- Designation is county-level, so it does not capture designations that cover only
  part of a county. Comparisons are descriptive, not causal.
