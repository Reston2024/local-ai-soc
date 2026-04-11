"""Phase 36: Unit tests for Zeek log normalizers in MalcolmCollector."""
import pytest
from unittest.mock import MagicMock, patch
from ingestion.jobs.malcolm_collector import MalcolmCollector
from backend.models.event import NormalizedEvent


@pytest.fixture
def collector():
    """MalcolmCollector with no HTTP/loader dependencies."""
    with patch("ingestion.jobs.malcolm_collector.httpx.AsyncClient"):
        c = MalcolmCollector.__new__(MalcolmCollector)
        c._loader = None
        return c


# ---- Plan 01 normalizers ----

def test_normalize_conn_basic(collector):
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "192.168.1.10", "port": 52000},
        "destination": {"ip": "1.2.3.4", "port": 443},
        "network": {"transport": "tcp", "bytes": 1024},
        "zeek": {"conn": {"state": "SF"}},
        "event": {"duration": 1.5},
    }
    evt = collector._normalize_conn(doc)
    assert evt is not None
    assert evt.event_type == "conn"
    assert evt.source_type == "zeek"
    assert evt.src_ip == "192.168.1.10"
    assert evt.conn_state == "SF"
    assert evt.conn_duration == 1.5
    assert evt.conn_orig_bytes == 1024


def test_normalize_conn_no_src_ip_returns_none(collector):
    doc = {"@timestamp": "2026-04-10T12:00:00Z"}
    assert collector._normalize_conn(doc) is None


def test_normalize_conn_triple_fallback(collector):
    """conn_state must resolve via dotted key fallback when nested dict absent."""
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "10.0.0.1"},
        "zeek.conn.state": "REJ",  # dotted flat form
    }
    evt = collector._normalize_conn(doc)
    assert evt is not None
    assert evt.conn_state == "REJ"


def test_normalize_weird_severity_high(collector):
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "10.0.0.2"},
        "zeek": {"weird": {"name": "unknown_protocol_on_port_80", "addl": "extra"}},
    }
    evt = collector._normalize_weird(doc)
    assert evt is not None
    assert evt.event_type == "weird"
    assert evt.severity == "high"
    assert evt.zeek_weird_name == "unknown_protocol_on_port_80"


def test_normalize_weird_no_src_ip_returns_none(collector):
    doc = {"@timestamp": "2026-04-10T12:00:00Z", "zeek": {"weird": {"name": "test"}}}
    assert collector._normalize_weird(doc) is None


# ---- Plan 02 normalizers (stubs — will be RED until Plan 02 implements them) ----

def test_normalize_http_basic(collector):
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "192.168.1.5", "port": 54321},
        "destination": {"ip": "93.184.216.34", "port": 80},
        "http": {"request": {"method": "GET"}, "response": {"status_code": 200}},
        "url": {"original": "http://example.com/path"},
        "user_agent": {"original": "Mozilla/5.0"},
    }
    evt = collector._normalize_http(doc)
    assert evt is not None
    assert evt.event_type == "http"
    assert evt.http_method == "GET"
    assert evt.http_status_code == 200


def test_normalize_ssl_basic(collector):
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "192.168.1.5"},
        "destination": {"ip": "1.2.3.4"},
        "tls": {"version": "TLSv1.3", "client": {"ja3": "abc123"}},
        "zeek": {"ssl": {"server_name": "example.com"}},
    }
    evt = collector._normalize_ssl(doc)
    assert evt is not None
    assert evt.event_type == "ssl"
    assert evt.tls_version == "TLSv1.3"


def test_normalize_notice_basic(collector):
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "10.0.0.1"},
        "zeek": {"notice": {"note": "Scan::Port_Scan", "msg": "detected port scan"}},
    }
    evt = collector._normalize_notice(doc)
    assert evt is not None
    assert evt.event_type == "notice"
    assert evt.zeek_notice_note == "Scan::Port_Scan"
    assert evt.severity == "high"


def test_normalize_ssh_auth_success(collector):
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "10.0.0.5"},
        "destination": {"ip": "192.168.1.100"},
        "zeek": {"ssh": {"auth_success": True, "version": 2}},
    }
    evt = collector._normalize_ssh(doc)
    assert evt is not None
    assert evt.event_type == "ssh"
    assert evt.ssh_auth_success is True
    assert evt.ssh_version == 2


def test_normalize_kerberos_basic(collector):
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "192.168.1.20"},
        "zeek": {"kerberos": {"client": "user@DOMAIN.LOCAL", "service": "krbtgt/DOMAIN.LOCAL"}},
    }
    evt = collector._normalize_kerberos(doc)
    assert evt is not None
    assert evt.event_type == "kerberos_tgs_request"
    assert evt.kerberos_client == "user@DOMAIN.LOCAL"


def test_normalize_ntlm_basic(collector):
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "192.168.1.30"},
        "zeek": {"ntlm": {"domain": "WORKGROUP", "username": "jsmith"}},
    }
    evt = collector._normalize_ntlm(doc)
    assert evt is not None
    assert evt.event_type == "ntlm_auth"
    assert evt.ntlm_username == "jsmith"


def test_normalize_smb_files_basic(collector):
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "192.168.1.40"},
        "zeek": {"smb_files": {"action": "SMB::FILE_OPEN", "name": "secret.docx"}},
    }
    evt = collector._normalize_smb_files(doc)
    assert evt is not None
    assert evt.event_type == "smb_files"
    assert evt.smb_action == "SMB::FILE_OPEN"


def test_normalize_rdp_basic(collector):
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "10.0.0.99"},
        "destination": {"ip": "192.168.1.50"},
        "zeek": {"rdp": {"cookie": "user", "security_protocol": "HYBRID"}},
    }
    evt = collector._normalize_rdp(doc)
    assert evt is not None
    assert evt.event_type == "rdp"
    assert evt.rdp_security_protocol == "HYBRID"


def test_normalize_dhcp_basic(collector):
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "0.0.0.0"},
        "zeek": {"dhcp": {"hostname": "workstation-01", "assigned_ip": "192.168.1.101"}},
    }
    evt = collector._normalize_dhcp(doc)
    assert evt is not None
    assert evt.event_type == "dhcp"


def test_normalize_smtp_basic(collector):
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "192.168.1.10"},
        "zeek": {"smtp": {"from": "alice@corp.com", "to": ["bob@corp.com"], "subject": "test"}},
    }
    evt = collector._normalize_smtp(doc)
    assert evt is not None
    assert evt.event_type == "smtp"


def test_normalize_ftp_basic(collector):
    doc = {
        "@timestamp": "2026-04-10T12:00:00Z",
        "source": {"ip": "10.0.0.1"},
        "zeek": {"ftp": {"command": "RETR", "reply_code": 226}},
    }
    evt = collector._normalize_ftp(doc)
    assert evt is not None
    assert evt.event_type == "ftp"
