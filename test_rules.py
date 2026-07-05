import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open
from rules import load_rules, match_rule, evaluate, load_default_action, load_exempt_tools, ApprovalRule

def test_load_rules_empty_config():
    # Mock config.yaml not existing
    with patch("builtins.open", side_effect=FileNotFoundError):
        assert load_rules() == []

def test_load_rules_empty_file():
    with patch("builtins.open", mock_open(read_data="")):
        assert load_rules() == []

def test_load_rules_valid():
    config_data = {
        "approvals": {
            "custom_rules": [
                {
                    "tool": "write_file",
                    "action": "approve",
                    "fields": {"path": r"\.ssh/"},
                    "message": "SSH check"
                },
                {
                    "tool": "terminal",
                    "action": "block",
                    "message": "No terminal"
                }
            ]
        }
    }
    with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
        rules = load_rules()
        assert len(rules) == 2
        assert rules[0].tool == "write_file"
        assert rules[0].action == "approve"
        assert rules[0].fields == {"path": r"\.ssh/"}
        assert rules[1].tool == "terminal"
        assert rules[1].action == "block"

def test_load_rules_invalid_skipped():
    config_data = {
        "approvals": {
            "custom_rules": [
                {"action": "approve"}, # missing tool
                {"tool": "test", "action": "invalid"}, # bad action
                {"tool": "test", "action": "approve"} # valid
            ]
        }
    }
    with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
        rules = load_rules()
        assert len(rules) == 1
        assert rules[0].tool == "test"

def test_match_rule_tool_mismatch():
    rule = ApprovalRule(tool="write_file", action="approve")
    assert match_rule(rule, "terminal", {}) is False

def test_match_rule_field_match():
    rule = ApprovalRule(tool="write_file", action="approve", fields={"path": r"\.ssh/"})
    assert match_rule(rule, "write_file", {"path": "/home/user/.ssh/config"}) is True
    assert match_rule(rule, "write_file", {"path": "some/other/path"}) is False

def test_match_rule_multiple_fields():
    rule = ApprovalRule(tool="write_file", action="approve", fields={"path": r"test", "content": r"secret"})
    assert match_rule(rule, "write_file", {"path": "test_file", "content": "top secret"}) is True
    assert match_rule(rule, "write_file", {"path": "test_file", "content": "public"}) is False
    assert match_rule(rule, "write_file", {"path": "other", "content": "secret"}) is False

def test_match_rule_empty_fields():
    rule = ApprovalRule(tool="write_file", action="approve", fields={})
    assert match_rule(rule, "write_file", {"path": "any"}) is True

def test_match_rule_absent_field():
    rule = ApprovalRule(tool="write_file", action="approve", fields={"path": r"test"})
    assert match_rule(rule, "write_file", {"content": "no path here"}) is False

# --- Regex tool name matching ---

def test_match_rule_regex_tool_name():
    rule = ApprovalRule(tool="webdav_.*", action="approve")
    assert match_rule(rule, "webdav_put", {}) is True
    assert match_rule(rule, "webdav_delete", {}) is True
    assert match_rule(rule, "webdav_get", {}) is True
    assert match_rule(rule, "write_file", {}) is False

def test_match_rule_regex_tool_name_partial():
    rule = ApprovalRule(tool="http", action="approve")
    # "http" matches as substring via re.search
    assert match_rule(rule, "http_get", {}) is True
    assert match_code(rule, "http_post", {}) is True

def match_code(rule, tool, args):
    return match_rule(rule, tool, args)

# --- default_action ---

def test_load_default_action_none():
    config_data = {"approvals": {}}
    with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
        assert load_default_action() is None

def test_load_default_action_approve():
    config_data = {"approvals": {"default_action": "approve"}}
    with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
        assert load_default_action() == "approve"

def test_load_default_action_invalid():
    config_data = {"approvals": {"default_action": "maybe"}}
    with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
        assert load_default_action() is None

# --- exempt_tools ---

def test_load_exempt_tools_empty():
    config_data = {"approvals": {}}
    with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
        assert load_exempt_tools() == set()

def test_load_exempt_tools():
    config_data = {"approvals": {"exempt_tools": ["web_search", "read_file"]}}
    with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
        assert load_exempt_tools() == {"web_search", "read_file"}

# --- evaluate() ---

def test_evaluate_explicit_rule_matches():
    config_data = {
        "approvals": {
            "custom_rules": [
                {"tool": "write_file", "action": "block", "fields": {"path": "/etc/passwd"}, "message": "Blocked"}
            ]
        }
    }
    with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
        result = evaluate("write_file", {"path": "/etc/passwd"})
        assert result is not None
        assert result.action == "block"

def test_evaluate_no_rules_no_default():
    config_data = {"approvals": {}}
    with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
        result = evaluate("any_tool", {})
        assert result is None

def test_evaluate_default_action_approve_unmatched():
    config_data = {
        "approvals": {
            "default_action": "approve",
            "exempt_tools": ["web_search"]
        }
    }
    with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
        # Unmatched, non-exempt tool → default_action applies
        result = evaluate("webdav_put", {})
        assert result is not None
        assert result.action == "approve"
        
        # Exempt tool → no gate
        result = evaluate("web_search", {})
        assert result is None

def test_evaluate_explicit_rule_overrides_default():
    config_data = {
        "approvals": {
            "default_action": "approve",
            "custom_rules": [
                {"tool": "write_file", "action": "block", "message": "Always blocked"}
            ],
            "exempt_tools": ["web_search"]
        }
    }
    with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
        # Explicit rule wins over default
        result = evaluate("write_file", {})
        assert result.action == "block"
        
        # Unmatched tool gets default
        result = evaluate("webdav_put", {})
        assert result.action == "approve"
        
        # Exempt tool passes
        result = evaluate("web_search", {})
        assert result is None

def test_evaluate_regex_tool_with_default():
    config_data = {
        "approvals": {
            "default_action": "approve",
            "custom_rules": [
                {"tool": "webdav_get.*", "action": "block", "message": "Read-only WebDAV"}
            ],
            "exempt_tools": []
        }
    }
    with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
        # Regex rule matches webdav_get
        result = evaluate("webdav_get_file", {})
        assert result.action == "block"
        
        # webdav_put not matched by rule → default_action
        result = evaluate("webdav_put", {})
        assert result.action == "approve"
