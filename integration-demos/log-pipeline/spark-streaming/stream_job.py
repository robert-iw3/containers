import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import approx_count_distinct, avg, col, count, expr, from_json, sum as spark_sum, window
from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType, TimestampType

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:19092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "app-logs")
ES_NODES = os.environ.get("ES_NODES", "elasticsearch")
ES_PORT = os.environ.get("ES_PORT", "9200")
RAW_INDEX = os.environ.get("ES_RAW_INDEX", "logs-raw")
METRICS_INDEX = os.environ.get("ES_METRICS_INDEX", "logs-metrics-1m")
CHECKPOINT_ROOT = os.environ.get("CHECKPOINT_ROOT", "/tmp/checkpoints")

LOG_SCHEMA = StructType(
    [
        StructField("timestamp", TimestampType(), True),
        StructField("trace_id", StringType(), True),
        StructField("service", StringType(), True),
        StructField("host", StringType(), True),
        StructField("level", StringType(), True),
        StructField("message", StringType(), True),
        StructField("status_code", IntegerType(), True),
        StructField("duration_ms", DoubleType(), True),
    ]
)


def es_options(resource):
    return {
        "es.nodes": ES_NODES,
        "es.port": ES_PORT,
        "es.resource": resource,
        "es.nodes.wan.only": "true",
        "es.index.auto.create": "true",
    }


def main():
    spark = (
        SparkSession.builder.appName("log-pipeline-stream")
        .config("spark.sql.shuffle.partitions", "6")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    events = raw.select(
        from_json(col("value").cast("string"), LOG_SCHEMA).alias("data")
    ).select("data.*")

    events_with_watermark = events.withWatermark("timestamp", "2 minutes")

    (
        events_with_watermark.writeStream.format("org.elasticsearch.spark.sql")
        .option("checkpointLocation", f"{CHECKPOINT_ROOT}/raw")
        .options(**es_options(f"{RAW_INDEX}/_doc"))
        .outputMode("append")
        .start()
    )

    metrics = (
        events_with_watermark.groupBy(
            window(col("timestamp"), "1 minute"), col("service"), col("level")
        )
        .agg(
            count("*").alias("event_count"),
            avg("duration_ms").alias("avg_duration_ms"),
            spark_sum(expr("case when status_code >= 500 then 1 else 0 end")).alias(
                "error_count"
            ),
            approx_count_distinct("host").alias("distinct_hosts"),
        )
        .select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("service"),
            col("level"),
            col("event_count"),
            col("avg_duration_ms"),
            col("error_count"),
            col("distinct_hosts"),
        )
    )

    (
        metrics.writeStream.format("org.elasticsearch.spark.sql")
        .option("checkpointLocation", f"{CHECKPOINT_ROOT}/metrics")
        .options(**es_options(f"{METRICS_INDEX}/_doc"))
        .outputMode("append")
        .start()
    )

    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
