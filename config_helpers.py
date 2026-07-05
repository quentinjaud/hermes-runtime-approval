from pathlib import Path
import yaml
import os
import tempfile
from hermes_constants import get_hermes_home

MATCHABLE_FIELDS = {
    "terminal": ["command", "workdir"],
    "execute_code": ["code"],
    "write_file": ["path"],
    "patch": ["path", "old_string", "new_string"],
    "browser_type": ["ref", "text"],
    "browser_click": ["ref"],
    "browser_navigate": ["url"],
}

def get_config_path() -> Path:
    return get_hermes_home() / "config.yaml"

def read_rules() -> list[dict]:
    path = get_config_path()
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f) or {}
        return config.get("approvals", {}).get("custom_rules", [])
    except Exception:
        return []

def write_rules(rules: list[dict]) -> None:
    path = get_config_path()
    
    # Read current config
    if path.exists():
        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            config = {}
    else:
        config = {}

    # Update ONLY custom_rules
    if "approvals" not in config:
        config["approvals"] = {}
    config["approvals"]["custom_rules"] = rules

    # Atomic write
    fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=".config.yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        os.replace(temp_path, path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

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
    path = get_config_path()
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f) or {}
        return config.get("approvals", {}).get("default_action")
    except Exception:
        return None

def write_default_action(action: str | None) -> str | None:
    """Set default_action. None clears it."""
    path = get_config_path()
    if path.exists():
        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            config = {}
    else:
        config = {}
    if "approvals" not in config:
        config["approvals"] = {}
    if action is None:
        config["approvals"].pop("default_action", None)
    else:
        config["approvals"]["default_action"] = action
    _atomic_write(config, path)
    return action

def read_exempt_tools() -> list[str]:
    path = get_config_path()
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f) or {}
        return config.get("approvals", {}).get("exempt_tools", [])
    except Exception:
        return []

def write_exempt_tools(tools: list[str]) -> list[str]:
    path = get_config_path()
    if path.exists():
        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            config = {}
    else:
        config = {}
    if "approvals" not in config:
        config["approvals"] = {}
    config["approvals"]["exempt_tools"] = tools
    _atomic_write(config, path)
    return tools

def _atomic_write(config: dict, path: Path) -> None:
    fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=".config.yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        os.replace(temp_path, path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

def validate_rule(rule: dict) -> tuple[bool, str]:
    if not rule.get("tool"):
        return False, "Tool is required"
    
    action = rule.get("action")
    if action not in {"approve", "block"}:
        return False, "Action must be either 'approve' or 'block'"
    
    fields = rule.get("fields")
    if fields is not None and not isinstance(fields, dict):
        return False, "Fields must be a dictionary of regex patterns"
    
    message = rule.get("message")
    if message is not None and not isinstance(message, str):
        return False, "Message must be a string"
        
    return True, ""
