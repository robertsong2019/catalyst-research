# AI Agent Framework Overview

**Focus:** Comprehensive comparison of major AI agent frameworks: LangChain, AutoGen, and CrewAI

---

## 🏗️ Framework Landscape

### LangChain + LangGraph Ecosystem

**What it is:**
- **LangChain**: High-level framework for building LLM applications with prebuilt agent architecture
- **LangGraph**: Low-level orchestration framework and runtime for stateful, long-running workflows
- **Deep Agents**: Batteries-included implementation with advanced features (compression, virtual filesystem, subagent spawning)

**Architecture:**
```
┌──────────────────────────────────────┐
│       Application Layer              │
│   (Agents, Chains, Tools)            │
├──────────────────────────────────────┤
│       LangChain                      │
│   (Model abstraction, Components)    │
├──────────────────────────────────────┤
│       LangGraph                      │
│   (Orchestration, State, Runtime)    │
├──────────────────────────────────────┤
│   Infrastructure (LangSmith)         │
│   (Observability, Deployment)        │
└──────────────────────────────────────┘
```

**Key Features:**
- Standard model interface (swap providers easily)
- Extensive tool integrations
- Built on LangGraph for durability
- Human-in-the-loop support
- Persistence and checkpointing
- Streaming support

**When to use:**
- Quick prototyping of agents
- Need standard LLM + tool calling loops
- Want prebuilt architectures
- Building autonomous applications

**Code Example:**
```python
from langchain.agents import create_agent

# Define custom tool
def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"

# Create agent
agent = create_agent(
    model="claude-sonnet-4-6",
    tools=[get_weather],
    system_prompt="You are a helpful assistant"
)

# Run agent
result = agent.invoke({
    "messages": [{"role": "user", "content": "what is the weather in sf"}]
})
```

**LangGraph Example:**
```python
from langgraph.graph import StateGraph, MessagesState, START, END

def mock_llm(state: MessagesState):
    return {"messages": [{"role": "ai", "content": "hello world"}]}

graph = StateGraph(MessagesState)
graph.add_node(mock_llm)
graph.add_edge(START, "mock_llm")
graph.add_edge("mock_llm", END)
graph = graph.compile()

result = graph.invoke({"messages": [{"role": "user", "content": "hi!"}]})
```

**Core Benefits:**
1. **Durable execution**: Persist through failures, resume from checkpoints
2. **Human-in-the-loop**: Inspect and modify state at any point
3. **Comprehensive memory**: Short-term working + long-term across sessions
4. **Production deployment**: Scalable infrastructure for stateful workflows
5. **Debugging**: LangSmith visualization for execution paths and state transitions

---

## 🤖 Microsoft AutoGen

**What it is:**
A framework for building AI agents and applications with three layers:
1. **AutoGen Studio**: Web-based UI for prototyping (no code)
2. **AgentChat**: Programming framework for conversational agents
3. **Core**: Event-driven framework for scalable multi-agent systems

**Architecture:**
```
┌──────────────────────────────────────┐
│   AutoGen Studio (No-code UI)        │
├──────────────────────────────────────┤
│   AgentChat (Python Framework)       │
│   - Single agents                    │
│   - Multi-agent conversations        │
├──────────────────────────────────────┤
│   AutoGen Core (Event-driven)        │
│   - Scalable multi-agent systems     │
│   - Distributed agents               │
├──────────────────────────────────────┤
│   Extensions                         │
│   - MCP Workbench                    │
│   - Docker execution                 │
│   - GRPC workers                     │
└──────────────────────────────────────┘
```

**Key Features:**
- **Conversational agents**: Natural agent-to-agent communication
- **Event-driven architecture**: Scalable multi-agent orchestration
- **Code execution**: Safe sandboxed execution with Docker
- **Distributed support**: GRPC workers for multi-language/machine setup
- **Model flexibility**: Supports OpenAI, Azure, local models

**When to use:**
- Multi-agent conversation flows
- Research on agent collaboration
- Complex business process automation
- Distributed agent systems

**Code Example:**
```python
import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

async def main() -> None:
    agent = AssistantAgent(
        "assistant", 
        OpenAIChatCompletionClient(model="gpt-4o")
    )
    result = await agent.run(task="Say 'Hello World!'")
    print(result)

asyncio.run(main())
```

**Multi-Agent Example:**
```python
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat

# Create agents
assistant = AssistantAgent("assistant", model_client)
user_proxy = UserProxyAgent("user", work_dir="coding")

# Create team
team = RoundRobinGroupChat([assistant, user_proxy])

# Run conversation
result = await team.run(task="Write a Python script to analyze stock data")
```

**Core Benefits:**
1. **Event-driven**: Scalable for production multi-agent systems
2. **Flexible conversations**: Natural agent-to-agent dialogue
3. **Safe execution**: Docker-based code sandboxing
4. **Distributed**: Multi-machine, multi-language support
5. **MCP integration**: Model Context Protocol for tools

**Components:**
- **AgentChat**: For prototyping with Python
- **Core**: For building scalable systems
- **Extensions**: Community integrations (MCP, Docker, GRPC)
- **Studio**: No-code prototyping interface

---

## 👥 CrewAI

**What it is:**
Framework for building collaborative AI agents, crews, and flows with production-ready features from day one.

**Philosophy:**
- Agents are **specialized team members** with specific skills and expertise
- Crews are **collaborative groups** working together on tasks
- Focus on **role-based collaboration** and human-like teamwork

**Architecture:**
```
┌──────────────────────────────────────┐
│   Crew (Collaborative Group)         │
│   ├─ Process (Sequential/Hierarchy)  │
│   ├─ Memory (Crew-level)             │
│   └─ Knowledge Sources               │
├──────────────────────────────────────┤
│   Agents (Specialized Roles)         │
│   ├─ Role, Goal, Backstory           │
│   ├─ Tools                           │
│   ├─ Memory                          │
│   └─ Delegation ability              │
├──────────────────────────────────────┤
│   Tasks (Assignments)                │
│   ├─ Description                     │
│   ├─ Expected Output                 │
│   ├─ Context (from other tasks)      │
│   └─ Guardrails & Callbacks          │
└──────────────────────────────────────┘
```

**Key Features:**
- **Role-based agents**: Clear specialization and expertise
- **Crew orchestration**: Sequential or hierarchical task execution
- **Memory systems**: Short-term, long-term, entity memory
- **Knowledge sources**: Shared knowledge across crew
- **Guardrails**: Validation and quality control
- **Visual builder**: Enterprise Studio for no-code creation

**When to use:**
- Team-based workflows
- Complex multi-step processes
- Need clear role separation
- Human-in-the-loop workflows

**Code Example:**
```python
from crewai import Agent, Task, Crew, Process

# Define specialized agents
researcher = Agent(
    role="Senior Data Researcher",
    goal="Uncover cutting-edge developments in AI",
    backstory="""You're a seasoned researcher with a knack for 
    uncovering the latest developments. Known for finding the 
    most relevant information.""",
    verbose=True,
    tools=[SerperDevTool()]
)

writer = Agent(
    role="Reporting Analyst",
    goal="Create detailed reports from research",
    backstory="""You're a meticulous analyst with a keen eye 
    for detail. Known for turning complex data into clear 
    and concise reports.""",
    verbose=True
)

# Define tasks
research_task = Task(
    description="Conduct thorough research about AI Agents",
    expected_output="List with 10 bullet points of key information",
    agent=researcher
)

writing_task = Task(
    description="Create a comprehensive report from research",
    expected_output="Full report with sections for each topic",
    agent=writer,
    output_file="report.md"
)

# Create crew
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential
)

# Execute
result = crew.kickoff()
```

**YAML Configuration (Recommended):**
```yaml
# config/agents.yaml
researcher:
  role: >
    {topic} Senior Data Researcher
  goal: >
    Uncover cutting-edge developments in {topic}
  backstory: >
    You're a seasoned researcher with expertise in {topic}

# config/tasks.yaml
research_task:
  description: >
    Conduct thorough research about {topic}
  expected_output: >
    A list with 10 bullet points
  agent: researcher
```

**Process Types:**
1. **Sequential**: Tasks executed in defined order
2. **Hierarchical**: Manager agent assigns based on expertise

**Core Benefits:**
1. **Clear role definition**: Agents have specific expertise
2. **Flexible orchestration**: Sequential or hierarchical
3. **Built-in memory**: Multiple memory types
4. **Enterprise ready**: Visual builder, deployment tools
5. **Human oversight**: Human-in-the-loop support

---

## 📊 Framework Comparison Matrix

| Dimension | LangChain/LangGraph | AutoGen | CrewAI |
|-----------|---------------------|---------|--------|
| **Primary Use Case** | Single agent apps, chains | Multi-agent conversations | Team collaboration |
| **Architecture Style** | Graph-based workflows | Event-driven | Role-based crews |
| **Abstraction Level** | Low (LangGraph) to High (LangChain) | Low to Medium | Medium to High |
| **Agent Communication** | State passing | Natural conversation | Task context |
| **Memory** | Flexible, pluggable | Agent-level | Crew + Agent level |
| **Orchestration** | LangGraph graphs | Event handlers | Process types |
| **Tool Integration** | Extensive (500+) | Moderate | Good |
| **Learning Curve** | Medium | Medium-High | Low-Medium |
| **Production Ready** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Deployment** | LangSmith | Manual/cloud | CrewAI Enterprise |
| **Observability** | LangSmith | Basic | Enterprise features |
| **Best For** | Custom workflows, research | Conversational AI | Business automation |

---

## 🎯 Framework Selection Guide

### Choose LangChain/LangGraph when:
- ✅ Need maximum flexibility and customization
- ✅ Building custom workflows with complex state
- ✅ Want production deployment with LangSmith
- ✅ Require durable execution and checkpointing
- ✅ Building autonomous applications
- ✅ Need extensive tool integrations

### Choose AutoGen when:
- ✅ Building conversational multi-agent systems
- ✅ Need distributed agent deployment
- ✅ Research on agent collaboration
- ✅ Want event-driven architecture
- ✅ Need code execution sandboxing
- ✅ Multi-language/machine setup required

### Choose CrewAI when:
- ✅ Building team-based workflows
- ✅ Need clear role separation
- ✅ Want rapid prototyping
- ✅ Prefer configuration over code (YAML)
- ✅ Business process automation
- ✅ Need visual builder (Enterprise)
- ✅ Human-in-the-loop workflows

---

## 🔧 Integration Patterns

### Hybrid Approaches

**LangChain + AutoGen:**
```python
# Use LangChain tools within AutoGen agents
from langchain.tools import Tool
from autogen_agentchat.agents import AssistantAgent

# Create LangChain tool
langchain_tool = Tool(
    name="search",
    func=search_function,
    description="Search the web"
)

# Use in AutoGen agent
agent = AssistantAgent(
    "assistant",
    model_client,
    tools=[langchain_tool]
)
```

**CrewAI + LangChain Tools:**
```python
from crewai import Agent
from langchain.tools import Tool

# Use LangChain tools in CrewAI
researcher = Agent(
    role="Researcher",
    goal="Find information",
    tools=[langchain_search_tool]
)
```

---

## 📈 Production Considerations

### LangChain/LangGraph
- **Deployment**: LangSmith managed deployment
- **Monitoring**: Built-in observability
- **Scaling**: Horizontal scaling via LangGraph
- **Cost**: Pay per usage (model + infrastructure)

### AutoGen
- **Deployment**: Manual deployment or Azure
- **Monitoring**: Custom logging needed
- **Scaling**: Distributed via GRPC workers
- **Cost**: Model costs + infrastructure

### CrewAI
- **Deployment**: CrewAI Enterprise or custom
- **Monitoring**: Enterprise features available
- **Scaling**: Manual scaling
- **Cost**: Open source (Enterprise paid)

---

## 🚀 Getting Started Paths

### LangChain Path
1. Install: `pip install langchain "langchain[anthropic]"`
2. Start with prebuilt agents
3. Add custom tools
4. Move to LangGraph for complex workflows
5. Deploy with LangSmith

### AutoGen Path
1. Install: `pip install "autogen-agentchat" "autogen-ext[openai]"`
2. Create single agent
3. Build multi-agent conversation
4. Add code execution
5. Scale with Core

### CrewAI Path
1. Install: `crewai create crew` (CLI)
2. Define agents in YAML
3. Define tasks in YAML
4. Create crew class
5. Run and iterate

---

## 📚 Additional Resources

### LangChain
- [Documentation](https://docs.langchain.com)
- [LangGraph Guide](https://docs.langchain.com/oss/python/langgraph/overview)
- [Examples Gallery](https://python.langchain.com/docs/use_cases/)
- [LangSmith](https://www.langchain.com/langsmith)

### AutoGen
- [Official Docs](https://microsoft.github.io/autogen/)
- [GitHub](https://github.com/microsoft/autogen)
- [Research Papers](https://arxiv.org/abs/2308.08155)

### CrewAI
- [Documentation](https://docs.crewai.com)
- [Examples](https://docs.crewai.com/examples/cookbooks)
- [Community](https://community.crewai.com)

---

**Next:** [Agent Architecture Fundamentals](./02-agent-architecture.md)
