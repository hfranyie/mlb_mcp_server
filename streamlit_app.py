"""
Streamlit chat UI that prefers Strands (agent) and falls back if it can't import.
- Launches mlb_mcp_server.py via MCP STDIO (same style as your CLI agent)
- If Strands loads: use Strands Agent + Bedrock
- Else: Bedrock-only planner -> call MCP tool -> summarize

Env (.env):
  AWS_REGION=us-east-1
  BEDROCK_MODEL_ID=us.anthropic.claude-3-7-sonnet-20250219-v1:0
  SERVER_CMD=uv run mcp run mlb_mcp_server.py   # default if not set; mirrors your CLI agent
"""

import os, json
from pathlib import Path
from typing import Any, Dict, Optional, List

import streamlit as st
from dotenv import load_dotenv

# ---- Try Strands. If it fails, we won't crash the app. ----
STRANDS_OK = True
STRANDS_ERR = None
try:
    from strands import Agent as StrandsAgent
    from strands.models import BedrockModel as StrandsBedrockModel
    from strands.tools.mcp import MCPClient  # only used when STRANDS_OK
except Exception as e:
    STRANDS_OK = False
    STRANDS_ERR = e
    MCPClient = None  # type: ignore

# MCP STDIO client (used in both Strands and fallback modes)
from mcp.client.stdio import stdio_client, StdioServerParameters

# Bedrock client (used by Strands and the fallback)
import boto3


# -------------------------
# Tool schema normalization
# -------------------------
def _tool_to_schema(t):
    """Return a dict {name, description, parameters} regardless of object type."""
    if isinstance(t, dict):
        name = t.get("name") or t.get("tool_name") or getattr(t, "name", None)
        desc = t.get("description") or t.get("desc", "") or ""
        params = t.get("parameters") or t.get("args_schema") or {}
        if hasattr(params, "model_json_schema"):
            params = params.model_json_schema()
        return {"name": name, "description": desc, "parameters": params}

    # Pydantic-like
    if hasattr(t, "model_dump"):
        return _tool_to_schema(t.model_dump())
    if hasattr(t, "dict"):
        return _tool_to_schema(t.dict())

    # Plain object
    name = getattr(t, "name", None)
    desc = getattr(t, "description", "") or getattr(t, "desc", "") or ""
    params = getattr(t, "parameters", None) or getattr(t, "args_schema", None) or {}
    if hasattr(params, "model_json_schema"):
        params = params.model_json_schema()
    return {"name": name, "description": desc, "parameters": params}


def _tools_to_schema(tools):
    return [_tool_to_schema(t) for t in tools]


def _build_client_factory():
    return lambda: stdio_client(
        StdioServerParameters(command=SERVER_CMD[0], args=SERVER_CMD[1:])
    )


# -------------------------
# Fallback planner helpers
# -------------------------
FALLBACK_SYS = """You are an MLB stats assistant with tools.
Return ONE JSON object only:

1) Tool call:
{"tool_name": "<name>", "args": {...}, "reason": "..."}

OR

2) Direct answer:
{"final": "<text>"}

Use exactly one tool if helpful. If required params are missing, reply with {"final": "..."} asking for them.
Keep answers concise and strictly based on tool outputs (no fabrication).
"""


def br_client(region: str):
    return boto3.client("bedrock-runtime", region_name=region)


def br_plan(
    brt, model_id: str, tools_schema: List[Dict[str, Any]], user_msg: str
) -> Dict[str, Any]:
    body = {
        "system": FALLBACK_SYS,
        "messages": [
            {
                "role": "user",
                "content": (
                    "TOOLS:\n"
                    + json.dumps(tools_schema, indent=2)
                    + "\n\nUSER:\n"
                    + user_msg
                    + "\nReturn ONLY one JSON object."
                ),
            }
        ],
        "max_output_tokens": 900,
        "temperature": 0.1,
    }
    r = brt.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body).encode(),
    )
    out = json.loads(r["body"].read().decode())
    text = (
        out.get("output", {}).get("message", {}).get("content", [{}])[0].get("text")
        or out.get("content")
        or json.dumps(out)
    )
    try:
        return json.loads(text)
    except Exception:
        return {"final": f"Could not parse model JSON: {text[:400]}"}


def br_reflect(
    brt,
    model_id: str,
    user_msg: str,
    tool_name: str,
    tool_args: Dict[str, Any],
    tool_result: Any,
) -> str:
    body = {
        "system": "Summarize the tool result concisely for the user.",
        "messages": [
            {
                "role": "user",
                "content": (
                    f"USER: {user_msg}\n\n"
                    f"TOOL: {tool_name}\n"
                    f"ARGS: {json.dumps(tool_args)}\n"
                    f"RESULT: {json.dumps(tool_result)}"
                ),
            }
        ],
        "max_output_tokens": 600,
        "temperature": 0.1,
    }
    r = brt.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body).encode(),
    )
    out = json.loads(r["body"].read().decode())
    return (
        out.get("output", {})
        .get("message", {})
        .get("content", [{}])[0]
        .get("text", json.dumps(out))
    )


# -------------------------
# App setup
# -------------------------
st.set_page_config(page_title="MLB Agent (Chat)", page_icon="⚾", layout="wide")
load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
)
SERVER_CMD_ENV = os.getenv("SERVER_CMD", "uv run mcp run mlb_mcp_server.py").strip()
SERVER_CMD = SERVER_CMD_ENV.split()

# MLB-focused system prompt (Strands mode)
SYSTEM_PROMPT = """You are an MLB stats assistant. You have access to MCP tools discovered at runtime
from the mlb_mcp_server (e.g., date, standings, linescore, boxscore, roster, team_leaders,
next_game, game_highlight_data). Plan minimal tool calls to answer user questions about teams,
games, standings context, leaders, rosters, and highlights.

GUIDELINES
- Use ONLY tools that are actually discovered; do not invent tools or fields.
- Validate required parameters BEFORE calling a tool (e.g., require numeric teamID if the tool needs it).
- If season is optional, default to the current season when user hasn’t specified.
- Keep answers short and practical; include key numbers and brief context.
- Never fabricate stats or box scores; summarize strictly from tool output.
"""


# -------------------------
# State
# -------------------------
if "mcp_client" not in st.session_state:
    st.session_state.mcp_client = None
if "agent_mode" not in st.session_state:
    st.session_state.agent_mode = None  # "strands" | "fallback"
if "agent_obj" not in st.session_state:
    st.session_state.agent_obj = None  # StrandsAgent OR bedrock client
if "tools_native" not in st.session_state:
    st.session_state.tools_native = []  # keep original objects for Strands agent
if "tools_schema" not in st.session_state:
    st.session_state.tools_schema = []  # normalized dicts for UI/planner
if "chat" not in st.session_state:
    st.session_state.chat = []


# -------------------------
# MCP bootstrap
# -------------------------
def start_mcp():
    # If you want to sanity-check file presence, uncomment:
    # if not Path("mlb_mcp_server.py").exists():
    #     st.error("mlb_mcp_server.py not found next to this app.")
    #     st.stop()

    if STRANDS_OK:
        mcp_cli = MCPClient(_build_client_factory())
        mcp_cli.__enter__()
        return mcp_cli
    else:
        # Minimal shim exposing list_tools_sync / call_tool_sync using stdio client
        class _Shim:
            def __init__(self):
                self._inner = stdio_client(
                    StdioServerParameters(command=SERVER_CMD[0], args=SERVER_CMD[1:])
                )
                self._conn = None

            def __enter__(self):
                self._conn = self._inner.__enter__()
                return self

            def __exit__(self, exc_type, exc, tb):
                return self._inner.__exit__(exc_type, exc, tb)

            def list_tools_sync(self):
                return self._conn.list_tools()

            def call_tool_sync(self, name: str, **kwargs):
                return self._conn.call_tool(name, arguments=kwargs)

        sh = _Shim()
        sh.__enter__()
        return sh


def discover_tools(mcp_client):
    tools_native = mcp_client.list_tools_sync()  # native objects
    tools_schema = _tools_to_schema(tools_native)  # safe dicts
    return tools_native, tools_schema


# -------------------------
# Connect / Disconnect
# -------------------------
def connect():
    if st.session_state.agent_mode is not None:
        return

    mcp_cli = start_mcp()
    st.session_state.mcp_client = mcp_cli

    tools_native, tools_schema = discover_tools(mcp_cli)
    st.session_state.tools_native = tools_native
    st.session_state.tools_schema = tools_schema

    if STRANDS_OK:
        model = StrandsBedrockModel(model_id=BEDROCK_MODEL_ID, region=AWS_REGION)
        agent = StrandsAgent(
            model=model,
            tools=tools_native,  # pass native objects
            system_prompt=SYSTEM_PROMPT,
        )
        st.session_state.agent_mode = "strands"
        st.session_state.agent_obj = agent
    else:
        st.session_state.agent_mode = "fallback"
        st.session_state.agent_obj = br_client(AWS_REGION)


def disconnect():
    if st.session_state.mcp_client:
        try:
            st.session_state.mcp_client.__exit__(None, None, None)
        except Exception:
            pass
    st.session_state.mcp_client = None
    st.session_state.agent_mode = None
    st.session_state.agent_obj = None
    st.session_state.tools_native = []
    st.session_state.tools_schema = []


# -------------------------
# Sidebar
# -------------------------
st.sidebar.header("⚾ MLB Agent")
c1, c2 = st.sidebar.columns(2)
c1.text_input("AWS Region", AWS_REGION, disabled=True)
c2.text_input("Model", BEDROCK_MODEL_ID.split(":")[0], disabled=True)
st.sidebar.text_input("Server command", SERVER_CMD_ENV, disabled=True)

connected = st.sidebar.toggle(
    "Start agent (launch MCP server)", value=False, key="connect_toggle"
)
if connected:
    try:
        connect()
        if st.session_state.agent_mode == "strands":
            st.sidebar.success(
                f"Connected • Strands agent • {len(st.session_state.tools_schema)} tools"
            )
        else:
            msg = (
                f"Connected • Fallback planner (Strands import failed: {type(STRANDS_ERR).__name__})"
                if STRANDS_ERR
                else "Connected • Fallback planner"
            )
            st.sidebar.warning(msg)
            st.sidebar.caption("You can still use the MCP tools; fix Strands later.")
        if st.sidebar.button("Stop agent"):
            disconnect()
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Failed to start: {e}")
else:
    if st.session_state.agent_mode is not None:
        disconnect()

with st.sidebar.expander("Discovered tools"):
    if st.session_state.tools_schema:
        st.code(json.dumps(st.session_state.tools_schema, indent=2))
    else:
        st.caption("(connect to list tools)")


# Guard before chat UI
if st.session_state.agent_mode is None:
    st.title("⚾ MLB Agent — Chat UI")
    info = "Toggle **Start agent** in the sidebar to begin."
    if not STRANDS_OK:
        info += " (Strands import failing; running fallback if you connect.)"
    st.info(info)
    st.stop()


# -------------------------
# Chat UI
# -------------------------
st.title("⚾ MLB Agent — Chat UI")
st.caption("Ask MLB questions; the agent will call MCP tools as needed (STDIO).")

# Render history
for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        if msg["role"] == "tool":
            st.markdown("**Tool call**")
        st.write(msg["content"])
        if msg.get("extra") is not None:
            with st.expander("details"):
                st.json(msg["extra"])

# Input
prompt = st.chat_input(
    "e.g., 'Standings today', 'Roster for LAD (2024)', 'Team leaders ATL homeRuns (2024)', 'Boxscore gamePk 716663'"
)

if prompt:
    st.session_state.chat.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    try:
        if st.session_state.agent_mode == "strands":
            # Strands agent plans & calls tools internally
            resp = st.session_state.agent_obj(prompt)
            text = resp.get("text") if isinstance(resp, dict) else str(resp)
            st.session_state.chat.append({"role": "assistant", "content": text})
            with st.chat_message("assistant"):
                st.write(text)

        else:
            # Fallback: plan -> call tool -> summarize
            brt = st.session_state.agent_obj
            tools_schema = st.session_state.tools_schema
            plan = br_plan(brt, BEDROCK_MODEL_ID, tools_schema, prompt)

            if "final" in plan:
                st.session_state.chat.append(
                    {"role": "assistant", "content": plan["final"]}
                )
                with st.chat_message("assistant"):
                    st.write(plan["final"])
            else:
                tname = plan.get("tool_name")
                targs = plan.get("args", {}) or {}
                if not tname:
                    msg = "Planner did not choose a tool. Provide missing parameters and try again."
                    st.session_state.chat.append({"role": "assistant", "content": msg})
                    with st.chat_message("assistant"):
                        st.warning(msg)
                else:
                    res = st.session_state.mcp_client.call_tool_sync(tname, **targs)
                    st.session_state.chat.append(
                        {
                            "role": "tool",
                            "content": tname,
                            "extra": {"args": targs, "result": res},
                        }
                    )
                    with st.chat_message("tool"):
                        st.write(tname)
                        st.json({"args": targs, "result": res})

                    final_text = br_reflect(
                        brt, BEDROCK_MODEL_ID, prompt, tname, targs, res
                    )
                    st.session_state.chat.append(
                        {"role": "assistant", "content": final_text}
                    )
                    with st.chat_message("assistant"):
                        st.write(final_text)

    except Exception as e:
        err = f"Error: {e}"
        st.session_state.chat.append({"role": "assistant", "content": err})
        with st.chat_message("assistant"):
            st.error(err)
