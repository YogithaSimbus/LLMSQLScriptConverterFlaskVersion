# Databricks notebook source
# MAGIC %md
# MAGIC # Analyze Input Files
# MAGIC This notebook is designed to count the tokens in files within the specified directory, aiding in understanding the size and structure of files for use with Large Language Models (LLMs). The results are saved to the target table in Delta Lake format.
# MAGIC
# MAGIC ## Task Overview
# MAGIC The following tasks are accomplished in this notebook:
# MAGIC
# MAGIC 1. **Directory Scanning**: The specified directory is scanned for files, and each file is prepared for analysis.
# MAGIC 2. **Tokenization**: Files are tokenized using the specified encoding to count the tokens effectively.
# MAGIC 3. **Result Compilation and Saving**: The token counts, along with file metadata, are compiled into a structured format. Files exceeding a predefined token threshold are filtered out. The results are saved to a Delta Lake table for further analysis or reference.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Install and import libraries

# COMMAND ----------

# DBTITLE 1,Setup Environment
# MAGIC %pip install -r ../../requirements.txt
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Add notebooks/ to Python path
import sys
import os

sys.path.append(os.path.dirname(os.getcwd()))

# COMMAND ----------

# DBTITLE 1,Import Libraries
import random
import string
from datetime import datetime, timezone

from pyspark.sql.functions import col, lit, when
from pyspark.sql.types import (
    ArrayType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
    FloatType,
    DoubleType,
)
from pyspark.sql.utils import AnalysisException

from pyscripts.helpers.llm_token_count_helper import FileTokenCountHelper
from pyscripts.types.source_format import SourceFormat
from pyscripts.types.table_config import TableConfig

# COMMAND ----------

# MAGIC %md
# MAGIC ## Set up configuration parameters

# COMMAND ----------

# DBTITLE 1,Configurations
# Parameters passed from parent orchestrators
dbutils.widgets.text("input_dir", "", "Input Directory")
dbutils.widgets.text("endpoint_name", "", "Serving Endpoint Name")
dbutils.widgets.text("result_catalog", "", "Result Catalog")
dbutils.widgets.text("result_schema", "", "Result Schema")
dbutils.widgets.text("token_count_threshold", "", "Token Count Threshold")
dbutils.widgets.text("existing_result_table", "", "Existing Result Table (Optional)")

# Notebook-specific parameters with defaults
dbutils.widgets.text("source_format", SourceFormat.SQL.value, "Source Format")
dbutils.widgets.text("result_table_prefix", TableConfig.DEFAULT_RESULT_TABLE_PREFIX, "Result Table Prefix")
dbutils.widgets.text("file_encoding", "", "File Encoding (Optional)")
dbutils.widgets.text("tokenizer_type", "", "Tokenizer Type (Optional)")
dbutils.widgets.text("tokenizer_model", "", "Tokenizer Model (Optional)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Notebook-Specific Parameters
# MAGIC This notebook accepts parameters from parent orchestrators. The table below shows only parameters that are specific to this notebook or have special behavior.
# MAGIC
# MAGIC Parameter Name | Required | Description | Default Value
# MAGIC --- | --- | --- | ---
# MAGIC `source_format` | Yes | Source file format type. If `sql`, SQL comments will be removed for preprocessing; if `generic`, original content will be used as-is for preprocessing. | `sql`
# MAGIC `result_table_prefix` | Yes | The prefix for the result table name where the results will be stored. | `lakebridge_switch`
# MAGIC `file_encoding` | No | The encoding used for reading files. If unspecified, the notebook will attempt to detect the encoding automatically. |
# MAGIC `tokenizer_type` | No | The type of tokenizer to use ('claude' or 'openai'). Only used if more specific control is needed than endpoint_name provides. |
# MAGIC `tokenizer_model` | No | The specific model to use for tokenization. Only used if tokenizer_type is also specified. |

# COMMAND ----------

# DBTITLE 1,Load Configurations
input_dir = dbutils.widgets.get("input_dir")
endpoint_name = dbutils.widgets.get("endpoint_name")
file_encoding = dbutils.widgets.get("file_encoding") if dbutils.widgets.get("file_encoding") else None
source_format = SourceFormat(dbutils.widgets.get("source_format"))
token_count_threshold = int(dbutils.widgets.get("token_count_threshold"))
result_catalog = dbutils.widgets.get("result_catalog")
result_schema = dbutils.widgets.get("result_schema")
result_table_prefix = dbutils.widgets.get("result_table_prefix")
existing_result_table = dbutils.widgets.get("existing_result_table")
tokenizer_type = dbutils.widgets.get("tokenizer_type") if dbutils.widgets.get("tokenizer_type") else None
tokenizer_model = dbutils.widgets.get("tokenizer_model") if dbutils.widgets.get("tokenizer_model") else None

input_dir, endpoint_name, file_encoding, source_format, token_count_threshold, result_catalog, result_schema, result_table_prefix, existing_result_table, tokenizer_type, tokenizer_model

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check if existing_result_table exists

# COMMAND ----------

# DBTITLE 1,Check Result Table Existance
if existing_result_table:
    try:
        spark.table(existing_result_table)
        dbutils.notebook.exit(existing_result_table)
    except AnalysisException:
        print(
            "'existing_result_table' is specified but the table does not exist. Continuing with the notebook processing."
        )
        pass
else:
    print("The parameter 'existing_result_table' is not specified. Continuing with the notebook processing.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Count tokens in all files within the specified directory

# COMMAND ----------

# DBTITLE 1,Count Tokens
# Initialize FileTokenCountHelper with the appropriate parameters
# Priority: 1. Use explicit tokenizer_type if provided
#           2. Otherwise, use endpoint_name to determine the tokenizer
if tokenizer_type:
    print(f"Using explicit tokenizer type: {tokenizer_type}")
    helper = FileTokenCountHelper(tokenizer_type=tokenizer_type, tokenizer_model=tokenizer_model)
else:
    print(f"Using endpoint name: {endpoint_name} to determine tokenizer")
    helper = FileTokenCountHelper(endpoint_name=endpoint_name)

# Print the actual tokenizer being used
print(f"Tokenizer selected: {helper.tokenizer_type} (model: {helper.tokenizer_model})")
results = helper.process_directory(input_dir=input_dir, file_encoding=file_encoding, source_format=source_format)

# COMMAND ----------

# DBTITLE 1,Create Spark DataFrame
schema = StructType(
    [
        StructField("input_file_number", IntegerType(), True),
        StructField("input_file_path", StringType(), True),
        StructField("input_file_encoding", StringType(), True),
        StructField("tokenizer_type", StringType(), True),
        StructField("tokenizer_model", StringType(), True),
        StructField("input_file_token_count", IntegerType(), True),
        StructField("input_file_token_count_preprocessed", IntegerType(), True),
        StructField("input_file_content", StringType(), True),
        StructField("input_file_content_preprocessed", StringType(), True),
        StructField("is_conversion_target", StringType(), True),
        StructField("model_serving_endpoint_for_conversion", StringType(), True),
        StructField("model_serving_endpoint_for_fix", StringType(), True),
        StructField("request_params_for_conversion", StringType(), True),
        StructField("request_params_for_fix", StringType(), True),
        StructField("result_content", StringType(), True),
        StructField("result_prompt_tokens", IntegerType(), True),
        StructField("result_completion_tokens", IntegerType(), True),
        StructField("result_total_tokens", IntegerType(), True),
        StructField("result_processing_time_seconds", FloatType(), True),
        StructField("result_timestamp", TimestampType(), True),
        StructField("result_error", StringType(), True),
        StructField("result_python_parse_error", StringType(), True),
        StructField("result_extracted_sqls", ArrayType(StringType()), True),
        StructField("result_sql_parse_errors", ArrayType(StringType()), True),
        StructField("export_output_path", StringType(), True),
        StructField("export_status", StringType(), True),
        StructField("export_error", StringType(), True),
        StructField("export_timestamp", TimestampType(), True),
        StructField("export_content_size_bytes", LongType(), True),
        StructField("accuracy_percent", DoubleType(), True),
    ]
)

result_df = (
    spark.createDataFrame(results, schema=schema)
    .withColumn(
        "is_conversion_target",
        when(col("input_file_token_count_preprocessed") > token_count_threshold, False).otherwise(True),
    )
    .withColumn("model_serving_endpoint_for_conversion", lit(None).cast(StringType()))
    .withColumn("model_serving_endpoint_for_fix", lit(None).cast(StringType()))
    .withColumn("request_params_for_conversion", lit(None).cast(StringType()))
    .withColumn("request_params_for_fix", lit(None).cast(StringType()))
    .withColumn("result_content", lit(None).cast(StringType()))
    .withColumn("result_prompt_tokens", lit(None).cast(IntegerType()))
    .withColumn("result_completion_tokens", lit(None).cast(IntegerType()))
    .withColumn("result_total_tokens", lit(None).cast(IntegerType()))
    .withColumn("result_processing_time_seconds", lit(None).cast(FloatType()))
    .withColumn("result_timestamp", lit(None).cast(TimestampType()))
    .withColumn("result_error", lit(None).cast(StringType()))
    .withColumn("result_python_parse_error", lit(None).cast(StringType()))
    .withColumn("result_extracted_sqls", lit(None).cast(ArrayType(StringType())))
    .withColumn("result_sql_parse_errors", lit(None).cast(ArrayType(StringType())))
    .withColumn("export_output_path", lit(None).cast(StringType()))
    .withColumn("export_status", lit(None).cast(StringType()))
    .withColumn("export_error", lit(None).cast(StringType()))
    .withColumn("export_timestamp", lit(None).cast(TimestampType()))
    .withColumn("export_content_size_bytes", lit(None).cast(LongType()))
    .withColumn("accuracy_percent", lit(None).cast(DoubleType()))
)

display(result_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Excluded files from conversion process
# MAGIC Files exceeding the `token_count_threshold` are excluded from further conversion processing. Consider splitting these files manually or adjusting the threshold as needed.

# COMMAND ----------

# DBTITLE 1,Warning for Token Count Threshold
warning_df = result_df.filter(col("is_conversion_target") == False)
if warning_df.count() > 0:
    print(
        f"Warning: The following files do not meet the token count threshold of "
        f"{token_count_threshold} and are excluded from conversion process."
    )
    display(warning_df)
else:
    print("No issues found. All files meet the token count threshold.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Save the result dataframe into a target delta table

# COMMAND ----------

# DBTITLE 1,Define Target Table
now = datetime.now(timezone.utc)
time_part = now.strftime("%Y%m%d%H%M%S")
random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
table_suffix = f"{time_part}_{random_part}"
result_table = f"{result_catalog}.{result_schema}.{result_table_prefix}_{table_suffix}"
print(result_table)

# COMMAND ----------

# DBTITLE 1,Save Result
result_df.write.format("delta").mode("overwrite").saveAsTable(result_table)
print(f"Successfully saved result into the table: {result_table}")

# COMMAND ----------

# DBTITLE 1,Display Result Table
spark.table(result_table).display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Return the result table name

# COMMAND ----------

# DBTITLE 1,Return Result Table Name
dbutils.notebook.exit(result_table)