"""Tests for harvest.security — SSRF, Prompt Injection, MCP Auth, Credential Stripping, P2P Signing."""

import pytest
from harvest.security import (
    is_safe_url,
    safe_url,
    strip_credentials,
    redact_url,
    sanitize_for_llm,
    generate_mcp_token,
    validate_mcp_token,
    sign_entry,
    verify_entry_signature,
    is_safe_response_size,
    MAX_LLM_CONTENT_LENGTH,
    MAX_FETCH_SIZE_BYTES,
)


# ============================================================================
# URL Validation (SSRF + LFI)
# ============================================================================


class TestURLValidation:
    def test_safe_urls(self):
        assert is_safe_url("https://example.com")[0] is True
        assert is_safe_url("http://example.com")[0] is True
        assert is_safe_url("https://example.com/path?q=1&b=2")[0] is True

    def test_blocked_schemes(self):
        assert is_safe_url("file:///etc/passwd")[0] is False
        assert is_safe_url("ftp://example.com")[0] is False
        assert is_safe_url("data:text/html,<script>")[0] is False
        assert is_safe_url("javascript:alert(1)")[0] is False

    def test_blocked_private_ips(self):
        assert is_safe_url("http://127.0.0.1")[0] is False
        assert is_safe_url("http://192.168.1.1")[0] is False
        assert is_safe_url("http://10.0.0.1")[0] is False
        assert is_safe_url("http://172.16.0.1")[0] is False
        assert is_safe_url("http://169.254.169.254")[0] is False
        assert is_safe_url("http://[::1]")[0] is False

    def test_blocked_hostnames(self):
        assert is_safe_url("http://localhost")[0] is False
        assert is_safe_url("http://0.0.0.0")[0] is False

    def test_shell_metacharacters(self):
        assert is_safe_url("https://example.com`id`")[0] is False
        assert is_safe_url("https://example.com/$(whoami)")[0] is False
        assert is_safe_url("https://example.com;rm -rf /")[0] is False

    def test_path_traversal(self):
        assert is_safe_url("https://example.com/../../etc/passwd")[0] is False

    def test_credentials_in_url(self):
        assert is_safe_url("https://admin:pass@example.com")[0] is False

    def test_safe_url_raises(self):
        with pytest.raises(ValueError):
            safe_url("file:///etc/passwd")

    def test_safe_url_returns_url(self):
        assert safe_url("https://example.com") == "https://example.com"


# ============================================================================
# Credential Stripping
# ============================================================================


class TestCredentialStripping:
    def test_strip_credentials(self):
        url = strip_credentials("https://admin:password123@example.com/path")
        assert "admin" not in url
        assert "password123" not in url
        assert "example.com" in url
        assert "/path" in url

    def test_strip_no_credentials(self):
        assert strip_credentials("https://example.com") == "https://example.com"

    def test_redact_url(self):
        url = redact_url("https://admin:password123@example.com/path")
        assert "admin" in url
        assert "***" in url
        assert "password123" not in url

    def test_redact_no_credentials(self):
        assert redact_url("https://example.com") == "https://example.com"


# ============================================================================
# Prompt Injection Prevention
# ============================================================================


class TestPromptInjection:
    def test_sanitization_markers(self):
        result = sanitize_for_llm("<p>Hello</p>")
        assert "<SCRAPED_CONTENT>" in result
        assert "</SCRAPED_CONTENT>" in result

    def test_html_comments_removed(self):
        result = sanitize_for_llm("Hello <!-- INJECT HERE --> World")
        assert "INJECT HERE" not in result

    def test_javascript_urls_removed(self):
        result = sanitize_for_llm("javascript:alert(1)")
        assert "javascript:" not in result

    def test_meta_refresh_removed(self):
        result = sanitize_for_llm('<meta http-equiv="refresh" content="0;url=http://evil.com">')
        assert "evil.com" not in result

    def test_truncation(self):
        big_content = "A" * (MAX_LLM_CONTENT_LENGTH + 10000)
        result = sanitize_for_llm(big_content)
        assert len(result) < MAX_LLM_CONTENT_LENGTH + 1000

    def test_empty_content(self):
        assert sanitize_for_llm("") == ""

    def test_hidden_elements_removed(self):
        html = '<div style="display:none">Secret</div>Visible'
        result = sanitize_for_llm(html)
        assert "Secret" not in result


# ============================================================================
# MCP Authentication
# ============================================================================


class TestMCPAuth:
    def test_generate_token(self):
        token = generate_mcp_token()
        assert len(token) > 20
        assert isinstance(token, str)

    def test_validate_correct_token(self):
        token = generate_mcp_token()
        assert validate_mcp_token(token, token) is True

    def test_validate_wrong_token(self):
        token = generate_mcp_token()
        assert validate_mcp_token("wrong", token) is False

    def test_validate_empty_token(self):
        assert validate_mcp_token("", "expected") is False
        assert validate_mcp_token("token", "") is False


# ============================================================================
# P2P Content Signing
# ============================================================================


class TestP2PSigning:
    def test_sign_and_verify(self):
        data = {"url": "https://example.com", "data": {"content": "test"}}
        sig = sign_entry(data, "secret_key")
        assert verify_entry_signature(data, sig, "secret_key") is True

    def test_wrong_key_fails(self):
        data = {"url": "https://example.com", "data": {"content": "test"}}
        sig = sign_entry(data, "key1")
        assert verify_entry_signature(data, sig, "key2") is False

    def test_tampered_data_fails(self):
        data = {"url": "https://example.com", "data": {"content": "test"}}
        sig = sign_entry(data, "key")
        tampered = {"url": "https://example.com", "data": {"content": "HACKED"}}
        assert verify_entry_signature(tampered, sig, "key") is False


# ============================================================================
# DoS Response Size Limits
# ============================================================================


class TestDoSLimits:
    def test_safe_size(self):
        ok, msg = is_safe_response_size(1024)
        assert ok is True

    def test_oversized(self):
        ok, msg = is_safe_response_size(MAX_FETCH_SIZE_BYTES + 1)
        assert ok is False
        assert "too large" in msg.lower()
