# Exploration: edge-agent-tiny (2026-03-30)

## What
Created **edge-agent-tiny** — a <500 line AI agent framework in C that can run on microcontrollers (ESP32, Pico W).

## Repo
https://github.com/robertsong2019/edge-agent-tiny

## Key Design Decisions
- **Core loop**: Observe → Think → Act pattern in pure C (~300 lines)
- **Memory**: ~16KB total working set (fits on devices with 256KB RAM)
- **Tool system**: Register sensors/actuators as named callbacks
- **LLM interface**: Abstracted `api_call` function pointer — platform provides HTTP/WS transport
- **Conversation**: Sliding window of last 3 turns (keeps memory bounded)
- **Tool call protocol**: Simple `tool:name(params)` text format (avoids JSON parser dependency)

## What Worked
- Clean compile with -Wall -Wextra, zero warnings
- Simulator runs smoothly with mock plant monitor
- Agent loop correctly cycles through observe → think → act states

## Next Steps Ideas
- ESP32 port (WiFi HTTP client for real API calls)
- TinyJSON parser for proper tool call parsing
- Multi-agent message passing via ESP-NOW
- Safe actuator limits (prevent hardware damage from bad LLM responses)
- Compare with MicroPython-based agent approaches

## Insights
- AI Agent pattern doesn't need heavy frameworks — the core loop is ~50 lines
- The real constraint on embedded isn't CPU, it's **network latency and RAM for HTTP buffers**
- Tool registration pattern from LangChain/etc maps directly to C function pointers
- "Offline-first" design matters — agent should degrade gracefully when WiFi drops

## Tags
`ai-agent` `embedded` `edge-computing` `c` `iot` `experimental`
