import re
import json
import yaml
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Set

logger = logging.getLogger(__name__)

# --- hermes_home resolution with standalone fallback ---

try:
    from hermes_constants import get_hermes_home
except ImportError:
    # Standalone mode (tests, dev outside Hermes venv)
    import os
    def get_hermes_home() -> Path:
        return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


@dataclass
class ApprovalRule:
    tool: str          # exact tool name OR regex pattern (matched via re.search)
    action: str        # "approve" | "block"
    fields: Dict[str, str] = field(default_factory=dict)
    always_allow: bool = False       # deprecated, kept for backward compat
    message: str = ""
    rule_key: str = ""   # per-rule allowlist grain for [a]lways approvals


# --- Config loading (single read per evaluate() call) ---

def load_config() -> dict:
    """Load the full config.yaml as a dict. Returns {} on error."""
    config_path = get_hermes_home() / "config.yaml"
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    except (FileNotFoundError, yaml.YAMLError) as e:
        logger.debug(f"Could not read config.yaml: {e}")
        return {}


def _parse_rules(config: Optional[dict]) -> List[ApprovalRule]:
    """Extract custom_rules from a config dict."""
    if not config:
        return []
    approvals = config.get("approvals", {})
    custom_rules = approvals.get("custom_rules")

    if not custom_rules or not isinstance(custom_rules, list):
        return []

    rules = []
    for rule_data in custom_rules:
        if not isinstance(rule_data, dict):
            logger.warning(f"Skipping invalid rule entry: {rule_data}")
            continue

        tool = rule_data.get("tool")
        action = rule_data.get("action")

        if not tool or action not in ("approve", "block"):
            logger.warning(f"Skipping invalid rule (missing tool or invalid action): {rule_data}")
            continue

        # Validate regex patterns in fields at load time
        fields = rule_data.get("fields", {})
        if isinstance(fields, dict):
            for fname, pattern in fields.items():
                try:
                    re.compile(pattern)
                except (re.error, TypeError) as e:
                    logger.warning(
                        f"Rule '{tool}': invalid regex in field '{fname}': {e}. "
                        f"Field will match nothing."
                    )
                    # Replace with a never-match pattern so the rule is inert
                    # rather than fail-opening silently.
                    fields[fname] = "(?!x)x"  # zero-width negative lookahead = never matches

        rules.append(ApprovalRule(
            tool=tool,
            action=action,
            fields=fields if isinstance(fields, dict) else {},
            always_allow=rule_data.get("always_allow", False),
            message=rule_data.get("message", ""),
            rule_key=rule_data.get("rule_key", ""),
        ))

    return rules


def _parse_default_action(config: Optional[dict]) -> Optional[str]:
    """Return the default_action for unmatched tools, or None if not set."""
    if not config:
        return None
    approvals = config.get("approvals", {})
    default_action = approvals.get("default_action")
    if default_action not in ("approve", "block", None):
        logger.warning(f"Invalid default_action: {default_action}, ignoring")
        return None
    return default_action


def _parse_exempt_tools(config: Optional[dict]) -> Set[str]:
    """Return the set of exempt tool names. Handles string-as-list gracefully."""
    if not config:
        return set()
    approvals = config.get("approvals", {})
    exempt = approvals.get("exempt_tools", [])

    # Handle the case where exempt_tools was serialized as a JSON string
    # by yaml.dump or manual editing
    if isinstance(exempt, str):
        try:
            exempt = json.loads(exempt)
        except (json.JSONDecodeError, ValueError):
            exempt = [t.strip() for t in exempt.split(",") if t.strip()]

    if not isinstance(exempt, list):
        return set()

    return set(str(t) for t in exempt)


# --- Backward-compatible single-purpose loaders (still used by config_helpers) ---

def load_rules() -> List[ApprovalRule]:
    return _parse_rules(load_config())

def load_default_action() -> Optional[str]:
    return _parse_default_action(load_config())

def load_exempt_tools() -> set:
    return _parse_exempt_tools(load_config())


# --- Matching engine ---

def match_rule(rule: ApprovalRule, tool_name: str, args: Dict) -> bool:
    """Test if a rule matches a given tool call.

    Tool name: exact match OR regex search.
    Fields: AND logic — all field patterns must match.
    Invalid regex in fields is caught (never raises).
    """
    # Tool name matching: exact match OR regex search
    if rule.tool == tool_name:
        pass  # exact match
    else:
        try:
            if not re.search(rule.tool, tool_name):
                return False
        except re.error:
            # Invalid regex in tool name → only exact match could work,
            # already checked above
            return False

    if not rule.fields:
        return True

    for field_name, pattern in rule.fields.items():
        val = str(args.get(field_name, ""))
        try:
            if not re.search(pattern, val):
                return False
        except re.error:
            # Invalid regex in a field → treat as non-match (fail-closed
            # for the rule, not fail-open for the action)
            return False

    return True


def evaluate(tool_name: str, args: Dict) -> Optional[ApprovalRule]:
    """Evaluate all rules + default_action against a tool call.

    Returns the matching ApprovalRule, or None if the call should proceed freely.
    Priority: explicit custom rules > default_action > pass.

    Reads config.yaml exactly once per call.
    """
    config = load_config()

    # Check explicit rules first
    rules = _parse_rules(config)
    for rule in rules:
        if match_rule(rule, tool_name, args or {}):
            return rule

    # Check default_action for unmatched tools
    default_action = _parse_default_action(config)
    if default_action is None:
        return None

    exempt = _parse_exempt_tools(config)
    if tool_name in exempt:
        return None

    # default_action applies — synthesize a rule
    return ApprovalRule(
        tool=tool_name,
        action=default_action,
        fields={},
        message=f"Default action: {tool_name} requires approval (no explicit rule)"
    )