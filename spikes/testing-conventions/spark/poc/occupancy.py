"""Spark PoC transformation (spike s008, P2).

Input: DataFrame of station status with `num_bikes_available` and `capacity`.
Output: the same rows plus `occupancy` = num_bikes_available / capacity.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def add_occupancy(df: DataFrame) -> DataFrame:
    return df.withColumn("occupancy", F.col("num_bikes_available") / F.col("capacity"))
