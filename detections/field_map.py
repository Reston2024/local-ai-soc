"""
Sigma-to-DuckDB field name mapping.

Maps Sigma canonical Windows field names to the normalized_events
column names used in DuckDB.  Used by SigmaMatcher when translating
Sigma detection conditions to SQL WHERE clauses.

Note on EventID:
    Sigma's ``EventID`` field refers to the Windows Event Log numeric ID
    (e.g. 4624, 1 for Sysmon).  In our schema this information lives in
    raw_event (as a JSON field) and in the event_type column (a derived
    string).  We do not map it to a top-level column because our event_id
    is a UUID, not the Windows EventID.  Rules that filter on EventID
    should use a raw_event LIKE/JSON_EXTRACT approach; the matcher handles
    this specially.
"""

from __future__ import annotations

# Version identifier for this field map — updated whenever the mapping changes.
# Used by detection provenance records so analysts can reconstruct which
# field translations were active when a Sigma rule fired.
FIELD_MAP_VERSION: str = "22"

# Sigma field name → normalized_events DuckDB column
SIGMA_FIELD_MAP: dict[str, str] = {
    # ------------------------------------------------------------------ #
    # Process fields (Sysmon EventID 1 / Windows Security 4688)
    # ------------------------------------------------------------------ #
    "Image":                "process_name",
    "CommandLine":          "command_line",
    "ProcessId":            "process_id",
    "NewProcessId":         "process_id",
    "ParentImage":          "parent_process_name",
    "ParentProcessId":      "parent_process_id",
    "ParentCommandLine":    "command_line",   # approximate — no dedicated column
    "OriginalFileName":     "process_name",
    # ------------------------------------------------------------------ #
    # User / authentication fields
    # ------------------------------------------------------------------ #
    "User":                 "username",
    "SubjectUserName":      "username",
    "TargetUserName":       "username",
    "AccountName":          "username",
    "ServiceName":          "username",       # approximate for service logons
    # ------------------------------------------------------------------ #
    # Host fields
    # ------------------------------------------------------------------ #
    "Computer":             "hostname",
    "ComputerName":         "hostname",
    "WorkstationName":      "hostname",
    # ------------------------------------------------------------------ #
    # Network fields
    # ------------------------------------------------------------------ #
    "DestinationIp":        "dst_ip",
    "DestinationPort":      "dst_port",
    "SourceIp":             "src_ip",
    "SourcePort":           "src_port",
    "DestinationHostname":  "domain",
    "QueryName":            "domain",
    "Initiated":            "src_ip",          # Sysmon net event direction flag
    # ------------------------------------------------------------------ #
    # File fields
    # ------------------------------------------------------------------ #
    "TargetFilename":       "file_path",
    "TargetObject":         "file_path",
    "ObjectName":           "file_path",
    "FileName":             "file_path",
    "Hashes":               "file_hash_sha256",
    "Hash":                 "file_hash_sha256",
    "Imphash":              "file_hash_sha256",  # approximate
    "Sha256":               "file_hash_sha256",
    # ------------------------------------------------------------------ #
    # Registry fields (mapped to file_path as closest equivalent)
    # ------------------------------------------------------------------ #
    "EventType":            "event_type",
    "ObjectType":           "event_type",
    # ------------------------------------------------------------------ #
    # Generic / metadata
    # ------------------------------------------------------------------ #
    "Channel":              "source_file",
    "Provider_Name":        "source_file",
    "Tags":                 "tags",
    "AttackTechnique":      "attack_technique",
    "Technique":            "attack_technique",
    # ------------------------------------------------------------------
    # ECS dotted-field names — pySigma ECS pipeline compatibility
    # ------------------------------------------------------------------
    "process.name":           "process_name",
    "process.pid":            "process_id",
    "process.command_line":   "command_line",
    "process.executable":     "process_executable",
    "process.parent.name":    "parent_process_name",
    "process.parent.pid":     "parent_process_id",
    "user.name":              "username",
    "user.domain":            "user_domain",
    "host.hostname":          "hostname",
    "source.ip":              "src_ip",
    "source.port":            "src_port",
    "destination.ip":         "dst_ip",
    "destination.port":       "dst_port",
    "destination.domain":     "domain",
    "file.path":              "file_path",
    "file.hash.sha256":       "file_hash_sha256",
    "network.protocol":       "network_protocol",
    "dns.question.name":      "domain",
    # Zeek / ECS field aliases
    "dns.query.name":         "dns_query",
    "http.user_agent":        "http_user_agent",
    "tls.client.ja3":         "tls_ja3",
    # Phase 36: Zeek full telemetry field mappings
    "zeek.conn.state":              "conn_state",
    "zeek.conn.duration":           "conn_duration",
    "zeek.conn.orig_bytes":         "conn_orig_bytes",
    "zeek.conn.resp_bytes":         "conn_resp_bytes",
    "zeek.weird.name":              "zeek_weird_name",
    "zeek.notice.note":             "zeek_notice_note",
    "zeek.notice.msg":              "zeek_notice_msg",
    "zeek.ssh.auth_success":        "ssh_auth_success",
    "zeek.ssh.version":             "ssh_version",
    "zeek.kerberos.client":         "kerberos_client",
    "zeek.kerberos.service":        "kerberos_service",
    "zeek.ntlm.username":           "ntlm_username",
    "zeek.ntlm.domain":             "ntlm_domain",
    "zeek.smb_mapping.path":        "smb_path",
    "zeek.smb_files.action":        "smb_action",
    "zeek.rdp.security_protocol":   "rdp_security_protocol",
    "zeek.rdp.cookie":              "rdp_cookie",
    # ------------------------------------------------------------------
    # New ECS column mappings (Windows Sigma field names)
    # ------------------------------------------------------------------
    "EventOutcome":           "event_outcome",
    "SubjectDomainName":      "user_domain",
    "TargetDomainName":       "user_domain",
    "DomainName":             "user_domain",
}

# Columns that hold integer values — used to decide whether to quote
INTEGER_COLUMNS: frozenset[str] = frozenset({
    "process_id",
    "parent_process_id",
    "src_port",
    "dst_port",
    # Phase 36: Zeek integer columns
    "conn_orig_bytes",
    "conn_resp_bytes",
    "ssh_version",
})
