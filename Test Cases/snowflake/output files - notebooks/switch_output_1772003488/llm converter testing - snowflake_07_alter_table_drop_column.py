# Databricks notebook source
# MAGIC %md
# MAGIC # llm converter testing - snowflake_07_alter_table_drop_column
# MAGIC This notebook was automatically converted from the script below. It may contain errors, so use it as a starting point and make necessary corrections.
# MAGIC
# MAGIC Source script: `/Volumes/lakebridge/switch/switch_volume/upload_1772003488/llm converter testing - snowflake_07_alter_table_drop_column.sql`

# COMMAND ----------

# Drop a column from a Delta table
spark.sql("""
ALTER TABLE sales
DROP COLUMN discount
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Static Syntax Check Results
# MAGIC No syntax errors were detected during the static check.
# MAGIC However, please review the code carefully as some issues may only be detected during runtime.