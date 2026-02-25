# Databricks notebook source
# MAGIC %md
# MAGIC # Fix Syntax Errors with LLM
# MAGIC This notebook fixes syntax errors in generated code using Large Language Models (LLMs). It automatically corrects syntax errors that were identified in the previous validation step. The main objectives of this notebook are:
# MAGIC
# MAGIC 1. **Error Identification**: Retrieve code with syntax errors from the result table.
# MAGIC 2. **Error Correction**: Use a Language Model (LLM) to automatically fix the identified syntax errors.
# MAGIC 3. **Batch Processing**: Implement a batch inference system to efficiently process multiple error corrections concurrently.
# MAGIC
# MAGIC The notebook utilizes a Databricks Model Serving endpoint to access the LLM for error correction. It processes the errors in batches, allowing for efficient handling of multiple correction requests simultaneously.
# MAGIC
# MAGIC ## Task Overview
# MAGIC The following tasks are accomplished in this notebook:
# MAGIC
# MAGIC 1. **Load Error Data**: Extract code with syntax errors from the result table.
# MAGIC 2. **Process Batch Inference**: Send requests to the LLM in batches and collect the corrected code.
# MAGIC 3. **Save Corrected Results**: Store the corrected code back into the result table.
# MAGIC 4. **Clean Results**: Perform additional cleaning on the corrected code for consistency.
# MAGIC
# MAGIC This notebook plays a crucial role in automating the error correction process, significantly reducing the manual effort required to fix syntax errors in generated code.

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
import json
from typing import Optional

from pyscripts.helpers.batch_inference_helper import AsyncChatClient, BatchInferenceManager, BatchInferenceRequest

# COMMAND ----------

# MAGIC %md
# MAGIC ## Set up configuration parameters

# COMMAND ----------

# DBTITLE 1,Configurations
# Parameters passed from parent orchestrators
dbutils.widgets.text("result_table", "", "Conversion Result Table")
dbutils.widgets.text("endpoint_name", "", "Serving Endpoint Name")
dbutils.widgets.text("concurrency", "", "Concurrency Requests")
dbutils.widgets.text("log_level", "", "Logging Level")
dbutils.widgets.text("request_params", "", "Chat Request Params")

# Notebook-specific parameters with defaults
dbutils.widgets.text("logging_interval", "1", "Logging Interval")
dbutils.widgets.text("timeout", "300", "Timeout Seconds")
dbutils.widgets.text("max_retries_backpressure", "10", "Max Retries on Backpressure")
dbutils.widgets.text("max_retries_other", "3", "Max Retries on Other Errors")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Notebook-Specific Parameters
# MAGIC This notebook accepts parameters from parent orchestrators. The table below shows only parameters that are specific to this notebook or have special behavior.
# MAGIC
# MAGIC Parameter Name | Required | Description | Default Value
# MAGIC --- | --- | --- | ---
# MAGIC `logging_interval` | Yes | The number of requests processed before logging a progress update. Controls the frequency of progress reports during batch processing. | `1`
# MAGIC `timeout` | Yes | The timeout for an HTTP request on the client side, in seconds. | `300`
# MAGIC `max_retries_backpressure` | Yes | The maximum number of retries on backpressure status code (such as `429` or `503`). | `10`
# MAGIC `max_retries_other` | Yes | The maximum number of retries on other errors (such as `5xx`, `408`, or `409`). | `3`

# COMMAND ----------

# DBTITLE 1,Load Configurations
config_endpoint_name = dbutils.widgets.get("endpoint_name")
config_result_table = dbutils.widgets.get("result_table")
config_concurrecy = int(dbutils.widgets.get("concurrency"))
config_log_level = dbutils.widgets.get("log_level")
config_logging_interval = int(dbutils.widgets.get("logging_interval"))
config_timeout = int(dbutils.widgets.get("timeout"))
config_max_retries_backpressure = int(dbutils.widgets.get("max_retries_backpressure"))
config_max_retries_other = int(dbutils.widgets.get("max_retries_other"))

# Reference: https://docs.databricks.com/en/machine-learning/foundation-models/api-reference.html#chat-request
_request_params = dbutils.widgets.get("request_params")
config_request_params = json.loads(_request_params) if _request_params.strip() else None

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run batch inference
# MAGIC The following code loads a Spark dataframe of the input data table and then converts that dataframe into a list of text that the model can process.

# COMMAND ----------

# DBTITLE 1,Function for Creating System Message

def create_system_message(python_error: Optional[str], sql_error: Optional[str]) -> str:
    """
    Create a system message for an LLM to fix errors in Python code running in a Databricks notebook.

    Args:
        python_error (Optional[str]): The Python parsing error message, if any.
        sql_error (Optional[str]): The Spark SQL-related error message, if any.

    Returns:
        str: A formatted system message with instructions and error details.
    """
    message = """Fix the following errors in the Python code running in a Databricks notebook.
The code contains Spark SQL queries, and most errors are Spark SQL-related.

Instructions:
1. Output only Python code and comments. No other text allowed.
2. Do not add explanations outside of Python code.
3. If asked to continue, resume the code without adding extra phrases.
4. Do not omit any part of the code.
5. Ensure proper handling of Spark SQL queries in the Databricks environment.
6. Prioritize fixing Spark SQL-related errors.

Errors to fix:
"""
    if python_error:
        message += f"{python_error}\n"
    if sql_error:
        message += f"{sql_error}\n"
    return message


# COMMAND ----------

# DBTITLE 1,Extract Input Data
input_sdf = spark.sql(
    f"""
    SELECT
        input_file_number,
        result_content,
        result_python_parse_error,
        result_sql_parse_errors
    FROM {config_result_table}
    WHERE result_python_parse_error IS NOT NULL
    OR (result_sql_parse_errors IS NOT NULL AND size(result_sql_parse_errors) > 0)
"""
)
display(input_sdf)

# COMMAND ----------

# DBTITLE 1,Create Batch Inference Requests
input_data = input_sdf.collect()
batch_inference_requests = [
    BatchInferenceRequest(
        index=row['input_file_number'],
        text=row['result_content'],
        system_message=create_system_message(row['result_python_parse_error'], row['result_sql_parse_errors']),
    )
    for row in input_data
]

# COMMAND ----------

# DBTITLE 1,Display Batch Inference Requests
display_df = spark.createDataFrame(
    [(req.index, req.text, req.system_message, str(req.few_shots)) for req in batch_inference_requests],
    ["index", "text", "system_message", "few_shots"],
)

display(display_df)

# COMMAND ----------

# MAGIC %md
# MAGIC The following records and stores the batch inference responses.

# COMMAND ----------

# DBTITLE 1,Create Batch Inference Manager
batch_manager = BatchInferenceManager(
    client=AsyncChatClient(
        endpoint_name=config_endpoint_name,
        request_params=config_request_params,
        timeout=config_timeout,
        max_retries_backpressure=config_max_retries_backpressure,
        max_retries_other=config_max_retries_other,
        log_level=config_log_level,
    ),
    concurrency=config_concurrecy,
    logging_interval=config_logging_interval,
    log_level=config_log_level,
)

# COMMAND ----------

# DBTITLE 1,Batch Inference
batch_inference_responses = await batch_manager.batch_inference(batch_inference_requests)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Save results
# MAGIC The following stores the output to the result table and displays the results

# COMMAND ----------

# DBTITLE 1,Load Notebook Utils
# MAGIC %run ../notebook_utils

# COMMAND ----------

# DBTITLE 1,Organize Output
source_sdf = spark.table(config_result_table)
batch_inference_result_processor = BatchInferenceResultProcessor(
    model_serving_endpoint_for_fix=config_endpoint_name,
    request_params_for_fix=config_request_params,
)
output_sdf = batch_inference_result_processor.process_results(source_sdf, batch_inference_responses)
display(output_sdf)

# COMMAND ----------

# DBTITLE 1,Save Result
output_sdf.write.mode("overwrite").saveAsTable(config_result_table)
print(f"Successfully saved result into the table: {config_result_table}")

# COMMAND ----------

# DBTITLE 1,Display Result Table
spark.table(config_result_table).display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cleaning results
# MAGIC The following performs cleaning on `result_content`. The reason for saving the data first and then performing cleaning is to enable time travel in case there are any issues with the cleaning process.

# COMMAND ----------

# DBTITLE 1,Clean Result
cleand_df = clean_conversion_results(config_result_table)
display(cleand_df)

# COMMAND ----------

# DBTITLE 1,Save Cleaned Result
cleand_df.write.mode("overwrite").saveAsTable(config_result_table)
print(f"Successfully saved cleaned result into the table: {config_result_table}")

# COMMAND ----------

# DBTITLE 1,Display Cleaned Result Table
spark.table(config_result_table).display()