import pytest
import json
import yaml
import re
from pathlib import Path
from unittest.mock import patch, mock_open
from rules import (
    load_rules, match_rule, evaluate,
    load_default_action, load_exempt_tools,
    ApprovalRule, _parse_rules, _parse_exempt_tools, _parse_default_action,
)


def _mock_config(config_data: dict):
    """Helper: mock open() to return YAML-serialized config."""
    return mock_open(read_data=yaml.dump(config_data))


# --- Config loading ---

def test_load_rules_empty_config():
    with patch("rules.load_config", return_value={}):
        assert load_rules() == []


def test_load_rules_empty_file():
    with patch("rules.load_config", return_value=None):
        assert load_rules() == []


def test_load_rules_valid():
    config_data = {
        "approvals": {
            "custom_rules": [
                {
                    "tool": "write_file",
                    "action": "approve",
                    "fields": {"path": r"\.ssh/"},
                    "message": "SSH check",
                    "rule_key": "write_file:ssh",
                },
                {
                    "tool": "terminal",
                    "action": "block",
                    "message": "No terminal",
                },
            ]
        }
    }
    with patch("rules.load_config", return_value=config_data):
        rules = load_rules()
        assert len(rules) == 2
        assert rules[0].tool == "write_file"
        assert rules[0].action == "approve"
        assert rules[0].fields == {"path": r"\.ssh/"}
        assert rules[0].rule_key == "write_file:ssh"
        assert rules[1].tool == "terminal"
        assert rules[1].action == "block"
        assert rules[1].rule_key == ""  # no rule_key → empty string


def test_load_rules_invalid_skipped():
    config_data = {
        "approvals": {
            "custom_rules": [
                {"action": "approve"},  # missing tool
                {"tool": "test", "action": "invalid"},  # bad action
                {"tool": "test", "action": "approve"},  # valid
            ]
        }
    }
    with patch("rules.load_config", return_value=config_data):
        rules = load_rules()
        assert len(rules) == 1
        assert rules[0].tool == "test"


# --- Matching ---

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
    assert match_rule(rule, "http_get", {}) is True
    assert match_rule(rule, "http_post", {}) is True


# --- Invalid regex handling (fail-closed) ---

def test_match_rule_invalid_regex_in_fields():
    rule = ApprovalRule(tool="write_file", action="approve", fields={"path": "[invalid("})
    # Should not raise; should return False (fail-closed for the rule)
    assert match_rule(rule, "write_file", {"path": "/etc/passwd"}) is False


def test_match_rule_invalid_regex_in_tool_name():
    rule = ApprovalRule(tool="[invalid(", action="approve")
    # Should not raise; should return False (only exact match could work,
    # and it doesn't match)
    assert match_rule(rule, "write_file", {}) is False


def test_load_rules_invalid_regex_replaced():
    """Invalid regex in fields is replaced with a never-match pattern at load."""
    config_data = {
        "approvals": {
            "custom_rules": [
                {
                    "tool": "write_file",
                    "action": "approve",
                    "fields": {"path": "[invalid("},
                }
            ]
        }
    }
    with patch("rules.load_config", return_value=config_data):
        rules = load_rules()
        assert len(rules) == 1
        # The invalid regex should have been replaced
        assert rules[0].fields["path"] == "(?!x)x"
        # And matching should return False
        assert match_rule(rules[0], "write_file", {"path": "/anything"}) is False


# --- default_action ---

def test_load_default_action_none():
    config_data = {"approvals": {}}
    with patch("rules.load_config", return_value=config_data):
        assert load_default_action() is None


def test_load_default_action_approve():
    config_data = {"approvals": {"default_action": "approve"}}
    with patch("rules.load_config", return_value=config_data):
        assert load_default_action() == "approve"


def test_load_default_action_invalid():
    config_data = {"approvals": {"default_action": "maybe"}}
    with patch("rules.load_config", return_value=config_data):
        assert load_default_action() is None


# --- exempt_tools (including string-as-list edge case) ---

def test_load_exempt_tools_empty():
    config_data = {"approvals": {}}
    with patch("rules.load_config", return_value=config_data):
        assert load_exempt_tools() == set()


def test_load_exempt_tools_list():
    config_data = {"approvals": {"exempt_tools": ["web_search", "read_file"]}}
    with patch("rules.load_config", return_value=config_data):
        assert load_exempt_tools() == {"web_search", "read_file"}


def test_load_exempt_tools_json_string():
    """exempt_tools serialized as JSON string (yaml.dump artifact)."""
    config_data = {"approvals": {"exempt_tools": '["web_search", "read_file"]'}}
    with patch("rules.load_config", return_value=config_data):
        result = load_exempt_tools()
        assert result == {"web_search", "read_file"}


def test_load_exempt_tools_comma_string():
    """exempt_tools as comma-separated string."""
    config_data = {"approvals": {"exempt_tools": "web_search, read_file"}}
    with patch("rules.load_config", return_value=config_data):
        result = load_exempt_tools()
        assert result == {"web_search", "read_file"}


# --- evaluate() ---

def test_evaluate_explicit_rule_matches():
    config_data = {
        "approvals": {
            "custom_rules": [
                {"tool": "write_file", "action": "block", "fields": {"path": "/etc/passwd"}, "message": "Blocked"}
            ]
        }
    }
    with patch("rules.load_config", return_value=config_data):
        result = evaluate("write_file", {"path": "/etc/passwd"})
        assert result is not None
        assert result.action == "block"


def test_evaluate_no_rules_no_default():
    config_data = {"approvals": {}}
    with patch("rules.load_config", return_value=config_data):
        result = evaluate("any_tool", {})
        assert result is None


def test_evaluate_default_action_approve_unmatched():
    config_data = {
        "approvals": {
            "default_action": "approve",
            "exempt_tools": ["web_search"],
        }
    }
    with patch("rules.load_config", return_value=config_data):
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
            "exempt_tools": ["web_search"],
        }
    }
    with patch("rules.load_config", return_value=config_data):
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
            "exempt_tools": [],
        }
    }
    with patch("rules.load_config", return_value=config_data):
        # Regex rule matches webdav_get
        result = evaluate("webdav_get_file", {})
        assert result.action == "block"

        # webdav_put not matched by rule → default_action
        result = evaluate("webdav_put", {})
        assert result.action == "approve"


def test_evaluate_reads_config_once():
    """evaluate() should call load_config() exactly once."""
    config_data = {"approvals": {"default_action": "approve", "exempt_tools": []}}
    call_count = 0
    original_load = __import__("rules").load_config

    def counting_load():
        nonlocal call_count
        call_count += 1
        return config_data

    with patch("rules.load_config", side_effect=counting_load):
        evaluate("some_tool", {})
        assert call_count == 1


# --- rule_key passthrough ---

def test_evaluate_rule_key_present():
    config_data = {
        "approvals": {
            "custom_rules": [
                {
                    "tool": "write_file",
                    "action": "approve",
                    "rule_key": "write_file:ssh",
                    "message": "SSH write",
                }
            ]
        }
    }
    with patch("rules.load_config", return_value=config_data):
        result = evaluate("write_file", {"path": "/home/.ssh/config"})
        assert result is not None
        assert result.rule_key == "write_file:ssh"


def test_evaluate_rule_key_empty_when_not_set():
    config_data = {
        "approvals": {
            "custom_rules": [
                {"tool": "write_file", "action": "approve", "message": "Any write"}
            ]
        }
    }
    with patch("rules.load_config", return_value=config_data):
        result = evaluate("write_file", {})
        assert result is not None
        assert result.rule_key == ""