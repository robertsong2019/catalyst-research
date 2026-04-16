# 2026-04-05 Agent Playground

## Project Created
**Repo:** https://github.com/robertsong2019/agent-playground

5 single-file AI agent experiments, zero frameworks:

| # | File | Pattern | Key Insight |
|---|------|---------|-------------|
| 1 | `repl_agent.py` | Tool-Use Loop | OpenAI function calling → tool dispatch → observe → repeat |
| 2 | `debate.py` | Multi-Agent Debate | Two agents with opposing system prompts + judge agent |
| 3 | `reflection.py` | Self-Critique | Agent writes → reviews own output → rewrites iteratively |
| 4 | `planner.py` | Plan-then-Execute | Separate planner prompt (decompose) → executor prompt (step-by-step) |
| 5 | `stream_agent.py` | Pipeline | Ideator → Architect → Coder → Tester → Documenter chain |

## Key Design Decisions
- **Single-file**: Each experiment is self-contained, easy to read and hack
- **No frameworks**: Raw `openai` Python client only — shows the building blocks
- **~100-200 lines each**: Enough to be real, short enough to understand in one sitting
- **Consistent patterns**: All use `chat()` helper, env var for model, `__main__` with CLI args

## Patterns Worth Noting
1. **Tool-Use** is the foundation — most agent frameworks are this loop with abstractions on top
2. **Debate** shows how different system prompts create different "personas" from the same model
3. **Reflection** is surprisingly effective — 2-3 iterations of self-critique dramatically improves output
4. **Planner** separates reasoning into planning vs execution — key for complex tasks
5. **Pipeline** is essentially a specialized version of planner where each step has a fixed role

## Next Ideas
- Add a `memory_agent.py` with RAG (embeddings + retrieval)
- Add a `tool_maker.py` that generates its own tools at runtime
- Add an `evolution_agent.py` that evolves prompts via genetic algorithms
