import asyncio
import os
import json
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

load_dotenv()

openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def run_agent(question: str):
    """
    Connect to the MCP server, load its tools, and run an agent
    that answers the question using GrantFlow data.
    """

    # ── Connect to MCP server via stdio ───────────────────────
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
        env=None,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            # Initialise the MCP session
            await session.initialize()

            # ── Discover tools from the server ─────────────────
            tools_response = await session.list_tools()

            # Convert MCP tool definitions to OpenAI tool format
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

            print(f"\nConnected to GrantFlow MCP server.")
            print(f"Available tools: {[t.name for t in tools_response.tools]}\n")
            print(f"Question: {question}\n")
            print("─" * 60)

            # ── Agentic loop ───────────────────────────────────
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful grants management assistant with access "
                        "to the GrantFlow system via tools. "
                        "Answer questions accurately using the available tools. "
                        "When you need data, call the appropriate tool. "
                        "Be concise and factual in your final answer."
                    ),
                },
                {
                    "role": "user",
                    "content": question,
                },
            ]

            # Loop until the model stops calling tools
            while True:
                response = await openai.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                )

                message = response.choices[0].message

                # No tool calls — model has a final answer
                if not message.tool_calls:
                    print(f"\nAnswer:\n{message.content}")
                    return message.content

                # Process each tool call
                messages.append(message)

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    print(f"  → calling {tool_name}({tool_args})")

                    # Call the tool via MCP
                    result = await session.call_tool(tool_name, tool_args)
                    result_text = result.content[0].text if result.content else "{}"

                    print(f"  ← {result_text[:120]}{'...' if len(result_text) > 120 else ''}")

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_text,
                    })


async def interactive_session():
    """Run an interactive Q&A session against your GrantFlow data."""

    print("GrantFlow MCP Client")
    print("=" * 60)
    print("Ask questions about your grants, budgets, reports,")
    print("subgrantees, and disbursements in plain English.")
    print("Type 'quit' to exit.\n")

    questions = [
        "How many active grants do we currently have?",
        "Which subgrantees are in the Northern region?",
        "What is the budget summary for grant ID 1?",
        "Show me all pending disbursements for grant 1.",
        "List all reports that have been submitted but not yet approved.",
    ]

    print("Sample questions you can ask:")
    for i, q in enumerate(questions, 1):
        print(f"  {i}. {q}")
    print()

    while True:
        question = input("Your question: ").strip()
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue

        try:
            await run_agent(question)
        except Exception as e:
            print(f"Error: {e}")

        print("\n" + "─" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(interactive_session())