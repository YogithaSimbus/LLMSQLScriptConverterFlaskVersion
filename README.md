# SQLSwitchConverter: LLM-Driven Migration Orchestrator

**SQLSwitchConverter** is an enterprise-grade web application designed to orchestrate the **Lakebridge Switch** LLM-transpiler. It simplifies the modernization of legacy data warehouses by automating the conversion of complex SQL scripts (tested on MSSQL, Teradata, and Snowflake) into Databricks-optimized code.

By leveraging a **Single-Model Architecture**, SQLSwitch Pro utilizes a powerful Foundation Model (Llama 3.3 70B) to handle both semantic code translation and internal validation in a unified pipeline.

---

## 🔄 System Workflow


<img width="1024" height="1536" alt="Workflow" src="https://github.com/user-attachments/assets/3a9e7e81-0e68-4174-ae83-6773b14f634e" />

---

## 🛠️ System Resources & Backend Setup

SQLSwitch Pro interfaces with these critical workspace resources:

| Resource Key | Resource Type | Implementation Detail |
| --- | --- | --- |
| **`sql-warehouse`** | SQL Warehouse | **Serverless Starter Warehouse** (`67633bcc9ea6a2d7`) used for querying migration metadata. |
| **`job`** | Databricks Job | **`lakebridge-switch-transpiler`**; the core engine executing Switch logic in the workspace. |
| **`serving-endpoint`** | Serving Endpoint | **`databricks-meta-llama-3-3-70b-instruct`**; providing unified conversion and validation. |
| **`volume`** | UC Volume | **`/Volumes/Lakebridge/switch/switch_input`**; for staging input source files. |

### Workspace & Backend Integration

The core Switch engine is installed in the workspace at `/Workspace/Users/[user]/.lakebridge/switch/`.

* **Accuracy Measurement**: The internal Switch processing logic in `.../notebooks/processors/analyze_input_files` has been customized by adding an **`accuracy_percent`** column to the Spark DataFrame schema within the `Create Spark DataFrame` block.
* **Switch Config**: Model behavior is managed via `.../resources/switch_config.yml`, with `target_type: "notebook"` for executable output and `max_fix_attempts: 1` for autonomous correction cycles.

---

## 🖥️ Application Modules

### 1. SQLSwitch Converter (Main UI)

* **Light Theme Interface**: A clean, professional aesthetic optimized for enterprise clarity.
* **Tested Dialects**: Currently optimized and tested for **MSSQL**, **Teradata**, and **Snowflake**.
* **Unified Upload**: Supports individual `.sql`/`.bteq` files or Batch ZIP uploads.

### 2. Migration Report Dashboard

* **Global Metrics**: Real-time display of **Average Accuracy**, **Files Passed**, and **Total Files**.
* **Accuracy Ring**: A dynamic visual representation of the conversion success percentage for each file.
* **SQL Inspector**: Compare **Legacy SQL** against **Converted SQL** with a dedicated **Errors** tab for failed runs.

### 3. Job Run History

* **Audit Log**: Tracks all previous migration attempts including **Run ID**, **Status (SUCCESS)**, **Start Time**, and **Duration**.
* **Direct Access**: The **"Open Folder"** button provides a deep link to view output artifacts directly within the Databricks Workspace.

---

## 🚀 Getting Started

1. **Install Lakebridge CLI**:
```bash
databricks labs install lakebridge
databricks labs lakebridge install-transpile --include-llm-transpiler true
```

2. **Environment Configuration**: Ensure `app.py` has the correct `DATABRICKS_HOST` and `DATABRICKS_HTTP_PATH`.

3. **Run Application**:
```bash
pip install -r requirements.txt
python app.py
```
