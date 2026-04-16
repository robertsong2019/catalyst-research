# AI Agent Programming - Quick Reference
**Date:** 2026-03-25

---

## Execution Modes Cheat Sheet

### Codex / Pi / OpenCode
```bash
# PTY mode required for terminal UIs
bash pty:true workdir:~/project command:"codex exec 'task'"

# Background for long tasks
bash pty:true workdir:~/project background:true command:"codex --yolo 'task'"
```

### Claude Code
```bash
# Print mode (no PTY)
bash workdir:~/project command:"claude --permission-mode bypassPermissions --print 'task'"

# Background
bash workdir:~/project background:true command:"claude --print 'task'"
```

---

## Agent Patterns at a Glance

| Pattern | Use Case | Key Feature |
|---------|----------|-------------|
| **Single Agent** | Quick tasks, one-offs | Direct execution |
| **Orchestrator** | Multi-step workflows | Phased execution, parallel sub-agents |
| **Ralph Loop** | Feature development | PRD-driven, fresh instances |
| **Better Ralph** | Simplified autonomous | One story per invocation |
| **Watch Mode** | Continuous monitoring | Polling with state tracking |

---

## Sub-agent Configuration

```yaml
# Standard sub-agent spawn
task: "Fix issue #42"
runtime: "subagent"
runTimeoutSeconds: 3600  # 1 hour
cleanup: "keep"  # Preserve for debugging

# With model override
model: "glm-5"

# Thread-bound (for chat platforms)
thread: true
mode: "session"
```

---

## Quality Gate Checklist

Before committing agent work:
- [ ] Tests pass
- [ ] Typecheck passes
- [ ] Lint passes
- [ ] No unrelated changes
- [ ] Commit message follows convention
- [ ] PR body describes changes

---

## Memory Files

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `memory/YYYY-MM-DD.md` | Daily raw logs | Every session |
| `MEMORY.md` | Curated long-term | Weekly review |
| `AGENTS.md` | Project patterns | As discovered |
| `progress.txt` | Ralph loop state | Per iteration |
| `prd.json` | Task definitions | Per feature |

---

## Coordination Patterns

### Claim System
```json
{
  "owner/repo#42": "2026-03-25T12:00:00Z"
}
```
- Prevents duplicate work
- Expires after 2 hours
- Check before spawning

### PR Tracking
```json
[
  {
    "number": 99,
    "branch": "fix/issue-42",
    "issue": 42
  }
]
```
- Skip issues with existing PRs
- Track for review handling

---

## Skill Structure

```
skill-name/
├── SKILL.md          # Required
│   ├── ---
│   │   name: skill-name
│   │   description: When to use
│   └── ---
│   └── Instructions
├── scripts/          # Executable helpers
├── references/       # Detailed docs
└── assets/           # Output templates
```

---

## Common Gotchas

1. **Context exhaustion** - Use fresh instances or auto-handoff
2. **PTY vs print** - Match mode to the tool (Codex=PTY, Claude=print)
3. **Rate limits** - Add delays, respect 429 headers
4. **Concurrent conflicts** - Use claims and branch isolation
5. **Silent failures** - Add monitoring and time limits

---

## Monitoring Commands

```bash
# List sub-agents
subagents action:list

# Check process
process action:poll sessionId:XXX

# Get output
process action:log sessionId:XXX

# Kill if stuck
subagents action:kill target:sessionId
```

---

## Key Numbers

- **Max concurrent agents:** 8
- **Default timeout:** 60 minutes
- **Claim expiration:** 2 hours
- **Context threshold:** 90% (for auto-handoff)
- **Description max:** 1024 characters
- **Name max:** 64 characters

---

*Quick reference for AI agent programming patterns*
