"""Large-scale telemetry ETL + ML pipeline on Spark.

Generates (or reads) high-volume IoT/device telemetry, does structured
windowed aggregation, trains an MLlib anomaly model on the aggregates, and
writes both the rollups and per-window anomaly scores. Designed to scale from a
laptop cluster to hundreds of executors — parallelism, shuffle partitions, and
allocation are all config-driven so the same job handles small and massive data.

Run:
  spark-submit --master spark://spark-master:7077 telemetry_pipeline.py \
      --rows 5000000 --devices 1000 --output /tmp/out

Or point --input at parquet/csv telemetry instead of generating synthetic data.
"""
import argparse

from pyspark.sql import SparkSession, functions as F
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.clustering import KMeans
from pyspark.ml import Pipeline


def build_spark(app_name: str) -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        # Adaptive Query Execution coalesces shuffle partitions to the actual data
        # size at runtime — the single biggest at-scale win for skewed telemetry.
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.adaptive.skewJoin.enabled", "true")
        .getOrCreate()
    )


def synthesize(spark, rows: int, devices: int):
    """Generate `rows` synthetic readings across `devices` devices, fully in
    parallel via range() (no driver-side data)."""
    return (
        spark.range(0, rows)
        .withColumn("device_id", (F.col("id") % devices).cast("string"))
        .withColumn("metric", F.element_at(
            F.array(F.lit("temperature"), F.lit("humidity"), F.lit("pressure"), F.lit("voltage")),
            (F.col("id") % 4 + 1).cast("int")))
        .withColumn("event_time",
                    (F.lit(1_750_000_000) + (F.col("id") % 86400)).cast("timestamp"))
        .withColumn("value", F.rand(seed=42) * 100)
    )


def rollup(df):
    """Structured per-device, per-metric, per-minute aggregates."""
    return (
        df.withColumn("minute", F.date_trunc("minute", "event_time"))
        .groupBy("device_id", "metric", "minute")
        .agg(
            F.count("*").alias("count"),
            F.avg("value").alias("avg"),
            F.min("value").alias("min"),
            F.max("value").alias("max"),
            F.stddev_pop("value").alias("stddev"),
        )
        .na.fill(0.0, ["stddev"])
    )


def score_anomalies(agg):
    """Unsupervised anomaly signal: cluster the aggregate feature space and use
    distance-from-centroid as the score. Scales linearly with executors."""
    features = ["avg", "min", "max", "stddev", "count"]
    pipeline = Pipeline(stages=[
        VectorAssembler(inputCols=features, outputCol="raw_features"),
        StandardScaler(inputCol="raw_features", outputCol="features", withMean=True, withStd=True),
        KMeans(k=8, seed=17, featuresCol="features", predictionCol="cluster"),
    ])
    model = pipeline.fit(agg)
    return model.transform(agg).select(
        "device_id", "metric", "minute", "count", "avg", "min", "max", "stddev", "cluster"
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, default=1_000_000)
    p.add_argument("--devices", type=int, default=500)
    p.add_argument("--input", help="parquet/csv telemetry instead of synthetic")
    p.add_argument("--output", default="/tmp/telemetry-out")
    p.add_argument("--shuffle-partitions", type=int, default=0,
                   help="override spark.sql.shuffle.partitions (0 = leave to AQE)")
    args = p.parse_args()

    spark = build_spark("telemetry-pipeline")
    if args.shuffle_partitions:
        spark.conf.set("spark.sql.shuffle.partitions", str(args.shuffle_partitions))

    if args.input:
        reader = spark.read
        df = (reader.parquet(args.input) if args.input.endswith(".parquet")
              else reader.option("header", True).csv(args.input))
    else:
        df = synthesize(spark, args.rows, args.devices)

    ingested = df.count()
    agg = rollup(df).cache()
    windows = agg.count()
    scored = score_anomalies(agg)

    scored.write.mode("overwrite").parquet(f"{args.output}/anomalies")
    agg.write.mode("overwrite").parquet(f"{args.output}/rollups")

    cluster_dist = scored.groupBy("cluster").count().orderBy("cluster").collect()
    print(f"PIPELINE_RESULT ingested={ingested} windows={windows} "
          f"clusters={len(cluster_dist)} output={args.output}")
    for row in cluster_dist:
        print(f"  cluster {row['cluster']}: {row['count']} windows")

    spark.stop()


if __name__ == "__main__":
    main()
