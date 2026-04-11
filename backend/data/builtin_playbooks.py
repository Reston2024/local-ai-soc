"""
Built-in CISA Federal IR Playbooks (Phase 38).

These replace the 5 NIST SP 800-61r3 IR starter playbooks with 4 CISA-derived
incident response flows covering the primary federal IR incident classes.

Source: CISA Federal Government Cybersecurity Incident and Vulnerability Response
Playbooks (November 2021), CISA Phishing Response Playbook, CISA Ransomware Guide
(September 2020, updated 2023).

Seeded into the SQLite database on first startup via seed_builtin_playbooks()
in backend/api/playbooks.py. The seed function replaces NIST starters (source='nist')
with these CISA playbooks (source='cisa') — idempotent across restarts.

Four playbooks cover:
1. Phishing / BEC Response
2. Ransomware Response
3. Credential / Account Compromise Response
4. Malware / Intrusion Response
"""

BUILTIN_PLAYBOOKS: list[dict] = [
    {
        "name": "Phishing / BEC Response",
        "description": (
            "CISA Federal IR Playbook: Detection, Analysis, and Containment phase for "
            "phishing and business email compromise (BEC) incidents. Covers mailbox "
            "identification, header/URL evidence collection, credential and session "
            "revocation, sender blocking, and CISA reporting."
        ),
        "trigger_conditions": [
            "phishing",
            "BEC",
            "business email compromise",
            "T1566",
            "T1598",
            "T1534",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Verify report and identify affected mailboxes",
                "description": (
                    "Confirm the phishing report is valid and identify all mailboxes "
                    "that received or interacted with the suspicious message. Check "
                    "email gateway logs, user reports, and security alert queues to "
                    "enumerate affected accounts and determine whether any user opened "
                    "attachments or followed embedded links."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "List all affected mailboxes (UPNs), message delivery timestamps, "
                    "and whether each user opened attachments or clicked links."
                ),
                "attack_techniques": ["T1566.001", "T1566.002"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Collect email headers, URLs, and attachment hashes",
                "description": (
                    "Retrieve full email headers including originating IP, DMARC/DKIM/SPF "
                    "disposition, and extract all embedded URLs and attachment SHA256 hashes. "
                    "Submit suspicious URLs and file hashes to threat intelligence platforms "
                    "to determine campaign attribution and payload classification."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Record: sender address, originating IP, subject line, all embedded URLs, "
                    "attachment SHA256 hashes, DMARC disposition, SPF/DKIM result."
                ),
                "attack_techniques": ["T1566.001", "T1598"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Check authentication logs for credential use post-delivery",
                "description": (
                    "Search authentication logs for any logins from affected accounts "
                    "after the phishing message delivery timestamp. Look for impossible "
                    "travel, unfamiliar source IPs, new device registrations, MFA bypass "
                    "attempts, or unusual service access patterns indicating credential "
                    "compromise."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "List authentication events after email delivery: timestamp, source IP, "
                    "country, success/failure, MFA status, device, service accessed."
                ),
                "attack_techniques": ["T1078", "T1110"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Search for OAuth app grants and mail forwarding rules (BEC indicator)",
                "description": (
                    "Investigate whether the attacker established persistence via OAuth "
                    "application grants or mail forwarding rules — key BEC indicators. "
                    "Review inbox rules, email delegation, and OAuth consent grants for "
                    "all affected accounts. Unusual app consents or forwarding to external "
                    "addresses indicate business email compromise."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "List any inbox forwarding rules (destination, creation time), OAuth "
                    "app consents (app name, permissions, granted-by), email delegation "
                    "changes discovered on affected accounts."
                ),
                "attack_techniques": ["T1114", "T1534"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 5,
                "title": "Reset credentials and revoke sessions if compromise confirmed",
                "description": (
                    "If credential compromise is confirmed, immediately reset affected "
                    "account passwords, revoke all active sessions and refresh tokens, "
                    "and force MFA re-enrollment. If OAuth app grants are malicious, "
                    "revoke them. Notify the affected user and their manager of the "
                    "compromise and required password change."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Record: credential reset timestamp, sessions revoked, OAuth app grants "
                    "revoked, MFA re-enrollment status, notification sent (user + manager)."
                ),
                "attack_techniques": ["T1078", "T1531"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["reset_credentials", "notify_management"],
            },
            {
                "step_number": 6,
                "title": "Block sender domain/IP and submit phishing URLs to CISA",
                "description": (
                    "Block the identified sender domain and originating IP at the email "
                    "gateway and perimeter firewall. Submit phishing URLs and indicators "
                    "to CISA (report@cisa.dhs.gov) per federal reporting requirements. "
                    "Quarantine or remove phishing messages from all affected mailboxes."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Domains/IPs blocked (rule IDs, timestamp), phishing URLs submitted to "
                    "CISA (submission ticket/confirmation), messages quarantined (count)."
                ),
                "attack_techniques": ["T1566"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["block_domain", "block_ip"],
            },
            {
                "step_number": 7,
                "title": "Notify affected users and document incident",
                "description": (
                    "Notify all users who received the phishing message with guidance "
                    "on what actions to take (change passwords, report suspicious activity). "
                    "Document the complete incident timeline, IOCs discovered, containment "
                    "actions taken, and lessons learned. Close or escalate based on scope."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "User notification sent (timestamp, channel), complete IOC list, "
                    "incident timeline summary, lessons learned, final determination "
                    "(false positive / contained / breach requiring escalation)."
                ),
                "attack_techniques": ["T1566"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["notify_management"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },
    {
        "name": "Ransomware Response",
        "description": (
            "CISA Ransomware Guide: Immediate response to ransomware and destructive "
            "encryption events. Prioritises volatile evidence collection, host isolation, "
            "lateral movement containment, backup assessment, and mandatory federal "
            "notification to CISA and executive leadership."
        ),
        "trigger_conditions": [
            "ransomware",
            "encryption",
            "T1486",
            "T1490",
            "ransom note",
            "T1059",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Identify patient-zero host and initial infection vector",
                "description": (
                    "Determine the first host affected (patient zero) and the initial "
                    "infection vector — phishing, exposed RDP/VPN (T1133), or exploited "
                    "public-facing application (T1190). Review endpoint detection alerts, "
                    "network flow logs, and email gateway records to establish the initial "
                    "access chain before isolation degrades evidence."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Patient-zero hostname and IP, infection vector (phishing/RDP/exploit), "
                    "earliest malicious activity timestamp, Sigma/EDR alert IDs."
                ),
                "attack_techniques": ["T1566", "T1190", "T1133"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Collect volatile evidence before isolation",
                "description": (
                    "Before isolating any host, capture volatile evidence that will be "
                    "lost after reboot or network disconnect: running process list, active "
                    "network connections, loaded kernel modules, and if feasible, a memory "
                    "dump of the ransomware process. This evidence is critical for malware "
                    "family identification and decryption key recovery research."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Process list snapshot (with PIDs and parent PIDs), active network "
                    "connections (remote IPs/ports), memory dump path and SHA256 if captured, "
                    "collection timestamp and method."
                ),
                "attack_techniques": ["T1057", "T1049"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Isolate affected hosts from network immediately",
                "description": (
                    "Immediately isolate all confirmed ransomware-infected hosts to prevent "
                    "further encryption spread. Use EDR network isolation, VLAN segmentation, "
                    "or physical disconnection. Engage your IR team. Time is critical — "
                    "ransomware propagates via SMB/RPC and can encrypt network shares "
                    "within minutes of initial execution."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Hosts isolated (hostname, IP, method, timestamp, EDR isolation ID), "
                    "IR team engaged (name, contact time), isolation approval chain."
                ),
                "attack_techniques": ["T1486"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 15,
                "containment_actions": ["isolate_host", "engage_ir_team"],
            },
            {
                "step_number": 4,
                "title": "Disable SMB/RPC laterally — block internal propagation",
                "description": (
                    "Block SMB (port 445) and RPC traffic between network segments at the "
                    "firewall or managed switch level to prevent ransomware lateral movement "
                    "via file share encryption or remote service execution (EternalBlue/WannaCry "
                    "pattern). Disable admin shares (ADMIN$, C$) on all uninfected hosts "
                    "as a compensating control."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Firewall rules added (rule IDs, ports blocked, segments affected), "
                    "admin shares disabled (scope), timestamp, approver name."
                ),
                "attack_techniques": ["T1021.002", "T1210"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 15,
                "containment_actions": ["block_ip", "isolate_host"],
            },
            {
                "step_number": 5,
                "title": "Determine scope: enumerate all encrypted file shares and hosts",
                "description": (
                    "Enumerate the full scope of the incident: identify all hosts with "
                    "encrypted files, affected network shares, and the total volume of "
                    "encrypted data. Check for ransom note files (.txt/.html) to identify "
                    "the ransomware family and any decryption negotiation instructions."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "List of all affected hosts (count), encrypted file shares (paths, "
                    "estimated file count), ransomware family (from ransom note or TI), "
                    "estimated total data volume encrypted."
                ),
                "attack_techniques": ["T1486"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 6,
                "title": "Assess backup availability and integrity",
                "description": (
                    "Determine whether clean backups exist and have not been compromised. "
                    "Ransomware operators frequently target backup systems before triggering "
                    "encryption (T1490 — Inhibit System Recovery). Verify offline/immutable "
                    "backup availability, confirm backup integrity via hash verification, "
                    "and estimate recovery time objectives (RTO) for critical systems."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Backup systems checked (NAS/cloud/tape), last known-good backup date, "
                    "backup integrity verification result, evidence of backup tampering, "
                    "RTO estimate for critical systems."
                ),
                "attack_techniques": ["T1490"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence", "notify_management"],
            },
            {
                "step_number": 7,
                "title": "Notify CISA, legal, and executive leadership",
                "description": (
                    "Federal agencies must notify CISA within 1 hour of confirming a "
                    "ransomware incident. Notify CISA via report@cisa.dhs.gov or the "
                    "24/7 hotline (888-282-0870). Simultaneously notify general counsel, "
                    "the CISO, and executive leadership. Do not pay the ransom without "
                    "legal and executive approval — payment does not guarantee decryption."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "CISA notification sent (ticket number, timestamp, reporter name), "
                    "legal counsel notified (name, timestamp), executive notification "
                    "chain (names, timestamps), ransom payment decision documented."
                ),
                "attack_techniques": ["T1486"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["notify_management", "engage_ir_team"],
            },
            {
                "step_number": 8,
                "title": "Eradicate and recover from clean backups or known-good snapshot",
                "description": (
                    "Once scope is determined and notifications are complete, begin "
                    "eradication. Rebuild infected hosts from clean images rather than "
                    "attempting in-place cleaning — ransomware often installs rootkits or "
                    "backdoors alongside the encryptor. Restore data from known-good "
                    "offline backups. Verify restored systems before reconnecting to "
                    "the network."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Hosts rebuilt (count, method — fresh image vs clean restore), "
                    "data restored from backup (source date, verification hash), "
                    "restored systems security-verified before reconnect (method, timestamp)."
                ),
                "attack_techniques": ["T1486"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 240,
                "containment_actions": ["isolate_host"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },
    {
        "name": "Credential / Account Compromise Response",
        "description": (
            "CISA Federal IR Playbook: Response to confirmed or suspected credential "
            "and account compromise including impossible travel, credential dumping, "
            "token abuse, and account takeover. Covers audit, session revocation, "
            "credential reset, and persistence removal."
        ),
        "trigger_conditions": [
            "credential compromise",
            "account takeover",
            "T1078",
            "T1110",
            "T1003",
            "impossible travel",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Confirm compromise and identify affected accounts and access vector",
                "description": (
                    "Verify the compromise is genuine (not a false positive from VPN or "
                    "travel). Identify all affected accounts, determine the initial access "
                    "vector (phishing credential harvest, brute force, VPN exploitation, "
                    "or insider), and establish the earliest known malicious authentication "
                    "event timestamp to bound the investigation scope."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Affected account(s) (UPN/username), initial access vector, earliest "
                    "malicious auth timestamp, source IP/country, confirmation method "
                    "(impossible travel / velocity / TI match / user report)."
                ),
                "attack_techniques": ["T1078", "T1133"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Audit recent activity: impossible travel, anomalous logins, MFA bypasses",
                "description": (
                    "Review the complete authentication history for affected accounts "
                    "across all services (on-prem AD, Azure AD, SaaS apps). Flag impossible "
                    "travel events, logins from new devices, MFA bypass (authenticator "
                    "fatigue, SIM swap, OTP phishing), and unusual service access. "
                    "Determine whether access was privileged."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Authentication log review period, anomalous events found (timestamp, "
                    "source IP, country, service), MFA bypass indicators, privileged "
                    "access observed (admin roles, service accounts accessed)."
                ),
                "attack_techniques": ["T1078", "T1556"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Check for credential dumping artifacts on associated hosts",
                "description": (
                    "Search endpoint telemetry on hosts accessed by the compromised account "
                    "for credential dumping tools and techniques: Mimikatz/sekurlsa, ProcDump "
                    "targeting LSASS, reg save of SAM/SYSTEM/SECURITY hives, NTDS.dit access, "
                    "or DCSync activity. Evidence of credential dumping expands the scope "
                    "to a full credential compromise across the environment."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Process executions matching credential dumping patterns (process name, "
                    "command line, parent, PID, timestamp), LSASS access events, registry "
                    "hive exports, DCSync activity in domain controller event logs."
                ),
                "attack_techniques": ["T1003", "T1552"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Revoke all active sessions and invalidate tokens",
                "description": (
                    "Immediately revoke all active sessions, OAuth tokens, SAML assertions, "
                    "and Kerberos TGTs for affected accounts. For domain-wide compromise, "
                    "initiate KRBTGT account rotation (double rotation required). Revoke "
                    "any API keys or service credentials that may have been exposed. "
                    "This containment action must be completed before password reset "
                    "to prevent re-authentication on compromised sessions."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Sessions revoked (service, count, timestamp), OAuth tokens invalidated "
                    "(apps, count), KRBTGT rotation status (single/double), Kerberos TGTs "
                    "invalidated, API keys rotated (services, count)."
                ),
                "attack_techniques": ["T1550", "T1134"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["reset_credentials", "notify_management"],
            },
            {
                "step_number": 5,
                "title": "Reset passwords and force MFA re-enrollment",
                "description": (
                    "Reset passwords for all affected accounts using a secure out-of-band "
                    "channel (not the compromised email account). Force MFA re-enrollment "
                    "to ensure the attacker's registered MFA device is replaced. For service "
                    "accounts, rotate all associated secrets and certificates. Verify the "
                    "new credentials work correctly before closing the containment step."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Accounts with passwords reset (UPN, timestamp, reset method), MFA "
                    "re-enrollment completed (count, method), service account secrets "
                    "rotated (service names), verification of new credentials successful."
                ),
                "attack_techniques": ["T1078"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["reset_credentials"],
            },
            {
                "step_number": 6,
                "title": "Search for persistence mechanisms established under compromised account",
                "description": (
                    "Investigate whether the attacker installed persistence under the "
                    "compromised account: new local/domain admin accounts, scheduled tasks, "
                    "SSH authorized keys, WMI event subscriptions, or registry run keys. "
                    "Check for new service principal names (SPNs) added for Kerberoasting, "
                    "group membership changes, and unusual application registrations."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "New accounts created (names, timestamps, created-by), scheduled tasks "
                    "added (name, command, user context), registry persistence (key, value), "
                    "group membership changes, new SPNs registered, app registrations created."
                ),
                "attack_techniques": ["T1098", "T1136", "T1053"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence", "isolate_host"],
            },
            {
                "step_number": 7,
                "title": "Review and revoke excessive permissions granted post-compromise",
                "description": (
                    "Audit permissions and group memberships modified after the initial "
                    "compromise timestamp. Revoke any excessive permissions granted to the "
                    "compromised account or new accounts created by the attacker. Review "
                    "cloud IAM roles, Azure AD app permissions, and on-prem privileged "
                    "group membership for unauthorized changes."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Permission changes reviewed (services/directories checked), excessive "
                    "permissions revoked (account, permission, revocation timestamp), "
                    "cloud IAM roles reviewed, privileged group membership restored "
                    "to baseline."
                ),
                "attack_techniques": ["T1098", "T1078.004"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["notify_management"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },
    {
        "name": "Malware / Intrusion Response",
        "description": (
            "CISA Federal IR Playbook: Response to confirmed malware infection and "
            "network intrusion including backdoors, C2 beaconing, and dropper execution. "
            "Prioritises artifact identification, TI correlation, C2 blocking, and host "
            "isolation before forensic preservation."
        ),
        "trigger_conditions": [
            "malware",
            "intrusion",
            "backdoor",
            "C2",
            "T1059",
            "T1105",
            "T1071",
            "T1055",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Identify malware artifact: hash, path, and digital signature",
                "description": (
                    "Locate the malware artifact on the affected host and collect full "
                    "file metadata: absolute path, SHA256 hash, file size, created/modified/ "
                    "accessed timestamps, digital signature status (signed/unsigned/invalid), "
                    "and originating process. This is the anchor for all subsequent TI "
                    "lookups and scope determination."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "SHA256 hash, full file path, file size, created/modified/accessed "
                    "timestamps (MACE), digital signature (signer CN or unsigned), "
                    "process that dropped or executed the artifact (PID, parent, command line)."
                ),
                "attack_techniques": ["T1204", "T1059"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Cross-reference with TI feeds and MITRE to identify malware family",
                "description": (
                    "Submit the malware hash, C2 domains/IPs, and behavioral indicators "
                    "to threat intelligence platforms (VirusTotal, MITRE ATT&CK, internal "
                    "TI feeds) to identify the malware family, associated threat actor, "
                    "and known TTPs. Malware family identification drives the IOC expansion "
                    "and scope assessment in subsequent steps."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "TI lookup results (platforms queried, hits/misses), malware family "
                    "identification (confidence level), associated threat actor (if known), "
                    "related IOCs from TI (hashes, domains, IPs, registry keys)."
                ),
                "attack_techniques": ["T1071", "T1105"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Identify all hosts running the same binary or showing the same network IOCs",
                "description": (
                    "Scan the environment for other hosts executing the same binary (by "
                    "SHA256), same process name with matching command-line patterns, or "
                    "communicating with the same C2 infrastructure. Use EDR hunt queries "
                    "and network flow logs to determine the full scope of the intrusion "
                    "before containment to avoid incomplete isolation."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Hunt query used, total hosts found with matching indicators (list: "
                    "hostname, IP, first-seen timestamp), network flow matches (source "
                    "hosts communicating with C2 IPs/domains), scope assessment summary."
                ),
                "attack_techniques": ["T1059", "T1071"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Identify C2 infrastructure: beacon destination IPs and domains",
                "description": (
                    "Identify all command-and-control (C2) destinations the malware "
                    "communicates with. Analyse network flows, DNS queries, and SSL/TLS "
                    "certificate metadata for beaconing patterns. Document beacon interval, "
                    "jitter, protocol, and data volumes. Correlate with threat intelligence "
                    "to confirm C2 attribution and identify any multi-stage infrastructure."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "C2 IPs and domains (full list), protocols used (HTTP/HTTPS/DNS/TCP), "
                    "beacon interval and jitter, TLS certificate details (issuer, CN, "
                    "SHA256), TI classification of C2 infrastructure."
                ),
                "attack_techniques": ["T1071", "T1095"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 5,
                "title": "Block C2 destinations at network perimeter",
                "description": (
                    "Block all identified C2 IPs and domains at the firewall, DNS resolver, "
                    "and web proxy before host isolation to cut attacker access while "
                    "preserving the ability to observe additional beaconing from undetected "
                    "infected hosts. Ensure blocks are logged for later analysis of blocked "
                    "connection attempts that reveal additional infected hosts."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Firewall rules added (C2 IPs blocked, rule IDs, timestamp), DNS "
                    "sinkhole/block entries (domains blocked), proxy block entries, "
                    "post-block connection attempts observed (additional hosts identified)."
                ),
                "attack_techniques": ["T1071"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 30,
                "containment_actions": ["block_ip", "block_domain"],
            },
            {
                "step_number": 6,
                "title": "Collect volatile forensics before isolation",
                "description": (
                    "Before isolating infected hosts from the network, capture volatile "
                    "forensic evidence: running process list with full command lines, "
                    "active network connections showing live C2 sessions, loaded DLLs "
                    "and injected code regions, and if feasible, a memory dump of the "
                    "malicious process for offline analysis and potential IOC extraction."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Process list snapshot (PID, parent PID, path, command line, start time), "
                    "network connections at capture time (remote IPs, ports, state), "
                    "memory dump path/SHA256 and acquisition method, DLL injection evidence."
                ),
                "attack_techniques": ["T1057", "T1049"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 7,
                "title": "Isolate infected hosts and disable lateral movement vectors",
                "description": (
                    "Isolate all confirmed infected hosts using EDR network isolation, "
                    "VLAN segmentation, or firewall ACLs. Disable or restrict lateral "
                    "movement vectors: disable WMI remote execution, restrict RDP/SMB "
                    "between segments, and disable process injection-susceptible services. "
                    "Engage external IR team if internal capacity is insufficient."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Hosts isolated (hostname, IP, isolation method, EDR isolation ID, "
                    "timestamp), lateral movement controls applied (SMB/RDP/WMI restrictions, "
                    "scope), IR team engaged (firm, contact name, engagement start time)."
                ),
                "attack_techniques": ["T1021", "T1055"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["isolate_host", "engage_ir_team"],
            },
            {
                "step_number": 8,
                "title": "Preserve forensic disk image and document chain of custody",
                "description": (
                    "Preserve a forensic disk image of each isolated infected host before "
                    "any remediation that could alter evidence. Use forensic acquisition "
                    "tools (FTK Imager, dd with hash verification) and document chain of "
                    "custody. Store images in the evidence archive per agency retention "
                    "policy. This image is required for malware analysis, legal proceedings, "
                    "and post-incident reporting."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Disk image acquisition: tool used, image path, SHA256 hash, "
                    "acquisition start/end time, chain of custody custodian name, "
                    "storage location and retention period."
                ),
                "attack_techniques": ["T1204"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },
]
