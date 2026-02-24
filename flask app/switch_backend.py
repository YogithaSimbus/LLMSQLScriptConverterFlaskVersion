import time
import base64
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import RunLifeCycleState

def get_workspace_client():
    """Auto-authenticates inside Databricks Apps or uses local CLI profile."""
    return WorkspaceClient()

def upload_file_to_volume(w, file_obj, target_path):
    """
    Uploads a file-like object to a Unity Catalog Volume.
    """
    file_obj.seek(0)
    w.files.upload(target_path, file_obj, overwrite=True)

def trigger_switch_job(w, job_name, params):
    """
    Finds the Switch job and triggers a run.
    """
    jobs = list(w.jobs.list(name=job_name))
    if not jobs:
        raise ValueError(f"Job '{job_name}' not found. Run 'install-transpile' CLI first.")
    
    run = w.jobs.run_now(job_id=jobs[0].job_id, job_parameters=params)
    return run.run_id

def wait_for_run(w, run_id):
    """
    Polls until the job finishes.
    """
    while True:
        run_info = w.jobs.get_run(run_id=run_id)
        state = run_info.state.life_cycle_state
        if state in [RunLifeCycleState.TERMINATED, RunLifeCycleState.SKIPPED, RunLifeCycleState.INTERNAL_ERROR]:
            return run_info.state
        time.sleep(5)

def download_output_file(w, workspace_path):
    """
    Downloads a converted notebook from the Workspace and returns the source code.
    """
    try:
        # Export format "SOURCE" gets the raw Python/SQL code
        resp = w.workspace.export(path=workspace_path, format="SOURCE")
        # Content is base64 encoded
        return base64.b64decode(resp.content).decode('utf-8')
    except Exception as e:
        return f"-- Error reading file: {str(e)}"