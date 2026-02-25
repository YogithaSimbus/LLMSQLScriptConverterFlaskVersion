# Databricks notebook source
# MAGIC %md
# MAGIC # Orchestrate Notebook Conversion
# MAGIC This notebook orchestrates the complete conversion flow from input files to Databricks notebooks.
# MAGIC It handles the sequential execution of all processing steps required for notebook generation.

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
max_fix_attempts = int(dbutils.widgets.get("max_fix_attempts"))
output_dir = dbutils.widgets.get("output_dir")
sql_output_dir = dbutils.widgets.get("sql_output_dir")

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
# MAGIC Files within token threshold: Will be converted to Databricks notebooks.

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
# MAGIC Converts the code to Databricks format using an LLM and updates the result table.

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
# MAGIC The following table shows files that have been successfully converted to Databricks notebooks.

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
# MAGIC ## 3. Syntax Check and Fix
# MAGIC Performs static syntax checks on Python functions and the Spark SQL contained within them, and attempts to fix any errors found.

# COMMAND ----------

# DBTITLE 1,Function for Syntax Error File Count

def get_error_file_count(result_table: str) -> int:
    """Get the count of files with syntax errors."""
    error_count = spark.sql(
        f"""
        SELECT COUNT(*) as error_count
        FROM {result_table}
        WHERE result_python_parse_error IS NOT NULL
        OR (result_sql_parse_errors IS NOT NULL AND size(result_sql_parse_errors) > 0)
    """
    ).collect()[0]['error_count']
    return error_count


# COMMAND ----------

# DBTITLE 1,Check and Fix Syntax Errors
error_count = 0

for attempt in range(max_fix_attempts):
    # Run static syntax check
    print(f"Attempt {attempt + 1} of {max_fix_attempts}")
    dbutils.notebook.run(
        "../processors/validate_python_notebook",
        0,
        {
            "result_table": result_table,
        },
    )

    # Check if there are any errors
    error_count = get_error_file_count(result_table)

    if error_count == 0:
        print("No syntax errors found. Exiting fix loop.")
        break

    # Run fix syntax error
    print(f"Found {error_count} files with syntax errors. Attempting to fix...")
    dbutils.notebook.run(
        "../processors/fix_syntax_with_llm",
        0,
        {
            "endpoint_name": endpoint_name,
            "result_table": result_table,
            "concurrency": concurrency,
            "request_params": request_params,
            "log_level": log_level,
        },
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ### Final Syntax Check
# MAGIC Performs a final static syntax check after all fix attempts.

# COMMAND ----------

# DBTITLE 1,Run Final Syntax Check
# Only run final syntax check if fix loop didn't already achieve zero errors
if error_count > 0:
    print("Running final syntax check...")
    dbutils.notebook.run(
        "../processors/validate_python_notebook",
        0,
        {
            "result_table": result_table,
        },
    )
    error_count = get_error_file_count(result_table)
    print(f"Found {error_count} files with syntax errors.")
else:
    print("Skipping final syntax check - fix loop already achieved zero errors.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Syntax Check Results
# MAGIC The following table shows the syntax check results for all files, including both successful and failed checks.

# COMMAND ----------

# DBTITLE 1,Syntax Check Status
spark.sql(
    f"""
    SELECT 
        input_file_number,
        input_file_path,
        result_content,
        CASE 
            WHEN result_python_parse_error IS NULL 
                AND (result_sql_parse_errors IS NULL OR size(result_sql_parse_errors) = 0)
            THEN 'No errors'
            ELSE 'Has errors'
        END as check_status,
        result_python_parse_error,
        result_sql_parse_errors
    FROM {result_table}
    ORDER BY input_file_number
"""
).display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Split Cells
# MAGIC Splits the converted Python code into multiple cells based on logical structure and control flow.

# COMMAND ----------

# DBTITLE 1,Split Cells
dbutils.notebook.run(
    "../processors/split_code_into_cells",
    0,
    {
        "result_table": result_table,
        "log_level": log_level,
    },
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Export to Databricks Notebooks
# MAGIC Exports the converted code to Databricks notebooks.

# COMMAND ----------

# DBTITLE 1,Export to Databricks Notebooks
dbutils.notebook.run(
    "../exporters/export_to_notebook",
    0,
    {"result_table": result_table, "output_dir": output_dir, "comment_lang": comment_lang},
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Convert to SQL Notebooks (Experimental)
# MAGIC Optionally converts Python notebooks to SQL notebooks if SQL output directory is specified.

# COMMAND ----------

# DBTITLE 1,Convert to SQL Notebooks (if requested)
sql_conversion_results = None
if sql_output_dir:
    print("Converting Python notebooks to SQL notebooks...")
    sql_conversion_results = dbutils.notebook.run(
        "../exporters/convert_notebook_to_sql",
        0,
        {
            "python_input_dir": output_dir,
            "sql_output_dir": sql_output_dir,
            "endpoint_name": endpoint_name,
            "concurrency": concurrency,
            "request_params": request_params,
            "comment_lang": comment_lang,
            "log_level": log_level,
        },
    )
    print("SQL notebook conversion completed.")
else:
    print("SQL notebook conversion skipped (sql_output_dir not specified).")

# COMMAND ----------

# DBTITLE 1,Return Results
# Return both result table and SQL conversion results for use by calling notebook
import json

orchestrator_results = {"result_table": result_table, "sql_conversion_results": sql_conversion_results}
dbutils.notebook.exit(json.dumps(orchestrator_results))