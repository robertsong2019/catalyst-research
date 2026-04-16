# AI Agent Programming Quick Reference

**Cheat sheet for common patterns and code snippets**

---

## 🚀 Framework Quick Start

### LangChain Agent
```python
from langchain.agents import create_agent

agent = create_agent(
    model="gpt-4",
    tools=[tool1, tool2],
    system_prompt="You are a helpful assistant"
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "Your question"}]
})
```

### AutoGen Agent
```python
from autogen_agentchat.agents import AssistantAgent

agent = AssistantAgent(
    "assistant",
    OpenAIChatCompletionClient(model="gpt-4o")
)

result = await agent.run(task="Your task")
```

### CrewAI Crew
```python
from crewai import Agent, Task, Crew, Process

researcher = Agent(role="Researcher", goal="Find info", backstory="Expert")
task = Task(description="Research topic", expected_output="Summary")

crew = Crew(agents=[researcher], tasks=[task], process=Process.sequential)
result = crew.kickoff()
```

---

## 🛠️ Common Tools

### Search Tool
```python
from langchain.tools import Tool

def search(query: str) -> str:
    # Implement search
    return results

search_tool = Tool(
    name="search",
    func=search,
    description="Search the web"
)
```

### Custom Tool
```python
from langchain.tools import BaseTool
from pydantic import BaseModel

class CustomInput(BaseModel):
    param: str

class CustomTool(BaseTool):
    name = "custom"
    description = "Custom tool description"
    args_schema = CustomInput
    
    def _run(self, param: str) -> str:
        return f"Result: {param}"
```

---

## 📝 Memory Patterns

### Conversation Memory
```python
from langchain.memory import ConversationBufferMemory

memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True
)
```

### Vector Store Memory
```python
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings

vectorstore = FAISS.from_texts(
    texts=documents,
    embedding=OpenAIEmbeddings()
)

# Search
results = vectorstore.similarity_search("query", k=5)
```

---

## 🔄 Coordination Patterns

### Sequential Tasks
```python
crew = Crew(
    agents=[agent1, agent2],
    tasks=[task1, task2],
    process=Process.sequential
)
```

### Hierarchical (Manager)
```python
crew = Crew(
    agents=[manager, worker1, worker2],
    tasks=[task],
    process=Process.hierarchical,
    manager_llm="gpt-4"
)
```

### Parallel Execution
```python
import asyncio

results = await asyncio.gather(
    agent1.run(task1),
    agent2.run(task2),
    agent3.run(task3)
)
```

---

## ⚡ Performance Tips

### Caching
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def expensive_operation(query: str):
    return llm.generate(query)
```

### Rate Limiting
```python
import asyncio

class RateLimiter:
    def __init__(self, calls_per_second: int):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
    
    async def wait(self):
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_call = time.time()
```

### Context Management
```python
from langchain.memory import ConversationBufferWindowMemory

# Limit context to last 5 exchanges
memory = ConversationBufferWindowMemory(k=5)
```

---

## 🧪 Testing

### Unit Test Tool
```python
import pytest
from unittest.mock import Mock

def test_tool():
    tool = MyTool()
    result = tool.execute({"input": "test"})
    assert result is not None
```

### Mock LLM
```python
from unittest.mock import patch

@patch('llm.generate')
def test_agent(mock_generate):
    mock_generate.return_value = "Mocked response"
    agent = Agent()
    result = agent.run("test")
    assert mock_generate.called
```

---

## 🔒 Security Snippets

### Input Sanitization
```python
import re

def sanitize_input(text: str) -> str:
    # Remove potential injection patterns
    patterns = [
        r"ignore.*instructions",
        r"system:",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()
```

### Output Filtering
```python
SENSITIVE_PATTERNS = [
    r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
    r'password\s*[:=]\s*\S+',  # Passwords
]

def filter_output(text: str) -> str:
    for pattern in SENSITIVE_PATTERNS:
        text = re.sub(pattern, "[REDACTED]", text)
    return text
```

---

## 📊 Common Metrics

### Track Token Usage
```python
def count_tokens(messages: list, model: str = "gpt-4") -> int:
    encoding = tiktoken.encoding_for_model(model)
    return sum(len(encoding.encode(m.content)) for m in messages)
```

### Calculate Cost
```python
PRICING = {
    "gpt-4": {"input": 0.03, "output": 0.06},  # per 1K tokens
    "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002}
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING[model]
    return (
        (input_tokens / 1000) * rates["input"] +
        (output_tokens / 1000) * rates["output"]
    )
```

---

## 🐛 Debugging

### Enable Verbose Logging
```python
# CrewAI
crew = Crew(agents=[...], tasks=[...], verbose=True)

# LangChain
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Inspect Agent State
```python
def inspect_agent(agent):
    print(f"Role: {agent.role}")
    print(f"Goal: {agent.goal}")
    print(f"Tools: {[t.name for t in agent.tools]}")
    print(f"Memory: {agent.memory}")
```

---

## 📚 Useful Resources

### Documentation
- [LangChain](https://docs.langchain.com)
- [AutoGen](https://microsoft.github.io/autogen/)
- [CrewAI](https://docs.crewai.com)

### Research Papers
- ReAct: arXiv:2210.03629
- Reflexion: arXiv:2303.11366
- Chain of Thought: arXiv:2201.11903

### Community
- [LangChain Discord](https://discord.gg/langchain)
- [AutoGen GitHub](https://github.com/microsoft/autogen)
- [CrewAI Discord](https://discord.gg/crewAI)

---

**Total Documentation:** 7 files, ~150KB of content  
**Coverage:** Frameworks, Architecture, Communication, Coordination, Implementation, Best Practices
