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

## Config schema

```yaml
approvals:
  custom_rules:
    - tool: write_file          # required: tool name
      action: approve           # required: "approve" | "block"
      fields:                   # optional: field -> regex (AND logic)
        path: "\\.ssh/"
      always_allow: false       # optional: currently a no-op (see Limitations)
      message: "Write to sensitive path"  # optional: shown in approval prompt
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
  message: "External HTTP write to Infomaniak"
```

### File writes to sensitive paths

```yaml
- tool: write_file
  action: approve
  fields:
    path: "\\.(ssh|gnupg|netrc)/"
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

## Limitations (v0.1)

1. **`always_allow: false` is a no-op.** The core's `resolve_pre_tool_block()` hardcodes `rule_key=tool_name`. All rules on the same tool share one allowlist entry. Answering `[a]lways` on any rule auto-approves all subsequent rules on that tool. See [issue #59067](https://github.com/NousResearch/hermes-agent/issues/59067) for the fix.

2. **Config write via dashboard.** The dashboard API writes `approvals.custom_rules` using `yaml.dump` which may reformat config.yaml. Other sections are preserved but formatting may change. Use `ruamel.yaml` for round-trip preservation if needed.

## Installation

```bash
# From this directory
hermes plugins enable runtime-approval --allow-tool-override

# Or if installed from GitHub
hermes plugins install quentinjaud/hermes-runtime-approval --enable --allow-tool-override
```

## Related

- [Issue #51221](https://github.com/NousResearch/hermes-agent/issues/51221) — User-configurable runtime approval for external actions
- [PR #58698](https://github.com/NousResearch/hermes-agent/pull/58698) — `pre_tool_call` approve action
- [Issue #59067](https://github.com/NousResearch/hermes-agent/issues/59067) — Pass `rule_key` through from plugin directive