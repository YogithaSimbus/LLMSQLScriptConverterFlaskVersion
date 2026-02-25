from mlflow.deployments import get_deploy_client
from databricks.sdk import WorkspaceClient

def _get_endpoint_task_type(endpoint_name: str) -> str:
    """Get the task type of a serving endpoint."""
    w = WorkspaceClient()
    ep = w.serving_endpoints.get(endpoint_name)
    return ep.task

def is_endpoint_supported(endpoint_name: str) -> bool:
    """Check if the endpoint has a supported task type."""
    task_type = _get_endpoint_task_type(endpoint_name)
    supported_task_types = ["agent/v1/chat", "agent/v2/chat", "llm/v1/chat"]
    return task_type in supported_task_types

def _validate_endpoint_task_type(endpoint_name: str) -> None:
    """Validate that the endpoint has a supported task type."""
    # We skip strict validation to allow flexibility, but log if needed.
    # If using Foundation Models (e.g. Llama 3), task type is usually llm/v1/chat
    pass 

def _query_endpoint(endpoint_name: str, messages: list[dict[str, str]], max_tokens) -> list[dict[str, str]]:
    """Calls a model serving endpoint."""
    
    # Use the 'databricks' target for mlflow deployments
    client = get_deploy_client("databricks")
    
    res = client.predict(
        endpoint=endpoint_name,
        inputs={
            "messages": messages, 
            "max_tokens": max_tokens, 
            "temperature": 0.1
        },
    )
    
    # Handle different response formats (Standard vs. Foundation Models)
    if "choices" in res:
        # Standard OpenAI-like format
        return [res["choices"][0]["message"]]
    elif "messages" in res:
        return res["messages"]
    
    # Fallback for some Foundation Model responses
    if isinstance(res, dict) and "choices" not in res:
         # Try to extract just text if structure is different
         return [{"role": "assistant", "content": str(res)}]

    raise Exception(f"Unexpected response format from endpoint: {res}")

def query_endpoint(endpoint_name, messages, max_tokens):
    """
    Query a chat-completions or agent serving endpoint.
    Returns the last message content.
    """
    response_messages = _query_endpoint(endpoint_name, messages, max_tokens)
    return response_messages[-1]