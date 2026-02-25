from flask import Flask, render_template, request, jsonify
import pandas as pd
import io
import zipfile
import time
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import re
import databricks.sql as dbsql
from databricks import sql
import os

from switch_backend import (
    get_workspace_client,
    upload_file_to_volume,
    trigger_switch_job
)

# -----------------------------------
# APP INIT
# -----------------------------------
app = Flask(__name__)
app.secret_key = "supersecretkey"

# -----------------------------------
# GLOBAL CONFIG
# -----------------------------------
DEFAULT_VOLUME = "switch_volume"
JOB_NAME = "lakebridge-switch-transpiler"

# -----------------------------------
# DATABRICKS SQL CONFIG (for dashboard)
# -----------------------------------

CATALOG = "lakebridge"
SCHEMA = "switch"
PREFIX = "lakebridge_switch_"

DATABRICKS_HOST = os.environ["DATABRICKS_HOST"].replace("https://", "").strip()

DATABRICKS_HTTP_PATH = "/sql/1.0/warehouses/67633bcc9ea6a2d7"

DATABRICKS_TOKEN = "dapif614983c0ca355e28e98e60cf54bf6c0"



# -----------------------------------
# SESSION STATE (SIMULATED)
# -----------------------------------
SESSION_STATE = {
    "theme": "light",
    "files_to_process": [],
    "job_running": False,
    "run_completed": False,
    "progress": 0,
    "job_state": None,
    "job_result": None,
    "job_error": None,
    "result_df": None,
    "run_output_map": {}
}

state_lock = threading.Lock()

# -----------------------------------
# UTIL: RESET STATE BEFORE NEW RUN
# -----------------------------------
def reset_job_state():
    with state_lock:
        SESSION_STATE["job_running"] = False
        SESSION_STATE["run_completed"] = False
        SESSION_STATE["progress"] = 0
        SESSION_STATE["job_state"] = None
        SESSION_STATE["job_result"] = None
        SESSION_STATE["job_error"] = None
        SESSION_STATE["result_df"] = None


# -----------------------------------
# DASHBOARD HELPER:
# GET LATEST TABLE NAME
# -----------------------------------
def get_latest_run_table_name(w, catalog, schema, prefix):

    try:
        tables = list(
            w.tables.list(
                catalog_name=catalog,
                schema_name=schema
            )
        )

        names = [
            t.name
            for t in tables
            if t.name.startswith(prefix)
        ]

        if not names:
            return None

        def extract_ts(name):
            match = re.search(r"_(\d{14})_", name)
            if match:
                return pd.to_datetime(
                    match.group(1),
                    format="%Y%m%d%H%M%S"
                )
            return pd.Timestamp.min

        names = sorted(
            names,
            key=extract_ts,
            reverse=True
        )

        return f"{catalog}.{schema}.{names[0]}"

    except Exception as e:
        print("Table detection error:", e)
        return None


# -----------------------------------
# DASHBOARD HELPER:
# LOAD TABLE INTO DATAFRAME
# -----------------------------------
def load_table_df(full_table_name, limit=1000):

    catalog, schema, table = full_table_name.split(".")

    refresh_query = f"""
    REFRESH TABLE `{catalog}`.`{schema}`.`{table}`
    """

    select_query = f"""
    SELECT *
    FROM `{catalog}`.`{schema}`.`{table}`
    LIMIT {limit}
    """

    with dbsql.connect(
        server_hostname=DATABRICKS_HOST,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN
    ) as conn:

        try:
            pd.read_sql(refresh_query, conn)
        except:
            pass

        df = pd.read_sql(select_query, conn)

    desired_cols = [
        "input_file_number",
        "input_file_path",
        "input_file_content",
        "result_extracted_sqls",
        "result_sql_parse_errors",
        "accuracy_percent",
        "result_content"
    ]

    return df[desired_cols]


# -----------------------------------
# BACKGROUND PIPELINE
# -----------------------------------
def background_pipeline(config):

    try:

        with state_lock:
            SESSION_STATE["job_running"] = True
            SESSION_STATE["progress"] = 5

        w = get_workspace_client()

        run_ts = int(time.time())

        unique_input_dir = (
            f"/Volumes/{config['catalog']}/"
            f"{config['schema']}/"
            f"{DEFAULT_VOLUME}/upload_{run_ts}"
        )

        unique_output_dir = (
            f"/Workspace/Shared/switch_output_{run_ts}"
        )

        files = SESSION_STATE["files_to_process"]
        total_files = len(files)

        if total_files == 0:
            raise Exception("No files to process")

        # ---------------------------
        # Upload Files
        # ---------------------------
        for i, (fname, content) in enumerate(files):

            upload_file_to_volume(
                w,
                io.BytesIO(content),
                f"{unique_input_dir}/{fname}"
            )

            with state_lock:
                SESSION_STATE["progress"] = int(
                    ((i + 1) / total_files) * 30
                )

        # ---------------------------
        # Trigger Job
        # ---------------------------
        params = {
            "input_dir": unique_input_dir,
            "output_dir": unique_output_dir,
            "source_tech": config["source_dialect"],
            "foundation_model": config["model_choice"],
            "catalog": config["catalog"],
            "schema": config["schema"]
        }

        run_id = trigger_switch_job(
            w,
            JOB_NAME,
            params
        )

        with state_lock:
            SESSION_STATE["run_output_map"][run_id] = unique_output_dir

        finished_states = [
            "TERMINATED",
            "SKIPPED",
            "INTERNAL_ERROR"
        ]

        # ---------------------------
        # Monitor Job
        # ---------------------------
        while True:

            run_info = w.jobs.get_run(
                run_id=run_id
            )

            state = getattr(
                run_info.state.life_cycle_state,
                "value",
                None
            )

            result = getattr(
                run_info.state.result_state,
                "value",
                None
            )

            with state_lock:
                SESSION_STATE["job_state"] = state
                SESSION_STATE["job_result"] = result
                SESSION_STATE["progress"] = 60

            if state in finished_states:
                break

            time.sleep(3)

        # ---------------------------
        # LOAD MIGRATION REPORT DATA
        # ---------------------------
        try:

            latest_table = get_latest_run_table_name(
                w,
                config["catalog"],
                config["schema"],
                PREFIX
            )


            if latest_table:

                df = load_table_df(
                    latest_table
                )

                with state_lock:
                    SESSION_STATE["result_df"] = df

        except Exception as e:
            print("Result load error:", e)

        # ---------------------------
        # COMPLETE JOB
        # ---------------------------
        with state_lock:
            SESSION_STATE["progress"] = 100
            SESSION_STATE["run_completed"] = True
            SESSION_STATE["job_running"] = False

    except Exception as e:

        with state_lock:
            SESSION_STATE["job_error"] = str(e)
            SESSION_STATE["job_running"] = False
            SESSION_STATE["progress"] = 0


# -----------------------------------
# ROUTES
# -----------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        theme=SESSION_STATE["theme"]
    )


@app.route("/upload_files", methods=["POST"])
def upload_files():

    upload_mode = request.form.get(
        "upload_mode",
        "single"
    )

    files_to_process = []

    if upload_mode == "zip":

        uploaded_file = request.files.get(
            "zip_file"
        )

        if not uploaded_file:
            return jsonify({
                "error": "No zip file uploaded"
            }), 400

        z = zipfile.ZipFile(
            uploaded_file
        )

        valid_files = [
            name for name in z.namelist()
            if name.endswith(
                (".sql", ".bteq")
            )
        ]

        for name in valid_files:

            files_to_process.append(
                (
                    name.replace("/", "_"),
                    z.read(name)
                )
            )

    else:

        uploaded_files = request.files.getlist(
            "sql_files"
        )

        if not uploaded_files:
            return jsonify({
                "error": "No SQL files uploaded"
            }), 400

        for f in uploaded_files:

            files_to_process.append(
                (
                    f.filename,
                    f.read()
                )
            )

    with state_lock:
        SESSION_STATE["files_to_process"] = files_to_process

    return jsonify({
        "status": "ok",
        "files_count": len(files_to_process)
    })


@app.route("/start_job", methods=["POST"])
def start_job():

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Invalid JSON payload"
        }), 400

    required_fields = [
        "source_dialect",
        "catalog",
        "schema",
        "model_choice"
    ]

    if not all(
        data.get(field)
        for field in required_fields
    ):
        return jsonify({
            "error": "Missing required configuration"
        }), 400

    if not SESSION_STATE["files_to_process"]:
        return jsonify({
            "error": "No files uploaded"
        }), 400

    reset_job_state()

    thread = threading.Thread(
        target=background_pipeline,
        args=(data,),
        daemon=True
    )

    thread.start()

    return jsonify({
        "status": "started"
    })


@app.route("/job_status")
def job_status():

    with state_lock:

        return jsonify({
            "running": SESSION_STATE["job_running"],
            "completed": SESSION_STATE["run_completed"],
            "progress": SESSION_STATE["progress"],
            "state": SESSION_STATE["job_state"],
            "result": SESSION_STATE["job_result"],
            "error": SESSION_STATE["job_error"]
        })




# -----------------------------------
# MIGRATION REPORT PAGE
# -----------------------------------
@app.route("/migration_report")
def migration_report():
    return render_template("migration_report.html")


# -----------------------------------
# JOB HISTORY PAGE
# -----------------------------------
@app.route("/job-history")
def job_history_page():
    return render_template("job_history.html")



@app.route("/api/migration_report")
def api_migration_report():

    try:

        w = get_workspace_client()

        tables = list(
            w.tables.list(
                catalog_name=CATALOG,
                schema_name=SCHEMA
            )
        )

        table_names = [
            t.name for t in tables
            if t.name.startswith(PREFIX)
        ]

        print("All switch tables:", table_names)

        if not table_names:
            return jsonify({"error": "No migration tables found"}), 404


        def extract_ts(name):

            match = re.search(r"(\d{14})", name)

            if match:
                return datetime.strptime(
                    match.group(1),
                    "%Y%m%d%H%M%S"
                )

            return datetime.min


        table_names.sort(
            key=extract_ts,
            reverse=True
        )

        latest_table = table_names[0]

        print("Latest table:", latest_table)


        print("Connecting to warehouse using token...")

        conn = dbsql.connect(
            server_hostname=DATABRICKS_HOST,
            http_path=DATABRICKS_HTTP_PATH,
            access_token=DATABRICKS_TOKEN
        )

        cursor = conn.cursor()

        print("Setting catalog and schema...")

        cursor.execute(f"USE CATALOG {CATALOG}")
        cursor.execute(f"USE SCHEMA {SCHEMA}")


        query = f"""
        SELECT
            input_file_path,
            CAST(accuracy_percent AS DOUBLE) AS accuracy_percent,
            CASE
                WHEN result_sql_parse_errors IS NULL THEN ''
                ELSE CONCAT_WS(', ', result_sql_parse_errors)
            END AS result_sql_parse_errors,
            input_file_content,
            result_content
        FROM `{CATALOG}`.`{SCHEMA}`.`{latest_table}`
        """


        print("Executing query on:", latest_table)

        cursor.execute(query)

        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]

        print("Rows fetched:", len(rows))

        df = pd.DataFrame(rows, columns=columns)




        if df.empty:
            return jsonify({"error": "No migration data available"}), 404


        files = []
        passed = 0
        accuracy_sum = 0


        for _, row in df.iterrows():

            errors = row["result_sql_parse_errors"]
            converted_sql = row["result_content"]

            # Accuracy calculation
            if not converted_sql or converted_sql.strip() == "":
                accuracy = 0.0

            elif errors and errors.strip() != "":
                error_count = len(errors.split(","))

                if error_count >= 3:
                    accuracy = 60.0
                elif error_count == 2:
                    accuracy = 75.0
                else:
                    accuracy = 85.0

            else:
                accuracy = 100.0


            if accuracy >= 90:
                passed += 1

            accuracy_sum += accuracy

            file_path = row["input_file_path"]

            if file_path:
                base = file_path.split("/")[-1]
                file_name = base.split("_", 1)[1] if "_" in base else base
            else:
                file_name = ""

            files.append({

                "file_name": file_name,
                "accuracy": round(accuracy, 2),
                "status":
                    "Pass" if accuracy >= 90 else
                    "Needs Review" if accuracy >= 70 else
                    "Fail",
                "errors": errors or "",
                "legacy_sql": row["input_file_content"] or "",
                "converted_sql": converted_sql or ""
            })



        total = len(files)

        avg_accuracy = round(
            accuracy_sum / total,
            2
        )


        return jsonify({

            "table_used": latest_table,

            "metrics": {

                "total": total,
                "passed": passed,
                "failed": total - passed,
                "avg_accuracy": avg_accuracy
            },

            "files": files
        })


    except Exception as e:

        print("Migration report error:", str(e))

        return jsonify({"error": str(e)}), 500
    


# -----------------------------------
# JOB HISTORY API
# -----------------------------------
@app.route("/api/job-history")
def api_job_history():

    try:

        limit = request.args.get("limit", default=100, type=int)

        if limit > 100:
            limit = 100

        w = get_workspace_client()

        # Convert iterator → list
        jobs = list(w.jobs.list())

        job_id = None

        for job in jobs:
            if job.settings and job.settings.name == JOB_NAME:
                job_id = job.job_id
                break

        if not job_id:
            return jsonify({
                "error": f"Job '{JOB_NAME}' not found"
            }), 404


        # Convert iterator → list BEFORE sorting
        runs = list(w.jobs.list_runs(job_id=job_id))

        runs = sorted(
            runs,
            key=lambda r: r.start_time or 0,
            reverse=True
        )[:limit]


        history = []

        for run in runs:

            start_time = None
            duration = None
            status = "UNKNOWN"
            output_dir = None
            workspace_link = None


            if run.start_time:
                start_time = datetime.fromtimestamp(
                    run.start_time / 1000,
                    tz=timezone.utc
                ).astimezone(
                    ZoneInfo("Asia/Kolkata")
                ).strftime("%b %d, %Y, %I:%M %p")


            if run.end_time and run.start_time:
                duration = round(
                    (run.end_time - run.start_time) / 1000,
                    1
                )


            if run.state and run.state.result_state:
                status = run.state.result_state.value

            #extraction of output dir
            output_dir = None

            try:
                run_details = w.jobs.get_run(run.run_id)

                # 1️⃣ Check overriding parameters
                override = getattr(run_details, "overriding_parameters", None)

                if override:
                    notebook_params = getattr(override, "notebook_params", None)
                    job_params = getattr(override, "job_parameters", None)

                    # notebook_params (usually dict)
                    if isinstance(notebook_params, dict):
                        output_dir = notebook_params.get("output_dir")

                    # job_params (SDK objects list)
                    elif job_params:
                        for param in job_params:
                            if getattr(param, "name", None) == "output_dir":
                                output_dir = getattr(param, "value", None)
                                break

                # 2️⃣ If not found, check job-level parameters
                if not output_dir:
                    job_params = getattr(run_details, "job_parameters", None)

                    if job_params:
                        for param in job_params:
                            if getattr(param, "name", None) == "output_dir":
                                output_dir = getattr(param, "value", None)
                                break

            except Exception as e:
                print("Could not fetch run parameters:", e)

            # Build workspace link
            workspace_link = None
            if output_dir:
                workspace_link = f"https://{DATABRICKS_HOST}/#workspace{output_dir.replace('/Workspace','')}"

            print("Output dir:", output_dir)   


            history.append({

                "run_id": run.run_id,
                "start_time": start_time,
                "status": status,
                "duration": duration,
                "output_dir": output_dir,
                "output_link": workspace_link,
                "run_page_url": run.run_page_url

            })


        return jsonify(history)


    except Exception as e:

        import traceback
        traceback.print_exc()

        return jsonify({
            "error": str(e)
        }), 500



@app.route("/toggle_theme", methods=["POST"])
def toggle_theme():
    with state_lock:
        # Toggle current theme
        current = SESSION_STATE.get("theme", "light")
        SESSION_STATE["theme"] = "dark" if current == "light" else "light"
        return jsonify({"theme": SESSION_STATE["theme"]})


# -----------------------------------
# RUN
# -----------------------------------
if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True
    )