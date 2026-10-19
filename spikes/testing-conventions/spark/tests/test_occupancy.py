"""Test of the occupancy transformation (spike s008, P2)."""

from pyspark.testing import assertDataFrameEqual

from poc.occupancy import add_occupancy


def test_add_occupancy_divides_bikes_by_capacity(spark):
    status = spark.createDataFrame(
        [("s1", 5, 20), ("s2", 0, 10)],
        ["station_id", "num_bikes_available", "capacity"],
    )
    expected = spark.createDataFrame(
        [("s1", 5, 20, 0.25), ("s2", 0, 10, 0.0)],
        ["station_id", "num_bikes_available", "capacity", "occupancy"],
    )

    assertDataFrameEqual(add_occupancy(status), expected)
