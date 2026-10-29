# PIB Resume Steps

## Immediate unblocks

### OpenAI
```bash
export OPENAI_API_KEY=...
```

### Anthropic
```bash
export ANTHROPIC_API_KEY=...
```

### Qwen3-14B (OpenAI-compatible endpoint)
Provide a reachable endpoint, for example:
```bash
export QWEN_ENDPOINT=http://<host>:<port>/v1/chat/completions
```
Optional quick check:
```bash
curl -s http://<host>:<port>/v1/models
```

## What can be resumed immediately after that
1. Re-check provider availability.
2. Run dynamic benchmarks for GPT-5.2, Claude Sonnet 4.6, and Qwen3-14B.
3. Add static controls for the strongest external models.
4. Refresh the scoreboard CSV and slide deck.
