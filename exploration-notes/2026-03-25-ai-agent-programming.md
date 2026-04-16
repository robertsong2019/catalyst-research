# AI Agent Programming - Deep Exploration
**Date:** 2026-03-25
**Duration:** ~2 hours
**Focus:** AI Agent Frameworks, Orchestration Patterns, and Multi-Agent Systems

---

## Executive Summary

Explored the landscape of AI agent programming through hands-on analysis of real-world implementations including OpenClaw's skill system, autonomous coding loops (Ralph pattern), multi-agent orchestration for GitHub automation, and the Agent Skills standard. Key insights: the field is moving from single-purpose agents to orchestrated multi-agent systems with progressive disclosure patterns, persistent memory, and PRD-driven autonomy.

---

## Table of Contents

1. [Agent Architecture Patterns](#agent-architecture-patterns)
2. [Multi-Agent Orchestration](#multi-agent-orchestration)
3. [Autonomous Coding Loops](#autonomous-coding-loops)
4. [Skill Systems & Progressive Disclosure](#skill-systems--progressive-disclosure)
5. [Memory & State Management](#memory--state-management)
6. [Tool Integration Patterns](#tool-integration-patterns)
7. [Challenges & Trade-offs](#challenges--trade-offs)
8. [Future Directions](#future-directions)
9. [Key Learnings](#key-learnings)

---

## 1. Agent Architecture Patterns

### 1.1 The Anatomy of an AI Agent

Modern AI agents consist of several key components:

```
┌─────────────────────────────────────────┐
│         AI Agent Architecture           │
├─────────────────────────────────────────┤
│  1. Core Loop (Reason → Act → Observe) │
│  2. Tool System (Capabilities)          │
│  3. Memory (Context & State)            │
│  4. Skills (Domain Expertise)           │
│  5. Orchestration Layer                 │
└─────────────────────────────────────────┘
```

**Key Insight:** Agents are not monolithic - they're composed of modular systems that can be mixed and matched.

### 1.2 Three Execution Modes

From analyzing the coding-agent skill, there are three distinct execution modes:

1. **Interactive (PTY Mode)**
   - Required for: Codex, Pi, OpenCode
   - Why: These are terminal UI apps that need pseudo-terminal allocation
   - Pattern: `pty:true` in exec commands

2. **Print Mode (Non-Interactive)**
   - Required for: Claude Code
   - Why: Uses `--print --permission-mode bypassPermissions` for programmatic execution
   - Pattern: No PTY, direct command execution

3. **Background Mode**
   - For long-running tasks
   - Returns sessionId for monitoring
   - Pattern: `background:true` with process polling

**Example from coding-agent skill:**
```bash
# Codex (PTY required)
bash pty:true workdir:~/project command:"codex exec 'Build a snake game'"

# Claude Code (no PTY)
bash workdir:~/project command:"claude --permission-mode bypassPermissions --print 'Your task'"

# Background execution
bash pty:true workdir:~/project background:true command:"codex --yolo 'Refactor the auth module'"
```

---

## 2. Multi-Agent Orchestration

### 2.1 The Orchestrator Pattern

The gh-issues skill demonstrates a sophisticated orchestrator that manages multiple sub-agents:

```
┌──────────────────────────────────────────┐
│          Orchestrator Agent              │
├──────────────────────────────────────────┤
│  Phase 1: Parse Arguments                │
│  Phase 2: Fetch Issues (via API)         │
│  Phase 3: Present & Confirm              │
│  Phase 4: Pre-flight Checks              │
│  Phase 5: Spawn Sub-agents (Parallel)    │
│  Phase 6: Monitor & Handle Reviews       │
└──────────────────────────────────────────┘
           │                    │
           ▼                    ▼
    ┌─────────────┐      ┌─────────────┐
    │ Sub-agent 1 │      │ Sub-agent 2 │
    │ (Issue #42) │      │ (Issue #37) │
    └─────────────┘      └─────────────┘
```

**Key Principles:**

1. **Phased Execution:** Break complex workflows into distinct phases with clear boundaries
2. **Parallel Processing:** Spawn up to 8 concurrent sub-agents
3. **State Management:** Track processed issues, addressed comments, open PRs
4. **Error Recovery:** Each phase has explicit error handling and recovery paths

### 2.2 Sub-agent Isolation

Each sub-agent gets:
- Isolated context (only relevant issue data)
- Specific constraints (time limits, file restrictions)
- Clear success criteria (PR opened, tests pass)
- Cleanup policies (`cleanup: "keep"` for debugging)

**Sub-agent prompt structure (from gh-issues):**
```
You are a focused code-fix agent.

<config>
Source repo: owner/repo
Base branch: main
Time limit: 60 minutes
</config>

<issue>
#42: Fix null pointer in parser
Body: [issue details]
</issue>

<instructions>
1. UNDERSTAND - Read the issue
2. BRANCH - Create feature branch
3. ANALYZE - Search codebase
4. IMPLEMENT - Make focused fix
5. TEST - Run existing tests
6. COMMIT - With conventional message
7. PUSH - To remote
8. PR - Create via API
</instructions>

<constraints>
- No force-push
- No unrelated changes
- Time limit: 60 minutes
</constraints>
```

### 2.3 Claim-Based Coordination

To prevent duplicate work, the orchestrator uses a claim system:

```json
{
  "owner/repo#42": "2026-03-25T12:00:00Z",
  "owner/repo#37": "2026-03-25T12:15:00Z"
}
```

**Claim lifecycle:**
1. Orchestrator claims issue before spawning agent
2. Claims expire after 2 hours (agent likely failed/finished)
3. Prevents duplicate processing across cron runs
4. Works across multiple orchestrator instances

---

## 3. Autonomous Coding Loops

### 3.1 The Ralph Pattern

The Ralph pattern (from Geoffrey Huntley) enables autonomous coding by:

1. **PRD-Driven:** Tasks defined in `prd.json` with acceptance criteria
2. **Fresh Instances:** Each iteration spawns a new AI instance
3. **Persistent Memory:** Git history, `progress.txt`, `prd.json`
4. **Self-Validation:** Quality checks before marking stories complete

**PRD.json structure:**
```json
{
  "branchName": "feature/user-dashboard",
  "projectContext": "Next.js SaaS app with Prisma, tRPC",
  "userStories": [
    {
      "id": "story-1",
      "title": "Add avatar column to users table",
      "priority": 1,
      "passes": false,
      "description": "Add avatarUrl via Prisma migration",
      "acceptanceCriteria": [
        "Migration created and applied",
        "TypeScript types regenerated",
        "Existing tests still pass"
      ]
    }
  ]
}
```

### 3.2 Iteration Workflow

```
┌──────────────────────────────────────┐
│   Ralph Loop Iteration               │
├──────────────────────────────────────┤
│  1. Read prd.json                    │
│  2. Pick highest-priority story      │
│     where passes: false              │
│  3. Spawn fresh AI instance          │
│  4. AI implements story              │
│  5. Run quality checks               │
│  6. If pass:                         │
│     - Commit                         │
│     - Set passes: true               │
│     - Append to progress.txt         │
│  7. Repeat until all stories pass    │
└──────────────────────────────────────┘
```

**Key Innovation:** Memory persists through files, not through context. Each iteration starts fresh but can read what previous iterations learned.

### 3.3 Better Ralph (Single-Agent Variant)

The Better Ralph skill shows a simplified approach where the orchestrator IS the agent:

**Advantages:**
- No external runner needed
- Uses standard OpenClaw tools (read, write, exec, git)
- One story per invocation
- Explicit quality gate before commit

**Trade-off:** Cannot parallelize multiple stories simultaneously.

### 3.4 Context Window Management

For long-running loops, context exhaustion is real:

**Amp solution:** Auto-handoff at 90% context
```json
{
  "amp.experimental.autoHandoff": { "context": 90 }
}
```

**Ralph solution:** Fresh instances per iteration naturally reset context.

---

## 4. Skill Systems & Progressive Disclosure

### 4.1 The Agent Skills Standard

The [Agent Skills specification](https://agentskills.io/specification) defines a standard format for agent capabilities:

**Skill structure:**
```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter
│   │   ├── name: skill-name
│   │   └── description: When to use
│   └── Markdown instructions
├── scripts/        # Executable helpers
├── references/     # Detailed docs
└── assets/         # Output templates
```

### 4.2 Progressive Disclosure

Skills use a three-level loading system:

```
Level 1: Metadata (always in context)
  - name: "pdf-processing"
  - description: "Extracts text and tables from PDFs"
  - ~100 words

Level 2: SKILL.md body (loaded when triggered)
  - Instructions
  - Setup steps
  - Usage examples
  - <5k words

Level 3: Bundled resources (loaded as needed)
  - scripts/ for execution
  - references/ for deep dives
  - assets/ for output
  - Unlimited (scripts don't load into context)
```

**Why this matters:**
- Context window is a scarce resource
- Only load what's needed when it's needed
- Skills share context with conversation history, system prompt, other skills

### 4.3 Skill Design Principles

From analyzing multiple skills:

1. **Concise is Key**
   - Challenge every paragraph: "Does this justify its token cost?"
   - Prefer examples over explanations
   - Assume the model is already smart

2. **Set Appropriate Degrees of Freedom**
   - High freedom: Text-based instructions (multiple approaches valid)
   - Medium freedom: Pseudocode with parameters (preferred pattern exists)
   - Low freedom: Specific scripts (fragile operations, must follow exactly)

3. **Avoid Duplication**
   - Information lives in ONE place
   - Either SKILL.md OR references/, not both
   - Cross-reference clearly

**Example - High freedom skill:**
```markdown
---
name: code-review
description: Review code for bugs, security issues, and improvements
---

# Code Review

Review the provided code for:
- Logic errors
- Security vulnerabilities
- Performance issues
- Code style violations

Provide actionable feedback with specific line references.
```

**Example - Low freedom skill:**
```markdown
---
name: database-migration
description: Create Prisma migrations for schema changes
---

# Database Migration

## Steps (follow exactly)

1. Edit prisma/schema.prisma
2. Run: `npx prisma migrate dev --name description`
3. Verify migration file in prisma/migrations/
4. Run: `npx prisma generate`

## Validation

After migration:
- TypeScript compiles
- Tests pass
- Migration applies cleanly
```

### 4.4 Skill Discovery & Triggering

Skills trigger based on description matching:

**Good description:**
```yaml
description: Extracts text and tables from PDF files, fills PDF forms, and merges PDFs. Use when working with PDF documents.
```

**Poor description:**
```yaml
description: Helps with PDFs.
```

**Pattern:** Include both WHAT the skill does and WHEN to use it in the description.

---

## 5. Memory & State Management

### 5.1 Memory Types in Agent Systems

From analyzing OpenClaw's AGENTS.md and various skills:

```
┌────────────────────────────────────────┐
│      Agent Memory Types                │
├────────────────────────────────────────┤
│  1. Session Memory (conversation)      │
│  2. Daily Notes (memory/YYYY-MM-DD.md) │
│  3. Long-term Memory (MEMORY.md)       │
│  4. Project Memory (AGENTS.md)         │
│  5. Skill Memory (progress.txt)        │
│  6. State Files (JSON)                 │
└────────────────────────────────────────┘
```

### 5.2 File-Based Persistence

Agents wake up fresh each session. Files provide continuity:

**Daily Notes (raw logs):**
```markdown
# 2026-03-25

## Morning
- Explored AI agent frameworks
- Set up Ralph loop for feature branch

## Afternoon
- Reviewed 3 PRs from sub-agents
- Fixed issue #42 in parser
```

**Long-term Memory (curated):**
```markdown
# MEMORY.md

## Key Decisions
- Use PTY mode for Codex, print mode for Claude Code
- Always check for existing PRs before spawning fix agents

## Lessons Learned
- Context window exhaustion is real - use fresh instances
- Claims prevent duplicate work in parallel orchestration
```

**Project Memory (AGENTS.md):**
```markdown
# AGENTS.md

## Patterns
- All agents use curl + GitHub REST API (no gh CLI)
- Time limit: 60 minutes per sub-agent
- Cleanup: "keep" for debugging

## Gotchas
- GH_TOKEN must be exported before API calls
- Fork mode requires separate push remote
```

### 5.3 State Files for Coordination

**Cursor tracking (cron mode):**
```json
{
  "last_processed": 42,
  "in_progress": 43
}
```

**Claims tracking:**
```json
{
  "owner/repo#42": "2026-03-25T12:00:00Z",
  "owner/repo#43": "2026-03-25T12:30:00Z"
}
```

**PR tracking:**
```json
[
  {
    "number": 99,
    "branch": "fix/issue-42",
    "issue": 42,
    "url": "https://github.com/owner/repo/pull/99"
  }
]
```

---

## 6. Tool Integration Patterns

### 6.1 Tool System Architecture

From OpenClaw's tool policy:

```
┌─────────────────────────────────────┐
│      Tool Availability              │
├─────────────────────────────────────┤
│  Core Tools (always available)      │
│  - read, write, edit                │
│  - exec, process                    │
│  - web_search, web_fetch            │
│                                     │
│  Channel Tools (configured)         │
│  - message (Discord, Telegram, etc) │
│                                     │
│  Integration Tools (optional)       │
│  - feishu_doc, feishu_drive         │
│  - sessions_spawn, subagents        │
│                                     │
│  Utility Tools                      │
│  - tts, canvas, cron                │
└─────────────────────────────────────┘
```

### 6.2 Tool Call Best Practices

From analyzing skill implementations:

1. **Batch Operations**
   - Don't loop one-item-at-a-time
   - Prefer fewer larger writes
   - Serialize bursts when possible

2. **Error Handling**
   - Check HTTP status codes
   - Parse error messages
   - Provide actionable feedback

3. **Rate Limiting**
   - Respect 429 / Retry-After headers
   - Add delays between API calls
   - Use background mode for long operations

### 6.3 Sub-agent Spawning

The `sessions_spawn` tool enables agent orchestration:

**Configuration options:**
```yaml
task: "Your task description"
runtime: "subagent"  # or "acp" for ACP harness
agentId: "specific-agent"  # optional
model: "glm-5"  # optional override
runTimeoutSeconds: 3600  # 1 hour
cleanup: "keep"  # or "delete"
mode: "run"  # or "session" for persistent
thread: true  # for thread-bound sessions
```

**Monitoring spawned agents:**
```bash
# List all sub-agents
subagents action:list

# Check status
subagents action:steer target:sessionId message:"status update"

# Kill if needed
subagents action:kill target:sessionId
```

---

## 7. Challenges & Trade-offs

### 7.1 Context Window Exhaustion

**Problem:** Long-running tasks exceed context limits.

**Solutions:**
1. Fresh instances per iteration (Ralph pattern)
2. Auto-handoff at threshold (Amp experimental)
3. Progressive disclosure (skills)
4. External memory (files)

**Trade-off:** Fresh instances lose conversational context.

### 7.2 Agent Reliability

**Problem:** Agents can get stuck, loop, or fail silently.

**Solutions:**
1. Time limits (60 minutes per sub-agent)
2. Quality gates (tests must pass before commit)
3. Monitoring (process polling)
4. Claim expiration (2-hour timeout)

**Trade-off:** Time limits may cut off legitimate long tasks.

### 7.3 Coordination Complexity

**Problem:** Multiple agents working simultaneously can conflict.

**Solutions:**
1. Branch isolation (each agent gets own branch)
2. Claim system (prevent duplicate work)
3. PR tracking (skip issues with existing PRs)
4. Sequential fallback (process one at a time)

**Trade-off:** Coordination overhead reduces parallelism benefits.

### 7.4 Tool Dependency Hell

**Problem:** Skills may require specific tools, APIs, or configurations.

**Solutions:**
1. Explicit prerequisites in skill frontmatter
2. Validation checks at skill load time
3. Graceful degradation (warn but continue)
4. Containerization (future)

**Trade-off:** Prerequisites create friction for adoption.

---

## 8. Future Directions

### 8.1 Emerging Patterns

Based on current implementations:

1. **Hybrid Orchestration**
   - Mix of orchestrated and autonomous agents
   - Human-in-the-loop for critical decisions
   - Graduated autonomy based on confidence

2. **Cross-Agent Communication**
   - Agents sharing insights via shared memory
   - Broadcast channels for coordination
   - Pub/sub patterns for event-driven orchestration

3. **Self-Improving Agents**
   - Agents that update their own skills
   - Learning from failures
   - Automatic skill generation

### 8.2 Technical Evolution

1. **Better Context Management**
   - Semantic compression of context
   - Hierarchical memory systems
   - Dynamic context prioritization

2. **Improved Tooling**
   - Standardized agent communication protocols
   - Better debugging and introspection
   - Visual orchestration builders

3. **Safety & Alignment**
   - Constrained execution environments
   - Audit logging and replay
   - Formal verification of agent behaviors

---

## 9. Key Learnings

### 9.1 Architecture Insights

1. **Modularity Wins**
   - Separate concerns: orchestration, execution, memory
   - Skills as composable building blocks
   - Clear interfaces between components

2. **Progressive Disclosure is Critical**
   - Don't load everything into context
   - Metadata → Instructions → Details
   - Scripts can execute without loading

3. **State Management is Hard**
   - Files are simple but limited
   - Claims prevent conflicts but add overhead
   - Balance between persistence and freshness

### 9.2 Implementation Insights

1. **PTY vs Print Mode**
   - Terminal UI apps need PTY
   - Programmatic agents use print mode
   - Choose based on the tool, not preference

2. **Parallelism Limits**
   - 8 concurrent agents is a good default
   - Too many creates coordination overhead
   - Sequential is simpler for dependent tasks

3. **Quality Gates are Essential**
   - Never commit failing code
   - Run tests before marking complete
   - Validation prevents cascading failures

### 9.3 Design Insights

1. **Description Drives Discovery**
   - Be specific in skill descriptions
   - Include both WHAT and WHEN
   - Poor descriptions = poor triggering

2. **Constraints Guide Behavior**
   - Time limits prevent runaway agents
   - File restrictions reduce scope creep
   - Clear success criteria enable autonomy

3. **Memory Enables Continuity**
   - Daily notes for raw logs
   - Curated memory for long-term
   - State files for coordination

---

## 10. Practical Applications

### 10.1 When to Use Agents

**Good use cases:**
- Repetitive, well-defined tasks (issue fixing, PR reviews)
- Multi-step workflows with clear phases
- Tasks requiring parallel processing
- Long-running operations with monitoring

**Poor use cases:**
- One-off simple edits (just use edit tool)
- Tasks requiring deep context understanding
- Highly creative or ambiguous work
- Critical operations without human oversight

### 10.2 Agent Selection Guide

| Task Type | Agent Type | Execution Mode |
|-----------|------------|----------------|
| Code generation | Codex | PTY, background |
| Code review | Claude Code | Print, foreground |
| Issue fixing | Sub-agent | PTY, 60min timeout |
| Multi-repo work | Orchestrator | Phased, parallel |
| Long feature | Ralph loop | Fresh instances |
| Quick question | Direct chat | No agent needed |

### 10.3 Building Your Own Agent System

**Step 1: Define the workflow**
- What phases are needed?
- What state must persist?
- What are success criteria?

**Step 2: Choose the pattern**
- Single agent with tools
- Orchestrator + sub-agents
- Autonomous loop with PRD

**Step 3: Implement memory**
- File-based for simplicity
- JSON for structured state
- Git for version history

**Step 4: Add quality gates**
- Validation before commit
- Tests must pass
- Time limits for safety

**Step 5: Monitor and iterate**
- Log everything
- Track success rates
- Refine based on failures

---

## 11. Code Examples

### 11.1 Basic Agent Spawning

```bash
# Spawn a sub-agent for issue fixing
bash pty:true workdir:~/project background:true command:"codex exec --full-auto '
Fix GitHub issue #42.

Steps:
1. Read the issue
2. Locate relevant code
3. Make minimal fix
4. Run tests
5. Commit with message: fix: #42 - description
'"
```

### 11.2 Orchestrator Pattern

```python
# Pseudo-code for orchestrator
class IssueOrchestrator:
    def __init__(self):
        self.claims = load_claims()
        self.processed = set()
    
    def run(self):
        issues = fetch_issues()
        for issue in issues:
            if self.is_claimed(issue):
                continue
            if self.has_pr(issue):
                continue
            
            self.claim(issue)
            spawn_subagent(issue)
    
    def claim(self, issue):
        self.claims[issue.id] = timestamp()
        save_claims(self.claims)
```

### 11.3 Ralph Loop Implementation

```bash
#!/bin/bash
# ralph.sh - Autonomous coding loop

MAX_ITERATIONS=${1:-10}
ITERATION=0

while [ $ITERATION -lt $MAX_ITERATIONS ]; do
    # Check if all stories complete
    if all_stories_complete prd.json; then
        echo "<promise>COMPLETE</promise>"
        exit 0
    fi
    
    # Pick next story
    STORY=$(pick_next_story prd.json)
    
    # Spawn fresh AI instance
    claude --print "
    You are implementing: $STORY
    
    Context from progress.txt:
    $(cat progress.txt)
    
    Implement this story, run quality checks, and commit.
    " > /tmp/ralph-output.txt
    
    # Update PRD if successful
    if quality_checks_pass; then
        mark_story_complete "$STORY"
        append_progress "$STORY"
    fi
    
    ITERATION=$((ITERATION + 1))
done
```

### 11.4 Skill Definition

```markdown
---
name: automated-testing
description: Generate and run tests for code changes. Use when adding new features or fixing bugs to ensure test coverage.
---

# Automated Testing

## Setup

Ensure testing framework is installed:
\`\`\`bash
npm install --save-dev jest @types/jest
\`\`\`

## Workflow

1. **Analyze Code**
   - Read the file to test
   - Identify functions and edge cases
   - Check existing test patterns

2. **Generate Tests**
   - Create test file: `filename.test.ts`
   - Cover happy path
   - Cover error cases
   - Cover edge cases

3. **Run Tests**
   \`\`\`bash
   npm test -- filename.test.ts
   \`\`\`

4. **Validate Coverage**
   - Aim for >80% coverage
   - Focus on critical paths

## Example

For `src/utils/parser.ts`:
\`\`\`typescript
// src/utils/parser.test.ts
import { parse } from './parser';

describe('parse', () => {
  it('should parse valid input', () => {
    expect(parse('valid')).toEqual({ /* ... */ });
  });
  
  it('should throw on invalid input', () => {
    expect(() => parse('invalid')).toThrow();
  });
});
\`\`\`

## References

- [Testing Best Practices](references/testing-patterns.md)
- [Coverage Guide](references/coverage.md)
```

---

## 12. Resources & References

### 12.1 Key Projects Analyzed

1. **OpenClaw** - AI assistant framework with skill system
2. **Ralph Pattern** - Autonomous coding loop by Geoffrey Huntley
3. **Pi Coding Agent** - Terminal-based AI coding assistant
4. **Agent Skills Spec** - Standard for agent capabilities
5. **Claude Code** - Anthropic's coding agent CLI

### 12.2 Further Reading

- [Agent Skills Specification](https://agentskills.io/specification)
- [Ralph Pattern](https://ghuntley.com/ralph/)
- [Claude Code Documentation](https://docs.anthropic.com/claude-code)
- [Amp Documentation](https://ampcode.com/manual)

### 12.3 Tools & Frameworks

- **Orchestration:** OpenClaw sessions_spawn, subagents
- **Coding Agents:** Codex, Claude Code, Pi, OpenCode
- **Skill Management:** ClawHub, skill-creator
- **Version Control:** Git, GitHub API

---

## Conclusion

AI agent programming is evolving rapidly from simple single-purpose tools to sophisticated multi-agent systems. Key trends:

1. **Orchestration over monoliths** - Coordinated agents beat single agents
2. **Progressive disclosure** - Context efficiency through staged loading
3. **File-based memory** - Simple persistence for complex workflows
4. **Quality gates** - Validation before action prevents cascading failures
5. **Standardization** - Agent Skills spec enables interoperability

The future points toward hybrid systems where humans and agents collaborate, with agents handling repetitive tasks while humans provide oversight and creative direction.

---

**Next Steps:**
- Explore MCP (Model Context Protocol) for tool standardization
- Investigate agent communication protocols
- Study safety and alignment in autonomous systems
- Build a custom skill for a specific workflow
- Experiment with multi-agent orchestration patterns

---

*Notes generated from deep exploration session - March 25, 2026*
