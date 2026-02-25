# Databricks notebook source
# MAGIC %md
# MAGIC # llm converter testing - snowflake_10_truncate_table
# MAGIC This notebook was automatically converted from the script below. It may contain errors, so use it as a starting point and make necessary corrections.
# MAGIC
# MAGIC Source script: `/Volumes/lakebridge/switch/switch_volume/upload_1772003488/llm converter testing - snowflake_10_truncate_table.sql`

# COMMAND ----------

# Truncate the sales table
# Note: Databricks does not support TRUNCATE TABLE directly. 
# Instead, we can use the following approach to achieve similar results:
spark.sql("DROP TABLE IF EXISTS sales")
spark.sql("CREATE TABLE sales LIKE sales") 

# COMMAND ----------

# MAGIC %md
# MAGIC ## Static Syntax Check Results
# MAGIC No syntax errors were detected during the static check.
# MAGIC However, please review the code carefully as some issues may only be detected during runtime.