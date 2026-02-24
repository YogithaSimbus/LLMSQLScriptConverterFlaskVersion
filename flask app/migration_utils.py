import re
import json
import os
import ast
from model_serving_utils import query_endpoint

# ==========================================
# 1. DYNAMIC PROMPT IMPORT
# ==========================================
# We import the PROMPTS dictionary from each of your files
try:
    from prompts_tsql import PROMPTS as TSQL_PROMPTS, JUDGE_PROMPTS as TSQL_JUDGE_PROMPTS
    from prompts_oracle import PROMPTS as ORACLE_PROMPTS, JUDGE_PROMPTS as ORACLE_JUDGE_PROMPTS
    from prompts_postgres import PROMPTS as POSTGRES_PROMPTS, JUDGE_PROMPTS as POSTGRES_JUDGE_PROMPTS
    from prompts_teradata import PROMPTS as TERADATA_PROMPTS, JUDGE_PROMPTS as TERADATA_JUDGE_PROMPTS
    from prompts_snowflake import PROMPTS as SNOWFLAKE_PROMPTS, JUDGE_PROMPTS as SNOWFLAKE_JUDGE_PROMPTS
except ImportError as e:
    print(f"Warning: Could not import one of the prompt modules. Check filenames. {e}")
    # Fallbacks to prevent crash if a file is missing
    TSQL_PROMPTS = {}
    ORACLE_PROMPTS = {}
    POSTGRES_PROMPTS = {}
    TERADATA_PROMPTS = {}
    SNOWFLAKE_PROMPTS = {}

    TSQL_JUDGE_PROMPTS = {}
    ORACLE_JUDGE_PROMPTS = {}
    POSTGRES_JUDGE_PROMPTS = {}
    TERADATA_JUDGE_PROMPTS = {}
    SNOWFLAKE_JUDGE_PROMPTS = {}

# Registry to map UI selection to prompt sets
PROMPT_REGISTRY = {
    "tsql": TSQL_PROMPTS,
    "oracle": ORACLE_PROMPTS,
    "postgres": POSTGRES_PROMPTS,
    "teradata": TERADATA_PROMPTS,
    "snowflake": SNOWFLAKE_PROMPTS
}

JUDGE_PROMPT_REGISTRY = {
    "tsql": TSQL_JUDGE_PROMPTS,
    "oracle": ORACLE_JUDGE_PROMPTS,
    "postgres": POSTGRES_JUDGE_PROMPTS,
    "teradata": TERADATA_JUDGE_PROMPTS,
    "snowflake": SNOWFLAKE_JUDGE_PROMPTS
}

# ==========================================
# 2. CONFIGURATION
# ==========================================
DEFAULT_CONVERTER_MODEL = os.getenv("SERVING_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")
DEFAULT_JUDGE_MODEL = os.getenv("SERVING_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")

# ==========================================
# 3. JUDGE TEMPLATES (Targeting Databricks SQL)
# ==========================================
# These evaluate the OUTPUT, so they are mostly universal for Delta Lake
JUDGE_TEMPLATES = {
    "TABLE": """
You are an expert Databricks SQL migration auditor.
Evaluate the converted TABLE DDL.

FAIL CONDITIONS (Databricks Delta Lake Incompatibility):
❌ CHECK / UNIQUE constraints inside CREATE TABLE
❌ DEFAULT expressions in CREATE TABLE (Must use ALTER COLUMN SET DEFAULT)
❌ Non-deterministic defaults (UUID, NEWID, RANDOM, SYSDATE)
❌ CLUSTERED / NONCLUSTERED / ORGANIZATION INDEX keywords
❌ PRIMARY KEY with ASC/DESC
❌ Missing `USING DELTA`

PASS CONDITIONS:
✅ Logic is preserved.
✅ Data types are mapped to Spark SQL (e.g., NUMBER/NUMERIC -> DECIMAL, VARCHAR2/TEXT -> STRING).
""",
    "VIEW": """
Evaluate the converted VIEW:
1. Syntax must be `CREATE OR REPLACE VIEW`.
2. No proprietary source syntax (e.g., Oracle `(+)`, T-SQL `WITH SCHEMABINDING`, Postgres `::` cast).
3. Standard ANSI SQL logic used.
""",
    "PROCEDURE": """
Evaluate the converted STORED PROCEDURE:
1. Syntax: `CREATE OR REPLACE PROCEDURE ... LANGUAGE SQL`.
2. Variables: `DECLARE VARIABLE name type`.
3. Flow: Standard `IF/ELSE`, `WHILE`.
4. Transactions: NO `COMMIT`, `ROLLBACK`, `PRAGMA`.
""",
    "FUNCTION": """
Evaluate the converted FUNCTION:
1. UDFs must be `CREATE FUNCTION ... RETURNS type RETURN expression` or `RETURNS TABLE`.
2. No procedural blocks (BEGIN...END) inside Scalar UDFs.
"""
}

GENERIC_JUDGE_TEMPLATE = """
Check for valid Spark SQL syntax. Ensure all source-specific legacy syntax (PL/SQL, T-SQL, ::, etc.) is removed.
"""

# ==========================================
# 4. CORE LOGIC
# ==========================================

def detect_object_type(sql_text: str) -> str:
    """Detects the PRIMARY object type of the SQL script."""
    text = sql_text.upper()
    
    # Priority Order
    if re.search(r"(CREATE|REPLACE)\s+(OR\s+REPLACE\s+)?(PROC|PROCEDURE)", text): return "PROCEDURE"
    if re.search(r"CREATE\s+(OR\s+REPLACE\s+)?FUNCTION", text): return "FUNCTION"
    if re.search(r"CREATE\s+(OR\s+REPLACE\s+)?VIEW", text): return "VIEW"
    if re.search(r"CREATE\s+TYPE", text): return "TYPE"
    if re.search(r"CREATE\s+SEQUENCE", text): return "SEQUENCE"
    if re.search(r"CREATE\s+(OR\s+REPLACE\s+)?TABLE", text): return "TABLE"
    if re.search(r"(CREATE|REPLACE)\s+MACRO", text):return "MACRO"
    if re.search(r"CREATE\s+(OR\s+REPLACE\s+)?(SET\s+|MULTISET\s+)?TABLE", text): return "TABLE"
    
    return "UNKNOWN"

def get_converter_prompt(object_type, source_dialect="tsql"):
    """
    Retrieves the specific prompt for the Dialect + Object Type.
    """
    # 1. Get the dictionary for the selected dialect
    dialect_prompts = PROMPT_REGISTRY.get(source_dialect, TSQL_PROMPTS)
    
    # 2. Get the prompt for the object type (Default to TABLE if missing)
    # Using .get() ensures we don't crash if "SEQUENCE" isn't defined for a dialect
    prompt = dialect_prompts.get(object_type, dialect_prompts.get("TABLE", ""))
    
    if not prompt:
        return f"Error: No prompt defined for {source_dialect} - {object_type}"
        
    return prompt

def get_judge_system_prompt(object_type, source_dialect="tsql"):
    # 1. Fetch dialect-specific prompts
    dialect_prompts = JUDGE_PROMPT_REGISTRY.get(source_dialect, TSQL_JUDGE_PROMPTS)

    # 2. Get specific rule, fallback to generic
    specific_rules = dialect_prompts.get(object_type, JUDGE_TEMPLATES.get(object_type, GENERIC_JUDGE_TEMPLATE))

    return f"""
    You are an expert SQL Migration Auditor.
    Validate the accuracy of the conversion for object type: **{object_type}** from dialect: **{source_dialect}**.
    
    {specific_rules}

    ### SCORING RUBRIC (0.0 to 1.0)
    - 1.0: Perfect Databricks syntax, logic preserved.
    - 0.8: Minor issues but executable.
    - 0.5: Critical logic drift or source syntax remains.
    - 0.0: Hallucination or invalid SQL.

    ### OUTPUT FORMAT (Strict JSON)
    Return ONLY valid JSON.
    {{
        "overall_score": <float>,
        "summary_reasoning": "<concise text>",
        "critical_errors": ["<list strings>"],
        "improvements_required": ["<list strings>"]
    }}
    """

def post_process_cleaner(sql: str) -> str:
    # Basic cleanup
    sql = sql.replace("```sql", "").replace("```", "").strip()
    
    # Safety Guards (Universal)
    sql = re.sub(r"(?i)DEFAULT\s+UUID\s*\(\s*\)", "", sql)
    sql = re.sub(r"(?i)DEFAULT\s+NEWID\s*\(\s*\)", "", sql)
    sql = re.sub(r"(?i)DEFAULT\s+SYSDATE", "", sql) 
    
    return sql

def extract_json_from_text(text):
    try: return json.loads(text)
    except: pass
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match: return json.loads(match.group(0))
    except: pass
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match: return ast.literal_eval(match.group(0))
    except: pass
    return None

# ==========================================
# 5. MODEL SERVING INTERFACE
# ==========================================

def call_llm(endpoint_name, system_prompt, user_content, max_tokens=4000):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    try:
        response_message = query_endpoint(endpoint_name, messages, max_tokens)
        return response_message["content"]
    except Exception as e:
        return f"Error calling model: {str(e)}"

# ==========================================
# 6. PIPELINE WRAPPERS
# ==========================================

def run_conversion_pipeline(sql_input, source_dialect="tsql"):
    obj_type = detect_object_type(sql_input)
    # Pass the source_dialect to fetch the correct prompt
    prompt = get_converter_prompt(obj_type, source_dialect)
    raw_spark_sql = call_llm(DEFAULT_CONVERTER_MODEL, prompt, sql_input)
    return post_process_cleaner(raw_spark_sql)

def run_accuracy_judge(original_sql, converted_sql, source_dialect="tsql"):
    obj_type = detect_object_type(original_sql)
    judge_prompt = get_judge_system_prompt(obj_type, source_dialect)
    judge_payload = f"ORIGINAL:\n{original_sql}\n\nCONVERTED:\n{converted_sql}"
    
    response_str = call_llm(DEFAULT_JUDGE_MODEL, judge_prompt, judge_payload)
    
    if response_str.startswith("Error calling model"):
        return {
            "overall_score": 0.0,
            "summary_reasoning": f"Endpoint Error: {DEFAULT_JUDGE_MODEL}",
            "critical_errors": ["Endpoint Offline"],
            "object_type_detected": obj_type
        }

    json_data = extract_json_from_text(response_str)
    
    if json_data:
        json_data["object_type_detected"] = obj_type 
        return json_data
    else:
        return {
            "overall_score": 0.0,
            "summary_reasoning": "Model returned invalid format.",
            "critical_errors": ["JSON Parse Error"],
            "raw_response": response_str,
            "object_type_detected": obj_type
        }

def run_iterative_pipeline(sql_input, source_dialect="tsql", max_retries=2, threshold=0.9):
    for attempt in range(1, max_retries + 1):
        # 1. Convert (Pass dialect)
        current_sql = run_conversion_pipeline(sql_input, source_dialect)
        
        # 2. Judge
        current_judge = run_accuracy_judge(sql_input, current_sql, source_dialect)
        score = current_judge.get("overall_score", 0.0)
        
        if score >= threshold:
            return {"final_sql": current_sql, "final_judge": current_judge, "attempts": attempt}
            
    return {"final_sql": current_sql, "final_judge": current_judge, "attempts": max_retries}