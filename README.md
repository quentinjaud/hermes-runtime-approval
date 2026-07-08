# Runtime Approval Plugin

Runtime-enforced approval rules for Hermes Agent. The LLM cannot bypass these.

## What it does

Hermes has a runtime approval system for dangerous shell commands (Tier 1/Tier 2 in `tools/approval.py`). But actions performed via other tools — HTTP calls, file writes, email sends — pass through with zero runtime gating.

This plugin extends the approval system to **any tool call**. Users define rules in `config.yaml`; when a rule matches, the tool call is intercepted before execution and escalated to the existing human approval gate. The LLM cannot skip or bypass it.

## How it works

1. A `pre_tool_call` hook reads `approvals.custom_rules` from config.yaml
2. Each rule matches a tool name + field patterns (AND logic, regex)
3. On match: `approve` → human approval prompt (`[o]nce/[s]ession/[a]lways/[d]eny`), `block` → unconditional block
4. The core's `resolve_pre_tool_block()` handles the actual gate via `request_tool_approval()`
5. Timeout or no human present → fail-closed (action denied)

## What's new in v0.2.0

- **`rule_key` support**: per-rule allowlist grain for `[a]lways` approvals. Answering `[a]lways` on one rule no longer blanket-approves all rules on the same tool.
- **Gateway notification fix**: approval prompts now surface on Discord/Telegram/Slack (requires Hermes v0.18.2+ with PR #60504).
- **Invalid regex handling**: invalid regex patterns in `fields` are detected at load time and replaced with never-match patterns. Fail-closed, not fail-open.
- **Config preservation**: dashboard API uses `ruamel.yaml` for round-trip preservation of comments, formatting, and key order in config.yaml.
- **Single config read per call**: `evaluate()` reads config.yaml exactly once per tool call (was 3x).
- **`exempt_tools` string handling**: gracefully handles `exempt_tools` serialized as JSON string (yaml.dump artifact) or comma-separated string.
- **29 tests** (was 9, all passing).

## Config schema

```yaml
approvals:
  default_action: approve       # optional: "approve" | "block" — applies to any tool not matched by an explicit rule
  exempt_tools:                 # optional: tools never gated by default_action
    - web_search
    - read_file
  custom_rules:
    - tool: write_file          # required: tool name (exact match OR regex pattern)
      action: approve           # required: "approve" | "block"
      fields:                   # optional: field -> regex (AND logic)
        path: "\.ssh/"
      rule_key: write_file:ssh  # optional: per-rule allowlist grain for [a]lways
      message: "Write to sensitive path"  # optional: shown in approval prompt
```

### `rule_key`

Optional stable identifier that controls the `[a]lways` allowlist grain. When set, answering `[a]lways` to a rule with `rule_key: "write_file:ssh"` only auto-approves future matches of that same rule — not other `write_file` rules.

When omitted, the core derives a key from `tool_name + hash(reason)` (as of Hermes v0.18.2 / PR #60504). This is still per-rule, just auto-generated.

### `default_action`

When set, any tool call not matched by an explicit `custom_rules` entry is gated with this action. This covers tools you haven't configured yet — new MCP server tools, newly installed plugins, etc.

Example for WebDAV: set `default_action: approve` and exempt your trusted read-only tools. Every new tool (including future WebDAV operations) requires approval until you explicitly exempt or add a rule for it.

### `exempt_tools`

List of tool names that bypass `default_action`. Only meaningful when `default_action` is set. Tools listed here are never gated by the default — only explicit `custom_rules` matching them apply.

### Regex tool names

The `tool` field supports regex via `re.search`. Examples:

```yaml
- tool: "webdav_.*"     # matches webdav_put, webdav_get, webdav_delete, etc.
- tool: "http_.*"       # matches any HTTP-prefixed tool
- tool: "write_file"    # exact match (also works as regex, but no wildcards)
```

## Matchable fields

| Tool | Matchable fields |
|------|-----------------|
| `terminal` | `command`, `workdir` |
| `execute_code` | `code` |
| `write_file` | `path` |
| `patch` | `path`, `old_string`, `new_string` |
| `browser_type` | `ref`, `text` |
| `browser_click` | `ref` |
| `browser_navigate` | `url` |

Empty `fields` = match any call to that tool.

## Use cases

### Read-only external service access

Gate HTTP writes to a CalDAV/CardDAV server:

```yaml
- tool: terminal
  action: approve
  fields:
    command: "curl.*-X.*(PUT|DELETE|POST).*infomaniak"
  rule_key: "infomaniak:write"
  message: "External HTTP write to Infomaniak"
```

### Gate MCP server tools (CalDAV)

```yaml
- tool: mcp_calendar_create_event
  action: approve
  rule_key: "caldav:create"
  message: "CalDAV: create event"

- tool: mcp_calendar_update_event
  action: approve
  rule_key: "caldav:update"
  message: "CalDAV: update event"

- tool: mcp_calendar_delete_event
  action: approve
  rule_key: "caldav:delete"
  message: "CalDAV: delete event"
```

### File writes to sensitive paths

```yaml
- tool: write_file
  action: approve
  fields:
    path: "\.(ssh|gnupg|netrc)/"
  rule_key: "write_file:credentials"
  message: "Write to credential path"
```

### Block unconditionally

```yaml
- tool: write_file
  action: block
  fields:
    path: "/etc/passwd"
  message: "Never write to /etc/passwd"
```

## Dashboard

A dashboard tab "Runtime Approval" provides visual CRUD for rules:

- `hermes dashboard` → open the web UI
- Navigate to the "Runtime Approval" tab
- Add/edit/delete rules via the form
- Tool dropdown shows matchable fields dynamically

## Runtime gate vs prompt-only

**Runtime gate** = interception at code level, before tool execution. The LLM cannot bypass it. This is what this plugin does.

**Prompt-only** = instruction in the system prompt like "ask before writing to ~/.ssh". The LLM can ignore it. Prompt injection or hallucination can skip it. Not a technical guarantee.

## Cron behavior

Rules honor `approvals.cron_mode` (inherited from `request_tool_approval`):
- `deny` (default) → cron jobs blocked on matching rules (no human to approve)
- `approve` → cron jobs bypass the gate

## Limitations

1. **MCP tool field matching**: MCP server tools (`mcp_calendar_*`) don't have matchable fields beyond the tool name. Use `rule_key` for per-action granularity instead of `fields`.

2. **Dashboard writes**: the dashboard API uses `ruamel.yaml` to preserve config formatting, but complex YAML constructs (anchors, multi-line strings) may still be reformatted on write.

## Installation

```bash
# From this directory
hermes plugins enable runtime-approval --allow-tool-override

# Or if installed from GitHub
hermes plugins install quentinjaud/hermes-runtime-approval --enable --allow-tool-override
```

## Requirements

- Hermes Agent v0.18.2+ (for gateway notification fix #60504 and `rule_key` support)

## Related

- [Issue #51221](https://github.com/NousResearch/hermes-agent/issues/51221) — User-configurable runtime approval for external actions (closed)
- [PR #58698](https://github.com/NousResearch/hermes-agent/pull/58698) — `pre_tool_call` approve action (merged, reverted, re-landed as #60504)
- [PR #60504](https://github.com/NousResearch/hermes-agent/pull/60504) — Re-land with rule keys + working gateway notify (merged)
- [Issue #59067](https://github.com/NousResearch/hermes-agent/issues/59067) — Pass `rule_key` through from plugin directive (closed)