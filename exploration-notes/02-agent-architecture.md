# Agent Architecture Fundamentals

**Focus:** Core components of AI agent systems - Planning, Memory, and Tool Use

---

## 🧠 Agent System Architecture

Based on Lilian Weng's comprehensive research, an LLM-powered autonomous agent consists of three core components:

```
┌────────────────────────────────────────────────────┐
│       LLM-Powered Autonomous Agent                 │
├────────────────────────────────────────────────────┤
│                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ PLANNING │  │  MEMORY  │  │ TOOL USE │        │
│  ├──────────┤  ├──────────┤  ├──────────┤        │
│  │Decompose │  │Short-term│  │  APIs    │        │
│  │Reflect   │  │Long-term │  │  Code    │        │
│  │Refine    │  │Vectors   │  │  Search  │        │
│  └──────────┘  └──────────┘  └──────────┘        │
│                                                    │
│  ┌─────────────────────────────────────────┐      │
│  │           LLM (Brain)                   │      │
│  │   - Reasoning & Decision Making         │      │
│  │   - Natural Language Understanding      │      │
│  └─────────────────────────────────────────┘      │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## 🎯 Component 1: Planning

### Overview

Planning enables agents to:
1. **Decompose** complex tasks into manageable subgoals
2. **Reflect** on past actions and learn from mistakes
3. **Refine** strategies based on feedback

### 1.1 Task Decomposition

#### Chain of Thought (CoT)

**Concept:** Instruct model to "think step by step" to decompose hard tasks.

**Mechanism:**
```
Task: "Write a blog post about AI agents"

Chain of Thought:
1. Research current AI agent technologies
2. Identify key topics to cover
3. Outline the blog structure
4. Write introduction
5. Write main content sections
6. Write conclusion
7. Review and edit
```

**When to use:**
- Complex multi-step tasks
- Tasks requiring explicit reasoning
- Need to interpret model's thinking

**Implementation:**
```python
# Simple CoT prompting
prompt = """
Question: {question}

Let's think step by step:
1. First, we need to understand...
2. Then, we should consider...
3. Finally, we can conclude...
"""

# Tree of Thoughts (advanced)
from langchain.prompts import PromptTemplate

tot_prompt = PromptTemplate(
    template="""
    Imagine three different experts answering this question.
    Each expert will write one step of their thinking.
    Then, all experts will discuss and vote on the best approach.
    
    Question: {question}
    """,
    input_variables=["question"]
)
```

#### Tree of Thoughts (ToT)

**Concept:** Extends CoT by exploring multiple reasoning paths simultaneously.

**Architecture:**
```
                    Root (Problem)
                   /      |      \
              Thought1  Thought2  Thought3
                /  \       |         \
          Action1 Action2 Action3   Action4
            |       |       |         |
          Eval1   Eval2   Eval3     Eval4
            ↓       ↓       ↓         ↓
         Select best path (BFS/DFS)
```

**Key Features:**
- Multiple thought branches per step
- Search algorithms (BFS or DFS)
- State evaluation (classifier or voting)
- Backtracking capability

**When to use:**
- Tasks with multiple valid solutions
- Need to explore alternatives
- Complex decision-making

**Example:**
```python
# Conceptual ToT implementation
class TreeOfThoughts:
    def __init__(self, llm, num_thoughts=3):
        self.llm = llm
        self.num_thoughts = num_thoughts
    
    def generate_thoughts(self, state):
        """Generate multiple thought branches"""
        thoughts = []
        for i in range(self.num_thoughts):
            thought = self.llm.generate(
                f"Given state: {state}, "
                f"generate thought #{i+1}"
            )
            thoughts.append(thought)
        return thoughts
    
    def evaluate_state(self, state):
        """Evaluate quality of current state"""
        return self.llm.generate(
            f"Evaluate this state from 0-10: {state}"
        )
    
    def search(self, problem, depth=3):
        """BFS or DFS through thought tree"""
        # Implementation of tree search
        pass
```

#### LLM+P (Classical Planning)

**Concept:** Use external classical planner with PDDL (Planning Domain Definition Language).

**Workflow:**
```
1. LLM translates problem → "Problem PDDL"
2. Classical planner generates PDDL plan
3. LLM translates PDDL plan → Natural language
```

**When to use:**
- Robotic planning
- Long-horizon tasks
- Domain-specific planning available

### 1.2 Self-Reflection

#### ReAct (Reasoning + Acting)

**Concept:** Integrate reasoning traces with task-specific actions.

**Pattern:**
```
Thought: I need to find information about AI agents
Action: Search[AI agent frameworks]
Observation: [Search results showing LangChain, AutoGen, CrewAI]
Thought: I found three major frameworks. I should compare them.
Action: Search[LangChain vs AutoGen vs CrewAI comparison]
Observation: [Comparison articles]
Thought: I have enough information to answer the question
Action: Finish[Here's the comparison of the three frameworks...]
```

**Implementation:**
```python
from langchain.agents import initialize_agent, Tool
from langchain.llms import OpenAI

# Define tools
tools = [
    Tool(
        name="Search",
        func=search_function,
        description="Search for information"
    ),
    Tool(
        name="Calculator",
        func=calculator_function,
        description="Perform calculations"
    )
]

# Create ReAct agent
agent = initialize_agent(
    tools=tools,
    llm=OpenAI(),
    agent="zero-shot-react-description",
    verbose=True
)

# Run agent
result = agent.run("What is 2^10 plus 100?")
```

**Key Components:**
1. **Thought**: Reasoning in natural language
2. **Action**: Tool or environment interaction
3. **Observation**: Result of action
4. **Iteration**: Repeat until goal achieved

**Advantages:**
- Interpretable reasoning
- Better performance than action-only
- Flexible action space
- Handles uncertainty

#### Reflexion

**Concept:** Dynamic memory + self-reflection to improve reasoning.

**Architecture:**
```
┌──────────────────────────────────────┐
│   Reflexion Framework                │
├──────────────────────────────────────┤
│  1. Actor: Takes actions             │
│  2. Evaluator: Binary reward         │
│  3. Self-Reflection: Generate        │
│     insights from failures           │
│  4. Memory: Store reflections        │
└──────────────────────────────────────┘
```

**Process:**
1. Agent takes action sequence
2. Evaluator provides reward
3. If failed, generate self-reflection
4. Add reflection to working memory
5. Restart with reflections as context
6. Repeat until success or max trials

**Key Innovation:**
- Learn from failures
- Store reflections in memory
- Use past reflections to guide future actions

**Implementation:**
```python
class ReflexionAgent:
    def __init__(self, llm, max_trials=3):
        self.llm = llm
        self.max_trials = max_trials
        self.reflections = []
    
    def act(self, task):
        """Take action on task"""
        context = self._build_context(task)
        return self.llm.generate(context)
    
    def reflect(self, trajectory, failure_reason):
        """Generate reflection from failure"""
        prompt = f"""
        Task failed: {failure_reason}
        Trajectory: {trajectory}
        
        What went wrong and how can we improve?
        """
        reflection = self.llm.generate(prompt)
        self.reflections.append(reflection)
        return reflection
    
    def run(self, task):
        """Run with reflection loop"""
        for trial in range(self.max_trials):
            result = self.act(task)
            if self._is_successful(result):
                return result
            self.reflect(result, "Task failed")
        return self.act(task)  # Final attempt
```

#### Chain of Hindsight (CoH)

**Concept:** Present sequence of improved outputs with feedback.

**Training Data Format:**
```
(x, z_1, y_1, z_2, y_2, ..., z_n, y_n)

x = prompt
y_i = model completion
z_i = human feedback
r_i = rating (r_n >= r_{n-1} >= ... >= r_1)
```

**How it works:**
1. Collect outputs with human feedback
2. Rank by quality
3. Train model to predict best output given history
4. Model learns to improve from feedback pattern

**Key Insight:**
- Model learns improvement trajectory
- Can generalize to new tasks
- No explicit reward model needed at inference

#### Algorithm Distillation (AD)

**Concept:** Learn RL algorithm from cross-episode trajectories.

**Approach:**
```
Episode 1: Poor performance →
Episode 2: Better performance →
Episode 3: Even better →
...
Episode N: Near-optimal

Train on concatenated history →
Model learns the learning algorithm itself
```

**Key Features:**
- In-context RL (no weight updates)
- Task-agnostic policy
- Learns exploration strategy
- Improves over episodes

---

## 💾 Component 2: Memory

### Memory Types

#### Human Memory Analogy

```
┌──────────────────────────────────────────┐
│          Human Memory System             │
├──────────────────────────────────────────┤
│                                          │
│  Sensory Memory (milliseconds)          │
│  ├─ Iconic (visual)                      │
│  ├─ Echoic (auditory)                    │
│  └─ Haptic (touch)                       │
│                                          │
│  Short-Term Memory (20-30 seconds)      │
│  └─ Capacity: ~7 items (Miller's Law)   │
│                                          │
│  Long-Term Memory (days to decades)     │
│  ├─ Explicit/Declarative                 │
│  │  ├─ Episodic (events/experiences)    │
│  │  └─ Semantic (facts/concepts)        │
│  └─ Implicit/Procedural                  │
│     └─ Skills/routines (riding bike)    │
│                                          │
└──────────────────────────────────────────┘
```

#### Agent Memory Mapping

```
┌──────────────────────────────────────────┐
│          Agent Memory System             │
├──────────────────────────────────────────┤
│                                          │
│  Sensory Memory                          │
│  └─ Embedding representations           │
│     (text, image, audio embeddings)     │
│                                          │
│  Short-Term Memory                      │
│  └─ In-context learning                 │
│     (limited by context window)         │
│                                          │
│  Long-Term Memory                       │
│  └─ External vector store               │
│     (unlimited capacity, fast retrieval)│
│                                          │
└──────────────────────────────────────────┘
```

### Short-Term Memory (In-Context Learning)

**Characteristics:**
- Limited by context window (4K - 200K tokens)
- Fast access (no retrieval needed)
- Temporary (lost after conversation)
- Used for current task reasoning

**Implementation:**
```python
# LangChain example
from langchain.memory import ConversationBufferMemory

memory = ConversationBufferMemory(
    return_messages=True,
    memory_key="chat_history"
)

# Add to conversation
memory.save_context(
    {"input": "Hi, I'm working on AI agents"},
    {"output": "Great! What aspect interests you?"}
)

# Retrieve context
history = memory.load_memory_variables({})
# {"chat_history": [HumanMessage(...), AIMessage(...)]}
```

**Optimization Strategies:**
1. **Sliding window**: Keep only recent N messages
2. **Summarization**: Compress older messages
3. **Entity extraction**: Track key entities
4. **Token management**: Respect context limits

### Long-Term Memory (Vector Stores)

**Purpose:**
- Store information beyond context window
- Enable retrieval of relevant memories
- Support learning across sessions
- Build persistent knowledge

**Vector Store Architecture:**
```
┌──────────────────────────────────────┐
│   Vector Store Memory System         │
├──────────────────────────────────────┤
│                                      │
│  1. Encoding                         │
│     Text → Embedding Model → Vector  │
│                                      │
│  2. Storage                          │
│     Vector + Metadata → Database     │
│                                      │
│  3. Retrieval                        │
│     Query → Similarity Search        │
│                                      │
│  4. Ranking                          │
│     Top-k most similar               │
│                                      │
└──────────────────────────────────────┘
```

**Implementation:**
```python
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings

# Initialize
embeddings = OpenAIEmbeddings()
vectorstore = Chroma(
    embedding_function=embeddings,
    persist_directory="./chroma_db"
)

# Store memories
vectorstore.add_texts(
    texts=["User prefers Python", "User works at Google"],
    metadatas=[{"type": "preference"}, {"type": "fact"}]
)

# Retrieve relevant memories
relevant = vectorstore.similarity_search(
    "What programming languages?",
    k=3
)
```

### Maximum Inner Product Search (MIPS)

**Challenge:** Find most similar vectors efficiently in high-dimensional space.

**Algorithms:**

#### 1. LSH (Locality-Sensitive Hashing)
```
Concept: Hash similar items to same bucket
Pros: Fast, memory-efficient
Cons: Approximate, quality varies

Use case: Large-scale similarity search
```

#### 2. ANNOY (Approximate Nearest Neighbors Oh Yeah)
```
Structure: Random projection trees
Search: Traverse multiple trees, aggregate results
Pros: Good balance of speed/accuracy
Cons: Static (rebuild for updates)

Use case: Spotify music recommendations
```

#### 3. HNSW (Hierarchical Navigable Small World)
```
Structure: Multi-layer graph
Search: Navigate from top layer down
Pros: Very fast, high accuracy
Cons: Memory-intensive

Use case: Production vector databases
```

#### 4. FAISS (Facebook AI Similarity Search)
```
Method: Vector quantization + clustering
Pros: Extremely fast for large datasets
Cons: Requires tuning

Use case: Billion-scale similarity search
```

#### 5. ScaNN (Scalable Nearest Neighbors)
```
Innovation: Anisotropic vector quantization
Pros: Best accuracy/speed tradeoff
Cons: Google-specific

Use case: Google production systems
```

**Performance Comparison:**
```
Recall@10 vs Latency:

ScaNN     ████████████░░░░ (Best)
HNSW      ███████████░░░░░
FAISS     ██████████░░░░░░
ANNOY     ████████░░░░░░░░
LSH       ██████░░░░░░░░░░
```

**Implementation Example:**
```python
from langchain.vectorstores import FAISS

# Create vector store
vectorstore = FAISS.from_texts(
    texts=documents,
    embedding=embeddings
)

# Similarity search
docs = vectorstore.similarity_search(
    query="AI agents",
    k=5
)

# MMR search (diverse results)
docs = vectorstore.max_marginal_relevance_search(
    query="AI agents",
    k=5,
    fetch_k=20
)
```

### Memory Patterns in Practice

#### 1. Conversation Memory
```python
from langchain.memory import ConversationBufferWindowMemory

# Keep last 5 exchanges
memory = ConversationBufferWindowMemory(
    k=5,
    return_messages=True
)
```

#### 2. Entity Memory
```python
from langchain.memory import ConversationEntityMemory

# Track entities mentioned
memory = ConversationEntityMemory(
    llm=llm,
    k=3  # Recall last 3 interactions per entity
)

# Automatically extracts and stores entities
memory.save_context(
    {"input": "I work at OpenAI"},
    {"output": "That's exciting!"}
)
# Stores entity: {"OpenAI": {"type": "company"}}
```

#### 3. Knowledge Graph Memory
```python
from langchain.memory import ConversationKGMemory

# Build knowledge graph from conversations
memory = ConversationKGMemory(
    llm=llm,
    knowledge_graph=graph
)
```

#### 4. Vector Store Memory
```python
from langchain.memory import VectorStoreRetrieverMemory

# Retrieve relevant past conversations
memory = VectorStoreRetrieverMemory(
    retriever=vectorstore.as_retriever(
        search_kwargs={"k": 3}
    )
)
```

---

## 🛠️ Component 3: Tool Use

### Why Tools Matter

**Limitations of pure LLMs:**
- No access to current information
- Cannot execute code
- No proprietary data access
- Limited math capability
- No physical world interaction

**Tool use enables:**
- Real-time data retrieval
- Code execution
- API integration
- Database queries
- File operations

### Tool Use Frameworks

#### 1. MRKL (Modular Reasoning, Knowledge, Language)

**Architecture:**
```
┌──────────────────────────────────────┐
│           MRKL System                │
├──────────────────────────────────────┤
│  LLM (Router)                        │
│   ↓                                  │
│  Expert Modules:                     │
│   ├─ Neural (deep learning models)   │
│   ├─ Symbolic (calculator, APIs)     │
│   └─ Knowledge (databases)           │
└──────────────────────────────────────┘
```

**Key Insight:** LLM routes queries to appropriate expert modules.

#### 2. TALM & Toolformer

**Approach:** Fine-tune LLM to learn tool usage.

**Training Process:**
1. Start with base model
2. Add tool call annotations
3. Keep if improves output quality
4. Fine-tune on filtered dataset

#### 3. ChatGPT Plugins & Function Calling

**Modern implementation:**
```python
from langchain.tools import Tool
from langchain.agents import initialize_agent

# Define tools
tools = [
    Tool(
        name="Calculator",
        func=calculator,
        description="Use for math. Input: expression"
    ),
    Tool(
        name="Search",
        func=search,
        description="Search for information. Input: query"
    )
]

# Create agent with tool access
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent="zero-shot-react-description"
)
```

### Tool Design Patterns

#### Pattern 1: Simple Tools
```python
def get_weather(city: str) -> str:
    """Get weather for a city."""
    # Call weather API
    return f"Weather in {city}: Sunny"

tool = Tool(
    name="weather",
    func=get_weather,
    description="Get weather for a city. Input: city name"
)
```

#### Pattern 2: Tools with Parameters
```python
from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    query: str = Field(description="Search query")
    num_results: int = Field(default=5)

@tool(args_schema=SearchInput)
def search(query: str, num_results: int = 5):
    """Search the web."""
    return search_api(query, num_results)
```

#### Pattern 3: Composite Tools
```python
class ResearchTool(BaseTool):
    name = "research"
    description = "Research a topic thoroughly"
    
    def _run(self, topic: str):
        # Step 1: Search
        results = search_tool.run(topic)
        # Step 2: Summarize
        summary = summarize_tool.run(results)
        # Step 3: Extract facts
        facts = extract_tool.run(summary)
        return facts
```

### Tool Selection Strategies

#### 1. Explicit Selection
```python
# Agent decides which tool to use
agent.run("What's the weather in SF?")
# → Uses weather tool

agent.run("Calculate 2^100")
# → Uses calculator tool
```

#### 2. Tool Chaining
```python
# Sequential tool use
workflow = [
    ("search", "Find AI agent papers"),
    ("summarize", "Summarize findings"),
    ("analyze", "Extract key insights")
]
```

#### 3. Conditional Tools
```python
def should_use_tool(query: str) -> bool:
    """Decide if tool is needed"""
    if "current" in query.lower():
        return True  # Need search
    if any(op in query for op in ["+", "-", "*", "/"]):
        return True  # Need calculator
    return False
```

### Tool Integration Examples

#### LangChain Tools
```python
from langchain.tools import (
    DuckDuckGoSearchRun,
    PythonREPLTool,
    WikipediaQueryRun
)

tools = [
    DuckDuckGoSearchRun(),
    PythonREPLTool(),
    WikipediaQueryRun()
]

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent="zero-shot-react-description",
    verbose=True
)
```

#### Custom Tool Creation
```python
from langchain.tools import BaseTool
from typing import Optional

class DatabaseQueryTool(BaseTool):
    name = "database_query"
    description = "Query the company database"
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def _run(self, query: str) -> str:
        results = self.db.execute(query)
        return str(results)
    
    async def _arun(self, query: str) -> str:
        # Async implementation
        pass
```

### Tool Evaluation: API-Bank Benchmark

**Three levels of tool proficiency:**

**Level 1: Call API**
- Given API description
- Determine if should call
- Call correctly
- Handle response

**Level 2: Retrieve API**
- Search for relevant APIs
- Learn from documentation
- Choose appropriate API

**Level 3: Plan & Execute**
- Multi-step tool planning
- Handle dependencies
- Iterate on failures

---

## 🔄 Integration: Putting It All Together

### Complete Agent Example

```python
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.memory import ConversationBufferMemory
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.tools import Tool

# 1. Setup Memory
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True
)

# Long-term memory
embeddings = OpenAIEmbeddings()
vectorstore = FAISS.from_texts(
    ["Important fact 1", "Important fact 2"],
    embeddings
)

# 2. Define Tools
def plan_task(task: str) -> str:
    """Decompose task into steps"""
    # Use CoT or ToT
    return f"Steps for {task}:\n1. ...\n2. ..."

def reflect_on_result(result: str) -> str:
    """Reflect on result quality"""
    return f"Reflection: {result} could be improved by..."

tools = [
    Tool(name="planner", func=plan_task),
    Tool(name="search", func=search_function),
    Tool(name="calculator", func=calculator_function)
]

# 3. Create Agent
agent = create_openai_functions_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    verbose=True
)

# 4. Run with Planning + Memory + Tools
result = agent_executor.invoke({
    "input": "Research and summarize latest AI agent frameworks"
})
```

### ReAct Pattern Implementation

```python
class ReActAgent:
    """Full ReAct implementation"""
    
    def __init__(self, llm, tools, memory):
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.memory = memory
    
    def think(self, context: str) -> str:
        """Generate thought"""
        return self.llm.generate(
            f"Context: {context}\nThought: "
        )
    
    def act(self, thought: str) -> tuple:
        """Decide action and execute"""
        # Parse action from thought
        action = self._parse_action(thought)
        observation = self._execute_action(action)
        return action, observation
    
    def run(self, task: str, max_iterations=10):
        """Run ReAct loop"""
        context = f"Task: {task}\n"
        
        for i in range(max_iterations):
            # 1. Think
            thought = self.think(context)
            
            # 2. Act
            action, observation = self.act(thought)
            
            # 3. Update context
            context += f"Thought: {thought}\n"
            context += f"Action: {action}\n"
            context += f"Observation: {observation}\n"
            
            # 4. Check if done
            if "Finish" in action:
                break
            
            # 5. Reflect (optional)
            if i % 3 == 0:
                reflection = self.reflect(context)
                context += f"Reflection: {reflection}\n"
        
        return self._extract_answer(context)
```

---

## 📊 Summary: Architecture Trade-offs

| Component | Simple | Advanced | Trade-off |
|-----------|--------|----------|-----------|
| **Planning** | CoT | ToT + Reflexion | Speed vs Quality |
| **Memory** | Buffer | Vector + Entity | Cost vs Recall |
| **Tools** | Fixed | Dynamic + Composite | Flexibility vs Complexity |

### Design Principles

1. **Start Simple**
   - Begin with CoT + Buffer memory + Basic tools
   - Add complexity as needed

2. **Measure Performance**
   - Track task success rate
   - Monitor token usage
   - Measure latency

3. **Iterate Based on Failure**
   - Use Reflexion for improvement
   - Analyze failure modes
   - Refine tools and prompts

4. **Balance Cost vs Quality**
   - More sophisticated = more expensive
   - Find sweet spot for use case

---

**Next:** [Communication Patterns](./03-communication-patterns.md)
