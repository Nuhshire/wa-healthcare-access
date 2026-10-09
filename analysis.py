"""Run the two SQL analyses against wa_healthcare.db (build it with etl.py first)."""
import sqlite3

import pandas as pd

RANK_SQL = """
SELECT county,
       pct_uninsured_adults,
       RANK() OVER (ORDER BY pct_uninsured_adults DESC) AS uninsured_rank
FROM county_health
ORDER BY uninsured_rank;
"""

COMPARE_SQL = """
SELECT CASE is_underserved WHEN 1 THEN 'Has MUA/P designation'
                           ELSE 'No designation' END AS group_name,
       COUNT(*)                         AS counties,
       ROUND(AVG(pct_uninsured_adults), 2)  AS avg_uninsured,
       ROUND(AVG(pct_diabetes), 2)          AS avg_diabetes,
       ROUND(AVG(pct_obesity), 2)           AS avg_obesity,
       ROUND(AVG(pct_depression), 2)        AS avg_depression
FROM county_health
GROUP BY is_underserved;
"""

if __name__ == "__main__":
    with sqlite3.connect("wa_healthcare.db") as con:
        print("Counties ranked by % uninsured adults\n")
        print(pd.read_sql(RANK_SQL, con).to_string(index=False))
        print("\nHealth outcome averages: designated vs. not\n")
        print(pd.read_sql(COMPARE_SQL, con).to_string(index=False))
