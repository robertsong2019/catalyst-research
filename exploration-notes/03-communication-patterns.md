# Communication Patterns in Multi-Agent Systems

**Focus:** Agent-to-agent communication protocols, task coordination, state management, and event-driven architectures

---

## 📡 Communication Fundamentals

### Why Communication Matters

In multi-agent systems, communication enables:
- **Coordination**: Synchronize actions across agents
- **Collaboration**: Share knowledge and resources
- **Negotiation**: Resolve conflicts and make decisions
- **Learning**: Transfer knowledge between agents

### Communication Models

```
┌──────────────────────────────────────────────┐
│   Communication Models                        │
├──────────────────────────────────────────────┤
│                                              │
│  1. Direct Messaging                         │
│     Agent A → Agent B (point-to-point)      │
│                                              │
│  2. Broadcast                                │
│     Agent A → [Agent B, C, D, ...]          │
│                                              │
│  3. Pub/Sub                                  │
│     Publisher → Topic → Subscribers         │
│                                              │
│  4. Shared State                             │
│     Agents read/write common state store    │
│                                              │
│  5. Blackboard                               │
│     Central knowledge repository             │
│                                              │
└──────────────────────────────────────────────┘
```

---

## 💬 Pattern 1: Direct Messaging

### Concept

Agents send messages directly to specific recipients.

### Implementation Patterns

#### LangChain: Chain Passing

```python
from langchain.schema import AgentAction, AgentFinish
from langchain.agents import AgentExecutor

class MessagingAgent:
    def __init__(self, name, llm, tools):
        self.name = name
        self.llm = llm
        self.tools = tools
        self.inbox = []
    
    def send_message(self, recipient, message):
        """Send message to another agent"""
        recipient.inbox.append({
            "from": self.name,
            "to": recipient.name,
            "content": message,
            "timestamp": time.time()
        })
    
    def process_inbox(self):
        """Process received messages"""
        while self.inbox:
            msg = self.inbox.pop(0)
            response = self._handle_message(msg)
            if response.get("reply"):
                self.send_message(
                    msg["from"],
                    response["reply"]
                )
    
    def _handle_message(self, msg):
        """Process incoming message"""
        prompt = f"""
        You received a message from {msg['from']}:
        {msg['content']}
        
        Respond appropriately.
        """
        return self.llm.generate(prompt)

# Usage
agent_a = MessagingAgent("researcher", llm, tools)
agent_b = MessagingAgent("writer", llm, tools)

# Direct message
agent_a.send_message(
    agent_b,
    "I found 3 papers on AI agents"
)

agent_b.process_inbox()
```

#### AutoGen: Conversational Agents

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat

# Define agents with conversational ability
researcher = AssistantAgent(
    name="researcher",
    system_message="You are a researcher. Ask the writer what they need.",
    llm_config=llm_config
)

writer = AssistantAgent(
    name="writer",
    system_message="You are a writer. Request research from the researcher.",
    llm_config=llm_config
)

# Create conversation
team = RoundRobinGroupChat(
    agents=[researcher, writer],
    max_rounds=10
)

# Run conversation
result = await team.run(
    task="Research and write about AI agents"
)
```

**Conversation Flow:**
```
Round 1:
Researcher: "I'll research AI agents. Writer, what angle do you want?"
Writer: "Focus on practical applications and real-world examples"

Round 2:
Researcher: "I found 5 papers on practical applications. Here's a summary..."
Writer: "Perfect! I'll incorporate these into the article"

Round 3:
Researcher: "Do you need more details on any specific application?"
Writer: "Yes, expand on the healthcare use case"

...
```

### Message Types

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

class MessageType(Enum):
    REQUEST = "request"        # Request action/info
    RESPONSE = "response"      # Response to request
    NOTIFICATION = "notify"    # Broadcast update
    QUERY = "query"            # Query state
    COMMAND = "command"        # Direct instruction
    ACKNOWLEDGMENT = "ack"     # Acknowledge receipt

@dataclass
class AgentMessage:
    sender: str
    recipient: str
    type: MessageType
    content: Any
    metadata: Optional[Dict] = None
    reply_to: Optional[str] = None  # Message ID
    correlation_id: Optional[str] = None  # Track conversation
```

---

## 📢 Pattern 2: Broadcast & Pub/Sub

### Concept

- **Broadcast**: Send to all agents
- **Pub/Sub**: Agents subscribe to topics

### Implementation

#### Simple Broadcast

```python
class BroadcastHub:
    def __init__(self):
        self.agents = []
    
    def register(self, agent):
        self.agents.append(agent)
    
    def broadcast(self, message, sender):
        """Broadcast to all agents except sender"""
        for agent in self.agents:
            if agent.name != sender:
                agent.receive(message, sender)

# Usage
hub = BroadcastHub()
hub.register(agent_a)
hub.register(agent_b)
hub.register(agent_c)

agent_a.broadcast("Starting research on topic X", hub)
# agent_b and agent_c receive the message
```

#### Pub/Sub Pattern

```python
class PubSubBroker:
    def __init__(self):
        self.topics = {}  # topic -> [agents]
    
    def subscribe(self, agent, topic):
        """Agent subscribes to topic"""
        if topic not in self.topics:
            self.topics[topic] = []
        self.topics[topic].append(agent)
    
    def unsubscribe(self, agent, topic):
        """Agent unsubscribes from topic"""
        if topic in self.topics:
            self.topics[topic].remove(agent)
    
    def publish(self, topic, message, publisher):
        """Publish message to topic subscribers"""
        if topic not in self.topics:
            return
        
        for agent in self.topics[topic]:
            if agent.name != publisher:
                agent.receive(message, publisher, topic)

# Usage
broker = PubSubBroker()

# Agents subscribe to topics
researcher.subscribe(broker, "research_updates")
writer.subscribe(broker, "research_updates")
reviewer.subscribe(broker, "review_requests")

# Publish to topic
researcher.publish(
    topic="research_updates",
    message="Found new relevant papers",
    broker=broker
)

# Only subscribed agents receive
```

### Topics & Channels

```python
# Define common topics
TOPICS = {
    "task_updates": "Task status changes",
    "research_findings": "New research discoveries",
    "review_requests": "Request for review",
    "system_alerts": "System notifications",
    "knowledge_share": "Share knowledge/insights"
}

class TopicAgent:
    def __init__(self, name, broker):
        self.name = name
        self.broker = broker
        self.subscriptions = set()
    
    def subscribe_to_topics(self, topics):
        """Subscribe to multiple topics"""
        for topic in topics:
            self.broker.subscribe(self, topic)
            self.subscriptions.add(topic)
    
    def publish_finding(self, topic, content):
        """Publish to a topic"""
        message = {
            "from": self.name,
            "topic": topic,
            "content": content,
            "timestamp": time.time()
        }
        self.broker.publish(topic, message, self.name)

# Setup
broker = PubSubBroker()

researcher = TopicAgent("researcher", broker)
researcher.subscribe_to_topics(["task_updates", "knowledge_share"])

writer = TopicAgent("writer", broker)
writer.subscribe_to_topics(["research_findings", "task_updates"])
```

---

## 🔄 Pattern 3: Shared State

### Concept

Agents communicate by reading/writing to a shared state store.

### Implementation

#### Centralized State Store

```python
from typing import Dict, Any, Optional
import threading

class SharedState:
    """Thread-safe shared state store"""
    
    def __init__(self):
        self.state = {}
        self.lock = threading.Lock()
        self.watchers = {}  # key -> [callback functions]
    
    def set(self, key: str, value: Any, agent: str):
        """Set value in state"""
        with self.lock:
            old_value = self.state.get(key)
            self.state[key] = {
                "value": value,
                "updated_by": agent,
                "timestamp": time.time()
            }
            
            # Notify watchers
            if key in self.watchers:
                for callback in self.watchers[key]:
                    callback(key, old_value, value)
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from state"""
        with self.lock:
            entry = self.state.get(key)
            return entry["value"] if entry else None
    
    def watch(self, key: str, callback):
        """Watch for changes to a key"""
        if key not in self.watchers:
            self.watchers[key] = []
        self.watchers[key].append(callback)
    
    def get_all(self) -> Dict[str, Any]:
        """Get entire state"""
        with self.lock:
            return {k: v["value"] for k, v in self.state.items()}

# Usage
shared_state = SharedState()

class StateAwareAgent:
    def __init__(self, name, state):
        self.name = name
        self.state = state
        
        # Watch for specific state changes
        state.watch("task_status", self.on_task_update)
    
    def on_task_update(self, key, old_value, new_value):
        """Callback when task_status changes"""
        print(f"{self.name}: Task status changed from {old_value} to {new_value}")
    
    def update_task(self, task_id, status):
        """Update task status"""
        self.state.set(
            f"task_{task_id}_status",
            status,
            self.name
        )

# Agents share state
agent_a = StateAwareAgent("researcher", shared_state)
agent_b = StateAwareAgent("writer", shared_state)

# Agent A updates state
agent_a.update_task("001", "in_progress")
# Agent B automatically notified via watcher
```

#### LangGraph State Management

```python
from langgraph.graph import StateGraph, MessagesState
from typing import TypedDict, Annotated
from langgraph.checkpoint.memory import MemorySaver

# Define state schema
class AgentState(TypedDict):
    messages: Annotated[list, "Conversation messages"]
    research_notes: Annotated[list, "Research findings"]
    current_task: str
    task_status: str

# Create graph with state
graph = StateGraph(AgentState)

# Define nodes that read/write state
def research_node(state: AgentState):
    """Research agent reads/writes state"""
    task = state["current_task"]
    
    # Do research
    findings = conduct_research(task)
    
    # Update state
    return {
        "research_notes": state["research_notes"] + findings,
        "task_status": "research_complete"
    }

def write_node(state: AgentState):
    """Writer agent reads state"""
    # Read from state
    notes = state["research_notes"]
    
    # Generate content
    content = write_content(notes)
    
    # Update state
    return {
        "messages": state["messages"] + [content],
        "task_status": "writing_complete"
    }

# Add nodes to graph
graph.add_node("researcher", research_node)
graph.add_node("writer", write_node)

# Define edges
graph.add_edge("researcher", "writer")

# Compile with checkpointing
checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)

# Run with state
result = app.invoke({
    "messages": [],
    "research_notes": [],
    "current_task": "Write about AI agents",
    "task_status": "started"
})
```

---

## 🎯 Pattern 4: Task Coordination

### Task Assignment Strategies

#### 1. Push Model (Centralized)

```python
class TaskCoordinator:
    """Central coordinator assigns tasks"""
    
    def __init__(self):
        self.agents = {}
        self.task_queue = []
        self.assignments = {}
    
    def register_agent(self, agent, capabilities):
        """Register agent with capabilities"""
        self.agents[agent.name] = {
            "agent": agent,
            "capabilities": capabilities,
            "current_task": None,
            "status": "idle"
        }
    
    def submit_task(self, task):
        """Submit task for assignment"""
        task["status"] = "pending"
        self.task_queue.append(task)
        self._assign_tasks()
    
    def _assign_tasks(self):
        """Assign pending tasks to available agents"""
        for task in self.task_queue[:]:
            if task["status"] != "pending":
                continue
            
            # Find best agent
            best_agent = self._find_best_agent(task)
            
            if best_agent:
                # Assign task
                self._assign_task(task, best_agent)
                self.task_queue.remove(task)
    
    def _find_best_agent(self, task):
        """Find agent with matching capabilities"""
        required = task.get("required_capabilities", [])
        
        for name, info in self.agents.items():
            if info["status"] != "idle":
                continue
            
            # Check capabilities
            if all(cap in info["capabilities"] for cap in required):
                return info["agent"]
        
        return None
    
    def _assign_task(self, task, agent):
        """Assign task to agent"""
        agent.assign_task(task)
        self.agents[agent.name]["current_task"] = task
        self.agents[agent.name]["status"] = "busy"
        self.assignments[task["id"]] = agent.name

# Usage
coordinator = TaskCoordinator()

# Register agents
coordinator.register_agent(researcher, ["search", "summarize"])
coordinator.register_agent(writer, ["write", "edit"])
coordinator.register_agent(coder, ["code", "debug"])

# Submit tasks
coordinator.submit_task({
    "id": "task_001",
    "type": "research",
    "required_capabilities": ["search"],
    "description": "Research AI agent frameworks"
})

# Coordinator automatically assigns to researcher
```

#### 2. Pull Model (Decentralized)

```python
class TaskBoard:
    """Shared task board agents pull from"""
    
    def __init__(self):
        self.tasks = []
        self.lock = threading.Lock()
    
    def post_task(self, task):
        """Post task to board"""
        with self.lock:
            task["status"] = "available"
            task["claimed_by"] = None
            self.tasks.append(task)
    
    def claim_task(self, agent_name, capabilities):
        """Agent claims available task"""
        with self.lock:
            for task in self.tasks:
                if task["status"] != "available":
                    continue
                
                # Check if agent can do task
                required = task.get("required_capabilities", [])
                if all(cap in capabilities for cap in required):
                    task["status"] = "claimed"
                    task["claimed_by"] = agent_name
                    return task
            
            return None
    
    def complete_task(self, task_id, agent_name):
        """Mark task as complete"""
        with self.lock:
            for task in self.tasks:
                if task["id"] == task_id and task["claimed_by"] == agent_name:
                    task["status"] = "complete"
                    break

class PullAgent:
    """Agent that pulls tasks from board"""
    
    def __init__(self, name, capabilities, task_board):
        self.name = name
        self.capabilities = capabilities
        self.board = task_board
    
    def look_for_work(self):
        """Check board for available tasks"""
        task = self.board.claim_task(
            self.name,
            self.capabilities
        )
        
        if task:
            self._execute_task(task)
    
    def _execute_task(self, task):
        """Execute claimed task"""
        # Do the work
        result = self._do_work(task)
        
        # Mark complete
        self.board.complete_task(task["id"], self.name)

# Usage
board = TaskBoard()

# Create agents
researcher = PullAgent("researcher", ["search"], board)
writer = PullAgent("writer", ["write"], board)

# Post tasks
board.post_task({
    "id": "task_001",
    "type": "research",
    "required_capabilities": ["search"]
})

# Agents pull tasks
researcher.look_for_work()  # Claims task_001
writer.look_for_work()      # No suitable tasks
```

#### 3. Contract Net Protocol

```python
class ContractNetProtocol:
    """Bidding-based task assignment"""
    
    def __init__(self):
        self.agents = []
        self.tasks = {}
    
    def announce_task(self, task):
        """Announce task to all agents"""
        task_id = task["id"]
        self.tasks[task_id] = {
            "task": task,
            "bids": [],
            "awarded_to": None
        }
        
        # Request bids from all agents
        for agent in self.agents:
            bid = agent.evaluate_task(task)
            if bid:
                self.tasks[task_id]["bids"].append({
                    "agent": agent,
                    "bid": bid
                })
    
    def award_task(self, task_id):
        """Award task to best bidder"""
        if task_id not in self.tasks:
            return None
        
        task_info = self.tasks[task_id]
        
        if not task_info["bids"]:
            return None
        
        # Select best bid
        best_bid = max(
            task_info["bids"],
            key=lambda x: x["bid"]["score"]
        )
        
        # Award task
        task_info["awarded_to"] = best_bid["agent"]
        best_bid["agent"].receive_task(task_info["task"])
        
        return best_bid["agent"]

class BiddingAgent:
    """Agent that bids on tasks"""
    
    def __init__(self, name, capabilities):
        self.name = name
        self.capabilities = capabilities
        self.current_workload = 0
    
    def evaluate_task(self, task):
        """Evaluate task and submit bid"""
        # Check if capable
        required = task.get("required_capabilities", [])
        if not all(cap in self.capabilities for cap in required):
            return None
        
        # Calculate bid score
        score = self._calculate_bid_score(task)
        
        return {
            "agent": self.name,
            "score": score,
            "estimated_time": self._estimate_time(task)
        }
    
    def _calculate_bid_score(self, task):
        """Calculate bid score (higher = better)"""
        # Factors: capability match, current workload, task priority
        capability_score = 0.5
        workload_score = 1.0 - (self.current_workload / 10)
        priority_score = task.get("priority", 0.5)
        
        return capability_score + workload_score + priority_score

# Usage
protocol = ContractNetProtocol()

# Register agents
protocol.agents = [
    BiddingAgent("researcher", ["search", "summarize"]),
    BiddingAgent("writer", ["write", "edit"])
]

# Announce task
protocol.announce_task({
    "id": "task_001",
    "type": "research",
    "required_capabilities": ["search"],
    "priority": 0.8
})

# Award to best bidder
winner = protocol.award_task("task_001")
```

---

## 🔄 Pattern 5: Workflow Orchestration

### Sequential Workflow

```python
class SequentialWorkflow:
    """Execute tasks in sequence"""
    
    def __init__(self, steps):
        self.steps = steps  # [(agent, task), ...]
        self.results = []
    
    def execute(self, initial_input):
        """Execute steps sequentially"""
        current_input = initial_input
        
        for i, (agent, task_template) in enumerate(self.steps):
            # Prepare task with input
            task = self._prepare_task(task_template, current_input, i)
            
            # Execute
            result = agent.execute(task)
            
            # Store result
            self.results.append({
                "step": i,
                "agent": agent.name,
                "task": task,
                "result": result
            })
            
            # Pass to next step
            current_input = result
        
        return current_input
    
    def _prepare_task(self, template, input_data, step_num):
        """Prepare task with context"""
        return {
            **template,
            "input": input_data,
            "previous_results": self.results[-3:] if self.results else []
        }

# Usage
workflow = SequentialWorkflow([
    (researcher, {"type": "research", "output": "findings"}),
    (analyst, {"type": "analyze", "output": "insights"}),
    (writer, {"type": "write", "output": "article"})
])

final_output = workflow.execute("AI agents")
```

### Parallel Workflow

```python
import concurrent.futures

class ParallelWorkflow:
    """Execute tasks in parallel"""
    
    def __init__(self, agents, task_generator):
        self.agents = agents
        self.task_generator = task_generator
    
    def execute(self, input_data):
        """Execute tasks in parallel"""
        # Generate tasks
        tasks = self.task_generator(input_data)
        
        results = []
        
        # Execute in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    agent.execute,
                    task
                ): (agent, task)
                for agent, task in zip(self.agents, tasks)
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(futures):
                agent, task = futures[future]
                try:
                    result = future.result()
                    results.append({
                        "agent": agent.name,
                        "task": task,
                        "result": result
                    })
                except Exception as e:
                    results.append({
                        "agent": agent.name,
                        "task": task,
                        "error": str(e)
                    })
        
        return results

# Usage
def generate_research_tasks(topic):
    """Generate parallel research tasks"""
    return [
        {"type": "search", "query": f"{topic} frameworks"},
        {"type": "search", "query": f"{topic} best practices"},
        {"type": "search", "query": f"{topic} case studies"}
    ]

workflow = ParallelWorkflow(
    agents=[researcher1, researcher2, researcher3],
    task_generator=generate_research_tasks
)

results = workflow.execute("AI agents")
```

### Conditional Workflow (LangGraph)

```python
from langgraph.graph import StateGraph, END

# Define state
class WorkflowState(TypedDict):
    input: str
    analysis: Optional[str]
    decision: Optional[str]
    output: Optional[str]

# Define conditional logic
def should_continue(state: WorkflowState) -> str:
    """Decide next step based on state"""
    if state.get("decision") == "research_more":
        return "research"
    elif state.get("decision") == "write":
        return "write"
    else:
        return END

# Build graph
graph = StateGraph(WorkflowState)

# Add nodes
graph.add_node("analyze", analyze_node)
graph.add_node("research", research_node)
graph.add_node("write", write_node)

# Add edges
graph.add_edge("analyze", "research")
graph.add_conditional_edges(
    "research",
    should_continue,
    {
        "research": "research",
        "write": "write",
        END: END
    }
)

# Compile
app = graph.compile()

# Run
result = app.invoke({"input": "Write about AI agents"})
```

---

## 📊 Communication Patterns Comparison

| Pattern | Best For | Complexity | Scalability |
|---------|----------|------------|-------------|
| Direct Messaging | Point-to-point communication | Low | Low |
| Pub/Sub | Event notifications | Medium | High |
| Shared State | Collaborative work | Medium | Medium |
| Push Coordination | Centralized control | Medium | Low-Medium |
| Pull Coordination | Decentralized work | Low-Medium | High |
| Contract Net | Competitive bidding | High | Medium |
| Sequential | Dependent tasks | Low | Low |
| Parallel | Independent tasks | Medium | High |

---

## 🎯 Best Practices

### 1. Choose Pattern Based on Use Case

```python
# Few agents, simple tasks → Direct messaging
agent_a.send_message(agent_b, "Task complete")

# Many agents, events → Pub/Sub
broker.publish("task_updates", message)

# Collaborative editing → Shared state
shared_state.set("document", content)

# Complex workflows → LangGraph
graph.add_conditional_edges(...)
```

### 2. Handle Failures

```python
class ResilientMessaging:
    def send_message(self, recipient, message, retries=3):
        """Send with retry logic"""
        for attempt in range(retries):
            try:
                return recipient.receive(message)
            except Exception as e:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
```

### 3. Monitor Communication

```python
class MonitoredCommunication:
    def __init__(self):
        self.metrics = {
            "messages_sent": 0,
            "messages_failed": 0,
            "avg_latency": 0
        }
    
    def send_message(self, recipient, message):
        start = time.time()
        try:
            result = recipient.receive(message)
            self.metrics["messages_sent"] += 1
            return result
        except Exception:
            self.metrics["messages_failed"] += 1
            raise
        finally:
            latency = time.time() - start
            self._update_avg_latency(latency)
```

---

**Next:** [Multi-Agent Coordination](./04-multi-agent-coordination.md)
