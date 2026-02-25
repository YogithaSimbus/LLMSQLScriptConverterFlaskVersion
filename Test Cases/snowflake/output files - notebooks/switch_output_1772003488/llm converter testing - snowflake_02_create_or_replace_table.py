# Databricks notebook source
# MAGIC %md
# MAGIC # llm converter testing - snowflake_02_create_or_replace_table
# MAGIC This notebook was automatically converted from the script below. It may contain errors, so use it as a starting point and make necessary corrections.
# MAGIC
# MAGIC Source script: `/Volumes/lakebridge/switch/switch_volume/upload_1772003488/llm converter testing - snowflake_02_create_or_replace_table.sql`

# COMMAND ----------

# Create a Delta table equivalent
spark.sql("""
CREATE OR REPLACE TABLE customers (
    customer_id INT,
    customer_name STRING,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Static Syntax Check Results
# MAGIC No syntax errors were detected during the static check.
# MAGIC However, please review the code carefully as some issues may only be detected during runtime.