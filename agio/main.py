import asyncio


async def main():
    # example api usage

    from agio.agent import Agent
    from agio.models import Deepseek
    from agio.tools import Tool
    from agio.knowledge import Knowledge
    from agio.db import DB
    from agio.memory import Memory

    class SearchTool(Tool):
        def __init__(self):
            super().__init__(
                name="search", description="Search the web for information"
            )

        async def execute(self, query: str | list[str]) -> str:
            # demo code, replace with your own implementation
            return "Search the web for information"

    from agio.tools.libs import McpTool_GoogleDocs, McpTool_GoogleSheets

    llm = Deepseek(
        model="deepseek-chat",
        max_tokens=4096,
        temperature=0.3,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None,
    )
    agent = Agent(
        model=llm,
        tools=[
            SearchTool(),
            McpTool_GoogleDocs(),
            McpTool_GoogleSheets(),
        ],
        knowledge=Knowledge(
            embeddings=OpenAIEmbeddings(
                model="text-embedding-3-small", dimensions=1536
            ),
            vector_store=Chroma(collection_name="agio"),
        ),
        db=MongoDBStorage(database_name="agio"),
        memory=SimpleMemory(writer=SimpleMemoryWriter(), retriever=SimpleMemoryRetriever()),
        max_history=10,
        
        stream=False,
        verbose=False,
    )

    async_stream_chunk = await agent.arun("Hello, how are you?")

    async for chunk in async_stream_chunk:
        yield chunk
    agent_id = agent.id
    print(f"agent_id: {agent_id}")
    # 基于历史所有 Agent 的对话轮次， 汇总的指标数据
    # token_stats: prompt tokens, completion tokens, total tokens
    # tool_stats: tool calls, tool call success rate, tool_call_distribution {tool-> cnt, avg_time}
    # llm_stats: llm calls, llm call success rate
    # errors: list[AgentRunError]
    # first_token_time
    # duration
    metrics: AgentMetrics = await agent.metrics()
    print(f"metrics: {metrics}")

    # 基于历史所有Agent的对话轮次，生成的总结报告（异步生成，每步触发）
    summary: AgentRunSummary = await agent.summary()
    print(f"summary: {summary}")

    # 基于历史所有 Agent 对话轮次，生成 Agent 的记忆内容（异步生成，异步记录，最终记录的会同步写入这个字段中）
    memoried_content: list[AgentMemoriedContent] = await agent.list_memoried()
    print(f"memoried_content: {memoried_content}")

    runs: list[AgentRun] = await agent.list_runs()
    print(f"runs: {runs}")

    for run in runs: # each turn is one user raw query & agent work out trajectory
        run_id = run.id
        print(f"run_id: {run_id}")
        steps: list[AgentRunStep] = await run.list_steps()
        print(f"steps: {steps}")

        # 基于在一轮对话中， 所有 step 汇总后的指标数据（同步生成，每步累加）
        metrics: AgentRunMetrics = await run.metrics()
        print(f"metrics: {metrics}")
        # 基于在一轮对话中， 所有 step 汇总后的总结报告（异步生成）
        summary: AgentRunSummary = await run.summary()
        print(f"summary: {summary}")

        for step in steps:  # each step is one llm call & toolcalls execute
            step_id = step.id
            print(step_id)
            # model, config params, messages, step_id, run_id, agent_id, created_at, ext
            raw_request = step.raw_request()
            print(raw_request)
            # assistant_message(content|thinking), toolcalls, token_usage, error, finish_reason, first_token_time, duration
            raw_response = step.raw_response()
            print(raw_response)
            # 工具执行的结果
            # 每个 ToolResult 记录了入参、成功失败、耗时、返回结果（for_llm, for_user）, 可用于分析工具执行的性能和效果 & 前端展示
            tool_results: list[ToolResult] = step.tool_results()
            print(f"tool_results: {tool_results}")
            
    

if __name__ == "__main__":
    print("Hello, World!")
