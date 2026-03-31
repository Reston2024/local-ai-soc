"""
Built-in NIST SP 800-61r3 IR starter playbooks.

These are seeded into the SQLite database on first startup via
seed_builtin_playbooks() in backend/api/playbooks.py.

Five playbooks cover the major NIST IR phases:
1. Phishing Initial Triage
2. Lateral Movement Investigation
3. Privilege Escalation Response
4. Data Exfiltration Containment
5. Malware Isolation
"""

BUILTIN_PLAYBOOKS: list[dict] = [
    {
        "name": "Phishing Initial Triage",
        "description": (
            "NIST IR Phase: Detection & Analysis + Containment. "
            "Covers initial response to suspected phishing incidents including "
            "user account identification, evidence collection, and credential remediation."
        ),
        "trigger_conditions": ["phishing", "suspicious email", "credential harvesting"],
        "steps": [
            {
                "step_number": 1,
                "title": "Identify affected user accounts",
                "description": (
                    "Determine which user accounts received or interacted with the "
                    "suspected phishing message. Check email gateway logs and user reports."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "List all affected user accounts (UPNs), timestamps of receipt, "
                    "and whether the user clicked any links or opened attachments."
                ),
            },
            {
                "step_number": 2,
                "title": "Collect email headers and links as evidence",
                "description": (
                    "Retrieve full email headers, sender IP, DMARC/DKIM/SPF results, "
                    "and extract all embedded URLs and attachment hashes."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Record: sender address, originating IP, subject line, "
                    "URL list, attachment SHA256 hashes, and DMARC disposition."
                ),
            },
            {
                "step_number": 3,
                "title": "Check for credential use post-receipt (auth logs)",
                "description": (
                    "Search authentication logs for logins from affected accounts "
                    "after the phishing email delivery timestamp, including impossible "
                    "travel or unusual source IPs."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "List any authentication events after email receipt: timestamp, "
                    "source IP, country, success/failure, MFA status."
                ),
            },
            {
                "step_number": 4,
                "title": "Search for lateral movement from affected account",
                "description": (
                    "Investigate whether the compromised account was used to access "
                    "other hosts, services, or accounts via remote desktop, "
                    "PsExec, WMI, or other lateral movement techniques."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Document any remote connections, service executions, or "
                    "authentication events originating from the affected account "
                    "after initial compromise."
                ),
            },
            {
                "step_number": 5,
                "title": "Notify user and reset credentials if compromise confirmed",
                "description": (
                    "If credential compromise is confirmed, immediately reset the "
                    "affected account password, revoke active sessions, and notify "
                    "the user and their manager."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Record: credential reset timestamp, sessions revoked, "
                    "MFA re-enrollment status, notification sent to user."
                ),
            },
            {
                "step_number": 6,
                "title": "Close or escalate with findings",
                "description": (
                    "Document final determination: false positive, contained incident, "
                    "or active breach requiring escalation. Update the case with "
                    "IOCs and lessons learned."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Final determination (FP/contained/breach), IOC list, "
                    "escalation decision with justification."
                ),
            },
        ],
        "version": "1.0",
        "is_builtin": True,
    },
    {
        "name": "Lateral Movement Investigation",
        "description": (
            "NIST IR Phase: Analysis + Containment. "
            "Investigates suspected lateral movement including pass-the-hash, "
            "remote service execution, and credential relay attacks."
        ),
        "trigger_conditions": [
            "lateral movement",
            "pass-the-hash",
            "remote service execution",
            "T1021",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Identify source host and compromised account",
                "description": (
                    "Determine the originating host and account used to initiate "
                    "the lateral movement. Review Sigma detections and event logs "
                    "for authentication anomalies."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Source hostname, IP, compromised account name, "
                    "initial detection timestamp and alert name."
                ),
            },
            {
                "step_number": 2,
                "title": "Map all remote connections from source in investigation timeline",
                "description": (
                    "Enumerate all remote authentication events (RDP, SMB, WinRM, "
                    "PsExec) originating from the source host and account within "
                    "the investigation timeframe."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Timeline of remote connections: target hostname, IP, "
                    "protocol, timestamp, account used, success/failure."
                ),
            },
            {
                "step_number": 3,
                "title": "Check for credential dumping artifacts on source host",
                "description": (
                    "Examine process execution logs on the source host for "
                    "credential dumping tools (Mimikatz, ProcDump on LSASS, "
                    "reg save HKLM\\SAM, etc.)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Process executions matching credential dumping patterns: "
                    "process name, command line, parent process, timestamp."
                ),
            },
            {
                "step_number": 4,
                "title": "Identify all destination hosts reached",
                "description": (
                    "Compile the complete list of hosts accessed via lateral movement "
                    "to determine the full scope of the compromise."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Complete list of destination hosts: hostname, IP, "
                    "access time, technique used, actions performed."
                ),
            },
            {
                "step_number": 5,
                "title": "Contain affected hosts and reset credentials",
                "description": (
                    "Isolate compromised hosts from the network, reset all "
                    "affected account credentials, and revoke Kerberos tickets "
                    "as appropriate."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Hosts isolated (timestamp, method), credentials reset, "
                    "krbtgt reset if domain-wide compromise suspected."
                ),
            },
        ],
        "version": "1.0",
        "is_builtin": True,
    },
    {
        "name": "Privilege Escalation Response",
        "description": (
            "NIST IR Phase: Analysis + Eradication. "
            "Handles confirmed or suspected privilege escalation including "
            "UAC bypass, token impersonation, and exploitation of privileged services."
        ),
        "trigger_conditions": [
            "privilege escalation",
            "UAC bypass",
            "T1548",
            "token impersonation",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Identify the escalation event and affected account",
                "description": (
                    "Determine the exact escalation event: which account was "
                    "escalated, to what privilege level, by what mechanism, "
                    "and on which host."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Account name before/after escalation, privilege level gained, "
                    "host, timestamp, MITRE technique ID."
                ),
            },
            {
                "step_number": 2,
                "title": "Collect process tree and parent-child evidence",
                "description": (
                    "Capture the full process tree around the escalation event: "
                    "parent process, escalated process, command line, and any "
                    "child processes spawned under elevated privileges."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Process tree: PID, parent PID, process name, command line, "
                    "user context, start time for all involved processes."
                ),
            },
            {
                "step_number": 3,
                "title": "Check persistence mechanisms installed post-escalation",
                "description": (
                    "Search for persistence artifacts that may have been installed "
                    "after privilege escalation: scheduled tasks, registry run keys, "
                    "services, WMI subscriptions."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "List any new scheduled tasks, registry run keys, services, "
                    "or WMI subscriptions created after the escalation timestamp."
                ),
            },
            {
                "step_number": 4,
                "title": "Revoke elevated tokens and sessions",
                "description": (
                    "Terminate the escalated session, revoke elevated tokens, "
                    "and if domain admin was obtained, initiate KRBTGT rotation."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Sessions terminated, tokens revoked, KRBTGT rotation initiated "
                    "if applicable. Timestamp of each action."
                ),
            },
            {
                "step_number": 5,
                "title": "Patch or remediate escalation vector",
                "description": (
                    "Identify and close the escalation vector: apply missing patch, "
                    "correct misconfiguration, restrict vulnerable service, "
                    "or add compensating control."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Escalation vector description, remediation applied "
                    "(patch KB, config change, ACL update), completion timestamp."
                ),
            },
        ],
        "version": "1.0",
        "is_builtin": True,
    },
    {
        "name": "Data Exfiltration Containment",
        "description": (
            "NIST IR Phase: Containment + Eradication + Recovery. "
            "Responds to suspected data exfiltration including C2 beacon callbacks, "
            "large outbound uploads, and archive staging."
        ),
        "trigger_conditions": [
            "data exfiltration",
            "large upload",
            "T1041",
            "T1048",
            "C2",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Identify exfiltration destination (IP/domain)",
                "description": (
                    "Determine the destination IP, domain, or URL that data "
                    "is being sent to. Cross-reference with threat intelligence "
                    "for known C2 infrastructure."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Destination IP(s), domain(s), port(s), protocol(s), "
                    "threat intel classification (known C2/benign/unknown)."
                ),
            },
            {
                "step_number": 2,
                "title": "Quantify data volume and file types involved",
                "description": (
                    "Estimate the volume of data exfiltrated and identify what "
                    "types of files or data were involved (credentials, PII, "
                    "intellectual property, configuration files)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Estimated data volume (bytes/MB), file types, "
                    "classification level, data owner, timeframe of exfiltration."
                ),
            },
            {
                "step_number": 3,
                "title": "Check for staging directory or archive creation",
                "description": (
                    "Search for evidence of data staging: temporary directories, "
                    "zip/rar archives, or encrypted archives created before "
                    "the outbound transfer."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Staging directory path, archive filenames, creation timestamps, "
                    "contents if accessible."
                ),
            },
            {
                "step_number": 4,
                "title": "Block destination at network level — document action for analyst",
                "description": (
                    "Block the identified exfiltration destination at the firewall "
                    "or proxy. This is a containment action — document thoroughly "
                    "before making changes."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Firewall/proxy rule added: destination blocked, rule ID, "
                    "timestamp, approver name."
                ),
            },
            {
                "step_number": 5,
                "title": "Identify data owner and initiate breach assessment",
                "description": (
                    "Identify the owner of the exfiltrated data and initiate a "
                    "formal breach assessment to determine notification obligations "
                    "under applicable regulations (GDPR, HIPAA, etc.)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Data owner name/department, regulatory framework applicable, "
                    "breach notification decision and rationale."
                ),
            },
            {
                "step_number": 6,
                "title": "Preserve forensic artifacts and document timeline",
                "description": (
                    "Capture all relevant forensic artifacts before any remediation "
                    "that could destroy evidence. Document a complete timeline "
                    "of the exfiltration."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Artifacts preserved (network capture, endpoint image, log exports), "
                    "chain of custody, complete exfiltration timeline."
                ),
            },
        ],
        "version": "1.0",
        "is_builtin": True,
    },
    {
        "name": "Malware Isolation",
        "description": (
            "NIST IR Phase: Containment + Eradication. "
            "Handles confirmed malware presence including ransomware, backdoors, "
            "and droppers — prioritising volatile evidence collection before isolation."
        ),
        "trigger_conditions": [
            "malware",
            "ransomware",
            "backdoor",
            "T1059",
            "T1105",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Hash and document the malware artifact",
                "description": (
                    "Compute SHA256 hash of the malware artifact and collect "
                    "full file metadata: path, size, timestamps (created/modified/accessed), "
                    "digital signature status."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "SHA256 hash, file path, file size, created/modified/accessed "
                    "timestamps, digital signature (signed/unsigned/invalid)."
                ),
            },
            {
                "step_number": 2,
                "title": "Check for known IOC matches in detection context",
                "description": (
                    "Cross-reference the malware hash, C2 domains/IPs, and process "
                    "indicators against threat intelligence feeds and MITRE ATT&CK "
                    "to identify the malware family."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "TI feed matches, known malware family name, "
                    "associated MITRE techniques, confidence level."
                ),
            },
            {
                "step_number": 3,
                "title": "Identify all hosts running the same process/file",
                "description": (
                    "Search across the environment for other hosts executing the "
                    "same binary (by hash), same process name, or same command-line "
                    "pattern to determine spread."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Complete list of affected hosts: hostname, IP, "
                    "first seen timestamp, process details."
                ),
            },
            {
                "step_number": 4,
                "title": "Collect volatile memory artifacts before isolation",
                "description": (
                    "Before isolating the host, capture volatile evidence: "
                    "running process list, network connections, memory dump "
                    "of the malicious process if feasible."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Process list snapshot, active network connections, "
                    "memory dump path/hash if captured, timestamp."
                ),
            },
            {
                "step_number": 5,
                "title": "Isolate affected host(s) — document action",
                "description": (
                    "Isolate the infected host(s) from the network to prevent "
                    "further spread. Use EDR isolation, VLAN segmentation, "
                    "or physical disconnection as appropriate."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Host(s) isolated: hostname, IP, isolation method, "
                    "timestamp, approver, EDR isolation ID if applicable."
                ),
            },
            {
                "step_number": 6,
                "title": "Preserve disk image reference for forensics",
                "description": (
                    "Preserve a forensic disk image or reference snapshot for "
                    "post-incident analysis. Document chain of custody and "
                    "storage location."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Disk image location, hash (SHA256), acquisition tool, "
                    "chain of custody custodian, storage path."
                ),
            },
        ],
        "version": "1.0",
        "is_builtin": True,
    },
]
