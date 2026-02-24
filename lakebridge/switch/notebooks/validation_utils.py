# Databricks notebook source
# MAGIC %md
# MAGIC # Validation Utilities
# MAGIC This notebook contains Databricks-specific validation functions for Switch parameters.

# COMMAND ----------

# DBTITLE 1,Import Libraries
import os
from typing import List

from databricks.sdk import WorkspaceClient
from pyspark.sql.utils import AnalysisException

from pyscripts.parameters.models import SwitchParameters
from pyscripts.parameters.validator import SwitchParameterValidator

# COMMAND ----------

# DBTITLE 1,Databricks Resource Validator

class DatabricksResourceValidator:
    """Validator for Databricks-specific resources."""

    def __init__(self):
        self.errors: List[str] = []

    def _check_path_exists(self, path: str, resource_name: str) -> None:
        """Check if path exists for a given resource."""
        if not os.path.exists(path):
            self.errors.append(f"{resource_name} does not exist or is not accessible: {path}")

    def _check_catalog_schema(self, catalog: str, schema: str) -> None:
        """Validate Unity Catalog and schema."""
        try:
            catalogs = [row.catalog for row in spark.sql("SHOW CATALOGS").collect()]
            if catalog not in catalogs:
                self.errors.append(f"Catalog does not exist: {catalog}")
            else:
                try:
                    spark.sql(f"USE CATALOG `{catalog}`")
                    schemas = [row.databaseName for row in spark.sql("SHOW SCHEMAS").collect()]
                    if schema not in schemas:
                        self.errors.append(f"Schema '{schema}' does not exist in catalog '{catalog}'")
                except Exception as e:
                    self.errors.append(f"Error accessing catalog '{catalog}': {e}")
        except AnalysisException as e:
            self.errors.append(f"Error checking catalog/schema: {e}")
        except Exception as e:
            self.errors.append(f"Unexpected error validating catalog/schema: {e}")

    def _check_serving_endpoint(self, endpoint_name: str) -> None:
        """Check if serving endpoint exists."""
        try:
            w = WorkspaceClient()
            w.serving_endpoints.get(endpoint_name)
        except Exception:
            self.errors.append(f"Serving endpoint does not exist or is not accessible: {endpoint_name}")

    def validate(self, params: SwitchParameters) -> List[str]:
        """
        Validate all Databricks resources.

        Args:
            params: SwitchParameters instance

        Returns:
            List of validation error messages
        """
        self.errors = []

        # Check each resource using dataclass attributes
        self._check_path_exists(params.input_dir, "Input directory")
        self._check_catalog_schema(params.catalog, params.schema)
        self._check_serving_endpoint(params.foundation_model)
        self._check_path_exists(params.conversion_prompt_yaml, "Conversion YAML file")

        return self.errors


# COMMAND ----------

# DBTITLE 1,Public Validation Function

def validate_all_parameters(params: SwitchParameters) -> None:
    """
    Perform complete validation of Switch parameters.
    Combines pure Python validation with Databricks-specific checks.

    Args:
        params: SwitchParameters instance

    Raises:
        ValueError: If any validation errors are found
    """
    # Run pure Python validation
    python_validator = SwitchParameterValidator()
    validation_errors = python_validator.validate(params)

    # Run Databricks-specific validation
    databricks_validator = DatabricksResourceValidator()
    databricks_errors = databricks_validator.validate(params)
    validation_errors.extend(databricks_errors)

    # Report all errors at once
    if validation_errors:
        error_message = "Parameter validation failed with the following errors:\n" + "\n".join(
            f"  - {error}" for error in validation_errors
        )
        raise ValueError(error_message)

    print("All parameters validated successfully")