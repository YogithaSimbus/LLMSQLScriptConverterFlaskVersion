# Databricks notebook source
# MAGIC %md
# MAGIC # llm converter testing - snowflake_05_create_external_table
# MAGIC This notebook was automatically converted from the script below. It may contain errors, so use it as a starting point and make necessary corrections.
# MAGIC
# MAGIC Source script: `/Volumes/lakebridge/switch/switch_volume/upload_1772003488/llm converter testing - snowflake_05_create_external_table.sql`

# COMMAND ----------

# Create an external table in Databricks
spark.sql("""
CREATE TABLE IF NOT EXISTS ext_events (
    event_id INT,
    event_type STRING
)
USING CSV
OPTIONS (header "false", inferSchema "false")
LOCATION '/mnt/my_stage/events/'
""")

# COMMAND ----------

# Note: 
# - The `@` symbol in Snowflake's external table location is used to reference a named internal stage.
# - In Databricks, we use the `mnt` path to reference a mounted storage location.
# - Make sure to replace `/mnt/my_stage/events/` with the actual path to your mounted storage location.

# Alternatively, if you want to use the `spark.read` API to create a DataFrame
df = spark.read.format("csv") \
    .option("header", "false") \
    .option("inferSchema", "false") \
    .load("/mnt/my_stage/events/")

# COMMAND ----------

# Create a temporary view from the DataFrame
df.createOrReplaceTempView("ext_events")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Static Syntax Check Results
# MAGIC No syntax errors were detected during the static check.
# MAGIC However, please review the code carefully as some issues may only be detected during runtime.