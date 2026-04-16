# Multi-Agent Coordination Systems

**Focus:** Crew orchestration, hierarchical processes, consensus mechanisms, and distributed agent architectures

---

## 🤝 Coordination Fundamentals

### Why Coordination Matters

Multi-agent coordination enables:
- **Specialization**: Agents focus on their expertise
- **Parallelism**: Work on independent tasks simultaneously
- **Scalability**: Add agents as needed
- **Robustness**: System continues if some agents fail
- **Emergent Intelligence**: Collective intelligence > individual

### Coordination Challenges

```
┌──────────────────────────────────────────┐
│   Coordination Challenges                │
├──────────────────────────────────────────┤
│  1. Task Allocation                      │
│     - Who does what?                     │
│     - When to assign?                    │
│                                          │
│  2. Synchronization                      │
│     - When to coordinate?                │
│     - How to handle dependencies?        │
│                                          │
│  3. Communication Overhead               │
│     - Too much = slow                    │
│     - Too little = miscoordination       │
│                                          │
│  4. Conflict Resolution                  │
│     - Agents disagree                    │
│     - Resource contention                │
│                                          │
│  5. Scalability                          │
│     - Coordination cost grows            │
│     - Need efficient protocols           │
└──────────────────────────────────────────┘
```

---

## 🏗️ Coordination Architectures

### Architecture 1: Hierarchical

```
           ┌─────────────┐
           │   Manager   │
           │    Agent    │
           └──────┬──────┘
                  │
        ┌─────────┼─────────┐
        │         │         │
   ┌────▼────┐ ┌──▼───┐ ┌──▼───┐
   │ Worker1 │ │Work2 │ │Work3 │
   └─────────┘ └──────┘ └──────┘
```

**Characteristics:**
- Top-down control
- Clear authority chain
- Manager coordinates workers
- Workers don't communicate directly

**When to use:**
- Clear task decomposition
- Need central decision-making
- Predictable workflow

**Implementation (CrewAI):**
```python
from crewai import Agent, Task, Crew, Process

# Create manager
manager = Agent(
    role="Project Manager",
    goal="Coordinate team to complete project",
    backstory="Experienced project manager with leadership skills",
    allow_delegation=True,
    llm="gpt-4"
)

# Create workers
researcher = Agent(
    role="Researcher",
    goal="Research topics thoroughly",
    backstory="Expert researcher",
    tools=[SerperDevTool()]
)

writer = Agent(
    role="Writer",
    goal="Write high-quality content",
    backstory="Professional writer"
)

analyst = Agent(
    role="Analyst",
    goal="Analyze data and provide insights",
    backstory="Data analyst"
)

# Create hierarchical crew
crew = Crew(
    agents=[manager, researcher, writer, analyst],
    tasks=[task1, task2, task3],
    process=Process.hierarchical,
    manager_llm="gpt-4",  # Required for hierarchical
    verbose=True
)

# Manager automatically assigns tasks to workers
result = crew.kickoff()
```

**Workflow:**
```
1. User submits goal to manager
2. Manager decomposes into subtasks
3. Manager assigns subtasks to workers based on:
   - Agent capabilities (role, goal, backstory)
   - Agent availability (current workload)
   - Task requirements
4. Workers execute tasks
5. Workers report results to manager
6. Manager reviews and coordinates next steps
7. Manager synthesizes final result
```

**Advantages:**
- Clear coordination
- Predictable behavior
- Easy to debug
- Efficient for structured tasks

**Disadvantages:**
- Manager bottleneck
- Single point of failure
- Less flexible
- Communication overhead

### Architecture 2: Sequential

```
┌────────┐    ┌────────┐    ┌────────┐
│ Agent1 │───▶│ Agent2 │───▶│ Agent3 │
└────────┘    └────────┘    └────────┘
```

**Characteristics:**
- Linear execution
- Each agent waits for previous
- Clear dependencies
- Easy to understand

**When to use:**
- Linear workflow (research → write → review)
- Clear task dependencies
- Simple coordination

**Implementation (CrewAI):**
```python
# Define sequential workflow
crew = Crew(
    agents=[researcher, analyst, writer],
    tasks=[
        Task(description="Research topic", agent=researcher),
        Task(description="Analyze findings", agent=analyst),
        Task(description="Write article", agent=writer)
    ],
    process=Process.sequential
)

# Execute sequentially
result = crew.kickoff()
```

**Task Context Passing:**
```python
from crewai import Task

# Task 1: Research
research_task = Task(
    description="Research AI agents",
    expected_output="Summary of key findings",
    agent=researcher
)

# Task 2: Write (receives context from research_task)
write_task = Task(
    description="Write article based on research",
    expected_output="Complete article",
    agent=writer,
    context=[research_task]  # Receives output from research_task
)

# Context automatically passed
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    process=Process.sequential
)
```

**Advantages:**
- Simple to implement
- Clear flow
- Easy debugging
- Predictable

**Disadvantages:**
- Slow (no parallelism)
- Agents can't collaborate
- Bottleneck if one agent slow

### Architecture 3: Parallel/Concurrent

```
           ┌─────────┐
           │   Task  │
           └────┬────┘
                │
        ┌───────┼───────┐
        │       │       │
   ┌────▼───┐ ┌─▼───┐ ┌─▼───┐
   │Agent 1 │ │Agt 2│ │Agt 3│
   └────┬───┘ └──┬──┘ └──┬──┘
        │       │       │
        └───────┼───────┘
                │
           ┌────▼────┐
           │ Aggregate│
           └─────────┘
```

**Characteristics:**
- Agents work simultaneously
- Independent tasks
- Aggregate results
- Faster execution

**When to use:**
- Independent subtasks
- Time-sensitive
- Resource-intensive tasks

**Implementation:**
```python
from concurrent.futures import ThreadPoolExecutor
import threading

class ParallelCrew:
    def __init__(self, agents):
        self.agents = agents
        self.results = []
        self.lock = threading.Lock()
    
    def execute_parallel(self, tasks):
        """Execute tasks in parallel"""
        with ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
            # Map tasks to agents
            futures = []
            for agent, task in zip(self.agents, tasks):
                future = executor.submit(
                    agent.execute,
                    task
                )
                futures.append(future)
            
            # Collect results
            for future in futures:
                result = future.result()
                with self.lock:
                    self.results.append(result)
        
        return self.aggregate(self.results)
    
    def aggregate(self, results):
        """Combine parallel results"""
        # Merge, summarize, or vote
        return {
            "combined": results,
            "summary": self._summarize(results)
        }

# Usage
crew = ParallelCrew([researcher1, researcher2, researcher3])

tasks = [
    {"query": "LangChain features"},
    {"query": "AutoGen features"},
    {"query": "CrewAI features"}
]

results = crew.execute_parallel(tasks)
```

**Advantages:**
- Fast execution
- Better resource utilization
- Scalable

**Disadvantages:**
- Coordination complexity
- Race conditions possible
- Aggregation needed

### Architecture 4: Network/Peer-to-Peer

```
        ┌───────┐
        │Agent 1│
        └───┬───┘
            │
    ┌───────┼───────┐
    │       │       │
┌───▼───┐ ┌─▼───┐ ┌─▼───┐
│Agent 2│ │Agt 3│ │Agt 4│
└───┬───┘ └──┬──┘ └─────┘
    │       │
    └───┬───┘
        │
    ┌───▼───┐
    │Agent 5│
    └───────┘
```

**Characteristics:**
- No central coordinator
- Agents communicate directly
- Emergent behavior
- Self-organizing

**When to use:**
- Complex, dynamic environments
- Need resilience
- Research scenarios

**Implementation (AutoGen):**
```python
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat

# Create agents
agents = [
    AssistantAgent(f"agent_{i}", llm_config=llm_config)
    for i in range(5)
]

# Create peer-to-peer conversation
team = RoundRobinGroupChat(
    agents=agents,
    max_rounds=20
)

# Agents communicate freely
result = await team.run(task="Collaboratively solve this problem")
```

**Advantages:**
- No single point of failure
- Flexible and adaptive
- Emergent solutions

**Disadvantages:**
- Unpredictable
- Hard to debug
- Communication overhead

---

## 🗳️ Consensus Mechanisms

### When Agents Disagree

```
┌──────────────────────────────────────┐
│   Consensus Scenario                 │
├──────────────────────────────────────┤
│                                      │
│  Researcher: "Use LangChain"         │
│  Coder: "Use AutoGen"                │
│  Manager: "Use CrewAI"               │
│                                      │
│  Question: Which framework to use?   │
│                                      │
└──────────────────────────────────────┘
```

### Mechanism 1: Voting

```python
from collections import Counter

class VotingConsensus:
    """Simple majority voting"""
    
    def __init__(self, agents):
        self.agents = agents
    
    def vote(self, options):
        """Agents vote on options"""
        votes = []
        
        for agent in self.agents:
            # Agent votes
            vote = agent.choose_option(options)
            votes.append(vote)
        
        # Count votes
        vote_counts = Counter(votes)
        
        # Return winner
        winner = vote_counts.most_common(1)[0]
        return {
            "decision": winner[0],
            "votes": winner[1],
            "total": len(votes)
        }

# Usage
consensus = VotingConsensus([agent1, agent2, agent3])
result = consensus.vote(["LangChain", "AutoGen", "CrewAI"])
# {"decision": "LangChain", "votes": 2, "total": 3}
```

### Mechanism 2: Weighted Voting

```python
class WeightedVoting:
    """Vote weighted by agent expertise"""
    
    def __init__(self, agents_with_weights):
        self.agents = agents_with_weights  # [(agent, weight), ...]
    
    def vote(self, options):
        """Weighted voting"""
        scores = {option: 0 for option in options}
        
        for agent, weight in self.agents:
            vote = agent.choose_option(options)
            scores[vote] += weight
        
        # Return highest score
        winner = max(scores.items(), key=lambda x: x[1])
        return {
            "decision": winner[0],
            "score": winner[1],
            "all_scores": scores
        }

# Usage
consensus = WeightedVoting([
    (researcher, 3.0),  # Expert in research
    (coder, 2.0),       # Moderate expertise
    (manager, 1.0)      # General oversight
])

result = consensus.vote(["LangChain", "AutoGen", "CrewAI"])
```

### Mechanism 3: Argumentation

```python
class ArgumentationConsensus:
    """Agents argue for their choice"""
    
    def __init__(self, agents):
        self.agents = agents
    
    def debate(self, options, rounds=3):
        """Structured debate"""
        arguments = {option: [] for option in options}
        
        for round_num in range(rounds):
            for agent in self.agents:
                # Agent presents argument
                for option in options:
                    argument = agent.argue_for(option, arguments)
                    if argument:
                        arguments[option].append({
                            "agent": agent.name,
                            "argument": argument,
                            "round": round_num
                        })
        
        # Evaluate arguments
        return self._evaluate(arguments)
    
    def _evaluate(self, arguments):
        """Evaluate argument strength"""
        scores = {}
        
        for option, args in arguments.items():
            # Score based on argument count and quality
            score = len(args) * self._assess_quality(args)
            scores[option] = score
        
        winner = max(scores.items(), key=lambda x: x[1])
        return {
            "decision": winner[0],
            "arguments": arguments,
            "scores": scores
        }

# Usage
consensus = ArgumentationConsensus([researcher, coder, manager])
result = consensus.debate(["LangChain", "AutoGen", "CrewAI"], rounds=2)
```

### Mechanism 4: Borda Count

```python
class BordaCount:
    """Ranking-based consensus"""
    
    def __init__(self, agents):
        self.agents = agents
    
    def rank(self, options):
        """Agents rank all options"""
        rankings = []
        
        for agent in self.agents:
            rank = agent.rank_options(options)
            rankings.append(rank)
        
        # Calculate Borda scores
        n = len(options)
        scores = {option: 0 for option in options}
        
        for ranking in rankings:
            for i, option in enumerate(ranking):
                # Higher rank = higher score
                scores[option] += (n - i)
        
        winner = max(scores.items(), key=lambda x: x[1])
        return {
            "decision": winner[0],
            "scores": scores,
            "rankings": rankings
        }

# Usage
consensus = BordaCount([agent1, agent2, agent3])
result = consensus.rank(["LangChain", "AutoGen", "CrewAI"])
```

---

## 🌐 Distributed Agent Systems

### Distribution Challenges

```
┌──────────────────────────────────────┐
│   Distributed Systems Challenges     │
├──────────────────────────────────────┤
│  1. Network latency                  │
│  2. Partial failures                 │
│  3. Consistency vs availability      │
│  4. Message ordering                 │
│  5. Resource coordination            │
└──────────────────────────────────────┘
```

### Architecture: Master-Worker

```python
import asyncio
from typing import Dict, List

class MasterAgent:
    """Master coordinates distributed workers"""
    
    def __init__(self):
        self.workers: Dict[str, WorkerAgent] = {}
        self.task_queue = asyncio.Queue()
        self.results = {}
    
    async def register_worker(self, worker):
        """Register worker"""
        self.workers[worker.id] = worker
        # Start worker listener
        asyncio.create_task(self._listen_to_worker(worker))
    
    async def submit_task(self, task):
        """Submit task to queue"""
        await self.task_queue.put(task)
    
    async def _listen_to_worker(self, worker):
        """Listen for worker results"""
        while True:
            result = await worker.get_result()
            self.results[result["task_id"]] = result
    
    async def distribute_tasks(self):
        """Distribute tasks to workers"""
        while not self.task_queue.empty():
            task = await self.task_queue.get()
            
            # Find available worker
            worker = await self._find_available_worker()
            
            if worker:
                await worker.assign_task(task)

class WorkerAgent:
    """Worker executes tasks"""
    
    def __init__(self, id):
        self.id = id
        self.status = "idle"
        self.current_task = None
    
    async def assign_task(self, task):
        """Receive task from master"""
        self.status = "busy"
        self.current_task = task
        
        # Execute task
        result = await self._execute(task)
        
        # Return result
        self.status = "idle"
        return result
    
    async def _execute(self, task):
        """Execute task"""
        # Do work
        await asyncio.sleep(1)  # Simulate work
        return {
            "task_id": task["id"],
            "result": "completed",
            "worker": self.id
        }

# Usage
async def main():
    master = MasterAgent()
    
    # Register workers
    for i in range(5):
        worker = WorkerAgent(f"worker_{i}")
        await master.register_worker(worker)
    
    # Submit tasks
    for i in range(20):
        await master.submit_task({"id": f"task_{i}"})
    
    # Distribute
    await master.distribute_tasks()

asyncio.run(main())
```

### Architecture: Actor Model

```python
class Actor:
    """Actor model agent"""
    
    def __init__(self, id):
        self.id = id
        self.mailbox = asyncio.Queue()
        self.behaviors = {}
    
    def register_behavior(self, message_type, handler):
        """Register message handler"""
        self.behaviors[message_type] = handler
    
    async def send(self, recipient, message):
        """Send message to another actor"""
        await recipient.mailbox.put({
            "from": self.id,
            "message": message
        })
    
    async def run(self):
        """Process messages"""
        while True:
            msg = await self.mailbox.get()
            
            message_type = msg["message"].get("type")
            handler = self.behaviors.get(message_type)
            
            if handler:
                await handler(msg)

# Usage
researcher = Actor("researcher")
writer = Actor("writer")

# Register behaviors
async def handle_research_request(msg):
    # Do research
    result = await conduct_research(msg["message"]["query"])
    # Send result back
    await researcher.send(
        writer,
        {"type": "research_result", "data": result}
    )

researcher.register_behavior("research_request", handle_research_request)

# Start actors
asyncio.create_task(researcher.run())
asyncio.create_task(writer.run())

# Send message
await writer.send(researcher, {
    "type": "research_request",
    "query": "AI agent frameworks"
})
```

---

## 🔧 Coordination Patterns in Practice

### Pattern: CrewAI Hierarchical with Tools

```python
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool, FileReadTool

# Manager with delegation
manager = Agent(
    role="Project Manager",
    goal="Coordinate team effectively",
    backstory="Experienced manager",
    allow_delegation=True,
    llm="gpt-4"
)

# Specialist workers
researcher = Agent(
    role="Senior Researcher",
    goal="Find comprehensive information",
    backstory="Expert researcher",
    tools=[SerperDevTool()]
)

analyst = Agent(
    role="Data Analyst",
    goal="Analyze and extract insights",
    backstory="Data science expert",
    tools=[FileReadTool()]
)

writer = Agent(
    role="Content Writer",
    goal="Create engaging content",
    backstory="Professional writer"
)

# Create crew
crew = Crew(
    agents=[manager, researcher, analyst, writer],
    tasks=[
        Task(
            description="Complete research project on {topic}",
            expected_output="Comprehensive report"
        )
    ],
    process=Process.hierarchical,
    manager_llm="gpt-4"
)

# Manager coordinates execution
result = crew.kickoff(inputs={"topic": "AI Agents"})
```

### Pattern: AutoGen Multi-Agent Conversation

```python
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat

# Create agents with different roles
researcher = AssistantAgent(
    name="Researcher",
    system_message="""
    You are a researcher. Your job is to find and summarize information.
    """,
    llm_config=llm_config
)

critic = AssistantAgent(
    name="Critic",
    system_message="""
    You are a critic. Review the researcher's work and provide feedback.
    """,
    llm_config=llm_config
)

improver = AssistantAgent(
    name="Improver",
    system_message="""
    You improve the work based on critic feedback.
    """,
    llm_config=llm_config
)

# Create conversation team
team = RoundRobinGroupChat(
    agents=[researcher, critic, improver],
    max_rounds=10
)

# Run conversation
result = await team.run(
    task="Research and refine a report on AI agent architectures"
)
```

---

## 📊 Coordination Patterns Comparison

| Pattern | Scalability | Complexity | Flexibility | Robustness |
|---------|-------------|------------|-------------|------------|
| Hierarchical | Low-Medium | Medium | Low | Medium |
| Sequential | Low | Low | Low | Low |
| Parallel | High | Medium | Medium | High |
| Network | High | High | High | High |
| Master-Worker | High | Medium-High | Medium | Medium |
| Actor Model | High | High | High | High |

---

## 🎯 Best Practices

### 1. Choose Architecture Wisely

```python
# Simple, linear workflow
if is_linear_workflow(tasks):
    use_sequential_coordination()

# Need parallelism
if are_independent_tasks(tasks):
    use_parallel_coordination()

# Complex, dynamic
if is_complex_environment():
    use_hierarchical_or_network()

# Large scale
if is_large_scale():
    use_distributed_coordination()
```

### 2. Implement Consensus When Needed

```python
# Agents might disagree
if agents_have_conflicting_views():
    use_consensus_mechanism()

# Simple disagreement
use_voting()

# Expertise-based
use_weighted_voting()

# Complex decision
use_argumentation()
```

### 3. Monitor Coordination

```python
class MonitoredCoordinator:
    def __init__(self):
        self.metrics = {
            "tasks_assigned": 0,
            "tasks_completed": 0,
            "coordination_overhead_ms": 0,
            "agent_utilization": {}
        }
    
    def track_task(self, task, agent):
        """Track task assignment"""
        self.metrics["tasks_assigned"] += 1
        # ... tracking logic
```

---

**Next:** [Real-World Implementations](./05-implementations.md)
