# Databricks notebook source
# MAGIC %md
# MAGIC # llm converter testing - snowflake_11_rename_table
# MAGIC This notebook was automatically converted from the script below. It may contain errors, so use it as a starting point and make necessary corrections.
# MAGIC
# MAGIC Source script: `/Volumes/lakebridge/switch/switch_volume/upload_1772003488/llm converter testing - snowflake_11_rename_table.sql`

# COMMAND ----------

# Rename the table
spark.sql("""
ALTER TABLE sales RENAME TO sales_archive
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Static Syntax Check Results
# MAGIC No syntax errors were detected during the static check.
# MAGIC However, please review the code carefully as some issues may only be detected during runtime.