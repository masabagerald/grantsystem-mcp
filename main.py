import asyncio
import json
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse
from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

app = FastAPI(title="GrantFlow MCP Chat")
templates = Jinja2Templates(directory="templates")
openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
    request,
    "index.html"
)


@app.get("/chat")
async def chat(request: Request, question: str, history: str = "[]"):
    """
    SSE endpoint — streams tool call events and the final answer
    to the browser as they happen.
    """

    async def event_stream():
        try:
            # Parse conversation history from the frontend
            past_messages = json.loads(history)

            server_params = StdioServerParameters(
                command="python",
                args=["server.py"],
                env=dict(os.environ),
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # Discover tools from MCP server
                    tools_response = await session.list_tools()
                    openai_tools = [
                        {
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema,
                            },
                        }
                        for tool in tools_response.tools
                    ]

                    # Emit which tools are available
                    yield {
                        "event": "tools_loaded",
                        "data": json.dumps({
                            "tools": [t.name for t in tools_response.tools]
                        }),
                    }

                    # Build message history
                    messages = [
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful grants management assistant "
                                "with access to the GrantFlow system via tools. "
                                "Answer questions accurately using the available "
                                "tools. Be concise and factual."
                            ),
                        },
                        *past_messages,
                        {"role": "user", "content": question},
                    ]

                    # ── Agentic loop ───────────────────────────
                    while True:
                        # Check if client disconnected
                        if await request.is_disconnected():
                            break

                        response = await openai.chat.completions.create(
                            model="gpt-4o",
                            messages=messages,
                            tools=openai_tools,
                            tool_choice="auto",
                        )

                        message = response.choices[0].message

                        # No tool calls — final answer ready
                        if not message.tool_calls:
                            yield {
                                "event": "answer",
                                "data": json.dumps({
                                    "content": message.content
                                }),
                            }
                            break

                        # Add LLM decision to history
                        messages.append(message)

                        # Process each tool call
                        for tool_call in message.tool_calls:
                            tool_name = tool_call.function.name
                            tool_args = json.loads(
                                tool_call.function.arguments
                            )

                            # Emit: tool call started
                            yield {
                                "event": "tool_call",
                                "data": json.dumps({
                                    "id":   tool_call.id,
                                    "name": tool_name,
                                    "args": tool_args,
                                }),
                            }

                            # Actually call the tool via MCP
                            result = await session.call_tool(
                                tool_name, tool_args
                            )
                            result_text = (
                                result.content[0].text
                                if result.content
                                else "{}"
                            )

                            # Parse result for display
                            try:
                                result_data = json.loads(result_text)
                            except json.JSONDecodeError:
                                result_data = result_text

                            # Emit: tool result received
                            yield {
                                "event": "tool_result",
                                "data": json.dumps({
                                    "id":     tool_call.id,
                                    "name":   tool_name,
                                    "result": result_data,
                                }),
                            }

                            # Add result to message history
                            messages.append({
                                "role":        "tool",
                                "tool_call_id": tool_call.id,
                                "content":     result_text,
                            })

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)}),
            }

    return EventSourceResponse(event_stream())