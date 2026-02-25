# Databricks notebook source
# MAGIC %md
# MAGIC # Switch
# MAGIC Switch converts SQL and code files to Databricks notebooks using LLMs. This notebook is the main entry point for the conversion process. For complete documentation, see the [Switch Overview Documentation](https://databrickslabs.github.io/lakebridge/docs/transpile/pluggable_transpilers/switch/).

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Set Up Configuration Parameters
# MAGIC Major configuration parameters are set up in this section.

# COMMAND ----------

# DBTITLE 1,Setup Environment
# MAGIC %pip install -r ../requirements.txt
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Display Switch Version
import sys

sys.path.append('../..')
from switch.__about__ import __version__

switch_version = __version__
print(f"Switch version: {switch_version}")

# COMMAND ----------

# DBTITLE 1,Import Libraries
import json
from pathlib import Path
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import with_user_agent_extra, with_product

from pyscripts.parameters.loader import ConfigLoader
from pyscripts.parameters.models import SwitchParameters
from pyscripts.types.builtin_prompt import BuiltinPrompt
from pyscripts.types.target_type import TargetType
from pyscripts.parameters.models import LakebridgeConfig

# COMMAND ----------

# DBTITLE 1,Widget Definitions
dbutils.widgets.text("input_dir", "", "1. Input Directory")
dbutils.widgets.text("output_dir", "", "2. Output Directory")
dbutils.widgets.dropdown("source_tech", "", [""] + BuiltinPrompt.get_supported_prompts(), "3. Source Technology")
dbutils.widgets.text("catalog", "", "4. Catalog")
dbutils.widgets.text("schema", "", "5. Schema")
dbutils.widgets.text("foundation_model", "", "6. Foundation Model")
dbutils.widgets.text("switch_config_path", "", "7. Switch Config Path (optional)")

# COMMAND ----------

# DBTITLE 1,Get Runtime Parameters
input_dir = dbutils.widgets.get("input_dir")
output_dir = dbutils.widgets.get("output_dir")
source_tech = dbutils.widgets.get("source_tech")
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
foundation_model = dbutils.widgets.get("foundation_model")
switch_config_path = dbutils.widgets.get("switch_config_path") or None

print("Runtime parameters from widgets:")
print(f"  input_dir: {input_dir}")
print(f"  output_dir: {output_dir}")
print(f"  source_tech: {source_tech}")
print(f"  switch_config_path: {switch_config_path or '(default)'}")
print(f"  catalog: {catalog}")
print(f"  schema: {schema}")
print(f"  foundation_model: {foundation_model}")

# COMMAND ----------

# DBTITLE 1,Load Configuration Files

install_path = Path.cwd().parent.parent
lakebridge_version = json.loads((install_path / "version.json").read_text())['version']

with_product("lakebridge", lakebridge_version)
with_user_agent_extra("lakebridge", lakebridge_version)
with_user_agent_extra("transpiler_name", "switch")
with_user_agent_extra("transpiler_version", switch_version)
ws = WorkspaceClient()

config_loader = ConfigLoader(ws)
switch_config = config_loader.load_switch_config(switch_config_path)
lakebridge_config = LakebridgeConfig(catalog, schema, foundation_model)

# COMMAND ----------

# DBTITLE 1,Create Unified Parameters
params = SwitchParameters(
    switch=switch_config,
    lakebridge=lakebridge_config,
    input_dir=input_dir,
    output_dir=output_dir,
    source_tech=source_tech,
)

print("Unified parameters:")
print(params)

# COMMAND ----------

# DBTITLE 1,Load Validation Utils
# MAGIC %run ./validation_utils

# COMMAND ----------

# DBTITLE 1,Validate Parameters
validate_all_parameters(params)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Execute Conversion
# MAGIC Based on `target_type`, this notebook executes the appropriate conversion process.

# COMMAND ----------

# DBTITLE 1,Execute Conversion Process
if params.target_type == TargetType.NOTEBOOK.value:
    print("Routing to notebook conversion orchestrator...")
    orchestrator_result = dbutils.notebook.run(
        "orchestrators/orchestrate_to_notebook",
        0,
        {
            "input_dir": params.input_dir,
            "endpoint_name": params.foundation_model,
            "result_catalog": params.catalog,
            "result_schema": params.schema,
            "token_count_threshold": str(params.token_count_threshold),
            "source_format": params.source_format,
            "conversion_prompt_yaml": params.conversion_prompt_yaml,
            "comment_lang": params.comment_lang,
            "concurrency": str(params.concurrency),
            "request_params": params.request_params,
            "log_level": params.log_level,
            "max_fix_attempts": str(params.max_fix_attempts),
            "output_dir": params.output_dir,
            "sql_output_dir": params.sql_output_dir,
        },
    )
    print("Notebook conversion completed.")

elif params.target_type == TargetType.FILE.value:
    print(f"Routing to file conversion orchestrator (output extension: {params.output_extension})...")
    orchestrator_result = dbutils.notebook.run(
        "orchestrators/orchestrate_to_file",
        0,
        {
            "input_dir": params.input_dir,
            "endpoint_name": params.foundation_model,
            "result_catalog": params.catalog,
            "result_schema": params.schema,
            "token_count_threshold": str(params.token_count_threshold),
            "source_format": params.source_format,
            "conversion_prompt_yaml": params.conversion_prompt_yaml,
            "comment_lang": params.comment_lang,
            "concurrency": str(params.concurrency),
            "request_params": params.request_params,
            "log_level": params.log_level,
            "output_dir": params.output_dir,
            "output_extension": params.output_extension,
        },
    )
    print("File conversion completed.")

# COMMAND ----------

# DBTITLE 1,Parse Orchestrator Results
# Parse orchestrator results to extract result table and SQL conversion data
if params.target_type == TargetType.NOTEBOOK.value:
    notebook_results = json.loads(orchestrator_result)
    result_table = notebook_results["result_table"]
    sql_conversion_results = notebook_results["sql_conversion_results"]
else:
    result_table = orchestrator_result
    sql_conversion_results = None

print(f"Result table: {result_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Conversion Results
# MAGIC High-level statistics and detailed output information for the completed conversion process.

# COMMAND ----------

# DBTITLE 1,Load Notebook Utils
# MAGIC %run ./notebook_utils

# COMMAND ----------

# DBTITLE 1,Conversion and Export Results
# Display main conversion and export results
display_main_results(result_table, params.output_dir, params.target_type)

# Display SQL conversion results if applicable (notebook target with sql_output_dir)
if params.target_type == TargetType.NOTEBOOK.value and params.sql_output_dir and sql_conversion_results:
    display_sql_conversion_summary(sql_conversion_results, params.sql_output_dir)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Next Steps
# MAGIC The conversion process is now complete. The results are available in the specified output directory. Review these results thoroughly to ensure the converted content meets your requirements and functions as expected.
# MAGIC
# MAGIC **Important Notes:**
# MAGIC
# MAGIC 1. **Files with 'Not converted' status:**
# MAGIC    - Often due to exceeding token count threshold or processing errors
# MAGIC    - Check the `input_tokens` column and consider splitting large files or increasing the threshold
# MAGIC    - Re-run conversion after making adjustments
# MAGIC
# MAGIC 2. **Files with 'Converted with errors' status:**
# MAGIC    - Review detailed error messages in the `error_details` column
# MAGIC    - For syntax errors: Manually fix the issues in the output files
# MAGIC    - For conversion errors: Verify LLM endpoint availability and retry if needed
# MAGIC
# MAGIC 3. **For notebook targets:** Import converted notebooks into Databricks and test functionality
# MAGIC 4. **For file targets:** Verify output format and integrate with your downstream systems