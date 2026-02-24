# Databricks notebook source
# MAGIC %md
# MAGIC # Export to Generic Files
# MAGIC This notebook exports the converted content from the Delta table to generic files with specified extensions.
# MAGIC It iterates through the rows of the input table, retrieves the converted content, and creates corresponding files in the specified output directory.
# MAGIC
# MAGIC ## Task Overview
# MAGIC The following tasks are accomplished in this notebook:
# MAGIC
# MAGIC 1. **Load Data:** The data is loaded from the input table, which is the output of the previous conversion steps.
# MAGIC 2. **Prepare File Content:** For each row in the table, the converted content is extracted and prepared for file export.
# MAGIC 3. **Export Files:** The content is written to files with the specified extension in the output directory.

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
from pathlib import Path
from typing import List, Dict, Any

# COMMAND ----------

# MAGIC %md
# MAGIC ## Set up configuration parameters

# COMMAND ----------

# DBTITLE 1,Configurations
dbutils.widgets.text("result_table", "", "Conversion Result Table")
dbutils.widgets.text("output_dir", "", "Output Directory")
dbutils.widgets.text("output_extension", "", "Output File Extension")

# COMMAND ----------

# DBTITLE 1,Load Configurations
result_table = dbutils.widgets.get("result_table")
output_dir = dbutils.widgets.get("output_dir")
output_extension = dbutils.widgets.get("output_extension")

result_table, output_dir, output_extension

# COMMAND ----------

# MAGIC %md
# MAGIC ## Helper Functions

# COMMAND ----------

# DBTITLE 1,Helper Functions

def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing or replacing invalid characters."""
    # Remove common invalid characters and replace with underscore
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename


def generate_output_path(input_file_path: str, output_dir: str, output_extension: str) -> str:
    """Generate output file path based on input file path and desired extension."""
    # Extract filename without extension from input path
    input_filename = Path(input_file_path).stem
    sanitized_filename = sanitize_filename(input_filename)

    # Ensure output extension starts with dot
    if not output_extension.startswith('.'):
        output_extension = '.' + output_extension

    # Construct output path
    output_filename = sanitized_filename + output_extension
    output_path = f"{output_dir.rstrip('/')}/{output_filename}"

    return output_path


# COMMAND ----------

# MAGIC %md
# MAGIC ## Load Data

# COMMAND ----------

# DBTITLE 1,Load and Process Data
# Load data from result table
df = spark.table(result_table)
converted_files = df.filter("result_content IS NOT NULL").collect()

print(f"Found {len(converted_files)} converted files to export")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Export Files

# COMMAND ----------

# DBTITLE 1,Export Files
export_results: List[Dict[str, Any]] = []

for row in converted_files:
    input_file_path = row['input_file_path']
    content = row['result_content']

    try:
        # Generate output path
        output_file_path = generate_output_path(input_file_path, output_dir, output_extension)

        # Create directory if it doesn't exist
        output_dir_path = str(Path(output_file_path).parent)
        os.makedirs(output_dir_path, exist_ok=True)

        # Write content to file
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Record successful export
        export_results.append(
            {
                "input_file_path": input_file_path,
                "output_file_path": output_file_path,
                "export_status": "success",
                "export_error": None,
                "content_size_bytes": len(content.encode('utf-8')),
            }
        )

        print(f"✓ Exported: {input_file_path} → {output_file_path}")

    except Exception as e:
        # Record failed export
        export_results.append(
            {
                "input_file_path": input_file_path,
                "output_file_path": None,
                "export_status": "failed",
                "export_error": str(e),
                "content_size_bytes": len(content.encode('utf-8')) if content else 0,
            }
        )

        print(f"✗ Failed to export {input_file_path}: {str(e)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Export Results

# COMMAND ----------

# DBTITLE 1,Export Summary
print("=== Export Summary ===")
print(f"Total files processed: {len(export_results)}")
successful_exports = [r for r in export_results if r['export_status'] == 'success']
failed_exports = [r for r in export_results if r['export_status'] == 'failed']
print(f"Successful exports: {len(successful_exports)}")
print(f"Failed exports: {len(failed_exports)}")

if failed_exports:
    print("\nFailed exports:")
    for failed in failed_exports:
        print(f"  - {failed['input_file_path']}: {failed['export_error']}")

# COMMAND ----------

# DBTITLE 1,Display Results Table
# Define explicit schema for DataFrame
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

schema = StructType(
    [
        StructField("input_file_path", StringType(), False),
        StructField("output_file_path", StringType(), True),  # Nullable
        StructField("export_status", StringType(), False),
        StructField("export_error", StringType(), True),  # Nullable
        StructField("content_size_bytes", IntegerType(), False),
    ]
)

# Create DataFrame with explicit schema
results_df = spark.createDataFrame(export_results, schema)
results_df.display()

# COMMAND ----------

# DBTITLE 1,Load Notebook Utils
# MAGIC %run ../notebook_utils

# COMMAND ----------

# DBTITLE 1,Update Result Table with Export Information
# Update result_table with export results
processor = ExportResultProcessor(target_type="file")
source_sdf = spark.table(result_table)
updated_sdf = processor.process_export_results(source_sdf, json.dumps(export_results))
updated_sdf.write.mode("overwrite").saveAsTable(result_table)