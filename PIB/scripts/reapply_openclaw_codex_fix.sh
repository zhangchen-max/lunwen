#!/bin/zsh

set -euo pipefail

timestamp="$(date +%Y%m%d-%H%M%S)"

config_path="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"
dispatch_path="${OPENCLAW_DISPATCH_PATH:-/opt/homebrew/lib/node_modules/openclaw/dist/plugin-sdk/dispatch-DwgTiP0N.js}"
provider_path="${OPENCLAW_PROVIDER_PATH:-/opt/homebrew/lib/node_modules/openclaw/node_modules/@mariozechner/pi-ai/dist/providers/openai-codex-responses.js}"

primary_model="openai-codex/gpt-5.4"
fallbacks_json='["openai-codex/gpt-5.3-codex","openai-codex/gpt-5.2"]'
models_json='{"openai-codex/gpt-5.4":{"params":{"transport":"sse","parallel_tool_calls":false}},"openai-codex/gpt-5.3-codex":{"params":{"transport":"sse","parallel_tool_calls":false}},"openai-codex/gpt-5.2":{"params":{"transport":"sse","parallel_tool_calls":false}}}'

log() {
  printf '[openclaw-fix] %s\n' "$*"
}

die() {
  printf '[openclaw-fix] ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

backup_file() {
  local src="$1"
  local dest="${src}.${timestamp}.bak"
  cp "$src" "$dest"
  log "backup created: $dest"
}

require_cmd openclaw
require_cmd python3

[[ -f "$config_path" ]] || die "missing config file: $config_path"
[[ -f "$dispatch_path" ]] || die "missing dispatch file: $dispatch_path"
[[ -f "$provider_path" ]] || die "missing provider file: $provider_path"

backup_file "$config_path"
backup_file "$dispatch_path"
backup_file "$provider_path"

log "applying OpenClaw model config"
openclaw config set agents.defaults.model.primary "\"${primary_model}\"" --strict-json
openclaw config set agents.defaults.model.fallbacks "$fallbacks_json" --strict-json
openclaw config set agents.defaults.models "$models_json" --strict-json

log "patching installed OpenClaw runtime"
python3 - "$dispatch_path" "$provider_path" <<'PY'
import sys
from pathlib import Path


dispatch_path = Path(sys.argv[1])
provider_path = Path(sys.argv[2])


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"missing expected snippet for {label}")
    return text.replace(old, new, 1)


dispatch_text = dispatch_path.read_text()
dispatch_old = """function createCodexDefaultTransportWrapper(baseStreamFn) {\n\tconst underlying = baseStreamFn ?? streamSimple;\n\treturn (model, context, options) => underlying(model, context, {\n\t\t...options,\n\t\ttransport: options?.transport ?? \"auto\"\n\t});\n}\n"""
dispatch_new = """function createCodexDefaultTransportWrapper(baseStreamFn) {\n\tconst underlying = baseStreamFn ?? streamSimple;\n\treturn (model, context, options) => underlying(model, context, {\n\t\t...options,\n\t\ttransport: options?.transport ?? \"sse\"\n\t});\n}\n"""
dispatch_text = replace_once(dispatch_text, dispatch_old, dispatch_new, "codex default transport")
dispatch_path.write_text(dispatch_text)

provider_text = provider_path.read_text()

provider_text = replace_once(
    provider_text,
    'const NODE_OS_SPECIFIER = "node:" + "os";\n',
    'const NODE_OS_SPECIFIER = "node:" + "os";\nconst NODE_CHILD_PROCESS_SPECIFIER = "node:" + "child_process";\n',
    "child_process import",
)

provider_text = replace_once(
    provider_text,
    "    const messages = convertResponsesMessages(model, context, CODEX_TOOL_CALL_PROVIDERS, {\n        includeSystemPrompt: false,\n    });\n    const body = {\n",
    "    const messages = convertResponsesMessages(model, context, CODEX_TOOL_CALL_PROVIDERS, {\n        includeSystemPrompt: false,\n    });\n    const parallelToolCalls = options?.parallel_tool_calls ?? options?.parallelToolCalls ?? false;\n    const body = {\n",
    "parallel tool calls default",
)

provider_text = replace_once(
    provider_text,
    "        parallel_tool_calls: true,\n",
    "        parallel_tool_calls: parallelToolCalls,\n",
    "parallel_tool_calls assignment",
)

fetch_bridge_old = """                    lastError = error instanceof Error ? error : new Error(String(error));\n                    // Network errors are retryable\n"""
fetch_bridge_new = """                    lastError = error instanceof Error ? error : new Error(String(error));\n                    if (shouldUsePythonCodexBridge(lastError)) {\n                        stream.push({ type: \"start\", partial: output });\n                        await processResponsesStream(mapCodexEvents(streamCodexEventsViaPython(resolveCodexUrl(model.baseUrl), headersToRecord(headers), bodyJson, options?.signal)), output, stream, model);\n                        if (options?.signal?.aborted) {\n                            throw new Error(\"Request was aborted\");\n                        }\n                        stream.push({ type: \"done\", reason: output.stopReason, message: output });\n                        stream.end();\n                        return;\n                    }\n                    // Network errors are retryable\n"""
provider_text = replace_once(provider_text, fetch_bridge_old, fetch_bridge_new, "python bridge trigger")

helper_anchor = """// ============================================================================\n// WebSocket Parsing\n// ============================================================================\n"""
helper_block = """async function* parseSSEChunks(chunks) {\n    const decoder = new TextDecoder();\n    let buffer = \"\";\n    for await (const value of chunks) {\n        buffer += decoder.decode(value, { stream: true });\n        let idx = buffer.indexOf(\"\\n\\n\");\n        while (idx !== -1) {\n            const chunk = buffer.slice(0, idx);\n            buffer = buffer.slice(idx + 2);\n            const dataLines = chunk\n                .split(\"\\n\")\n                .filter((l) => l.startsWith(\"data:\"))\n                .map((l) => l.slice(5).trim());\n            if (dataLines.length > 0) {\n                const data = dataLines.join(\"\\n\").trim();\n                if (data && data !== \"[DONE]\") {\n                    try {\n                        yield JSON.parse(data);\n                    }\n                    catch { }\n                }\n            }\n            idx = buffer.indexOf(\"\\n\\n\");\n        }\n    }\n}\nfunction shouldUsePythonCodexBridge(error) {\n    if (!(typeof process !== \"undefined\" && (process.versions?.node || process.versions?.bun))) {\n        return false;\n    }\n    const message = error instanceof Error ? error.message : String(error);\n    const cause = error instanceof Error ? error.cause : undefined;\n    const causeCode = typeof cause === \"object\" && cause && \"code\" in cause ? String(cause.code) : \"\";\n    const causeMessage = typeof cause === \"object\" && cause && \"message\" in cause ? String(cause.message) : \"\";\n    return message.includes(\"fetch failed\") || causeCode === \"ECONNRESET\" || causeMessage.includes(\"ECONNRESET\");\n}\nasync function* streamCodexEventsViaPython(url, headers, bodyJson, signal) {\n    const childProcess = await dynamicImport(NODE_CHILD_PROCESS_SPECIFIER);\n    const python = process.env.PYTHON || \"python3\";\n    const script = [\n        \"import json, sys, urllib.request, urllib.error\",\n        \"url = sys.argv[1]\",\n        \"headers = json.loads(sys.argv[2])\",\n        \"body = sys.argv[3].encode()\",\n        \"req = urllib.request.Request(url, method='POST', headers=headers, data=body)\",\n        \"try:\",\n        \"    with urllib.request.urlopen(req, timeout=600) as resp:\",\n        \"        while True:\",\n        \"            chunk = resp.read(8192)\",\n        \"            if not chunk:\",\n        \"                break\",\n        \"            sys.stdout.buffer.write(chunk)\",\n        \"            sys.stdout.buffer.flush()\",\n        \"except urllib.error.HTTPError as exc:\",\n        \"    sys.stderr.write(exc.read(4096).decode('utf-8', 'replace'))\",\n        \"    sys.exit(1)\",\n        \"except Exception as exc:\",\n        \"    sys.stderr.write(str(exc))\",\n        \"    sys.exit(1)\",\n    ].join(\"\\n\");\n    const child = childProcess.spawn(python, [\"-u\", \"-c\", script, url, JSON.stringify(headers), bodyJson], {\n        stdio: [\"ignore\", \"pipe\", \"pipe\"],\n    });\n    let stderr = \"\";\n    const onAbort = () => {\n        try {\n            child.kill(\"SIGTERM\");\n        }\n        catch { }\n    };\n    signal?.addEventListener(\"abort\", onAbort, { once: true });\n    child.stderr?.on(\"data\", (chunk) => {\n        stderr += chunk.toString(\"utf8\");\n        if (stderr.length > 4000)\n            stderr = stderr.slice(-4000);\n    });\n    try {\n        for await (const event of parseSSEChunks(child.stdout)) {\n            yield event;\n        }\n        const exit = await new Promise((resolve, reject) => {\n            child.once(\"error\", reject);\n            child.once(\"close\", (code, childSignal) => resolve({ code, signal: childSignal }));\n        });\n        if (signal?.aborted) {\n            throw new Error(\"Request was aborted\");\n        }\n        if (exit.code !== 0) {\n            const detail = stderr.trim();\n            throw new Error(detail || `Python Codex bridge exited with code ${exit.code ?? \"unknown\"}`);\n        }\n    }\n    finally {\n        signal?.removeEventListener(\"abort\", onAbort);\n    }\n}\n// ============================================================================\n// WebSocket Parsing\n// ============================================================================\n"""
provider_text = replace_once(provider_text, helper_anchor, helper_block, "python bridge helpers")

provider_path.write_text(provider_text)
PY

log "validating config"
openclaw config validate

log "restarting gateway"
openclaw gateway restart

log "probing openai-codex provider"
openclaw models status --probe --probe-provider openai-codex --json

log "repair complete"
