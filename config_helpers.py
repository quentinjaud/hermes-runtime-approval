from pathlib import Path
import json
import os
import re
import tempfile
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

try:
    from hermes_constants import get_hermes_home
except ImportError:
    def get_hermes_home() -> Path:
        return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))

MATCHABLE_FIELDS = {
    "terminal": ["command", "workdir"],
    "execute_code": ["code"],
    "write_file": ["path"],
    "patch": ["path", "old_string", "new_string"],
    "browser_type": ["ref", "text"],
    "browser_click": ["ref"],
    "browser_navigate": ["url"],
}

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=4, offset=2)


def get_config_path() -> Path:
    return get_hermes_home() / "config.yaml"


def _read_config_ruamel() -> CommentedMap:
    """Read config.yaml preserving comments, formatting, and key order."""
    path = get_config_path()
    if not path.exists():
        return CommentedMap()
    with open(path, "r") as f:
        data = _yaml.load(f)
    return data if data is not None else CommentedMap()


def _write_config_ruamel(config: CommentedMap) -> None:
    """Atomic write preserving ruamel formatting."""
    path = get_config_path()
    fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=".config.yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            _yaml.dump(config, f)
        os.replace(temp_path, path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def _normalize_exempt_tools(exempt) -> list:
    """Handle string-as-list gracefully. Always returns a list."""
    if isinstance(exempt, str):
        try:
            parsed = json.loads(exempt)
            if isinstance(parsed, list):
                return [str(t) for t in parsed]
        except (json.JSONDecodeError, ValueError):
            pass
        return [t.strip() for t in exempt.split(",") if t.strip()]
    if isinstance(exempt, list):
        return [str(t) for t in exempt]
    return []


def read_rules() -> list[dict]:
    path = get_config_path()
    if not path.exists():
        return []
    try:
        config = _read_config_ruamel()
        return list(config.get("approvals", {}).get("custom_rules", []) or [])
    except Exception:
        return []


def write_rules(rules: list[dict]) -> None:
    config = _read_config_ruamel()
    if "approvals" not in config:
        config["approvals"] = CommentedMap()
    config["approvals"]["custom_rules"] = rules
    _write_config_ruamel(config)


def add_rule(rule: dict) -> list[dict]:
    rules = read_rules()
    rules.append(rule)
    write_rules(rules)
    return rules


def update_rule(index: int, rule: dict) -> list[dict]:
    rules = read_rules()
    if 0 <= index < len(rules):
        rules[index] = rule
        write_rules(rules)
    return rules


def delete_rule(index: int) -> list[dict]:
    rules = read_rules()
    if 0 <= index < len(rules):
        rules.pop(index)
        write_rules(rules)
    return rules


def read_default_action() -> str | None:
    try:
        config = _read_config_ruamel()
        return config.get("approvals", {}).get("default_action")
    except Exception:
        return None


def write_default_action(action: str | None) -> str | None:
    config = _read_config_ruamel()
    if "approvals" not in config:
        config["approvals"] = CommentedMap()
    if action is None:
        config["approvals"].pop("default_action", None)
    else:
        config["approvals"]["default_action"] = action
    _write_config_ruamel(config)
    return action


def read_exempt_tools() -> list[str]:
    try:
        config = _read_config_ruamel()
        raw = config.get("approvals", {}).get("exempt_tools", [])
        return _normalize_exempt_tools(raw)
    except Exception:
        return []


def write_exempt_tools(tools: list[str]) -> list[str]:
    config = _read_config_ruamel()
    if "approvals" not in config:
        config["approvals"] = CommentedMap()
    config["approvals"]["exempt_tools"] = tools
    _write_config_ruamel(config)
    return tools


def validate_rule(rule: dict) -> tuple[bool, str]:
    if not rule.get("tool"):
        return False, "Tool is required"

    action = rule.get("action")
    if action not in {"approve", "block"}:
        return False, "Action must be either 'approve' or 'block'"

    fields = rule.get("fields")
    if fields is not None:
        if not isinstance(fields, dict):
            return False, "Fields must be a dictionary of regex patterns"
        for fname, pattern in fields.items():
            try:
                re.compile(pattern)
            except (re.error, TypeError) as e:
                return False, f"Invalid regex in field '{fname}': {e}"

    message = rule.get("message")
    if message is not None and not isinstance(message, str):
        return False, "Message must be a string"

    rule_key = rule.get("rule_key")
    if rule_key is not None and not isinstance(rule_key, str):
        return False, "rule_key must be a string"

    return True, ""