# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook Utilities
# MAGIC This notebook contains utility functions for use in other notebooks.

# COMMAND ----------

# DBTITLE 1,Import Libraries
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pyspark.sql import DataFrame
from pyspark.sql.functions import coalesce, col, lit, try_divide, udf, when
from pyspark.sql.types import (
    ArrayType,
    FloatType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from pyscripts.helpers.batch_inference_helper import BatchInferenceResponse
from pyscripts.helpers.conversion_result_clean_helper import ConversionResultCleanHelper
from pyscripts.utils.databricks_credentials import DatabricksCredentials

# COMMAND ----------

# DBTITLE 1,Define Functions

def clean_conversion_results(target_table: str, size_ratio_threshold: float = 0.9) -> DataFrame:
    """
    Cleans the conversion results in the specified Delta table.

    Args:
        target_table (str): The name of the target table.
        size_ratio_threshold (float): The threshold for the ratio of cleaned content size to original content size. If the ratio is below this threshold, a warning is printed. Default is 0.9 (90%).

    Returns:
        pyspark.sql.DataFrame: The cleaned DataFrame.
    """
    original_df = spark.table(target_table)
    cleaned_df = original_df

    # Apply each UDF function to clean the result_content column
    helper = ConversionResultCleanHelper()
    udf_functions = helper.get_udf_functions()
    for udf_func in udf_functions:
        clean_udf = udf(udf_func, StringType())
        cleaned_df = cleaned_df.withColumn("result_content", clean_udf(cleaned_df["result_content"]))

    # Compare the sizes of the original and cleaned content. If the cleaned content　is under the threshold, print a warning.
    small_content_files_df = compare_content_sizes(original_df, cleaned_df, "result_content", size_ratio_threshold)
    if small_content_files_df.count() > 0:
        print(
            f"Warning: The following files have cleaned content sizes less than "
            f"{size_ratio_threshold * 100}% of their original sizes, "
            f"indicating potential data loss:"
        )
        display(small_content_files_df)

    # Update result_timestamp if the cleaned content is different from the original content
    return (
        cleaned_df.alias("cleaned")
        .join(original_df.select("input_file_number", "result_content").alias("original"), on="input_file_number")
        .withColumn(
            "result_timestamp",
            when(col("cleaned.result_content") != col("original.result_content"), datetime.now()).otherwise(
                col("cleaned.result_timestamp")
            ),
        )
        .drop(col("original.result_content"))
    )


def compare_content_sizes(df1: DataFrame, df2: DataFrame, col_name: str, threshold: float = 0.9) -> DataFrame:
    """
    Compares the sizes of the specified column in two DataFrames and returns a DataFrame
    containing rows where the size ratio is below the threshold.

    Args:
        df1 (DataFrame): The first DataFrame (original).
        df2 (DataFrame): The second DataFrame (cleaned).
        col_name (str): The name of the column to compare sizes.
        threshold (float): The threshold for the size ratio. Default is 0.9 (90%).

    Returns:
        DataFrame: A DataFrame containing rows where the size ratio is below the threshold.
    """

    def safe_len(value):
        if value is None:
            return 0
        return len(value)

    size_udf = udf(safe_len, IntegerType())
    df1 = df1.select("input_file_number", "input_file_path", size_udf(col(col_name)).alias("original_content_size"))
    df2 = df2.select("input_file_number", size_udf(col(col_name)).alias("cleaned_content_size"))
    return (
        df1.join(df2, on="input_file_number")
        .filter(try_divide(col("cleaned_content_size"), col("original_content_size")) < threshold)
        .select(
            "input_file_number",
            "input_file_path",
            "original_content_size",
            "cleaned_content_size",
            try_divide(col("cleaned_content_size"), col("original_content_size")).alias("size_ratio"),
        )
    )


class BatchInferenceResultProcessor:
    """
    A class to process batch inference results and merge them with source data in a Databricks environment.
    """

    def __init__(
        self,
        model_serving_endpoint_for_conversion: Optional[str] = None,
        model_serving_endpoint_for_fix: Optional[str] = None,
        request_params_for_conversion: Optional[Dict[str, Any]] = None,
        request_params_for_fix: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the BatchInferenceResultProcessor with the schema for inference responses and model serving endpoints.

        Args:
            model_serving_endpoint_for_conversion (Optional[str]): The model serving endpoint for conversion.
            model_serving_endpoint_for_fix (Optional[str]): The model serving endpoint for fix.
            request_params_for_conversion (Optional[Dict[str, Any]]): Request parameters for conversion.
            request_params_for_fix (Optional[Dict[str, Any]]): Request parameters for fix.
        """
        self.model_serving_endpoint_for_conversion = model_serving_endpoint_for_conversion
        self.model_serving_endpoint_for_fix = model_serving_endpoint_for_fix

        # Convert request parameters to JSON strings during initialization
        self.request_params_for_conversion_json = (
            json.dumps(request_params_for_conversion) if request_params_for_conversion is not None else None
        )
        self.request_params_for_fix_json = (
            json.dumps(request_params_for_fix) if request_params_for_fix is not None else None
        )

        self.schema = StructType(
            [
                StructField("input_file_number", LongType(), True),
                StructField("result_content", StringType(), True),
                StructField("result_prompt_tokens", IntegerType(), True),
                StructField("result_completion_tokens", IntegerType(), True),
                StructField("result_total_tokens", IntegerType(), True),
                StructField("result_processing_time_seconds", FloatType(), True),
                StructField("result_timestamp", TimestampType(), True),
                StructField("result_error", StringType(), True),
            ]
        )

    def process_results(self, source_sdf: DataFrame, responses: List[BatchInferenceResponse]) -> DataFrame:
        """
        Process the batch inference results and merge them with the source DataFrame.

        Args:
            source_sdf (DataFrame): The source DataFrame containing original data.
            responses (List[BatchInferenceResponse]): The list of responses from batch inference.

        Returns:
            DataFrame: The processed DataFrame with merged results.
        """
        result_sdf = self._create_result_dataframe(responses)
        joined_sdf = self._join_dataframes(source_sdf, result_sdf)
        update_columns = self._get_update_columns()
        select_columns = self._get_select_columns(source_sdf, update_columns)
        return joined_sdf.select(*select_columns)

    def _create_result_dataframe(self, responses: List[BatchInferenceResponse]) -> DataFrame:
        """Create a DataFrame from the batch inference responses."""
        current_time = datetime.now()
        responses_with_timestamp = [
            (
                res.index,
                res.content,
                res.token_usage.prompt_tokens if res.token_usage else None,
                res.token_usage.completion_tokens if res.token_usage else None,
                res.token_usage.total_tokens if res.token_usage else None,
                res.processing_time_seconds,
                current_time,
                res.error,
            )
            for res in responses
        ]
        return spark.createDataFrame(responses_with_timestamp, schema=self.schema)

    def _join_dataframes(self, source_sdf: DataFrame, result_sdf: DataFrame) -> DataFrame:
        """Join the source and result DataFrames."""
        return source_sdf.alias("source").join(result_sdf.alias("result"), on="input_file_number", how="left")

    def _get_update_columns(self) -> List:
        """Get the list of columns to update or add."""
        return [
            # Update conversion target flag based on successful conversion
            when((col("result.result_content").isNotNull()) & (col("result.result_error").isNull()), lit(False))
            .otherwise(col("source.is_conversion_target"))
            .alias("is_conversion_target"),
            # Basic result columns
            coalesce(col("result.result_content"), col("source.result_content")).alias("result_content"),
            coalesce(col("result.result_prompt_tokens"), col("source.result_prompt_tokens")).alias(
                "result_prompt_tokens"
            ),
            coalesce(col("result.result_completion_tokens"), col("source.result_completion_tokens")).alias(
                "result_completion_tokens"
            ),
            coalesce(col("result.result_total_tokens"), col("source.result_total_tokens")).alias("result_total_tokens"),
            coalesce(col("result.result_processing_time_seconds"), col("source.result_processing_time_seconds")).alias(
                "result_processing_time_seconds"
            ),
            coalesce(col("result.result_timestamp"), col("source.result_timestamp")).alias("result_timestamp"),
            # Update result_error with appropriate error handling
            # - Clear error if conversion succeeded (result_content exists and no new error)
            # - Set new error if conversion failed
            # - Keep existing error otherwise
            when((col("result.result_content").isNotNull()) & (col("result.result_error").isNull()), lit(None))
            .when(col("result.result_error").isNotNull(), col("result.result_error"))
            .otherwise(col("source.result_error"))
            .alias("result_error"),
            # Reset analysis-related columns
            lit(None).cast(StringType()).alias("result_python_parse_error"),
            lit(None).cast(ArrayType(StringType())).alias("result_extracted_sqls"),
            lit(None).cast(ArrayType(StringType())).alias("result_sql_parse_errors"),
            # Model serving endpoints and request params
            coalesce(
                lit(self.model_serving_endpoint_for_conversion), col("source.model_serving_endpoint_for_conversion")
            ).alias("model_serving_endpoint_for_conversion"),
            coalesce(lit(self.model_serving_endpoint_for_fix), col("source.model_serving_endpoint_for_fix")).alias(
                "model_serving_endpoint_for_fix"
            ),
            coalesce(lit(self.request_params_for_conversion_json), col("source.request_params_for_conversion")).alias(
                "request_params_for_conversion"
            ),
            coalesce(lit(self.request_params_for_fix_json), col("source.request_params_for_fix")).alias(
                "request_params_for_fix"
            ),
        ]

    def _get_select_columns(self, source_sdf: DataFrame, update_columns: List) -> List:
        """Get the list of columns to select in the final DataFrame."""
        excluded_columns = [
            "is_conversion_target",
            "result_content",
            "result_prompt_tokens",
            "result_completion_tokens",
            "result_total_tokens",
            "result_processing_time_seconds",
            "result_timestamp",
            "result_error",
            "result_python_parse_error",
            "result_extracted_sqls",
            "result_sql_parse_errors",
            "model_serving_endpoint_for_conversion",
            "model_serving_endpoint_for_fix",
            "request_params_for_conversion",
            "request_params_for_fix",
        ]
        select_columns = [col("source." + c) for c in source_sdf.columns if c not in excluded_columns]
        select_columns.extend(update_columns)
        return select_columns


class ExportResultProcessor:
    """
    Processor for updating result_table with export results.
    Processes main export results (notebook/file) only.
    """

    def __init__(self, target_type: str):
        """
        Initialize the ExportResultProcessor.

        Args:
            target_type (str): Target type - "notebook" or "file"
        """
        self.target_type = target_type
        self.schema = StructType(
            [
                StructField("input_file_path", StringType(), True),
                StructField("export_output_path", StringType(), True),
                StructField("export_status", StringType(), True),
                StructField("export_error", StringType(), True),
                StructField("export_timestamp", TimestampType(), True),
                StructField("export_content_size_bytes", LongType(), True),
            ]
        )

    def process_export_results(self, source_sdf: DataFrame, export_results_json: str) -> DataFrame:
        """
        Process export results and merge them with the source DataFrame.

        Args:
            source_sdf (DataFrame): The source DataFrame containing original data
            export_results_json (str): JSON string containing export results

        Returns:
            DataFrame: The processed DataFrame with merged export results
        """
        export_results = json.loads(export_results_json)
        export_sdf = self._create_export_dataframe(export_results)
        joined_sdf = self._join_dataframes(source_sdf, export_sdf)
        update_columns = self._get_update_columns()
        select_columns = self._get_select_columns(source_sdf, update_columns)
        return joined_sdf.select(*select_columns)

    def _create_export_dataframe(self, export_results: List[Dict]) -> DataFrame:
        """Create a DataFrame from export results."""
        current_time = datetime.now()
        export_data = []

        for result in export_results:
            # Normalize different export result formats
            if self.target_type == "notebook":
                # From export_to_notebook.py
                export_data.append(
                    (
                        result.get("input_file_path"),
                        result.get("output_file_path"),
                        "exported" if result.get("export_succeeded", False) else "export_failed",
                        result.get("export_error"),
                        current_time,
                        result.get("base64_encoded_content_size", 0),
                    )
                )
            elif self.target_type == "file":
                # From export_to_file.py
                export_data.append(
                    (
                        result.get("input_file_path"),
                        result.get("output_file_path"),
                        result.get("export_status", "export_failed"),
                        result.get("export_error"),
                        current_time,
                        result.get("content_size_bytes", 0),
                    )
                )

        return spark.createDataFrame(export_data, schema=self.schema)

    def _join_dataframes(self, source_sdf: DataFrame, export_sdf: DataFrame) -> DataFrame:
        """Join the source and export DataFrames."""
        return source_sdf.alias("source").join(
            export_sdf.alias("export"), col("source.input_file_path") == col("export.input_file_path"), how="left"
        )

    def _get_update_columns(self) -> List:
        """Get the list of columns to update or add."""
        return [
            coalesce(col("export.export_output_path"), col("source.export_output_path")).alias("export_output_path"),
            coalesce(col("export.export_status"), col("source.export_status")).alias("export_status"),
            coalesce(col("export.export_error"), col("source.export_error")).alias("export_error"),
            coalesce(col("export.export_timestamp"), col("source.export_timestamp")).alias("export_timestamp"),
            coalesce(col("export.export_content_size_bytes"), col("source.export_content_size_bytes")).alias(
                "export_content_size_bytes"
            ),
        ]

    def _get_select_columns(self, source_sdf: DataFrame, update_columns: List) -> List:
        """Get the list of columns to select in the final DataFrame."""
        excluded_columns = [
            "export_output_path",
            "export_status",
            "export_error",
            "export_timestamp",
            "export_content_size_bytes",
        ]
        select_columns = [col("source." + c) for c in source_sdf.columns if c not in excluded_columns]
        select_columns.extend(update_columns)
        return select_columns


def display_main_results(result_table: str, output_dir: str, target_type: str):
    """
    Display comprehensive conversion and export results.

    Args:
        result_table (str): Name of the result table
        output_dir (str): Output directory path
        target_type (str): Target type - "notebook" or "file"
    """
    # Display statistics
    stats = spark.sql(
        f"""
        SELECT 
            COUNT(*) as total_files,
            SUM(CASE WHEN result_content IS NOT NULL THEN 1 ELSE 0 END) as successful_conversions,
            SUM(CASE WHEN export_status = 'exported' THEN 1 ELSE 0 END) as successful_exports,
            SUM(CASE WHEN result_python_parse_error IS NOT NULL OR 
                         (result_sql_parse_errors IS NOT NULL AND size(result_sql_parse_errors) > 0) 
                     THEN 1 ELSE 0 END) as files_with_errors
        FROM {result_table}
        WHERE result_content IS NOT NULL OR result_error IS NOT NULL
    """
    ).collect()[0]

    print("=== Conversion Summary ===")
    print(f"Target type: {target_type}")
    print(f"Files processed: {stats['total_files']}")
    print(f"Successful conversions: {stats['successful_conversions']}")
    print(f"Successful exports: {stats['successful_exports']}")
    print(f"Files with parse errors: {stats['files_with_errors']}")

    # Display output directory URL
    full_url = f"{DatabricksCredentials().host}#workspace{output_dir}"
    displayHTML(f'<p><strong>Output Directory URL: </strong><a href="{full_url}" target="_blank">{full_url}</a></p>')

    # Display detailed results table
    spark.sql(
        f"""
        SELECT 
            input_file_number,
            input_file_path,
            CASE 
                WHEN result_content IS NULL THEN 'Not converted'
                WHEN result_python_parse_error IS NOT NULL OR 
                     (result_sql_parse_errors IS NOT NULL AND size(result_sql_parse_errors) > 0)
                THEN 'Converted with errors'
                ELSE 'Converted successfully'
            END as conversion_status,
            CASE 
                WHEN export_status IS NULL THEN 'Not exported'
                WHEN export_status = 'exported' THEN 'Exported successfully'
                ELSE 'Export failed'
            END as export_status,
            export_output_path,
            COALESCE(export_content_size_bytes, 0) as content_size_bytes,
            CASE 
                WHEN result_python_parse_error IS NOT NULL THEN 
                    concat('Python errors: ', result_python_parse_error)
                WHEN result_sql_parse_errors IS NOT NULL AND size(result_sql_parse_errors) > 0 THEN
                    concat('SQL errors (', size(result_sql_parse_errors), '): ', array_join(result_sql_parse_errors, '; '))
                WHEN result_error IS NOT NULL THEN 
                    concat('Conversion error: ', result_error)
                WHEN export_error IS NOT NULL THEN
                    concat('Export error: ', export_error)
                ELSE NULL
            END as error_details
        FROM {result_table}
        WHERE result_content IS NOT NULL OR result_error IS NOT NULL
        ORDER BY input_file_number
    """
    ).display()


def display_sql_conversion_summary(sql_results_json: str, sql_output_dir: str):
    """
    Display SQL conversion results summary.

    Args:
        sql_results_json (str): JSON string containing SQL conversion results
        sql_output_dir (str): SQL output directory path
    """
    try:
        sql_results = json.loads(sql_results_json)

        if not sql_results:
            print("No SQL conversion results to display")
            return

        print("\n=== SQL Conversion Summary ===")

        # Display statistics
        total_sql = len(sql_results)
        successful_sql = len([r for r in sql_results if r.get('success', False)])

        print(f"Python notebooks converted to SQL: {successful_sql}/{total_sql}")

        # Display output directory URL
        full_url = f"{DatabricksCredentials().host}#workspace{sql_output_dir}"
        displayHTML(
            f'<p><strong>SQL Output Directory URL: </strong><a href="{full_url}" target="_blank">{full_url}</a></p>'
        )

        # Display detailed results table
        import pandas as pd

        sql_df = pd.DataFrame(sql_results)
        spark.createDataFrame(sql_df).createOrReplaceTempView("temp_sql_results")

        spark.sql(
            """
            SELECT 
                python_notebook_path,
                CASE WHEN success = true THEN 'SQL converted' ELSE 'SQL conversion failed' END as sql_status,
                sql_output_path,
                ROUND(size_mb, 2) as size_mb,
                error
            FROM temp_sql_results
            ORDER BY python_notebook_path
        """
        ).display()

    except Exception as e:
        print(f"Error displaying SQL conversion results: {e}")