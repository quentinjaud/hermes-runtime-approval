import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open
from rules import load_rules, match_rule, ApprovalRule

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
