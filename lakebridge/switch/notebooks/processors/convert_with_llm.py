# Databricks notebook source
# MAGIC %md
# MAGIC # Convert Content with LLM
# MAGIC This notebook facilitates the conversion of input files into Databricks-compatible code using Large Language Models (LLMs), allowing for seamless migration to the Databricks environment. It supports both SQL files and generic text files through configurable conversion prompts.
# MAGIC
# MAGIC This notebook is inspired by the following reference: [chat-batch-inference-api - Databricks](https://learn.microsoft.com/en-us/azure/databricks/_extras/notebooks/source/machine-learning/large-language-models/chat-batch-inference-api.html).
# MAGIC
# MAGIC ## Task Overview
# MAGIC The following tasks are accomplished in this notebook:
# MAGIC
# MAGIC 1. **Configure Conversion Prompt**: By specifying a custom YAML file in the `conversion_prompt_yaml` parameter, you can adapt the conversion process for various input formats and target outputs. Each YAML file defines the system message and few-shot examples tailored to specific conversion requirements.
# MAGIC 2. **Read Data**: Data is read from the input table and specified columns. The input table is assumed to have been created in the preceding notebook, and the `input_file_content_preprocessed` column is utilized for processing.
# MAGIC 3. **Request Construction and Submission**: Requests are constructed and sent to the specified Databricks model serving endpoint with concurrent processing.
# MAGIC 4. **Persist Results**: The results of the conversion process are added to the input table.

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

from pyscripts.helpers.batch_inference_helper import AsyncChatClient, BatchInferenceManager, BatchInferenceRequest
from pyscripts.helpers.conversion_prompt_helper import ConversionPromptHelper

# COMMAND ----------

# MAGIC %md
# MAGIC ## Set up configuration parameters
# MAGIC

# COMMAND ----------

# DBTITLE 1,Configurations
# Parameters passed from parent orchestrators
dbutils.widgets.text("result_table", "", "Conversion Result Table")
dbutils.widgets.text("endpoint_name", "", "Serving Endpoint Name")
dbutils.widgets.text("conversion_prompt_yaml", "", "YAML path for Conversion Prompt")
dbutils.widgets.text("comment_lang", "", "Comment Language")
dbutils.widgets.text("concurrency", "", "Concurrency Requests")
dbutils.widgets.text("log_level", "", "Log Level")
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
config_conversion_prompt_yaml = dbutils.widgets.get("conversion_prompt_yaml")
config_comment_lang = dbutils.widgets.get("comment_lang")
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
# MAGIC ## System message & few-shots from YAML configuration
# MAGIC The system message and few-shot examples are loaded from the YAML configuration file specified in the `conversion_prompt_yaml` parameter. By creating and specifying different YAML files, you can adapt the conversion process for various source formats and dialects (e.g., SQL dialects like T-SQL, PL/SQL, PostgreSQL, or generic text/code files) without modifying the notebook code.

# COMMAND ----------

# DBTITLE 1,Load System Message and Few-Shots
conv_prompt_helper = ConversionPromptHelper(
    yaml_path=config_conversion_prompt_yaml,
    comment_lang=config_comment_lang,
)
system_message = conv_prompt_helper.get_system_message()
few_shots = conv_prompt_helper.get_few_shots()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run batch inference
# MAGIC The following code loads a Spark dataframe of the input data table and then converts that dataframe into a list of text that the model can process.

# COMMAND ----------

# DBTITLE 1,Retrieve Pre-Update Data for Batch Inference Result Update
source_sdf = spark.table(config_result_table)
display(source_sdf)

# COMMAND ----------

# DBTITLE 1,Retrieve Data for Batch Inference
input_sdf = spark.sql(
    f"""
    SELECT input_file_number, input_file_content_preprocessed
    FROM {config_result_table}
    WHERE is_conversion_target = true
"""
)
display(input_sdf)

# Check if there are any records
if input_sdf.count() == 0:
    raise Exception(
        "No records found for conversion. Please check if there are any records with is_conversion_target = true in the result table."
    )

# COMMAND ----------

# DBTITLE 1,Create Batch Inference Requests
batch_inference_requests = [
    BatchInferenceRequest(index=int(row[0]), text=row[1], system_message=system_message, few_shots=few_shots)
    for row in input_sdf.toPandas().itertuples(index=False, name=None)
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
batch_inference_result_processor = BatchInferenceResultProcessor(
    model_serving_endpoint_for_conversion=config_endpoint_name,
    request_params_for_conversion=config_request_params,
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