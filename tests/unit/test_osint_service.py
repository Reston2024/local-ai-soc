"""
Unit tests for backend.services.osint — TDD RED phase stubs.

Tests for:
- _is_cache_valid: TTL check logic
- _sanitize_ip: RFC1918/loopback/invalid rejection
- OsintResult: dataclass field existence
"""

import datetime

import pytest

from backend.services.osint import OsintResult, _is_cache_valid, _sanitize_ip


# ---------------------------------------------------------------------------
# _is_cache_valid tests
# ---------------------------------------------------------------------------


def test_cache_valid_recent():
    """Test 1: _is_cache_valid returns True when fetched_at is 1 hour ago."""
    one_hour_ago = (
        datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(hours=1)
    ).isoformat()
    assert _is_cache_valid(one_hour_ago, ttl_hours=24) is True


def test_cache_invalid_expired():
    """Test 2: _is_cache_valid returns False when fetched_at is 25 hours ago."""
    twenty_five_hours_ago = (
        datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(hours=25)
    ).isoformat()
    assert _is_cache_valid(twenty_five_hours_ago, ttl_hours=24) is False


def test_cache_invalid_none():
    """Test 3: _is_cache_valid returns False when fetched_at is None."""
    assert _is_cache_valid(None, ttl_hours=24) is False


# ---------------------------------------------------------------------------
# _sanitize_ip tests
# ---------------------------------------------------------------------------


def test_sanitize_valid_ipv4():
    """Test 4: _sanitize_ip returns unchanged string for valid public IPv4."""
    assert _sanitize_ip("8.8.8.8") == "8.8.8.8"


def test_sanitize_private_ip():
    """Test 5: _sanitize_ip raises ValueError with 'private IP' for RFC1918."""
    with pytest.raises(ValueError, match="private IP"):
        _sanitize_ip("192.168.1.1")


def test_sanitize_invalid_ip():
    """Test 6: _sanitize_ip raises ValueError with 'invalid IP' for non-IP string."""
    with pytest.raises(ValueError, match="invalid IP"):
        _sanitize_ip("not-an-ip")


def test_sanitize_loopback_ip():
    """Test 7: _sanitize_ip raises ValueError with 'loopback IP not enriched' for 127.0.0.1."""
    with pytest.raises(ValueError, match="loopback IP not enriched"):
        _sanitize_ip("127.0.0.1")


# ---------------------------------------------------------------------------
# OsintResult dataclass tests
# ---------------------------------------------------------------------------


def test_osint_result_fields():
    """Test 8: OsintResult dataclass has all required fields."""
    result = OsintResult(
        ip="8.8.8.8",
        whois=None,
        abuseipdb=None,
        geo=None,
        virustotal=None,
        shodan=None,
    )
    assert result.ip == "8.8.8.8"
    assert result.whois is None
    assert result.abuseipdb is None
    assert result.geo is None
    assert result.virustotal is None
    assert result.shodan is None
    assert result.cached is False
    assert result.fetched_at == ""
