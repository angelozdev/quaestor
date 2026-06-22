from types import SimpleNamespace

from quaestor.chat.mcp.schema import to_openai_tools


def test_converts_minimal_tool():
    mcp_tools = [
        SimpleNamespace(
            name="list_accounts",
            description="List all accounts.",
            inputSchema={
                "type": "object",
                "properties": {"archived": {"type": "boolean"}},
                "required": [],
            },
        )
    ]
    out = to_openai_tools(mcp_tools)
    assert out == [
        {
            "type": "function",
            "function": {
                "name": "list_accounts",
                "description": "List all accounts.",
                "parameters": mcp_tools[0].inputSchema,
            },
        }
    ]


def test_converts_tool_without_input_schema_uses_empty_object():
    mcp_tools = [
        SimpleNamespace(
            name="noop", description="Does nothing.", inputSchema=None
        )
    ]
    out = to_openai_tools(mcp_tools)
    assert out[0]["function"]["parameters"] == {"type": "object", "properties": {}}


def test_preserves_anyof_and_ref_in_input_schema():
    schema = {
        "type": "object",
        "properties": {
            "tag": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "tx_id": {"$ref": "#/$defs/TxId"},
        },
    }
    mcp_tools = [SimpleNamespace(name="t", description="d", inputSchema=schema)]
    out = to_openai_tools(mcp_tools)
    assert out[0]["function"]["parameters"] == schema