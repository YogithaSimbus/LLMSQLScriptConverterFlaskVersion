# Databricks notebook source
# MAGIC %md
# MAGIC # Orchestrate File Conversion
# MAGIC This notebook orchestrates the conversion flow from input files to generic output files.
# MAGIC It handles conversion to various file formats (YAML, JSON, XML, etc.) without notebook-specific processing.

# COMMAND ----------

# DBTITLE 1,Get Parameters
# Parameters passed from main orchestrator
input_dir = dbutils.widgets.get("input_dir")
endpoint_name = dbutils.widgets.get("endpoint_name")
result_catalog = dbutils.widgets.get("result_catalog")
result_schema = dbutils.widgets.get("result_schema")
token_count_threshold = int(dbutils.widgets.get("token_count_threshold"))
source_format = dbutils.widgets.get("source_format")
conversion_prompt_yaml = dbutils.widgets.get("conversion_prompt_yaml")
comment_lang = dbutils.widgets.get("comment_lang")
concurrency = int(dbutils.widgets.get("concurrency"))
request_params = dbutils.widgets.get("request_params")
log_level = dbutils.widgets.get("log_level")
output_dir = dbutils.widgets.get("output_dir")
output_extension = dbutils.widgets.get("output_extension")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Analyze Input Files
# MAGIC Analyzes the input files, calculates token counts, and saves the results to a Delta table.

# COMMAND ----------

# DBTITLE 1,Analyze Input Files
result_table = dbutils.notebook.run(
    "../processors/analyze_input_files",
    0,
    {
        "input_dir": input_dir,
        "endpoint_name": endpoint_name,
        "result_catalog": result_catalog,
        "result_schema": result_schema,
        "token_count_threshold": token_count_threshold,
        "source_format": source_format,
    },
)
print(f"Conversion result table: {result_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Files Selected for Conversion
# MAGIC Files within token threshold: Will be converted to target format.

# COMMAND ----------

# DBTITLE 1,Files Selected for Conversion
spark.sql(
    f"""
    SELECT 
        input_file_number,
        input_file_path,
        input_file_token_count_preprocessed
    FROM {result_table}
    WHERE is_conversion_target = true
    ORDER BY input_file_number
"""
).display()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Files Exceeding Token Threshold
# MAGIC Files exceeding threshold: Need manual review. (Consider splitting into smaller files)

# COMMAND ----------

# DBTITLE 1,Files Exceeding Token Threshold
spark.sql(
    f"""
    SELECT 
        input_file_number,
        input_file_path,
        input_file_token_count_preprocessed
    FROM {result_table}
    WHERE is_conversion_target = false
    ORDER BY input_file_number
"""
).display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Convert with LLM
# MAGIC Converts the files using an LLM and updates the result table.

# COMMAND ----------

# DBTITLE 1,Convert with LLM
dbutils.notebook.run(
    "../processors/convert_with_llm",
    0,
    {
        "endpoint_name": endpoint_name,
        "result_table": result_table,
        "conversion_prompt_yaml": conversion_prompt_yaml,
        "comment_lang": comment_lang,
        "concurrency": concurrency,
        "request_params": request_params,
        "log_level": log_level,
    },
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Successfully Converted Files
# MAGIC The following table shows files that have been successfully converted.

# COMMAND ----------

# DBTITLE 1,Successfully Converted Files
spark.sql(
    f"""
    SELECT 
        input_file_number,
        input_file_path,
        result_content,
        input_file_token_count_preprocessed,
        result_prompt_tokens,
        result_completion_tokens,
        result_total_tokens,
        result_timestamp
    FROM {result_table}
    WHERE result_content IS NOT NULL
    ORDER BY input_file_number
"""
).display()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Files with Conversion Errors
# MAGIC The following table shows files that have conversion errors.

# COMMAND ----------

# DBTITLE 1,Files with Conversion Errors
spark.sql(
    f"""
    SELECT 
        input_file_number,
        input_file_path,
        result_error,
        result_timestamp
    FROM {result_table}
    WHERE result_error IS NOT NULL
    ORDER BY input_file_number
"""
).display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Export to Files
# MAGIC Exports the converted content to files with specified format.
# MAGIC Note: Skipping syntax checking and cell splitting for generic file conversion.

# COMMAND ----------

# DBTITLE 1,Export to Files
dbutils.notebook.run(
    "../exporters/export_to_file",
    0,
    {"result_table": result_table, "output_dir": output_dir, "output_extension": output_extension},
)

# COMMAND ----------

# Return result table for use by calling notebook
dbutils.notebook.exit(result_table)