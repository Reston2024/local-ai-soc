"""
Built-in CISA Federal IR Playbooks (Phase 38 + Phase 46 expansion).

Sources:
- CISA Federal Government Cybersecurity Incident and Vulnerability Response
  Playbooks (November 2021)
- CISA Phishing Response Playbook
- CISA Ransomware Guide (September 2020, updated 2023)
- CISA Vulnerability Response Playbook (November 2021)
- CISA/MS-ISAC DDoS Quick Guide
- CISA Advisory AA22-047A (Supply Chain / SolarWinds lessons)
- CISA/FBI Data Exfiltration Joint Advisories
- CISA Vulnerability Scanning / Web App Security Program
- CISA Insider Threat Mitigation Guide (2020)
- CISA SCuBA Cloud Security Technical Reference Architecture
- CISA ICS-CERT Advisory AA22-103A / ICS/OT Intrusion guidance
- NSA/CISA Advisory AA22-011A (Active Directory security)
- CISA/FBI Advisory AA23-061A (Destructive Wiper / Royal ransomware)
- Microsoft DART / CISA AA23-193A (M365 Tenant Compromise)
- CISA Advisory AA22-320A (APT / Long-Dwell Intrusion)
- FBI IC3 / FinCEN Advisory FIN-2019-A005 (Wire Fraud / BEC payment)
- NSA/CISA Advisory AA22-137A (Living-off-the-Land / LOLBins)
- CISA/FBI Advisory AA23-046A (Cryptojacking / Resource Hijacking)

Seeded into the SQLite database on first startup via seed_builtin_playbooks()
in backend/api/playbooks.py. The seed function replaces NIST starters (source='nist')
with these CISA playbooks (source='cisa') — idempotent across restarts.

Nineteen playbooks cover:
 1. Phishing / BEC Response
 2. Ransomware Response
 3. Credential / Account Compromise Response
 4. Malware / Intrusion Response
 5. Vulnerability Response (CVE / KEV exploitation)
 6. Denial of Service / DDoS Response
 7. Supply Chain Compromise Response
 8. Data Exfiltration / Breach Response
 9. Web Application Attack Response
10. Insider Threat Response
11. Cloud Account Compromise Response
12. ICS / OT Intrusion Response
13. Active Directory Full Compromise (Golden Ticket / DCSync)
14. Cryptojacking / Resource Hijacking Response
15. Destructive Wiper Response
16. M365 Tenant Compromise Response
17. APT / Long-Dwell Intrusion Response
18. Wire Fraud / Business Payment Fraud Response
19. Living-off-the-Land (LotL) Attack Response
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

    # -------------------------------------------------------------------------
    # Phase 46 expansion — 7 additional CISA playbooks
    # -------------------------------------------------------------------------

    {
        "name": "Vulnerability Response",
        "description": (
            "CISA Federal Vulnerability Response Playbook (November 2021): Structured "
            "triage and remediation workflow for newly disclosed CVEs, with priority "
            "lane for CISA Known Exploited Vulnerabilities (KEV). Covers asset "
            "identification, risk scoring, patch deployment verification, and "
            "compensating controls when patching is not immediately possible."
        ),
        "trigger_conditions": [
            "CVE",
            "vulnerability",
            "KEV",
            "patch",
            "exploit",
            "T1203",
            "T1068",
            "unpatched",
            "zero-day",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Confirm CVE details and check CISA KEV catalog",
                "description": (
                    "Retrieve the full CVE advisory (NVD, vendor bulletin) and immediately "
                    "check whether the vulnerability appears in the CISA Known Exploited "
                    "Vulnerabilities catalog (cisa.gov/KEV). KEV-listed vulnerabilities carry "
                    "a mandatory remediation deadline for federal agencies (typically 2 weeks "
                    "for KEV vs 30 days for high-severity non-KEV). Document CVSS base score, "
                    "attack vector, privileges required, and whether a public exploit exists."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "CVE ID, CVSS score (base/temporal), attack vector (network/local), "
                    "privileges required, KEV status (yes/no, mandatory deadline if KEV), "
                    "public exploit availability (PoC/weaponised), vendor patch status "
                    "(available/pending/no-fix)."
                ),
                "attack_techniques": ["T1190", "T1203"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Enumerate all affected assets in the environment",
                "description": (
                    "Identify every asset (hosts, applications, network devices, cloud "
                    "workloads) running the vulnerable software version. Cross-reference "
                    "the asset inventory with vulnerability scanner output, CMDB, and "
                    "osquery/EDR telemetry. Prioritise internet-facing, privileged, or "
                    "critical-system instances for immediate action."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Total affected asset count, asset list (hostname/IP, OS, software "
                    "version, exposure — internet-facing/internal/cloud), critical assets "
                    "identified, scan tool and scan date used for enumeration."
                ),
                "attack_techniques": ["T1190", "T1203"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Search for evidence of active exploitation",
                "description": (
                    "Before patching, determine whether the vulnerability has already been "
                    "exploited in the environment. Search SIEM/EDR for exploitation indicators: "
                    "anomalous process spawning from the vulnerable service, unexpected outbound "
                    "connections, web server error logs showing exploit strings, and any "
                    "Sigma detections matching the CVE's exploitation pattern."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Log sources queried (SIEM, EDR, web logs), search time window, "
                    "exploitation indicators found (yes/no), evidence details if found "
                    "(hostname, timestamp, process, network connection), Sigma rule hits."
                ),
                "attack_techniques": ["T1190", "T1068"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Apply vendor patch or deploy compensating controls",
                "description": (
                    "Deploy the vendor-supplied patch to all affected assets. For systems "
                    "that cannot be patched immediately (legacy systems, operational "
                    "constraints), implement CISA-recommended compensating controls: "
                    "network segmentation to restrict access to the vulnerable service, "
                    "WAF rules blocking exploit patterns, disabling the vulnerable feature, "
                    "or requiring additional authentication. Document any deferred patches "
                    "with a formal risk acceptance and re-assessment date."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Patched assets (hostname, patch version, deployment method, timestamp), "
                    "unpatched assets with compensating controls (hostname, control applied, "
                    "risk acceptance approver, re-assessment date), patch deployment "
                    "verification method (version check / vulnerability rescan)."
                ),
                "attack_techniques": ["T1190"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 120,
                "containment_actions": ["patch_system", "block_ip"],
            },
            {
                "step_number": 5,
                "title": "Verify remediation with authenticated vulnerability rescan",
                "description": (
                    "Run an authenticated vulnerability scan against all previously affected "
                    "assets to confirm the CVE no longer appears as exploitable. Compare "
                    "pre- and post-patch scan results. For KEV items, document scan results "
                    "as evidence of compliance with the mandatory remediation deadline. "
                    "Retain scan reports per agency records retention policy."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Rescan tool and scan date, pre-patch affected count vs post-patch "
                    "affected count, any assets still vulnerable (with justification), "
                    "scan report reference (ticket/file path), KEV compliance deadline met "
                    "(yes/no)."
                ),
                "attack_techniques": ["T1190"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["notify_management"],
            },
            {
                "step_number": 6,
                "title": "Report to CISA if KEV exploitation was confirmed",
                "description": (
                    "If active exploitation was confirmed in step 3, this constitutes a "
                    "cybersecurity incident requiring CISA notification per the Federal "
                    "Incident Notification Guidelines. Report to CISA (report@cisa.dhs.gov "
                    "or 888-282-0870) within the required timeframe based on severity "
                    "category. Document the complete vulnerability response timeline, "
                    "affected asset count, exploitation evidence, and remediation actions."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "CISA notification sent (yes/no, ticket number, timestamp), incident "
                    "severity category, affected asset count, exploitation evidence summary, "
                    "complete remediation timeline, post-incident monitoring in place."
                ),
                "attack_techniques": ["T1190"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["notify_management"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },

    {
        "name": "Denial of Service / DDoS Response",
        "description": (
            "CISA / MS-ISAC DDoS Quick Guide: Detection, characterisation, and "
            "mitigation of volumetric, protocol, and application-layer denial of service "
            "attacks. Covers upstream scrubbing activation, ACL-based blocking, ISP "
            "coordination, and service restoration verification."
        ),
        "trigger_conditions": [
            "DoS",
            "DDoS",
            "denial of service",
            "flood",
            "amplification",
            "T1498",
            "T1499",
            "bandwidth saturation",
            "SYN flood",
            "UDP flood",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Confirm DoS condition and classify attack type",
                "description": (
                    "Confirm that the service degradation is caused by a DoS/DDoS attack "
                    "rather than an infrastructure failure or configuration error. Collect "
                    "network flow data (NetFlow/sFlow) and interface utilisation statistics "
                    "to characterise the attack: volumetric (bandwidth saturation via UDP/"
                    "ICMP flood or amplification), protocol (SYN flood, fragmented packets), "
                    "or application-layer (HTTP flood, Slowloris, API abuse — T1499.002)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Attack type (volumetric/protocol/application), observed traffic volume "
                    "(Gbps/Mpps), affected services/IPs, attack source characterisation "
                    "(single source/distributed/amplification), first detected timestamp, "
                    "NetFlow/interface stats collected."
                ),
                "attack_techniques": ["T1498", "T1499"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 15,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Activate upstream scrubbing or DDoS mitigation service",
                "description": (
                    "Activate the organisation's DDoS mitigation service (cloud scrubbing "
                    "centre, ISP-level black-hole routing, or on-premises scrubbing appliance). "
                    "For cloud scrubbing: redirect traffic via BGP announcement or DNS change. "
                    "For ISP black-holing: contact the upstream ISP NOC with the targeted IP "
                    "prefix for Remotely-Triggered Black Hole (RTBH) routing. Document "
                    "activation time and method."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Mitigation service activated (vendor/method, activation timestamp), "
                    "BGP change or DNS redirect details, ISP NOC contact name and ticket "
                    "number (if RTBH), traffic volume before/after activation, "
                    "services impacted during mitigation activation."
                ),
                "attack_techniques": ["T1498"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["block_ip", "engage_ir_team"],
            },
            {
                "step_number": 3,
                "title": "Deploy ACL-based blocks for identified attack sources",
                "description": (
                    "For attacks with identifiable source IP ranges, deploy ACL/firewall rules "
                    "to block them at the network perimeter or upstream router. For reflection "
                    "amplification attacks (DNS, NTP, SSDP, memcached), block the amplification "
                    "protocol traffic inbound rather than source IPs. For application-layer "
                    "attacks, deploy WAF rate-limiting rules against attack signatures (HTTP "
                    "user agents, URI patterns, request rates)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "ACL rules deployed (prefix/IP ranges, protocol, port, device, rule ID, "
                    "timestamp), WAF rules activated (rule name, pattern, rate limit), "
                    "attack source ASNs identified, estimated traffic reduction achieved."
                ),
                "attack_techniques": ["T1498", "T1499"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["block_ip"],
            },
            {
                "step_number": 4,
                "title": "Monitor service recovery and validate normal operation",
                "description": (
                    "Monitor targeted service health metrics (response time, error rates, "
                    "CPU/memory) continuously during and after mitigation to confirm "
                    "service recovery. Verify that legitimate users can access services "
                    "and that mitigation controls are not blocking benign traffic. "
                    "Confirm attack has ceased before removing ACL rules."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Service health metrics before/during/after mitigation, synthetic "
                    "transaction test results (pass/fail), legitimate user impact "
                    "assessment, time to service restoration, residual attack traffic "
                    "observed after mitigation."
                ),
                "attack_techniques": ["T1499"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 5,
                "title": "Notify CISA and document attack for after-action reporting",
                "description": (
                    "Significant DDoS attacks against federal agencies must be reported to "
                    "CISA. Submit an incident report with attack characterisation, duration, "
                    "impact to services, and mitigation actions. After the incident is "
                    "resolved, produce an after-action report documenting attack characteristics, "
                    "mitigation effectiveness, and recommended improvements to DDoS resilience "
                    "(anycast, additional upstream scrubbing capacity, rate-limiting hardening)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "CISA notification sent (ticket, timestamp), attack duration (start–end), "
                    "peak attack volume, services affected and downtime, mitigation "
                    "effectiveness summary, after-action report drafted (yes/no), "
                    "recommended DDoS resilience improvements."
                ),
                "attack_techniques": ["T1498", "T1499"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["notify_management"],
            },
            {
                "step_number": 6,
                "title": "Post-Incident Review and Resilience Hardening",
                "description": (
                    "Conduct a blameless post-incident review within 5 business days. "
                    "Document attack timeline, characterisation (volumetric/protocol/application), "
                    "peak traffic, affected services, and total downtime. Evaluate mitigation "
                    "effectiveness and identify gaps. Update DDoS runbook with lessons learned. "
                    "Implement recommended resilience improvements: anycast routing, expanded "
                    "scrubbing capacity, BGP blackhole automation, rate-limiting tuning, "
                    "and upstream provider SLA review."
                ),
                "requires_approval": False,
                "evidence_prompt": (
                    "Post-incident review document completed (yes/no), lessons-learned items "
                    "captured in ticketing system, runbook updated, resilience improvements "
                    "backlogged with owner and target date, provider SLA reviewed."
                ),
                "attack_techniques": ["T1498", "T1499"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 2880,  # 48h post-incident
                "containment_actions": ["preserve_evidence"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },

    {
        "name": "Supply Chain Compromise Response",
        "description": (
            "CISA Advisory AA22-047A / SolarWinds Lessons Learned: Response to confirmed "
            "or suspected supply chain compromise including trojanised software updates, "
            "malicious third-party dependencies, and compromised build pipelines. Covers "
            "artifact isolation, scope determination across downstream consumers, trust "
            "revocation, and rebuild from verified sources."
        ),
        "trigger_conditions": [
            "supply chain",
            "trojanised",
            "trojanized",
            "T1195",
            "T1199",
            "T1553.002",
            "build pipeline",
            "software update compromise",
            "dependency confusion",
            "SolarWinds",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Identify the compromised software component and version range",
                "description": (
                    "Determine the exact software package, library, or update that has been "
                    "compromised — including the specific version(s) affected and the "
                    "compromise window (dates between which malicious versions were distributed). "
                    "Obtain the vendor advisory or CISA alert detailing the compromise. "
                    "Collect the legitimate vs malicious binary hashes to distinguish "
                    "infected from clean deployments in the environment."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Compromised software name and vendor, affected version range, "
                    "compromise window (start–end dates), malicious binary SHA256 hash(es), "
                    "clean/expected SHA256 hash(es), vendor advisory or CISA alert reference."
                ),
                "attack_techniques": ["T1195.002", "T1553.002"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Enumerate all systems that installed the compromised component",
                "description": (
                    "Identify every system in the environment that installed or ran the "
                    "compromised version. Query software inventory (SCCM, osquery, endpoint "
                    "management platforms) for the package name and affected version range. "
                    "For web dependencies, review package-lock.json / requirements.txt. "
                    "This enumeration defines the maximum possible blast radius before "
                    "any activity analysis is performed."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Query method (SCCM/osquery/inventory tool), total systems with "
                    "compromised version installed, list of affected systems (hostname, IP, "
                    "role, install date), systems that actively ran the software vs "
                    "installed-but-not-executed."
                ),
                "attack_techniques": ["T1195"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Hunt for attacker activity on all affected systems",
                "description": (
                    "For every system identified in step 2, search for evidence of attacker "
                    "activity that may have been introduced via the trojanised component: "
                    "beaconing to C2 infrastructure (known IOCs from the vendor advisory), "
                    "unusual process execution by the compromised service, lateral movement "
                    "attempts, new scheduled tasks or services, and credential access. "
                    "Supply chain attacks often have a significant dwell time before "
                    "secondary activity begins."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Hunt queries executed (SIEM/EDR), IOCs searched (IPs, domains, hashes "
                    "from vendor advisory), systems with positive hits (hostname, activity "
                    "type, timestamp), dwell time estimate (earliest attacker activity "
                    "vs software install date)."
                ),
                "attack_techniques": ["T1195", "T1071", "T1053"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 120,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Isolate and remove compromised component from all affected systems",
                "description": (
                    "Remove or disable the compromised software component from all affected "
                    "systems. For systems with confirmed attacker activity, isolate before "
                    "removal to preserve forensic evidence. Block the software vendor's "
                    "update distribution infrastructure at the firewall and DNS level until "
                    "the vendor has issued a verified clean update. Revoke code-signing "
                    "certificates used to sign the compromised component."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Systems with software removed/disabled (count, method, timestamp), "
                    "systems isolated due to active compromise (list), vendor update "
                    "infrastructure blocked (domains/IPs, rule IDs), code-signing "
                    "certificate revocation status."
                ),
                "attack_techniques": ["T1195"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["isolate_host", "block_domain", "block_ip"],
            },
            {
                "step_number": 5,
                "title": "Rebuild compromised systems and verify software supply chain integrity",
                "description": (
                    "Rebuild systems with confirmed attacker activity from known-good images "
                    "rather than attempting in-place remediation — supply chain attacks "
                    "frequently install additional backdoors. Before redeploying any software "
                    "from the affected vendor, verify hash integrity of all downloaded "
                    "packages against official checksums. Review and harden the software "
                    "update/build pipeline to prevent recurrence."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Systems rebuilt (count, base image date, verification method), "
                    "vendor software re-deployed with integrity verification (package name, "
                    "version, verified hash), build pipeline security review findings, "
                    "dependency pinning and integrity checking controls implemented."
                ),
                "attack_techniques": ["T1195.002"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 240,
                "containment_actions": ["isolate_host", "notify_management"],
            },
            {
                "step_number": 6,
                "title": "Report to CISA and notify downstream consumers",
                "description": (
                    "Report the supply chain compromise to CISA — these incidents receive "
                    "elevated attention and CISA may issue a broader advisory to other "
                    "potentially affected organisations. If the organisation itself "
                    "distributes software or services that may have incorporated the "
                    "compromised component, notify downstream customers and partners. "
                    "Coordinate disclosure timing with the software vendor."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "CISA notification sent (ticket, timestamp), downstream consumer "
                    "notification plan (scope, method, timing), vendor coordination "
                    "status, public disclosure timeline agreed, incident report drafted."
                ),
                "attack_techniques": ["T1195"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["notify_management"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },

    {
        "name": "Data Exfiltration / Breach Response",
        "description": (
            "CISA / FBI Joint Advisory: Response to confirmed or suspected unauthorised "
            "data exfiltration. Covers data scope determination, exfiltration channel "
            "identification, containment, legal notification obligations, and evidence "
            "preservation for regulatory and law enforcement requirements."
        ),
        "trigger_conditions": [
            "exfiltration",
            "data breach",
            "data theft",
            "T1048",
            "T1567",
            "T1020",
            "T1041",
            "large outbound transfer",
            "data leak",
            "PII exposure",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Confirm exfiltration and identify the exfiltration channel",
                "description": (
                    "Verify that data exfiltration has occurred — distinguish from authorised "
                    "bulk transfers or backups. Identify the exfiltration channel: direct C2 "
                    "transfer (T1041), cloud storage staging (T1567 — Google Drive, OneDrive, "
                    "Dropbox), encrypted DNS (T1048.003), HTTPS to external host (T1048.002), "
                    "or removable media (T1052). Quantify the transfer volume and direction "
                    "from network flow data."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Exfiltration channel identified (protocol, destination IP/domain, cloud "
                    "service), transfer volume (bytes sent, connection count), source hosts "
                    "involved, transfer timestamps, network flow or proxy log evidence, "
                    "authorised transfer verification (ruled out normal backup/sync)."
                ),
                "attack_techniques": ["T1048", "T1041", "T1567"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Determine scope of data exfiltrated",
                "description": (
                    "Identify what data was accessed and transferred. Review file access "
                    "logs, DLP alerts, cloud storage audit logs, and staged file artefacts "
                    "to reconstruct the data set. Classify the data (PII, PHI, PCI, "
                    "classified, trade secret, credential stores) to determine regulatory "
                    "notification obligations and legal impact. Establish the access chain "
                    "— how the attacker accessed the data store."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Data repositories accessed (file shares, databases, cloud buckets, "
                    "email), estimated record count or file list, data classification "
                    "(PII/PHI/PCI/credentials/IP), access method (direct DB, file share, "
                    "cloud API, email export), notification obligations triggered "
                    "(HIPAA/GDPR/state breach law/federal reporting)."
                ),
                "attack_techniques": ["T1074", "T1213", "T1530"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence", "notify_management"],
            },
            {
                "step_number": 3,
                "title": "Block exfiltration destination and cut active exfiltration sessions",
                "description": (
                    "Immediately block the identified exfiltration destination(s) at the "
                    "network perimeter (firewall, web proxy, DNS resolver). Terminate any "
                    "active sessions exfiltrating data. If cloud storage was used as staging "
                    "(T1567), work with the cloud provider's abuse team to restrict or "
                    "remove the staged data. Block removable media ports via policy if "
                    "physical exfiltration was detected."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Exfiltration destinations blocked (IPs, domains, cloud service endpoints, "
                    "rule IDs, timestamp), active sessions terminated (source host, session "
                    "count), cloud provider notified (provider, ticket number), removable "
                    "media policy applied, post-block traffic confirmed ceased."
                ),
                "attack_techniques": ["T1048", "T1567"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["block_ip", "block_domain", "isolate_host"],
            },
            {
                "step_number": 4,
                "title": "Preserve forensic evidence for legal and regulatory purposes",
                "description": (
                    "Preserve all evidence in a forensically sound manner for regulatory "
                    "investigation and potential law enforcement referral. Capture: network "
                    "flow logs, proxy logs, DLP alerts, file access audit logs, authentication "
                    "records, and disk images from compromised systems. Implement legal hold "
                    "on relevant log sources and notify legal counsel to preserve the "
                    "attorney-client privilege on investigation communications."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Evidence preserved (log types, retention extended, legal hold applied), "
                    "disk images acquired (systems, acquisition method, chain of custody), "
                    "legal hold notification sent (timestamp, custodians notified), "
                    "law enforcement referral decision documented."
                ),
                "attack_techniques": ["T1020", "T1048"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence", "notify_legal"],
            },
            {
                "step_number": 5,
                "title": "Notify CISA, legal counsel, and affected data subjects",
                "description": (
                    "Federal agencies must notify CISA of a confirmed data breach. Engage "
                    "legal counsel immediately to determine notification obligations under "
                    "applicable regulations: HIPAA (60 days for covered entities), GDPR "
                    "(72 hours for EU data subjects), state breach notification laws (varies), "
                    "and sector-specific requirements (FISMA, PCI DSS). Notify affected "
                    "individuals and any required regulators within mandated timeframes. "
                    "Do not suppress breach notifications."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "CISA notification sent (ticket, timestamp), legal counsel engaged "
                    "(name, timestamp), applicable notification regulations identified, "
                    "notification deadlines for each regulation, affected individual "
                    "notification plan (method, timeline, draft), regulator notifications "
                    "filed (regulator, filing timestamp, confirmation number)."
                ),
                "attack_techniques": ["T1048"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["notify_management", "notify_legal"],
            },
            {
                "step_number": 6,
                "title": "Identify and eradicate the access vector that enabled exfiltration",
                "description": (
                    "Determine the full attack chain that led to the exfiltration — initial "
                    "access, privilege escalation, lateral movement to the data store, and "
                    "staging. Eradicate all attacker footholds: remove malware, revoke "
                    "compromised credentials, close the initial access vector (patch "
                    "vulnerability, disable compromised account, remove malicious OAuth app). "
                    "Verify eradication is complete before ending containment."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Full attack chain documented (initial access → privilege escalation → "
                    "lateral movement → data access → exfiltration), all footholds removed "
                    "(method per foothold type), initial access vector closed (patch/account "
                    "disable/OAuth revoke), eradication verification method."
                ),
                "attack_techniques": ["T1078", "T1048"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 120,
                "containment_actions": ["reset_credentials", "notify_management"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },

    {
        "name": "Web Application Attack Response",
        "description": (
            "CISA Web Application Security Program: Response to web application attacks "
            "including SQL injection, command injection, cross-site scripting, file "
            "inclusion, and server-side template injection. Covers evidence collection "
            "from web server and WAF logs, attacker scope determination, vulnerability "
            "remediation, and web shell detection."
        ),
        "trigger_conditions": [
            "web application attack",
            "SQL injection",
            "SQLi",
            "command injection",
            "web shell",
            "T1505.003",
            "T1059.007",
            "T1190",
            "T1055.001",
            "file inclusion",
            "SSRF",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Collect and preserve web server, WAF, and application logs",
                "description": (
                    "Immediately archive web server access logs (Apache/Nginx/IIS), WAF "
                    "logs, application error logs, and database query logs for the affected "
                    "time window. Rotate logs to a separate secure location to prevent "
                    "attacker log tampering. Identify the attack timeline from the first "
                    "exploit attempt to the most recent activity, and determine the "
                    "source IP(s) or Tor exit nodes used."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Log sources collected (web server, WAF, application, database), "
                    "log archive path and hash, attack timeline (first/last observed), "
                    "attacker source IPs, user agents, request patterns (URI, method, "
                    "payload strings), WAF blocks vs bypasses observed."
                ),
                "attack_techniques": ["T1190", "T1059.007"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Determine attack type and whether exploitation was successful",
                "description": (
                    "Analyse the collected logs to determine the specific attack technique "
                    "and whether it successfully exploited the application. For SQLi: look "
                    "for error-based, blind, or time-based injection patterns and check "
                    "database query logs for unauthorised data access. For RCE/command "
                    "injection: check for OS command execution in application logs. For "
                    "file inclusion: check for remote file fetches or LFI path traversal. "
                    "Determine if a web shell was successfully uploaded (T1505.003)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Attack type confirmed (SQLi/RCE/LFI/RFI/XSS/SSRF/web shell), "
                    "exploitation successful (yes/no, evidence), data accessed or extracted "
                    "(tables, records, files), OS commands executed (if RCE), web shell "
                    "uploaded (path, hash, content snippet if found)."
                ),
                "attack_techniques": ["T1190", "T1505.003", "T1059.007"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Hunt for and remove web shells and persistent backdoors",
                "description": (
                    "Scan the web server file system for web shells and unauthorised file "
                    "modifications. Use file integrity monitoring comparison, hash scanning "
                    "against known web shell signatures (PHP/JSP/ASPX shells), and review "
                    "recently modified files in the web root. Check application logs for "
                    "POST requests to unusual file paths. Remove any discovered web shells "
                    "and preserve copies for analysis."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "File integrity scan method and scope, web shells found (path, hash, "
                    "creation timestamp, content type), recently modified files list, "
                    "suspicious POST requests to static paths, web shells removed (method, "
                    "timestamp, forensic copy preserved)."
                ),
                "attack_techniques": ["T1505.003"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["isolate_host", "preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Block attacker IPs and deploy WAF rules for the exploit pattern",
                "description": (
                    "Block identified attacker source IPs at the WAF and perimeter firewall. "
                    "Deploy WAF virtual patching rules targeting the specific exploit pattern "
                    "(SQL injection keywords, command injection characters, LFI path "
                    "traversal patterns, SSRF block lists). This provides immediate "
                    "protection while the underlying vulnerability is remediated. "
                    "Monitor for bypass attempts using different payloads or source IPs."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Attacker IPs blocked (IP list, rule IDs, timestamp), WAF rules deployed "
                    "(rule name/ID, pattern, mode — block vs detect), bypass attempts observed "
                    "post-block (yes/no), false positive rate of WAF rules (legitimate traffic "
                    "blocked — verification required)."
                ),
                "attack_techniques": ["T1190"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["block_ip"],
            },
            {
                "step_number": 5,
                "title": "Remediate the vulnerable application code or configuration",
                "description": (
                    "Engage the development team to remediate the root cause vulnerability "
                    "in the application code: parameterised queries for SQLi, input validation "
                    "and output encoding for XSS, allowlist validation for file inclusion, "
                    "SSRF protection via allowlist of permitted destinations. Deploy the fix "
                    "through the standard change management process with expedited approval "
                    "given the active exploitation context."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Root cause vulnerability (CWE ID, description), remediation implemented "
                    "(code change description, PR/commit reference), deployment method and "
                    "timestamp, post-fix regression testing completed (yes/no), WAF virtual "
                    "patch retained as defence-in-depth (yes/no)."
                ),
                "attack_techniques": ["T1190"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 120,
                "containment_actions": ["patch_system", "notify_management"],
            },
            {
                "step_number": 6,
                "title": "Assess data exposure and determine breach notification requirements",
                "description": (
                    "Determine whether the attack resulted in unauthorised data access "
                    "or exfiltration. If SQLi was successful, review database query logs "
                    "for SELECT statements against sensitive tables. Classify any exposed "
                    "data and determine breach notification obligations. If exploitation "
                    "confirmed, escalate to the Data Exfiltration playbook for full "
                    "breach response."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Data exposure assessment (tables/records accessed, data classification), "
                    "notification obligations identified (yes/no, applicable regulations), "
                    "escalation to data breach playbook (yes/no), CISA notification sent "
                    "(if applicable, ticket number)."
                ),
                "attack_techniques": ["T1190", "T1048"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["notify_management", "notify_legal"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },

    {
        "name": "Insider Threat Response",
        "description": (
            "CISA Insider Threat Mitigation Guide (2020): Response to suspected or "
            "confirmed insider threat activity including data theft by employees, "
            "contractors, or privileged users. Covers activity corroboration, HR and "
            "legal coordination, account suspension, forensic preservation, and "
            "disciplinary/legal referral process."
        ),
        "trigger_conditions": [
            "insider threat",
            "insider",
            "privileged abuse",
            "employee data theft",
            "T1052",
            "T1074.001",
            "T1537",
            "abnormal data access",
            "disgruntled employee",
            "termination risk",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Corroborate the indicator with multiple data sources before action",
                "description": (
                    "Insider threat investigations are highly sensitive — premature or "
                    "incorrect action can have severe legal and HR consequences. Before "
                    "any containment action, corroborate the suspicious indicator with "
                    "at least two independent data sources: DLP alerts, UEBA/anomaly "
                    "detection, access log review, email monitoring (if authorised), "
                    "physical access logs, and HR signals (termination notice, performance "
                    "issues, access request anomalies). Brief legal counsel immediately."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Primary indicator (DLP alert/UEBA/access log/report), corroborating "
                    "data sources (minimum 2, with specifics), subject's role and access "
                    "level, data sensitivity involved, HR signal correlation (if any), "
                    "legal counsel briefed (name, timestamp)."
                ),
                "attack_techniques": ["T1078", "T1074"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence", "notify_legal"],
            },
            {
                "step_number": 2,
                "title": "Quietly preserve forensic evidence before subject is alerted",
                "description": (
                    "Preserve forensic evidence covertly before the subject is aware of "
                    "the investigation — alerting the subject prematurely risks evidence "
                    "destruction. Silently collect: complete file access audit logs, email "
                    "records, authentication logs, DLP events, and a forensic image of "
                    "the subject's workstation (if authorised by legal counsel and HR). "
                    "Implement legal hold on all relevant data immediately."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Evidence collected (log types, date range, storage location, "
                    "chain of custody custodian), workstation image acquired (yes/no, "
                    "authorisation obtained, hash), legal hold implemented (custodians, "
                    "systems, timestamp), covert collection completed without alerting "
                    "subject (confirmed yes/no)."
                ),
                "attack_techniques": ["T1074", "T1052"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence", "notify_legal"],
            },
            {
                "step_number": 3,
                "title": "Scope the data accessed and removed",
                "description": (
                    "Determine the full scope of data accessed or exfiltrated by the "
                    "subject. Review file server access logs, DLP events, email records, "
                    "USB/removable media logs, cloud sync logs (OneDrive, Dropbox personal), "
                    "and print logs. Classify the data and quantify the exposure. Determine "
                    "whether the data constitutes trade secrets, PII, classified information, "
                    "or other regulated content."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Data repositories accessed (file shares, email, database, cloud), "
                    "files/records accessed or copied (count, classification), exfiltration "
                    "channel (USB/email/cloud/print), data classification of exposed content, "
                    "estimated business impact and regulatory notification implications."
                ),
                "attack_techniques": ["T1074.001", "T1052", "T1537"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 90,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Coordinate account suspension with HR and legal",
                "description": (
                    "Do not disable the subject's account without explicit coordination "
                    "with HR and legal counsel — the timing of account suspension must "
                    "align with the HR disciplinary or termination process to ensure "
                    "compliance with employment law. Once authorised, disable the subject's "
                    "accounts across all systems (AD, SaaS, VPN, cloud), revoke physical "
                    "access badges, and collect any company-issued devices."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "HR coordination confirmed (HR representative name, timestamp), "
                    "legal counsel authorisation obtained (yes/no), accounts disabled "
                    "(systems, timestamp, performed by), physical access revoked "
                    "(badge deactivated, timestamp), devices collected (serial numbers)."
                ),
                "attack_techniques": ["T1078"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["disable_account", "revoke_access", "notify_management"],
            },
            {
                "step_number": 5,
                "title": "Refer to legal / law enforcement if criminal activity is suspected",
                "description": (
                    "If the insider threat activity constitutes a crime (theft of trade "
                    "secrets, Computer Fraud and Abuse Act violation, financial fraud, "
                    "regulatory violation), legal counsel must determine whether to refer "
                    "to law enforcement (FBI for federal matters, local police for criminal "
                    "matters). Preserve the full chain of custody for any evidence that "
                    "may be used in civil or criminal proceedings. Do not destroy any "
                    "evidence pending legal guidance."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Criminal activity type suspected (CFAA/trade secret theft/fraud/other), "
                    "law enforcement referral decision (yes/no, agency, report number), "
                    "chain of custody maintained (confirmed by legal counsel), "
                    "civil action consideration (legal hold status), "
                    "CISA notification sent if federal data involved."
                ),
                "attack_techniques": ["T1074", "T1052"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["notify_legal", "notify_management"],
            },
            {
                "step_number": 6,
                "title": "Remediate access gaps and strengthen preventive controls",
                "description": (
                    "After containment, review and remediate the access control gaps that "
                    "enabled the insider threat: excessive data access (principle of least "
                    "privilege violations), lack of DLP coverage on sensitive repositories, "
                    "missing UEBA baselines, absent USB/removable media controls. "
                    "Implement recommended CISA insider threat programme controls: "
                    "centralised logging, user activity monitoring (with consent/policy), "
                    "and a formal insider threat working group."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Access control gaps identified (over-privileged accounts, unmonitored "
                    "data stores), remediation actions taken (least privilege enforced, "
                    "DLP rules added, UEBA tuned), USB/media controls status, "
                    "insider threat programme improvements documented."
                ),
                "attack_techniques": ["T1078", "T1052"],
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
        "name": "Cloud Account Compromise Response",
        "description": (
            "CISA SCuBA / Cloud Security Technical Reference Architecture: Response to "
            "compromise of cloud-hosted accounts and workloads (IaaS/PaaS/SaaS). Covers "
            "IAM investigation, cloud-specific persistence mechanisms, resource abuse "
            "detection, and recovery across AWS, Azure, GCP, and M365 environments."
        ),
        "trigger_conditions": [
            "cloud compromise",
            "cloud account",
            "T1078.004",
            "T1530",
            "T1619",
            "T1537",
            "IAM abuse",
            "cloud storage exfiltration",
            "Azure AD compromise",
            "AWS root account",
            "service principal abuse",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Identify the compromised cloud identity and initial access vector",
                "description": (
                    "Determine which cloud identity (IAM user, service principal, managed "
                    "identity, OAuth application) was compromised and the initial access "
                    "vector: phishing for cloud credentials, API key exposure in public "
                    "repository, compromised CI/CD pipeline credential, SaaS OAuth phishing, "
                    "or exploitation of a misconfigured cloud resource. Review cloud-provider "
                    "audit logs (AWS CloudTrail, Azure Activity Log, GCP Cloud Audit Logs, "
                    "M365 Unified Audit Log)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Compromised identity (user/service principal/API key), cloud provider "
                    "and affected tenants, initial access vector, earliest malicious API "
                    "call timestamp, source IP and geolocation of anomalous calls, "
                    "API key or credential exposed in public repo (yes/no, repo URL)."
                ),
                "attack_techniques": ["T1078.004", "T1528"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Audit all API actions taken under the compromised identity",
                "description": (
                    "Enumerate all actions performed under the compromised identity from "
                    "the earliest malicious activity timestamp. Focus on high-impact "
                    "cloud actions: IAM role/policy modifications, new user/key creation, "
                    "privilege escalation (assuming higher-privileged roles), data access "
                    "or exfiltration from cloud storage buckets (T1530), resource creation "
                    "(EC2/VMs for crypto mining), secrets manager access, and cross-account "
                    "trust modifications."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Audit log time window analysed, IAM changes made (new users/roles/keys "
                    "created, policy modifications), cloud storage access (buckets/blobs "
                    "accessed, data volume), resource provisioning (VMs, Lambda, containers), "
                    "secrets accessed, cross-account trust changes, total API call count."
                ),
                "attack_techniques": ["T1078.004", "T1530", "T1619"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Revoke the compromised credential and all attacker-created identities",
                "description": (
                    "Immediately invalidate the compromised credential: rotate API keys, "
                    "disable service principal, revoke OAuth tokens, invalidate session "
                    "tokens, or disable the IAM user. Remove all attacker-created identities "
                    "(new IAM users, service principals, access keys, OAuth app registrations). "
                    "Rotate KRBTGT equivalent for cloud identity (Azure AD: revoke all "
                    "refresh tokens org-wide if admin compromise is suspected)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Compromised credential revoked (method, timestamp), attacker-created "
                    "identities removed (count and type: IAM users/service principals/API "
                    "keys/OAuth apps), session tokens invalidated (scope), org-wide token "
                    "revocation performed (yes/no, justification)."
                ),
                "attack_techniques": ["T1078.004"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["reset_credentials", "revoke_access"],
            },
            {
                "step_number": 4,
                "title": "Identify and remove attacker-deployed cloud resources and backdoors",
                "description": (
                    "Survey the cloud environment for attacker-deployed resources: new "
                    "virtual machines (crypto mining), Lambda/serverless functions (C2 relay), "
                    "container workloads, storage buckets with external sharing, new VPC "
                    "peerings or firewall rules opening inbound access, and IAM trust "
                    "relationships with attacker-controlled accounts. Remove all unauthorised "
                    "resources and document for cost recovery purposes."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Unauthorised resources discovered (type, region, creation time, "
                    "attacker-controlled identity used), resources terminated/removed "
                    "(count by type), network configuration changes reverted (firewall "
                    "rules, VPC peerings, security groups), estimated cost of attacker "
                    "resource usage."
                ),
                "attack_techniques": ["T1578", "T1537", "T1619"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["isolate_host", "revoke_access"],
            },
            {
                "step_number": 5,
                "title": "Assess data exposure from cloud storage and SaaS services",
                "description": (
                    "Determine whether cloud-hosted data was accessed or exfiltrated. "
                    "Review S3/Blob/GCS access logs for object-level reads by the compromised "
                    "identity, M365 audit logs for mail/SharePoint/OneDrive access, SaaS "
                    "application audit logs. Identify buckets or shares with public access "
                    "misconfiguration that may have been exploited. Determine breach "
                    "notification obligations based on data classification."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Cloud storage objects accessed (bucket/container, object count, "
                    "estimated data volume), SaaS data accessed (M365/Salesforce/Workday), "
                    "public access misconfigurations found (bucket/share, exposure period), "
                    "data classification of exposed content, breach notification obligations "
                    "triggered (regulation, deadline)."
                ),
                "attack_techniques": ["T1530", "T1213"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence", "notify_legal"],
            },
            {
                "step_number": 6,
                "title": "Harden cloud IAM posture and report to CISA",
                "description": (
                    "After containment, apply CISA SCuBA hardening recommendations: enforce "
                    "MFA for all privileged cloud identities, remove long-lived API keys in "
                    "favour of short-lived credentials (IAM roles, managed identities), "
                    "enable CloudTrail/Audit Logging in all regions, restrict public cloud "
                    "storage access, and implement AWS GuardDuty / Azure Defender / GCP "
                    "Security Command Center. Report the incident to CISA per federal "
                    "reporting requirements."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "MFA enforcement status (privileged identities covered), long-lived "
                    "API keys removed (count), audit logging enabled across all regions "
                    "(coverage), public storage access reviewed and remediated, cloud "
                    "threat detection services enabled, CISA notification sent "
                    "(ticket, timestamp)."
                ),
                "attack_techniques": ["T1078.004"],
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

    # -------------------------------------------------------------------------
    # Phase 46 tranche 2 — 8 additional high-value playbooks
    # -------------------------------------------------------------------------

    {
        "name": "ICS / OT Intrusion Response",
        "description": (
            "CISA ICS-CERT AA22-103A: Response to intrusions targeting Industrial Control "
            "Systems (ICS), Operational Technology (OT), SCADA systems, PLCs, and HMIs. "
            "Follows CISA/NIST ICS security guidance with emphasis on safe operational "
            "state before digital forensics — physical safety takes absolute precedence "
            "over cyber investigation in OT environments."
        ),
        "trigger_conditions": [
            "ICS",
            "OT",
            "SCADA",
            "PLC",
            "HMI",
            "T0826",
            "T0878",
            "T0831",
            "T0836",
            "industrial control",
            "operational technology",
            "historian",
            "Modbus",
            "DNP3",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Establish safe operational state — physical safety first",
                "description": (
                    "Before any cyber investigation, coordinate with operations engineering "
                    "to verify the physical process is in a safe and stable state. In ICS/OT "
                    "environments, cyber response actions (isolating hosts, blocking network "
                    "traffic, shutting down systems) can cause physical harm, equipment "
                    "damage, or hazardous conditions. Engage the plant/facility manager and "
                    "safety officer immediately. Do not isolate OT systems without explicit "
                    "engineering sign-off that the physical process is safe to do so."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Physical process status (stable/degraded/emergency), plant manager "
                    "notified (name, timestamp), safety officer sign-off obtained, "
                    "operations engineering team engaged (names), current control mode "
                    "(automatic/manual/emergency), any safety system activations observed."
                ),
                "attack_techniques": ["T0826", "T0878"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 15,
                "containment_actions": ["preserve_evidence", "notify_management"],
            },
            {
                "step_number": 2,
                "title": "Identify the compromised IT/OT network boundary and intrusion path",
                "description": (
                    "Determine how the attacker crossed the IT/OT network boundary. Most ICS "
                    "intrusions originate in IT and pivot to OT through jump servers, "
                    "historian connections, or remote access (VPN, RDP) to the OT DMZ. "
                    "Review firewall logs at the IT/OT boundary, historian server activity, "
                    "and remote access logs. Identify the initial IT foothold before the "
                    "OT pivot — this determines the full scope of the breach."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "IT/OT boundary crossing method (firewall logs, jump server access, "
                    "historian connection), IT initial foothold (hostname, user, timestamp), "
                    "OT systems accessed (engineering workstation, HMI, historian, PLC), "
                    "remote access sessions to OT DMZ (source IPs, duration), "
                    "Purdue model level of deepest penetration (L1/L2/L3)."
                ),
                "attack_techniques": ["T0886", "T0822", "T0859"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Collect engineering workstation and HMI artefacts passively",
                "description": (
                    "Collect forensic artefacts from OT systems passively — avoid active "
                    "scanning or aggressive forensic tools that may cause unexpected process "
                    "behaviour. Gather: Windows Event Logs from engineering workstations "
                    "and HMIs, ICS application logs (Wonderware, IgnitionScada, FactoryTalk), "
                    "network captures from the OT network switch, PLC audit logs if available, "
                    "and historian query logs. Preserve original artefacts before any remediation."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Engineering workstation logs collected (hostnames, log types, time window), "
                    "HMI application logs collected, ICS software audit logs (application, "
                    "version, log path), network capture collected (switch, duration, size), "
                    "PLC audit logs available (yes/no, model, log retention period)."
                ),
                "attack_techniques": ["T0801", "T0845"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Determine attacker intent: reconnaissance vs active manipulation",
                "description": (
                    "Assess whether the attacker was conducting passive reconnaissance "
                    "(reading sensor values, mapping the network, downloading PLC ladder logic) "
                    "or actively manipulating control processes (modifying setpoints, "
                    "issuing unauthorised commands to PLCs, disabling safety instrumented "
                    "systems). Active manipulation constitutes a Critical Infrastructure "
                    "attack requiring immediate CISA notification and potential CISA ICS-CERT "
                    "on-site response team request."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Attacker activity type (reconnaissance/active manipulation), ICS commands "
                    "or program uploads observed (yes/no, details), safety system interactions "
                    "(safety PLC accessed, SIS bypassed), setpoint or configuration changes "
                    "detected, physical process anomalies correlated to attacker activity."
                ),
                "attack_techniques": ["T0836", "T0855", "T0831"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence", "notify_management"],
            },
            {
                "step_number": 5,
                "title": "Isolate compromised OT segments with engineering approval",
                "description": (
                    "With explicit engineering sign-off, isolate compromised OT network "
                    "segments by blocking traffic at the IT/OT firewall and disabling "
                    "compromised remote access. Transition affected processes to manual "
                    "control before network isolation. Do not power-cycle PLCs or HMIs "
                    "without engineering authorisation — many ICS devices have non-volatile "
                    "memory that retains attacker-modified logic after reboot."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Engineering authorisation for isolation obtained (engineer name, "
                    "timestamp), OT segments isolated (network ranges, isolation method), "
                    "processes transitioned to manual control (process names, operator names), "
                    "remote access disabled (method, timestamp), production impact documented."
                ),
                "attack_techniques": ["T0826"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["isolate_host", "engage_ir_team"],
            },
            {
                "step_number": 6,
                "title": "Notify CISA ICS-CERT and request on-site support if needed",
                "description": (
                    "ICS/OT incidents against critical infrastructure require immediate "
                    "notification to CISA ICS-CERT (ics-cert@hq.dhs.gov, 1-888-282-0870). "
                    "CISA can deploy a Hunt and Incident Response team (HIRT) on-site to "
                    "assist with OT-specific forensics. Notify sector-specific regulators "
                    "(NERC CIP for energy, NRC for nuclear, TSA for pipeline/rail). "
                    "Preserve all evidence — do not restore modified PLC programs before "
                    "CISA HIRT reviews them."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "CISA ICS-CERT notification sent (ticket, timestamp, HIRT requested yes/no), "
                    "sector regulator notified (agency, timestamp, requirement basis), "
                    "PLC program backups preserved (before/after comparison available), "
                    "CISA HIRT engagement status, law enforcement notification (FBI, if applicable)."
                ),
                "attack_techniques": ["T0826", "T0878"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["notify_management", "engage_ir_team"],
            },
            {
                "step_number": 7,
                "title": "Verify PLC/HMI program integrity before restoring to automatic control",
                "description": (
                    "Before returning any OT system to automatic control, verify the "
                    "integrity of all PLC programs, HMI configurations, and safety system "
                    "logic. Compare current PLC ladder logic against a known-good backup "
                    "(pre-incident version-controlled copy). Have a qualified control "
                    "systems engineer review all configurations. Test in simulation or "
                    "manual mode before enabling automatic control. Document the validation "
                    "for regulatory compliance."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "PLC programs compared against baseline (PLCs verified, engineer name, "
                    "comparison method), modifications found (yes/no, description if found), "
                    "HMI configurations verified, safety system logic integrity confirmed, "
                    "test/simulation validation completed, engineering sign-off for return "
                    "to automatic control (engineer, timestamp)."
                ),
                "attack_techniques": ["T0836", "T0831"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 120,
                "containment_actions": ["notify_management"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },

    {
        "name": "Active Directory Full Compromise Response",
        "description": (
            "NSA/CISA Advisory AA22-011A: Response to full Active Directory compromise "
            "including Golden Ticket / Silver Ticket attacks, DCSync credential dumping, "
            "KRBTGT abuse, and domain controller backdooring. Covers the specialised "
            "recovery steps required when domain-level trust is broken, including the "
            "mandatory double KRBTGT rotation and forest recovery procedures."
        ),
        "trigger_conditions": [
            "golden ticket",
            "silver ticket",
            "DCSync",
            "KRBTGT",
            "T1558.001",
            "T1003.006",
            "domain controller compromise",
            "pass the ticket",
            "skeleton key",
            "AD forest compromise",
            "T1207",
            "Mimikatz lsadump",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Confirm the scope: is this a domain-level or forest-level compromise?",
                "description": (
                    "Determine whether the compromise is limited to a single domain or "
                    "extends to the entire AD forest. Forest-level compromise (e.g., "
                    "Enterprise Admin access, Schema Admin abuse, forest trust exploitation) "
                    "requires a complete forest recovery — a significantly more disruptive "
                    "procedure. Review event logs on all domain controllers for DCSync "
                    "activity (Event ID 4662 with GetChangesAll right), Golden Ticket use "
                    "(anomalous TGT lifetimes, Event ID 4768 with unusual encryption types), "
                    "and newly created privileged accounts."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Compromise scope (single domain / multiple domains / full forest), "
                    "DCSync events found (Event 4662, source account, destination DC, "
                    "timestamp), Golden Ticket indicators (Event 4768 anomalies, "
                    "TGT lifetime > 10 hours, RC4 encryption with AES-capable DC), "
                    "Enterprise/Schema Admin accounts accessed, new privileged accounts created."
                ),
                "attack_techniques": ["T1003.006", "T1558.001"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Identify all attacker-controlled accounts and persistence mechanisms",
                "description": (
                    "Enumerate every account the attacker controls or has modified. This "
                    "includes: accounts with password resets post-breach, new accounts "
                    "added to Domain Admins / Enterprise Admins / Schema Admins, AdminSDHolder "
                    "modifications, new Group Policy Objects (GPOs) with malicious settings, "
                    "new or modified AD replication (DCShadow - T1207), rogue domain "
                    "controllers added, and Skeleton Key malware installed on existing DCs."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "New privileged accounts (UPN, group membership, created-by, timestamp), "
                    "AdminSDHolder modifications (ACEs added), GPO changes (name, "
                    "modification timestamp, policy content), DCShadow indicators "
                    "(rogue DC registration), Skeleton Key indicators (LSASS modification "
                    "on DCs), new/modified replication agreements."
                ),
                "attack_techniques": ["T1136.002", "T1207", "T1098"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 90,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Isolate compromised domain controllers from the network",
                "description": (
                    "Isolate domain controllers confirmed to have Skeleton Key malware or "
                    "other attacker modifications. Use physical network disconnection or "
                    "hypervisor-level isolation (do not use EDR network isolation, which "
                    "the attacker may have disabled). Maintain at least one clean DC for "
                    "authentication continuity before isolation. Take a VM snapshot of "
                    "each isolated DC before any remediation."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Compromised DCs identified (hostname, evidence of compromise), "
                    "DCs isolated (method, timestamp), clean DCs maintained for auth "
                    "continuity (hostname, verified clean), VM snapshots taken "
                    "(DC hostname, snapshot ID, timestamp), AD replication status verified."
                ),
                "attack_techniques": ["T1207"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["isolate_host", "preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Perform mandatory double KRBTGT password rotation",
                "description": (
                    "Golden Tickets are forged using the KRBTGT account password hash. "
                    "A single KRBTGT reset is insufficient — the previous password is "
                    "retained for replication. Two resets are required (separated by the "
                    "maximum ticket lifetime, typically 10 hours, or both performed "
                    "consecutively and then waiting out existing Golden Tickets). "
                    "Per NSA/CISA AA22-011A: reset KRBTGT in each domain, wait the "
                    "maximum user ticket lifetime, then reset again."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "First KRBTGT reset performed (domain, timestamp, performed by), "
                    "wait period observed (hours elapsed or immediate second reset rationale), "
                    "second KRBTGT reset performed (domain, timestamp), all domains in "
                    "forest rotated (yes/no), existing Golden Tickets invalidated "
                    "(confirmed by monitoring for 4769 failures with old ticket), "
                    "AD replication confirmed successful post-rotation."
                ),
                "attack_techniques": ["T1558.001"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["reset_credentials"],
            },
            {
                "step_number": 5,
                "title": "Reset all Tier 0 and privileged account credentials",
                "description": (
                    "After KRBTGT rotation, reset credentials for all Tier 0 accounts "
                    "(Domain Admins, Enterprise Admins, Schema Admins, KRBTGT, built-in "
                    "Administrator, service accounts with DC access) and any account "
                    "identified as compromised. Use secure, out-of-band communication "
                    "for password reset coordination. For service accounts, update the "
                    "password in both AD and all dependent services/applications to "
                    "prevent service outages."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Tier 0 accounts reset (count, account names, timestamp), Domain "
                    "Admin accounts reset, service accounts reset (names, dependent "
                    "services updated), built-in Administrator renamed/disabled, "
                    "password complexity and length enforced (min chars, policy), "
                    "out-of-band reset channel used (not compromised email)."
                ),
                "attack_techniques": ["T1078.002"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 120,
                "containment_actions": ["reset_credentials", "notify_management"],
            },
            {
                "step_number": 6,
                "title": "Remove all attacker persistence: rogue accounts, GPOs, AdminSDHolder changes",
                "description": (
                    "Remove every attacker persistence mechanism identified in step 2: "
                    "delete attacker-created accounts, remove them from privileged groups, "
                    "restore AdminSDHolder ACL to baseline, delete or revert malicious GPOs, "
                    "remove DCShadow replication registrations, rebuild domain controllers "
                    "with confirmed Skeleton Key malware from clean images rather than "
                    "attempting in-place disinfection."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Attacker accounts deleted (count, names), group membership changes "
                    "reverted, AdminSDHolder ACL restored (baseline comparison confirmed), "
                    "malicious GPOs deleted or reverted, DCShadow replication "
                    "registrations removed, DCs rebuilt from clean images "
                    "(count, image date, verification method)."
                ),
                "attack_techniques": ["T1136.002", "T1207", "T1098"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 180,
                "containment_actions": ["isolate_host", "reset_credentials"],
            },
            {
                "step_number": 7,
                "title": "Implement AD tiering model and privileged access workstations",
                "description": (
                    "Post-eradication, implement structural controls to prevent recurrence. "
                    "NSA/CISA AA22-011A mandates: AD administrative tier model (Tier 0/1/2 "
                    "isolation), dedicated Privileged Access Workstations (PAWs) for DC "
                    "administration, removal of all internet access from Tier 0 systems, "
                    "Protected Users security group enrollment for all privileged accounts, "
                    "and enabling Windows Defender Credential Guard on all DCs and "
                    "admin workstations to prevent future LSASS dumping."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "AD tier model implemented (Tier 0/1/2 separation, GPOs applied), "
                    "PAWs deployed for Tier 0 admin (count), internet access blocked "
                    "from Tier 0 systems, Protected Users group enrollment (privileged "
                    "accounts enrolled), Credential Guard enabled (DCs and PAWs), "
                    "LAPS deployed for local admin password management."
                ),
                "attack_techniques": ["T1003.006", "T1558.001"],
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
        "name": "Cryptojacking / Resource Hijacking Response",
        "description": (
            "CISA/FBI Advisory AA23-046A: Response to unauthorised cryptocurrency mining "
            "on organisational infrastructure. Covers detection via performance anomalies "
            "and process analysis, miner removal, exploitation path identification, and "
            "cloud resource abuse containment. Cryptojacking often indicates a broader "
            "compromise — the mining payload is frequently a secondary objective."
        ),
        "trigger_conditions": [
            "cryptojacking",
            "cryptomining",
            "T1496",
            "coin miner",
            "XMRig",
            "Monero",
            "cryptocurrency",
            "high CPU",
            "resource hijacking",
            "mining pool",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Confirm cryptomining and identify affected hosts",
                "description": (
                    "Confirm the anomalous CPU/GPU usage is caused by a cryptocurrency miner "
                    "rather than a legitimate process or runaway workload. Identify all "
                    "affected hosts via: EDR process telemetry (XMRig, coin-miner variants, "
                    "PowerShell-based miners), sustained high CPU usage alerts (>80% for "
                    "extended periods), outbound connections to known mining pool IPs/domains, "
                    "and DNS queries for mining pool domains (*.minexmr.com, *.f2pool.com)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Miner process identified (name, path, SHA256, parent process), "
                    "affected hosts (count, hostnames), CPU/GPU utilisation observed, "
                    "mining pool connections (destination IPs/domains, protocol, port), "
                    "DNS queries to mining pools (timestamps), cryptocurrency wallet "
                    "address observed in miner config."
                ),
                "attack_techniques": ["T1496"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Identify the delivery and persistence mechanism",
                "description": (
                    "Determine how the miner was installed and how it persists. Cryptominers "
                    "are commonly delivered via: exploitation of public-facing applications "
                    "(T1190 — unpatched web servers, containers, Kubernetes), exposed Docker "
                    "APIs, compromised credentials for cloud management consoles, malicious "
                    "npm/PyPI packages in build pipelines (T1195.002), or as secondary "
                    "payloads from phishing campaigns. Identifying the delivery method "
                    "is critical — cryptojacking is often a canary indicating a more "
                    "serious compromise."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Delivery method identified (exploit/credential/supply chain/phishing), "
                    "persistence mechanism (scheduled task/cron/service/container entrypoint), "
                    "initial access vulnerability (CVE or misconfiguration), "
                    "other malicious activity on affected hosts beyond mining "
                    "(lateral movement/data access/backdoor), cloud resource abuse detected "
                    "(EC2/GCP/Azure VMs spun up)."
                ),
                "attack_techniques": ["T1190", "T1053", "T1543"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Block mining pool network destinations",
                "description": (
                    "Block all identified mining pool IPs, domains, and ports at the "
                    "firewall, DNS resolver, and web proxy. Stratum mining protocol "
                    "typically uses port 3333, 4444, 5555, 7777, or 443 (HTTPS to "
                    "bypass filtering). Deploy threat intelligence-based blocks of known "
                    "mining pool IP ranges. For cloud environments, restrict outbound "
                    "traffic to only necessary destinations via security group / VPC "
                    "firewall rules."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Mining pool IPs/domains blocked (list, rule IDs, timestamp), "
                    "stratum ports blocked (3333/4444/5555/7777), DNS block entries "
                    "(mining pool domains), proxy block entries, post-block connection "
                    "attempts observed (indicates hosts not yet remediated), "
                    "cloud outbound firewall rules applied."
                ),
                "attack_techniques": ["T1496"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["block_ip", "block_domain"],
            },
            {
                "step_number": 4,
                "title": "Terminate miner process, remove persistence, and patch delivery vector",
                "description": (
                    "Terminate the miner process on all affected hosts, remove the miner "
                    "binary and all associated files, and delete the persistence mechanism "
                    "(scheduled task, cron job, service, init script, or container "
                    "entrypoint). Patch the vulnerability or misconfiguration used for "
                    "initial access. For cloud environments, terminate all unauthorised VM "
                    "instances and revoke compromised API credentials. Verify remediation "
                    "by confirming CPU usage returns to baseline."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Miner processes terminated (host, PID, method), miner binaries removed "
                    "(paths, confirmed deleted), persistence mechanisms removed (type, name), "
                    "delivery vulnerability patched (CVE/misconfiguration, patch version), "
                    "CPU utilisation post-remediation (returned to baseline: yes/no), "
                    "cloud VMs terminated (count, region, estimated cost incurred)."
                ),
                "attack_techniques": ["T1496", "T1190"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["isolate_host", "patch_system"],
            },
            {
                "step_number": 5,
                "title": "Investigate for secondary payloads and broader compromise",
                "description": (
                    "Threat actors deploying cryptominers often install secondary backdoors, "
                    "credential stealers, or lateral movement tools alongside the miner. "
                    "Investigate all affected hosts for: additional malware beyond the "
                    "miner, credential dumping artefacts, lateral movement to other systems, "
                    "data access on file servers or databases, and any exfiltration. "
                    "Cryptojacking incidents that reveal broader compromise should escalate "
                    "to the Malware/Intrusion or Data Exfiltration playbooks."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Additional malware found (yes/no, names, paths), credential dumping "
                    "artefacts found (yes/no), lateral movement evidence (yes/no), "
                    "data access beyond miner activity (yes/no), escalation to secondary "
                    "playbook required (yes/no, playbook name), full scope assessment summary."
                ),
                "attack_techniques": ["T1496", "T1003", "T1021"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 6,
                "title": "Rebuild affected systems and harden against future abuse",
                "description": (
                    "Remove all miner software, scheduled tasks, startup persistence, and "
                    "cron jobs. Patch the vulnerability used for initial access. Harden "
                    "compute resources: enforce resource quotas, enable GPU/CPU utilisation "
                    "alerting, restrict outbound connections to mining pool ports (3333, 4444, "
                    "8888, 14444, 45560), and deploy cloud-specific compute anomaly "
                    "detection. Rotate any credentials or API keys accessible to the "
                    "compromised systems. Post-incident review within 5 business days."
                ),
                "requires_approval": False,
                "evidence_prompt": (
                    "All miner persistence mechanisms removed (yes/no), patch applied (CVE, "
                    "date), resource quotas enforced (yes/no), mining pool port blocks added "
                    "to firewall (yes/no), credentials rotated (yes/no), post-incident "
                    "review scheduled (date)."
                ),
                "attack_techniques": ["T1496", "T1053"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 480,
                "containment_actions": ["patch_system"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },

    {
        "name": "Destructive Wiper Response",
        "description": (
            "CISA/FBI Advisory AA23-061A / WhisperGate / HermeticWiper: Response to "
            "destructive malware designed to permanently destroy data and render systems "
            "unbootable. Distinguishes from ransomware by the absence of a ransom demand "
            "and the intent to cause operational disruption. Prioritises scope containment "
            "to prevent propagation and rapid shift to recovery operations."
        ),
        "trigger_conditions": [
            "wiper",
            "destructive malware",
            "T1485",
            "T1561",
            "T1529",
            "data destruction",
            "MBR wipe",
            "unbootable",
            "WhisperGate",
            "HermeticWiper",
            "NotPetya",
            "T1491",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Identify wiper malware family and confirm destructive intent",
                "description": (
                    "Confirm the malware is a wiper (destructive intent, no decryption key "
                    "offered) rather than ransomware. Collect the malware binary hash and "
                    "cross-reference with CISA advisories and threat intelligence — major "
                    "wiper families (WhisperGate, HermeticWiper, NotPetya, Shamoon, "
                    "CaddyWiper) have known signatures. Determine the wiper's destruction "
                    "method: MBR overwrite, volume shadow copy deletion, file overwrite, "
                    "or partition table corruption."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Wiper binary SHA256, family identification (TI lookup results), "
                    "destruction method (MBR/VSS/file overwrite/partition), "
                    "ransom demand present (yes/no — no demand confirms wiper), "
                    "systems already rendered unbootable (count), "
                    "first detection timestamp and patient-zero host."
                ),
                "attack_techniques": ["T1485", "T1561.002"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 15,
                "containment_actions": ["preserve_evidence", "notify_management"],
            },
            {
                "step_number": 2,
                "title": "Immediately isolate all affected hosts — speed is critical",
                "description": (
                    "Wiper malware propagates rapidly via SMB, WMI, and domain admin "
                    "credentials. Every minute of delay allows further destruction. "
                    "Immediately isolate all confirmed infected hosts. If the wiper has "
                    "domain admin credentials (common in nation-state wiper attacks), "
                    "disconnect the entire network from the internet and consider "
                    "isolating entire network segments. Speed of isolation takes "
                    "precedence over forensic evidence collection in a wiper scenario."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Hosts isolated (count, method, timestamp), internet connectivity "
                    "severed (yes/no, scope), network segments isolated (VLANs/subnets), "
                    "domain admin credentials suspected compromised (yes/no), "
                    "hosts actively being wiped at time of isolation (count), "
                    "propagation stopped (confirmed by monitoring)."
                ),
                "attack_techniques": ["T1485", "T1021.002"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 15,
                "containment_actions": ["isolate_host", "engage_ir_team"],
            },
            {
                "step_number": 3,
                "title": "Enumerate scope: all wiped, being wiped, and at-risk systems",
                "description": (
                    "Categorise all systems into three buckets: (1) already wiped — "
                    "confirm unbootable/destroyed, preserve for forensics if accessible; "
                    "(2) currently infected but not yet fully wiped — immediate isolation "
                    "priority; (3) at-risk but clean — assess whether they were reachable "
                    "by the wiper's propagation method and protect accordingly. "
                    "This triage drives recovery prioritisation."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Systems fully wiped (count, hostnames, system role/criticality), "
                    "systems infected but recoverable (count, status), "
                    "systems at-risk but clean (count, protective action taken), "
                    "critical systems affected (DCs, file servers, databases, ERP), "
                    "estimated total data loss, backup availability for wiped systems."
                ),
                "attack_techniques": ["T1485"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Notify CISA, executive leadership, and initiate crisis management",
                "description": (
                    "A destructive wiper attack is a significant cyber incident requiring "
                    "immediate executive escalation and CISA notification. Activate the "
                    "organisation's crisis management or business continuity plan. "
                    "CISA can deploy a HIRT team on-site within hours for major destructive "
                    "attacks. For attacks with nation-state attribution indicators, notify "
                    "FBI Cyber Division. Consider whether operational continuity requires "
                    "activating disaster recovery or fallback sites."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "CISA notification sent (ticket, timestamp, HIRT requested), "
                    "FBI notified (yes/no, case number if applicable), "
                    "crisis management plan activated (yes/no, plan name), "
                    "business continuity / DR plan activated (yes/no, DR site status), "
                    "executive leadership briefed (names, timestamp), "
                    "public communications plan (PR/comms team engaged)."
                ),
                "attack_techniques": ["T1485", "T1529"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["notify_management", "engage_ir_team"],
            },
            {
                "step_number": 5,
                "title": "Investigate initial access and lateral movement before the wiper triggered",
                "description": (
                    "Collect forensic evidence from any systems not yet wiped to reconstruct "
                    "the attack chain. Wiper attacks are typically the final stage of a "
                    "multi-week intrusion — the attacker established access, moved laterally, "
                    "and then triggered the wiper. Understanding the initial access vector "
                    "and the timeline is essential for remediation and for determining "
                    "whether data was exfiltrated before destruction."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Forensic collection from surviving systems (log types, retention available), "
                    "initial access vector identified (phishing/exploit/credential), "
                    "estimated dwell time before wiper triggered (days/weeks), "
                    "data exfiltration evidence (yes/no — wipers often precede leak extortion), "
                    "attacker tools found (lateral movement, C2, staging)."
                ),
                "attack_techniques": ["T1485", "T1074"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 120,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 6,
                "title": "Rebuild from clean backups — verify backup integrity before restore",
                "description": (
                    "Shift to recovery operations: rebuild wiped systems from the most "
                    "recent clean backups. Critically verify backup integrity before "
                    "restoration — sophisticated wiper attacks target backup systems "
                    "before triggering destruction. Rebuild domain controllers and "
                    "infrastructure first, then application servers, then end-user "
                    "systems. Scan restored systems before reconnecting to the network "
                    "to ensure the wiper or any secondary malware was not present "
                    "in the backup."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Backup systems verified clean (backup server, last backup date, "
                    "integrity check method), systems restored (count, backup date used, "
                    "restore method), pre-restore malware scan results (clean/infected), "
                    "recovery order followed (DCs → infra → apps → endpoints), "
                    "systems reconnected to network post-scan (count, timestamp)."
                ),
                "attack_techniques": ["T1490"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 480,
                "containment_actions": ["notify_management"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },

    {
        "name": "M365 Tenant Compromise Response",
        "description": (
            "Microsoft DART / CISA AA23-193A: Response to compromise of Microsoft 365 "
            "tenants including Exchange Online mail access, SharePoint/OneDrive data "
            "theft, Teams eavesdropping, and OAuth application abuse. Covers tenant-wide "
            "token revocation, conditional access hardening, unified audit log analysis, "
            "and mailbox forensics distinct from the general Cloud Account Compromise playbook."
        ),
        "trigger_conditions": [
            "M365 compromise",
            "Exchange Online",
            "Teams data access",
            "T1114.002",
            "T1087.004",
            "T1137",
            "SharePoint exfiltration",
            "OAuth app abuse",
            "Microsoft 365",
            "unified audit log",
            "mailbox rule forwarding",
            "O365",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Enable and review the M365 Unified Audit Log",
                "description": (
                    "Verify the M365 Unified Audit Log (UAL) is enabled — many organisations "
                    "have it disabled by default or on lower E3 licences. If disabled, "
                    "enable it immediately (90-day retention). Run audit log searches in "
                    "the Microsoft Purview compliance portal or via PowerShell "
                    "(Search-UnifiedAuditLog) for: MailboxLogin, FileAccessed, "
                    "FileDownloaded, AnonymousLinkCreated, AddedToGroup, "
                    "ConsentToApp, and New-InboxRule events across the investigation window."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "UAL enabled status (yes/no, enabled by whom), audit log retention "
                    "period (days), suspicious event types found (MailboxLogin anomalies, "
                    "file downloads, sharing link creation, app consent), "
                    "source IPs of anomalous activity, affected user accounts identified, "
                    "investigation time window used."
                ),
                "attack_techniques": ["T1114.002", "T1530"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Identify all malicious inbox rules and mail forwarding",
                "description": (
                    "Search for attacker-created inbox rules that forward, redirect, or "
                    "delete emails — a primary BEC persistence technique. Use "
                    "Get-InboxRule / Get-MailboxFolderStatistics via Exchange Online "
                    "PowerShell and audit log searches for New-InboxRule events. Also "
                    "check: SMTP forwarding addresses on mailboxes (Set-Mailbox "
                    "-ForwardingSmtpAddress), mail transport rules (Get-TransportRule), "
                    "and calendar sharing grants added post-compromise."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Malicious inbox rules found (rule name, forwarding address, "
                    "creation timestamp, created-by account), SMTP forwarding enabled "
                    "(mailboxes with external forwarding, destination address), "
                    "transport rules modified (name, condition, action), "
                    "calendar sharing grants added, all forwarding destinations identified."
                ),
                "attack_techniques": ["T1114.003", "T1137"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Audit OAuth application consents and service principal permissions",
                "description": (
                    "Attackers exploit M365 OAuth consent phishing to gain persistent access "
                    "via registered applications. Review: Enterprise Applications in Azure AD "
                    "for recently consented apps with Mail.Read, Files.ReadWrite, or "
                    "full_access_as_user permissions, user-consented vs admin-consented "
                    "applications, new service principals and their API permissions, "
                    "and app-only access tokens used outside of normal business applications."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "OAuth apps with suspicious permissions (app name, permissions, "
                    "consent type, consented-by, consent timestamp), apps with "
                    "Mail.Read/ReadWrite or Files access (list), new service principals "
                    "created post-breach (name, permissions, created-by), "
                    "app-only access token usage from unexpected IPs."
                ),
                "attack_techniques": ["T1528", "T1550.001"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Revoke all sessions, tokens, and malicious OAuth app consents",
                "description": (
                    "Revoke all active sessions for compromised accounts using Revoke-AzureADUserAllRefreshToken "
                    "or the Microsoft Purview portal. For tenant-wide admin compromise, "
                    "revoke all refresh tokens organisation-wide. Remove malicious OAuth "
                    "app consents (Enterprise Applications → Delete). Disable SMTP AUTH "
                    "for all mailboxes that don't require it (most modern mail clients "
                    "use modern auth). Re-enable Conditional Access policies if they were "
                    "modified or disabled."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Sessions revoked (scope — per-user or org-wide, timestamp), "
                    "malicious OAuth consents removed (app names, count), "
                    "SMTP AUTH disabled (scope, timestamp), Conditional Access policies "
                    "reviewed and restored (policies modified by attacker, if any), "
                    "MFA re-enrolled for all affected accounts."
                ),
                "attack_techniques": ["T1528", "T1114.002"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["reset_credentials", "revoke_access"],
            },
            {
                "step_number": 5,
                "title": "Determine email, SharePoint, and Teams data accessed",
                "description": (
                    "Quantify the data exposure: use UAL FileAccessed/FileDownloaded events "
                    "to identify SharePoint/OneDrive files accessed, email content accessed "
                    "via MailboxLogin and MailItemsAccessed events (E5 licence required for "
                    "MailItemsAccessed), Teams channel messages read, and any anonymous "
                    "sharing links created. Classify the exposed data and determine breach "
                    "notification obligations."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Emails accessed (accounts, volume, sensitive content identified), "
                    "SharePoint/OneDrive files accessed (count, site, classification), "
                    "Teams data accessed (channels, message content sensitivity), "
                    "anonymous sharing links created (URLs, target files, expiry), "
                    "data classification and notification obligations (GDPR/HIPAA/state law)."
                ),
                "attack_techniques": ["T1114.002", "T1530", "T1213"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence", "notify_legal"],
            },
            {
                "step_number": 6,
                "title": "Harden tenant: CISA SCuBA M365 baseline and report to CISA",
                "description": (
                    "Apply CISA SCuBA M365 hardening baseline: enable MFA for all accounts "
                    "via Conditional Access (not per-user MFA), block legacy authentication "
                    "protocols (SMTP AUTH, POP3, IMAP — primary phishing bypass vectors), "
                    "enable Microsoft Defender for Office 365 Safe Links/Attachments, "
                    "restrict user OAuth consent to verified publishers only, enable "
                    "mailbox audit logging (E3: 90 days, E5: MailItemsAccessed), and "
                    "report the incident to CISA."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "MFA via Conditional Access enforced (coverage %), legacy auth blocked "
                    "(protocols, policy name), Defender for O365 Safe Links/Attachments "
                    "enabled, user OAuth consent restricted to verified publishers, "
                    "mailbox audit logging enabled (retention period), "
                    "CISA notification sent (ticket, timestamp)."
                ),
                "attack_techniques": ["T1114.002"],
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
        "name": "APT / Long-Dwell Intrusion Response",
        "description": (
            "CISA Advisory AA22-320A / NSA guidance: Response to Advanced Persistent Threat "
            "intrusions characterised by long dwell times (weeks to months), low-and-slow "
            "reconnaissance, living-off-the-land techniques, and sophisticated evasion. "
            "Covers the specialised hunt methodology, careful evidence collection to avoid "
            "tipping off the attacker, and strategic eradication to prevent re-entry."
        ),
        "trigger_conditions": [
            "APT",
            "nation-state",
            "long dwell",
            "T1583",
            "T1586",
            "persistent access",
            "advanced persistent threat",
            "state-sponsored",
            "T1070",
            "log tampering",
            "strategic intelligence collection",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Establish a covert investigation — do not tip off the attacker",
                "description": (
                    "APT actors monitor their own access — premature containment actions "
                    "alert the attacker, who will destroy evidence and re-establish access "
                    "via pre-positioned backdoors. Conduct the initial investigation covertly: "
                    "do not block C2 IPs, do not reset compromised passwords, do not isolate "
                    "hosts until the full scope is understood. Limit knowledge of the "
                    "investigation to a small, trusted team. Use read-only log access "
                    "and passive monitoring only during this phase."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Investigation team members (cleared, need-to-know), covert investigation "
                    "mode confirmed (no containment actions taken), passive monitoring "
                    "deployed (network sensor, EDR read-only query), initial TTPs observed "
                    "(techniques, tools, C2 infrastructure), estimated dwell time based "
                    "on earliest attacker artefact found."
                ),
                "attack_techniques": ["T1071", "T1583"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 120,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Map the full intrusion: all footholds, C2 channels, and lateral movement",
                "description": (
                    "Before any eradication, map the complete attack infrastructure: every "
                    "compromised host, every backdoor/implant, every C2 channel, every "
                    "set of compromised credentials, and every lateral movement path. "
                    "APT actors typically maintain multiple redundant footholds. Eradicating "
                    "a subset while missing others means the attacker retains access. "
                    "Use threat intelligence to identify the full C2 infrastructure "
                    "(domain registrant patterns, certificate reuse, ASN clustering)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "All compromised hosts (list, role, implant type), all C2 channels "
                    "(IPs, domains, protocols, beacon intervals), all compromised credentials "
                    "(accounts, privilege level), lateral movement graph (source → destination "
                    "for each hop), all backdoor/persistence mechanisms per host, "
                    "TI-expanded C2 infrastructure (related IPs/domains via TI pivots)."
                ),
                "attack_techniques": ["T1071", "T1021", "T1078"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 240,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Determine data accessed and assess strategic intelligence loss",
                "description": (
                    "APT intrusions are primarily intelligence-collection operations. "
                    "Determine what data the attacker accessed and staged: sensitive "
                    "documents, email archives, intellectual property, personnel records, "
                    "strategic plans, or government/military information. Review file "
                    "staging artefacts (T1074), archive creation (T1560), large outbound "
                    "transfers, and cloud storage staging. The intelligence value of "
                    "stolen data determines the national security / business impact "
                    "and the notification requirements."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Data repositories accessed (file shares, email, database, SharePoint), "
                    "files staged or archived (staging directory, archive names, sizes), "
                    "exfiltration evidence (outbound transfer volume, destination IPs), "
                    "data classification of accessed content (sensitivity level), "
                    "estimated total data exfiltrated, strategic impact assessment."
                ),
                "attack_techniques": ["T1074", "T1560", "T1041"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 120,
                "containment_actions": ["preserve_evidence", "notify_management"],
            },
            {
                "step_number": 4,
                "title": "Coordinate with CISA and FBI before eradication",
                "description": (
                    "Before eradicating an APT actor, notify CISA and FBI — they may "
                    "have visibility into the broader campaign and can advise on the "
                    "optimal eradication timing and method. FBI may request the attacker "
                    "be monitored for a period for intelligence or law enforcement purposes. "
                    "CISA can provide technical assistance and share IOCs with other "
                    "potentially-affected organisations. Coordinate eradication timing "
                    "to a window where the organisation can monitor for re-entry attempts."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "CISA notified (ticket, timestamp, HIRT requested), FBI Cyber Division "
                    "notified (field office, agent name, case number), intelligence "
                    "community notification if applicable, eradication timing agreed "
                    "(date/window), monitoring plan for re-entry post-eradication, "
                    "IOCs shared with CISA for sector-wide advisory."
                ),
                "attack_techniques": ["T1071"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["notify_management", "engage_ir_team"],
            },
            {
                "step_number": 5,
                "title": "Simultaneous eradication of all footholds — no sequential patching",
                "description": (
                    "Execute eradication simultaneously across all identified footholds "
                    "in a coordinated 'D-Day' operation. Sequential eradication (fixing "
                    "one system at a time) alerts the attacker who will re-establish access "
                    "through remaining backdoors. Simultaneously: isolate all infected hosts, "
                    "reset all compromised credentials, block all C2 infrastructure at the "
                    "network level, remove all implants and persistence, and patch all "
                    "exploited vulnerabilities in a single maintenance window."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Eradication executed simultaneously (confirmed yes), all infected hosts "
                    "isolated (count, method, timestamp), all compromised credentials reset "
                    "(count, scope), all C2 blocked (IP/domain count), all implants removed "
                    "(host count, persistence types removed), all vulnerabilities patched, "
                    "post-eradication monitoring active (C2 block hit count, re-entry attempts)."
                ),
                "attack_techniques": ["T1071", "T1078", "T1053"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": [
                    "isolate_host", "reset_credentials", "block_ip", "block_domain",
                ],
            },
            {
                "step_number": 6,
                "title": "Monitor intensively for re-entry in the 30 days post-eradication",
                "description": (
                    "APT actors who lose access almost always attempt re-entry within 30 days "
                    "using: new phishing campaigns targeting the same organisation, exploitation "
                    "of related vulnerabilities, compromised third-party/supply chain access, "
                    "or pre-positioned access via a foothold missed in the initial eradication. "
                    "Deploy enhanced monitoring: full packet capture at the perimeter, "
                    "EDR alert thresholds lowered, threat hunting on attacker TTPs, "
                    "and review of all new remote access. Report any re-entry indicators "
                    "to CISA immediately."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Enhanced monitoring deployed (full PCAP, lowered EDR thresholds, "
                    "threat hunt schedule), re-entry indicators observed (yes/no — list "
                    "if yes), new phishing campaigns targeting org post-eradication, "
                    "30-day monitoring period completion date, lessons-learned report "
                    "submitted to CISA, structural improvements implemented to raise "
                    "cost of future intrusion."
                ),
                "attack_techniques": ["T1586", "T1566"],
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
        "name": "Wire Fraud / Business Payment Fraud Response",
        "description": (
            "FBI IC3 / FinCEN Advisory FIN-2019-A005: Response to business email compromise "
            "wire fraud, ACH redirect fraud, and vendor payment fraud. Covers the critical "
            "first-hour financial recovery window (SWIFT CARE, FinCEN RAPID), forensic "
            "documentation for law enforcement, and notification requirements distinct "
            "from the general Phishing/BEC playbook."
        ),
        "trigger_conditions": [
            "wire fraud",
            "ACH fraud",
            "payment fraud",
            "BEC wire transfer",
            "vendor impersonation",
            "CEO fraud",
            "invoice manipulation",
            "bank account change",
            "fraudulent wire",
            "FinCEN",
            # ATT&CK T-numbers for BEC / financial fraud techniques
            "T1566",    # Phishing (initial access vector)
            "T1566.002",  # Phishing: Spearphishing Link
            "T1534",    # Internal Spearphishing
            "T1586",    # Compromise Accounts
            "T1586.002",  # Compromise Accounts: Email Accounts
            "T1657",    # Financial Theft
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "IMMEDIATE: Contact sending bank to recall or freeze the wire",
                "description": (
                    "Wire fraud response is extremely time-sensitive — there is typically "
                    "a 24–72 hour window to recover funds before they are moved or "
                    "converted. Within the first hour: contact the sending financial "
                    "institution's wire operations team immediately, provide the transaction "
                    "details, and request a wire recall or a SWIFT gpi STOP/RETURN. "
                    "The bank can contact the beneficiary bank via SWIFT to freeze or "
                    "return the funds before the fraudsters move them."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Sending bank contacted (bank name, phone, contact name, timestamp), "
                    "wire transaction details (amount, date/time, sending account, "
                    "beneficiary bank, beneficiary account, SWIFT/reference number), "
                    "wire recall / SWIFT STOP requested (reference number, bank confirmation), "
                    "funds frozen at beneficiary bank (yes/no, confirmation number)."
                ),
                "attack_techniques": ["T1566", "T1534"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["notify_management", "notify_legal"],
            },
            {
                "step_number": 2,
                "title": "File FBI IC3 complaint and FinCEN RAPID report within 72 hours",
                "description": (
                    "File a complaint with the FBI Internet Crime Complaint Center (IC3.gov) "
                    "within 72 hours — IC3 operates the Financial Fraud Kill Chain (FFKC) "
                    "which can coordinate with financial institutions to freeze fraudulent "
                    "accounts. Simultaneously submit a FinCEN RAPID (Rapid Assistance to "
                    "Protect Institutions from Directed) report if a US financial institution "
                    "is involved. These reports significantly increase fund recovery "
                    "probability when filed promptly."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "FBI IC3 complaint filed (IC3 complaint number, timestamp), "
                    "FinCEN RAPID report submitted (FinCEN reference, timestamp), "
                    "local FBI field office notified (office, agent name, case number), "
                    "Secret Service notified if applicable (electronic crimes task force), "
                    "all transaction details provided in reports."
                ),
                "attack_techniques": ["T1566"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["notify_management", "notify_legal"],
            },
            {
                "step_number": 3,
                "title": "Identify the email compromise or social engineering vector",
                "description": (
                    "Determine how the attacker manipulated the payment: email account "
                    "compromise (victim's or vendor's email was hacked), email spoofing "
                    "(attacker spoofed a vendor or executive domain), phone social engineering "
                    "(voice call impersonating vendor or bank), or insider manipulation. "
                    "Collect the fraudulent email chain, payment change instructions, "
                    "phone call logs, and any vendor portal access. This determines "
                    "the scope — whether it is an isolated incident or part of a "
                    "broader BEC campaign."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Attack vector (compromised email/spoofing/phone/insider), fraudulent "
                    "email chain preserved (headers, sending IP, return-path), "
                    "impersonated party (vendor name, executive name), "
                    "phone call logs if applicable (number, timestamp), "
                    "vendor portal access logs, any other payments at risk."
                ),
                "attack_techniques": ["T1566", "T1534"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Secure all financial accounts and verify pending payments",
                "description": (
                    "Immediately review all pending outbound payments, wire transfers, and "
                    "ACH batches for additional fraudulent transactions. Place a temporary "
                    "hold on outbound payments pending manual verification via out-of-band "
                    "callback to known-good phone numbers. Notify the finance team and AP "
                    "department. If email accounts were compromised, reset credentials per "
                    "the Credential Compromise playbook. Update bank account change "
                    "procedures to require dual approval and out-of-band verification."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Pending payments reviewed (count, total value), additional fraudulent "
                    "payments identified (count, amounts), payment hold implemented "
                    "(scope, duration), finance team notified (names, timestamp), "
                    "email credentials reset if compromised, bank account change verification "
                    "procedures updated."
                ),
                "attack_techniques": ["T1534"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["reset_credentials", "notify_management"],
            },
            {
                "step_number": 5,
                "title": "Notify insurance, legal counsel, and document financial loss",
                "description": (
                    "Notify cyber insurance carrier immediately — many policies have reporting "
                    "deadlines and wire fraud coverage varies by policy. Engage legal counsel "
                    "to advise on civil recovery options (court order to freeze beneficiary "
                    "account, civil litigation against the bank if they failed to follow "
                    "security procedures). Document the complete financial loss for insurance "
                    "claims and regulatory reporting. Notify the board if the loss exceeds "
                    "materiality thresholds."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Insurance carrier notified (carrier name, policy number, claim number, "
                    "timestamp), legal counsel engaged (firm, attorney, timestamp), "
                    "total financial loss documented (amounts, currencies, recovery status), "
                    "insurance coverage determination (covered/excluded/pending review), "
                    "board notification if material loss, regulatory reporting obligations "
                    "(SEC 8-K, bank regulator SAR if applicable)."
                ),
                "attack_techniques": ["T1566"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["notify_legal", "notify_management"],
            },
            {
                "step_number": 6,
                "title": "Post-Incident Review and Anti-Fraud Process Hardening",
                "description": (
                    "Conduct a post-incident review to assess process and control failures "
                    "that enabled the fraud. Harden payment processes: implement mandatory "
                    "dual-approval for all wire transfers, out-of-band callback verification "
                    "to registered numbers before processing bank account changes, and "
                    "DMARC/DKIM/SPF enforcement to reduce email spoofing risk. Deliver "
                    "targeted anti-BEC awareness training to finance and AP staff. "
                    "Review vendor onboarding and bank detail change procedures."
                ),
                "requires_approval": False,
                "evidence_prompt": (
                    "Post-incident review completed (date, participants), dual-approval "
                    "payment controls implemented (yes/no), out-of-band verification "
                    "procedure documented (yes/no), DMARC/DKIM/SPF status checked "
                    "(current policy), anti-BEC training delivered to finance staff "
                    "(date, attendees), vendor change-of-bank procedure updated (yes/no)."
                ),
                "attack_techniques": ["T1566.002", "T1534"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 2880,
                "containment_actions": ["preserve_evidence"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },

    {
        "name": "Living-off-the-Land (LotL) Attack Response",
        "description": (
            "NSA/CISA Advisory AA22-137A: Response to attacks using built-in operating "
            "system tools and signed binaries (LOLBins) to evade detection — including "
            "abuse of PowerShell, WMI, certutil, mshta, regsvr32, rundll32, and "
            "scheduled tasks. These attacks are difficult to detect because malicious "
            "activity is indistinguishable from legitimate administration without "
            "behavioural baselining."
        ),
        "trigger_conditions": [
            "living off the land",
            "LotL",
            "LOLBins",
            "T1218",
            "T1047",
            "T1059.001",
            "T1059.003",
            "PowerShell encoded command",
            "certutil download",
            "mshta",
            "regsvr32 scrobj",
            "rundll32 javascript",
            "WMIC lateral",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Baseline normal LOLBin usage before hunting for anomalies",
                "description": (
                    "LotL detection requires understanding what is normal in the environment "
                    "before identifying anomalous usage. Establish a baseline of legitimate "
                    "PowerShell, WMI, certutil, and other LOLBin usage by IT and operations "
                    "teams. Identify systems where these tools should never run (end-user "
                    "workstations, kiosk machines), users who legitimately use them "
                    "(sysadmins, DevOps), and normal execution parent processes "
                    "(expected parent: powershell.exe for scripts, unexpected: "
                    "winword.exe, outlook.exe, svchost.exe spawning PowerShell)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Baseline established (yes/no, data source used — EDR/Sysmon/WEF), "
                    "legitimate LOLBin users identified (accounts, systems, use cases), "
                    "anomalous executions found (tool name, parent process, command line, "
                    "hostname, user, timestamp), encoded/obfuscated commands found "
                    "(base64 decoded content), network connections spawned by LOLBins "
                    "(certutil/mshta/bitsadmin outbound)."
                ),
                "attack_techniques": ["T1059.001", "T1047", "T1218"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Trace the full execution chain from initial LOLBin to impact",
                "description": (
                    "Map the complete execution chain: what spawned the initial LOLBin, "
                    "what the LOLBin did (download, execute, lateral move, persist), and "
                    "what subsequent activity occurred. Attackers chain multiple LOLBins: "
                    "e.g., mshta → PowerShell → certutil download → regsvr32 execute. "
                    "Use Sysmon Event ID 1 (process creation) with full command line "
                    "logging, PowerShell Script Block Logging (Event 4104), and WMI "
                    "activity logging to reconstruct the chain."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Full execution chain (process tree from initial compromise to "
                    "final payload, with timestamps), PowerShell Script Block Log "
                    "content (decoded), files downloaded via certutil/bitsadmin/mshta "
                    "(URLs, SHA256s), WMI commands executed (query/method/target), "
                    "persistence established via LOLBins (scheduled task XML, service, "
                    "registry run key), lateral movement attempts (target hosts, methods)."
                ),
                "attack_techniques": ["T1059.001", "T1218.005", "T1218.010"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 90,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Identify and remove all LOLBin-established persistence",
                "description": (
                    "LotL attackers commonly persist via: scheduled tasks created with "
                    "schtasks.exe (Task Scheduler XML inspection), WMI event subscriptions "
                    "(ActiveScriptEventConsumer, CommandLineEventConsumer), registry run "
                    "keys set via reg.exe, services created via sc.exe, and COM object "
                    "hijacking via regsvr32. Enumerate all scheduled tasks, WMI "
                    "subscriptions, and registry run keys created post-breach and "
                    "remove attacker-created entries."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Scheduled tasks reviewed (attacker-created tasks: name, command, "
                    "trigger, creation time), WMI subscriptions found (name, consumer "
                    "type, command), registry run keys added (hive, key, value), "
                    "services created by attacker (name, binary path), all persistence "
                    "mechanisms removed (method, timestamp)."
                ),
                "attack_techniques": ["T1053.005", "T1546.003", "T1547.001"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence", "isolate_host"],
            },
            {
                "step_number": 4,
                "title": "Isolate affected hosts and reset credentials used in lateral movement",
                "description": (
                    "Isolate hosts where attacker-controlled LOLBin execution occurred. "
                    "For lateral movement via WMI/SMB (T1047, T1021.002), reset all "
                    "credentials used to authenticate between affected hosts — the attacker "
                    "may have captured these credentials for future use. Block WMI remote "
                    "execution and disable SMBv1 on all remaining systems if not already done."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Hosts isolated (list, method, timestamp), credentials used in "
                    "lateral movement reset (account names, systems authenticated to), "
                    "WMI remote execution blocked (scope, method), SMBv1 disabled "
                    "(count of systems updated), attacker-captured credentials "
                    "invalidated (confirmed no ongoing use)."
                ),
                "attack_techniques": ["T1047", "T1021.002"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["isolate_host", "reset_credentials"],
            },
            {
                "step_number": 5,
                "title": "Implement LOLBin detection and restriction controls",
                "description": (
                    "Per NSA/CISA AA22-137A guidance, implement controls to restrict and "
                    "detect LOLBin abuse: enable PowerShell Constrained Language Mode on "
                    "non-admin workstations, enable Script Block Logging and Module Logging, "
                    "enable WMI activity logging (Microsoft-Windows-WMI-Activity/Operational), "
                    "block certutil/bitsadmin outbound connections at the proxy, deploy "
                    "AppLocker or WDAC to prevent execution of scripts from user-writable "
                    "locations, and tune SIEM rules for encoded PowerShell commands and "
                    "anomalous LOLBin parent processes."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "PowerShell CLM enabled on workstations (coverage %), Script Block "
                    "and Module logging enabled (coverage %), WMI activity logging "
                    "enabled, certutil/bitsadmin outbound blocked at proxy, AppLocker/"
                    "WDAC policy deployed (scope), SIEM rules tuned for LOLBin abuse "
                    "(rule names/IDs), Sysmon config updated (version, config hash)."
                ),
                "attack_techniques": ["T1059.001", "T1218"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["notify_management"],
            },
            {
                "step_number": 6,
                "title": "Post-Incident Review and Behavioural Detection Baseline",
                "description": (
                    "Conduct a post-incident review to document the attack chain, "
                    "LOLBins leveraged, detection gaps, and lessons learned. Update "
                    "the Sysmon configuration and SIEM detection rules to catch the "
                    "specific technique variations used. Establish baselines for normal "
                    "LOLBin usage in your environment (authorised IT admin usage of "
                    "PowerShell, certutil, etc.) to reduce false positives and sharpen "
                    "anomaly detection. Verify that all implemented controls are "
                    "sustained and reviewed quarterly."
                ),
                "requires_approval": False,
                "evidence_prompt": (
                    "Post-incident review document completed (date, attendees, attack chain "
                    "documented), new Sysmon rules deployed (rule names), SIEM detection "
                    "rules updated (names/IDs), LOLBin baseline documented for environment, "
                    "controls effectiveness verified (test method), quarterly review "
                    "calendar entry created."
                ),
                "attack_techniques": ["T1059.001", "T1218", "T1047"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 2880,
                "containment_actions": ["preserve_evidence"],
            },
        ],
        "version": "2.0",
        "is_builtin": True,
        "source": "cisa",
    },

    # -------------------------------------------------------------------------
    # Phase 46 additions — multi-source playbook library expansion
    # Sources: CERT-SG IRM, AWS Security, Microsoft DART, GuardSight, community
    # -------------------------------------------------------------------------

    {
        "name": "Password Spray / Credential Stuffing Response",
        "description": (
            "Microsoft DART / austinsonger T1110.003: Detection and response to password "
            "spray and credential stuffing attacks targeting Azure AD, M365, VPN, and "
            "web applications. Covers burst-detection, account lockout triage, source "
            "attribution, forced password reset, and MFA hardening."
        ),
        "category": "identity",
        "trigger_conditions": [
            "password spray",
            "credential stuffing",
            "T1110.003",
            "T1110.004",
            "multiple failed logins",
            "brute force",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Detect and scope the spray campaign",
                "description": (
                    "Identify the spray pattern: single IP/ASN attempting many accounts "
                    "with one or two guesses each (low-and-slow spray) vs. high-volume "
                    "attempts from distributed IPs (credential stuffing from breached list). "
                    "Query authentication logs for: same password attempt across >10 unique "
                    "accounts within a rolling 15-minute window, failure spikes from single "
                    "source IPs or user-agent strings, and any successful auths within the "
                    "spray window indicating a hit."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Source IPs and ASNs, total accounts targeted, timeframe, "
                    "success/failure ratio, user-agent strings observed, geographic origin."
                ),
                "attack_techniques": ["T1110.003", "T1110.004"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Identify any successful authentications",
                "description": (
                    "Cross-reference the spray source IPs and timeframe against successful "
                    "authentication events. A successful login from a spray source during "
                    "or shortly after the spray indicates credential compromise. For each "
                    "successful auth: note the account, source IP, time, accessed service, "
                    "and whether MFA was bypassed or not enrolled."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "List of accounts with successful auths during/after spray (UPN, "
                    "source IP, timestamp, service accessed, MFA bypassed y/n)."
                ),
                "attack_techniques": ["T1078", "T1078.004"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Block spray sources at perimeter",
                "description": (
                    "Block identified spray source IPs at the WAF, Azure AD Conditional "
                    "Access (Named Locations), or corporate firewall. For distributed "
                    "credential stuffing, consider enabling CAPTCHA/bot detection at the "
                    "login endpoint. Update threat intel block list with attacker ASNs "
                    "and hosting providers (e.g. residential proxies, VPS providers)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "IPs/CIDRs blocked (rule IDs, platform), Conditional Access policy "
                    "updated (policy name, change timestamp), CAPTCHA enabled (y/n)."
                ),
                "attack_techniques": ["T1110"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["block_ip"],
            },
            {
                "step_number": 4,
                "title": "Force password reset for targeted and compromised accounts",
                "description": (
                    "Force an immediate password reset for all accounts confirmed compromised. "
                    "For accounts that were sprayed but not confirmed compromised, assess "
                    "risk level (privileged accounts, service accounts, executives) and "
                    "proactively reset those as well. Revoke all active sessions and tokens. "
                    "Enrol all affected accounts in MFA if not already enrolled."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Accounts reset (count, privileged/standard breakdown), "
                    "sessions revoked, MFA enrollment status change (pre/post counts)."
                ),
                "attack_techniques": ["T1078", "T1531"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["reset_credentials"],
            },
            {
                "step_number": 5,
                "title": "Hunt for post-access activity from compromised accounts",
                "description": (
                    "For each confirmed compromised account, hunt for post-access activity: "
                    "email rule creation, OAuth app grants, data downloads, mailbox search "
                    "activity, lateral movement attempts, persistence mechanisms, and any "
                    "MFA registration changes (attacker registering their own MFA device "
                    "to maintain access after credential reset)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Post-access activity summary per compromised account: email rules "
                    "created, OAuth grants made, data accessed, lateral movement observed, "
                    "MFA device changes, persistence artifacts found."
                ),
                "attack_techniques": ["T1114", "T1098", "T1556"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 120,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 6,
                "title": "Implement long-term hardening and notify affected users",
                "description": (
                    "Enforce MFA for all accounts, enable Smart Lockout and risk-based "
                    "Conditional Access policies, and ban common passwords via Microsoft's "
                    "banned password list or equivalent. Notify affected users of the "
                    "campaign, advise them to watch for account anomalies, and provide "
                    "guidance on recognising account takeover indicators."
                ),
                "requires_approval": False,
                "evidence_prompt": (
                    "MFA coverage percentage post-remediation, Conditional Access policies "
                    "updated, banned password policy enabled, user notifications sent."
                ),
                "attack_techniques": ["T1110"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 1440,
                "containment_actions": ["notify_management"],
            },
        ],
        "version": "1.0",
        "is_builtin": True,
        "source": "microsoft",
    },

    {
        "name": "AWS Cloud Account / IAM Credential Compromise",
        "description": (
            "AWS Security Incident Response Guide: Response to suspected AWS IAM credential "
            "exposure, console account takeover, or EC2/Lambda instance compromise. Covers "
            "CloudTrail forensics, credential rotation, blast-radius assessment, and "
            "notification per AWS Acceptable Use Policy."
        ),
        "category": "cloud",
        "trigger_conditions": [
            "AWS compromise",
            "IAM abuse",
            "T1078.004",
            "cloud credential",
            "CloudTrail anomaly",
            "EC2 instance compromise",
            "S3 exfiltration",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Review CloudTrail for anomalous API activity",
                "description": (
                    "Query AWS CloudTrail for the suspected compromised principal (IAM user, "
                    "role, or root account) across all regions. Look for: console logins from "
                    "unusual IPs/countries, API calls at unusual hours, new IAM user/key/role "
                    "creation, Security Group modifications, S3 bucket policy changes, data "
                    "downloads (GetObject, CopyObject), EC2 instance launches (cryptomining), "
                    "and attempts to disable CloudTrail logging itself."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "CloudTrail query time window, principal(s) investigated, anomalous API "
                    "calls found (EventName, EventTime, SourceIPAddress, UserAgent), "
                    "regions affected, estimated data volume accessed."
                ),
                "attack_techniques": ["T1078.004", "T1530", "T1537"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Immediately rotate or disable the compromised credential",
                "description": (
                    "For IAM access keys: deactivate the compromised key immediately. "
                    "For console users: disable the account login, force password reset. "
                    "For EC2 instance roles: detach the overly-permissive role or revoke "
                    "temporary STS credentials by attaching a deny-all inline policy. "
                    "For root account: disable root access keys entirely (AWS best practice). "
                    "Do NOT delete keys yet — preserve for forensic chain-of-custody."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Access key status change (KeyId, previous/new status, timestamp), "
                    "console login disabled (user ARN), role policy modification (policy "
                    "ARN, change type), STS token revocation method used."
                ),
                "attack_techniques": ["T1078.004"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["reset_credentials"],
            },
            {
                "step_number": 3,
                "title": "Assess blast radius — enumerate attacker-created resources",
                "description": (
                    "Determine what the attacker created, modified, or accessed during the "
                    "compromise window. Use CloudTrail with the compromised principal as "
                    "filter. Check: new IAM entities (users, roles, keys, SAML providers), "
                    "modified security groups or NACLs, new EC2 instances or Lambda "
                    "functions, modified S3 bucket ACLs or policies, Route53 / CloudFront "
                    "changes, SNS/SQS subscriptions (C2 exfil), and cost spike in billing."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "All AWS resources created/modified by compromised principal: ARNs, "
                    "creation time, region, resource type. IAM backdoors created. "
                    "Data volume exfiltrated (S3 GetObject bytes). Cost spike estimate."
                ),
                "attack_techniques": ["T1578", "T1530", "T1098"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 120,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Remove attacker-created backdoors and remediate affected resources",
                "description": (
                    "Delete or disable all IAM entities created by the attacker. "
                    "Remove attacker-added keys from existing accounts. Restore modified "
                    "security group rules, S3 bucket policies, and IAM policies to known-good "
                    "state. Terminate attacker-launched EC2 instances (preserve snapshots). "
                    "Review and remove any SNS/SQS subscriptions or Lambda triggers the "
                    "attacker added for persistence."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "IAM backdoor entities removed (ARNs), security group rules restored, "
                    "S3 policies reverted, attacker EC2 instances terminated (snapshot ARNs "
                    "preserved), Lambda/SNS triggers removed."
                ),
                "attack_techniques": ["T1098", "T1578"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 120,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 5,
                "title": "Assess data exposure and initiate breach notification",
                "description": (
                    "If S3 objects, RDS data, or other sensitive data was accessed or "
                    "exfiltrated, identify the data classification, record counts, and "
                    "whether PII/PHI/PCI data was involved. Notify your AWS account team "
                    "via Support case. Assess reporting obligations under applicable "
                    "regulations (GDPR 72-hour, US state breach laws, HIPAA 60-day). "
                    "Preserve all CloudTrail logs as legal hold."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "S3 buckets / databases accessed, data classification assessment, "
                    "estimated record count, PII/PHI/PCI confirmed (y/n), AWS support "
                    "case ID, regulatory notification timeline determined."
                ),
                "attack_techniques": ["T1530"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 240,
                "containment_actions": ["notify_management", "preserve_evidence"],
            },
            {
                "step_number": 6,
                "title": "Harden IAM and enable detective controls",
                "description": (
                    "Post-incident hardening: enable MFA for all IAM users, apply least-"
                    "privilege by removing unused permissions (use IAM Access Analyzer), "
                    "enable AWS Security Hub with FSBP standard, enable GuardDuty in all "
                    "regions, configure CloudTrail with log file validation and S3 bucket "
                    "access logging, and set up CloudWatch alarms for root account activity "
                    "and IAM changes."
                ),
                "requires_approval": False,
                "evidence_prompt": (
                    "MFA enforced for all users (y/n), IAM Access Analyzer findings "
                    "resolved, Security Hub and GuardDuty enabled (regions), CloudTrail "
                    "hardening applied, CloudWatch alarms configured."
                ),
                "attack_techniques": ["T1078.004"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 2880,
                "containment_actions": [],
            },
        ],
        "version": "1.0",
        "is_builtin": True,
        "source": "aws",
    },

    {
        "name": "Lateral Movement / Pass-the-Hash Investigation",
        "description": (
            "GuardSight SOC Runbook: Detection and containment of attacker lateral movement "
            "using stolen credentials, pass-the-hash (PtH), pass-the-ticket (PtT), or "
            "remote service abuse. Maps the full movement graph from patient-zero to "
            "farthest-reached host and contains compromised credential material."
        ),
        "category": "network",
        "trigger_conditions": [
            "lateral movement",
            "T1021",
            "T1550",
            "T1550.002",
            "pass-the-hash",
            "pass-the-ticket",
            "PsExec",
            "WMI remote",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Establish patient-zero and initial access vector",
                "description": (
                    "Before tracing lateral movement, confirm the initial access event: "
                    "which host was first compromised, by what means (phishing, exploit, "
                    "exposed service), and what credential material was obtained. This "
                    "anchor point is essential — lateral movement tracing works forward "
                    "from the initial foothold host and credential."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Patient-zero hostname/IP, initial access technique, credential "
                    "compromised (account name, type — local/domain/service), "
                    "timestamp of first compromise indicator."
                ),
                "attack_techniques": ["T1566", "T1190", "T1078"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Map lateral movement path using authentication logs",
                "description": (
                    "Query Windows Security Event Log (4624/4625/4648/4776) and Sysmon "
                    "network events for the compromised credential and patient-zero host "
                    "as source. Map each hop: which accounts were used, which destination "
                    "hosts were accessed, and what mechanism (SMB/WMI/WinRM/RDP/PsExec). "
                    "Build a directed graph of movement: A to B to C using timestamp order."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Movement graph: each hop as (source_host, destination_host, "
                    "credential_used, technique, timestamp). Total hosts reached. "
                    "Highest-privilege credential obtained during movement."
                ),
                "attack_techniques": ["T1021", "T1550.002", "T1021.002"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Identify credential material harvested at each hop",
                "description": (
                    "At each pivot host, assess what credentials may have been dumped "
                    "or available: LSASS process access events (Sysmon event 10, "
                    "EID 4656), SAM database reads, ntds.dit access, LSA secrets access, "
                    "or use of known credential dumping tools (Mimikatz, Impacket, "
                    "CrackMapExec). Enumerate all accounts whose credentials may be "
                    "known to the attacker at each stage of the movement chain."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Per pivot host: credential dumping tool/technique observed, "
                    "accounts exposed (hostname, account name, privilege level), "
                    "ntds.dit / SAM / LSASS access confirmed (y/n)."
                ),
                "attack_techniques": ["T1003", "T1003.001", "T1003.002"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Isolate all hosts in the movement path",
                "description": (
                    "Isolate every host confirmed to be part of the lateral movement "
                    "path — not just patient-zero. Use EDR network isolation or VLAN "
                    "reassignment. Prioritise hosts with sensitive data or privileged "
                    "access. If a domain controller was reached, treat as full AD "
                    "compromise and escalate immediately to the AD Compromise playbook."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Hosts isolated (hostname, isolation method, timestamp), "
                    "domain controller reached (y/n — if yes: escalate to AD Compromise "
                    "playbook), critical systems affected."
                ),
                "attack_techniques": ["T1021"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["isolate_host"],
            },
            {
                "step_number": 5,
                "title": "Reset all compromised credential material",
                "description": (
                    "Reset passwords for every account identified as potentially "
                    "harvested. This includes: the initial compromised account, all "
                    "accounts logged into on pivot hosts, any service accounts with "
                    "cached credentials on pivot hosts, and local administrator accounts "
                    "on all affected hosts (use LAPS or equivalent). Disable NTLM where "
                    "possible to block future pass-the-hash attacks."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Accounts reset (count, privileged/service/standard breakdown), "
                    "LAPS deployed/rotated on affected hosts, NTLM restricted "
                    "(group policy applied, scope)."
                ),
                "attack_techniques": ["T1078", "T1550.002"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 120,
                "containment_actions": ["reset_credentials"],
            },
            {
                "step_number": 6,
                "title": "Hunt for persistence on all pivot hosts",
                "description": (
                    "On every host in the movement path, hunt for persistence mechanisms "
                    "the attacker may have installed: scheduled tasks, registry run keys, "
                    "WMI subscriptions, new local admin accounts, malicious services, "
                    "DLL hijacking paths, and web shells. Remove any persistence found "
                    "and re-image hosts where persistence is confirmed."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Persistence artifacts found per host (type, path/registry key, "
                    "creation timestamp, account used), hosts reimaged vs. cleaned in-place."
                ),
                "attack_techniques": ["T1053", "T1547", "T1546"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 240,
                "containment_actions": ["preserve_evidence"],
            },
        ],
        "version": "1.0",
        "is_builtin": True,
        "source": "guardsight",
    },

    {
        "name": "Suspicious Outbound Traffic / C2 Beaconing",
        "description": (
            "CERT-SG IRM-01 (Unusual Network Activity): Detection and response to suspicious "
            "outbound network traffic indicative of command-and-control beaconing, data "
            "staging, or C2 channel establishment. Covers traffic analysis, C2 identification, "
            "host attribution, and network-level containment."
        ),
        "category": "network",
        "trigger_conditions": [
            "C2 beaconing",
            "suspicious outbound",
            "T1071",
            "T1095",
            "T1071.001",
            "T1071.004",
            "DNS tunneling",
            "beaconing pattern",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Capture and characterise the suspicious traffic",
                "description": (
                    "Obtain the full network flow records (NetFlow/IPFIX) and, if available, "
                    "full packet capture (PCAP) for the suspicious traffic. Characterise "
                    "the communication: periodicity (fixed vs. jittered beacon interval), "
                    "destination IP/domain, protocol (HTTP/HTTPS/DNS/custom TCP/UDP), "
                    "payload size patterns, and geographic destination. Jitter in interval "
                    "with consistent payload sizes is a strong C2 indicator."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Source host(s), destination IP/domain, protocol and port, "
                    "beacon interval (mean/variance), payload sizes, traffic volume, "
                    "first-seen and last-seen timestamps, PCAP reference."
                ),
                "attack_techniques": ["T1071", "T1571"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Identify the responsible process on the source host",
                "description": (
                    "On the source host, correlate the suspicious network connection to "
                    "the owning process using EDR telemetry (Sysmon Event 3 — NetworkConnect, "
                    "or equivalent). Capture: process name, PID, parent PID, full command "
                    "line, executable path, and SHA256 hash. Submit the hash to VirusTotal "
                    "and internal threat intel. Determine whether the process is a legitimate "
                    "LOLBin (living-off-the-land binary) being abused for C2."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Process name, PID, PPID, full command line, executable path, "
                    "SHA256 hash, VirusTotal/TI result, binary signed/unsigned, "
                    "LOLBin abuse assessment."
                ),
                "attack_techniques": ["T1071", "T1059"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Block C2 destination at network perimeter",
                "description": (
                    "Immediately block the identified C2 IP(s) and domain(s) at the "
                    "firewall, DNS resolver (sinkhole), and web proxy. Where the C2 "
                    "uses domain-fronting through a CDN, apply proxy SSL inspection to "
                    "identify and block the fronted domain. Log all post-block connection "
                    "attempts to identify other infected hosts that attempt to reach the "
                    "same C2 infrastructure."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "C2 IPs/domains blocked (firewall rule IDs, DNS sinkhole entries, "
                    "proxy block entries, timestamp), post-block hit count, "
                    "additional hosts identified from post-block attempts."
                ),
                "attack_techniques": ["T1071"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["block_ip", "block_domain"],
            },
            {
                "step_number": 4,
                "title": "Hunt for additional infected hosts using C2 IOCs",
                "description": (
                    "Using the C2 IOCs (IPs, domains, user agents, JA3 TLS fingerprints, "
                    "URI patterns), hunt across all endpoints and network logs for other "
                    "hosts communicating with the same infrastructure. Expand the hunt "
                    "to include domain registrar clustering (similar TLDs, registration "
                    "dates) and infrastructure pivot (same hosting ASN, certificate SAN)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Hunt query details, additional hosts found (count, hostnames/IPs), "
                    "shared C2 infrastructure indicators, campaign scope assessment."
                ),
                "attack_techniques": ["T1071", "T1008"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 120,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 5,
                "title": "Isolate infected hosts and begin malware triage",
                "description": (
                    "Network-isolate all confirmed infected hosts. Collect volatile "
                    "artefacts (running processes, network connections, loaded DLLs, "
                    "scheduled tasks) before any changes. Submit implant binary to "
                    "sandbox for dynamic analysis. Determine malware family (RAT, "
                    "backdoor, stealer, loader) and assess what data may have been "
                    "exfiltrated based on the malware's known capabilities."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Hosts isolated, volatile artefacts captured, malware family identified, "
                    "sandbox report link, data exfiltration risk assessment (high/medium/low)."
                ),
                "attack_techniques": ["T1071"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 120,
                "containment_actions": ["isolate_host", "preserve_evidence"],
            },
        ],
        "version": "1.0",
        "is_builtin": True,
        "source": "cert_sg",
    },

    {
        "name": "Credential Dumping / LSASS Attack Response",
        "description": (
            "GuardSight SOC Runbook: Response to confirmed credential dumping from LSASS "
            "memory, SAM database, Active Directory ntds.dit, or cached credentials. "
            "Covers tool identification, scope determination, mass credential rotation, "
            "and NTLM/Kerberos hardening to prevent re-exploitation."
        ),
        "category": "identity",
        "trigger_conditions": [
            "credential dumping",
            "Mimikatz",
            "T1003",
            "T1003.001",
            "lsass",
            "ntds.dit",
            "secretsdump",
            "T1003.002",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Confirm the credential dumping event",
                "description": (
                    "Verify the detection: check EDR for process access events to lsass.exe "
                    "(Sysmon Event ID 10 — ProcessAccess with GrantedAccess 0x1010 or 0x1038), "
                    "Windows Security EID 4656 (handle request to lsass), or known tool "
                    "signatures (Mimikatz sekurlsa::logonpasswords, procdump targeting lsass). "
                    "Identify the tool used, the process that invoked it, and the account "
                    "under which it ran."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Dumping tool/technique confirmed, invoking process (path, PID, PPID, "
                    "command line, hash), account used, host, timestamp, "
                    "access flags captured."
                ),
                "attack_techniques": ["T1003.001", "T1003.002"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Determine scope of credential exposure",
                "description": (
                    "Identify all accounts whose credentials were resident on the compromised "
                    "host at the time of the dump: currently logged-in users, cached domain "
                    "credentials (offline logon cache), and service accounts running processes "
                    "on the host. For ntds.dit dumps from domain controllers, ALL domain "
                    "accounts are potentially compromised. Classify exposed accounts by "
                    "privilege tier: Tier 0 (DCs, PKI), Tier 1 (servers), Tier 2 (workstations)."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Host where dump occurred, accounts exposed (list with privilege tier), "
                    "ntds.dit/SAM dump from DC confirmed (y/n — if yes: full AD compromise "
                    "declared), service accounts affected."
                ),
                "attack_techniques": ["T1003"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Isolate affected host and block lateral movement immediately",
                "description": (
                    "Isolate the host where the dump occurred to prevent the attacker from "
                    "using the harvested credentials for immediate lateral movement. "
                    "Simultaneously, if any Tier-0 accounts (domain admins, krbtgt) were "
                    "exposed: immediately disable Kerberos pre-authentication exceptions and "
                    "enforce AES-only Kerberos encryption to reduce the usefulness of NTLM hashes."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Host isolated (method, timestamp), Tier-0 exposure confirmed (y/n), "
                    "Kerberos policy changes applied, NTLM restriction scope."
                ),
                "attack_techniques": ["T1550.002", "T1558"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 15,
                "containment_actions": ["isolate_host"],
            },
            {
                "step_number": 4,
                "title": "Perform mass credential rotation",
                "description": (
                    "Reset credentials for all exposed accounts in order of privilege: "
                    "krbtgt (twice, 10+ hours apart for ticket expiry), domain admin accounts, "
                    "privileged service accounts, standard domain accounts, and local "
                    "admin accounts (via LAPS rotation). For each reset: revoke all active "
                    "sessions and Kerberos tickets. If ntds.dit was dumped, treat as full "
                    "Kerberos golden ticket scenario and follow the AD Compromise playbook."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "krbtgt reset count and timestamps (must be done twice), "
                    "privileged accounts reset, service accounts reset and dependencies "
                    "verified functional, LAPS rotation confirmed."
                ),
                "attack_techniques": ["T1003", "T1558.001"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 240,
                "containment_actions": ["reset_credentials"],
            },
            {
                "step_number": 5,
                "title": "Deploy credential theft mitigations",
                "description": (
                    "Implement technical controls to prevent re-exploitation: enable "
                    "Credential Guard on Windows 10/11 and Server 2016+ to protect "
                    "LSASS from direct memory access; enable Protected Process Light (PPL) "
                    "for LSASS; deploy Attack Surface Reduction rule 'Block credential "
                    "stealing from LSASS'; restrict WDigest authentication; implement "
                    "tiered admin model if not already in place."
                ),
                "requires_approval": False,
                "evidence_prompt": (
                    "Credential Guard enabled (scope), PPL enabled for LSASS, "
                    "ASR rule deployed, WDigest disabled, tiered admin model status."
                ),
                "attack_techniques": ["T1003"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 1440,
                "containment_actions": [],
            },
        ],
        "version": "1.0",
        "is_builtin": True,
        "source": "guardsight",
    },

    {
        "name": "Obfuscated PowerShell / Script-Based Attack",
        "description": (
            "Microsoft DART: Detection and response to obfuscated PowerShell or "
            "script-based attacks including AMSI bypass attempts, encoded command "
            "execution, and reflective loading. Covers script deobfuscation, payload "
            "analysis, execution chain tracing, and enforcement hardening."
        ),
        "category": "endpoint",
        "trigger_conditions": [
            "PowerShell obfuscation",
            "T1059.001",
            "AMSI bypass",
            "T1562.001",
            "encoded command",
            "reflective loading",
            "T1620",
            "ScriptBlock logging",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Collect and decode the obfuscated script",
                "description": (
                    "Retrieve the full PowerShell script or command from: Windows "
                    "PowerShell Operational Event Log (EID 4103/4104 ScriptBlock "
                    "logging), EDR process command line capture, or Sysmon EID 1. "
                    "If base64-encoded via -EncodedCommand, decode the payload. "
                    "For multi-layer obfuscation (Invoke-Obfuscation, Invoke-Stealth, "
                    "character substitution), apply iterative decoding until plaintext "
                    "is obtained. Document each layer's technique."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Raw encoded command (full), decoded plaintext, obfuscation technique "
                    "identified (base64/string substitution/char concatenation/invoke), "
                    "EID captured (4103/4104/1)."
                ),
                "attack_techniques": ["T1059.001", "T1027"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Identify payload and final intent",
                "description": (
                    "Analyse the decoded script to determine payload type and intent: "
                    "download cradle (IEX/DownloadString) loading a remote payload, "
                    "reflective PE injection, credential harvesting, C2 implant installation, "
                    "lateral movement via WMI/PsExec, or data exfiltration. "
                    "If a remote URL is present, capture and sandbox the remote payload. "
                    "Assess whether AMSI was bypassed by inspecting amsiContext manipulation "
                    "or SetErrorMode calls in the decoded script."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Final payload type, remote URL if present (blocked/sinkholed), "
                    "AMSI bypass technique used (y/n, method), execution intent "
                    "(credential theft/C2/lateral movement/exfil/other)."
                ),
                "attack_techniques": ["T1059.001", "T1620", "T1562.001"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Trace full execution chain and parent processes",
                "description": (
                    "Map the complete execution chain: which process spawned PowerShell, "
                    "what spawned that process, and so on back to the initial vector. "
                    "Common patterns: Word/Excel macro → PowerShell, "
                    "mshta/wscript → PowerShell, browser plugin → PowerShell, "
                    "scheduled task → PowerShell. Identify the initial lure or trigger "
                    "document/URL that started the chain."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Full process tree (PID chain from initial trigger to PowerShell), "
                    "initial trigger identified (document name/URL/scheduled task), "
                    "LOLBin abuse confirmed (y/n, which binary)."
                ),
                "attack_techniques": ["T1059.001", "T1566"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Contain and remediate affected host",
                "description": (
                    "Isolate the host. Remove any persistence installed by the script "
                    "(scheduled tasks, registry run keys, WMI subscriptions). "
                    "Terminate any lingering malicious processes. If a payload was injected "
                    "into a legitimate process, terminate and restart the clean process. "
                    "Submit all IOCs (hashes, IPs, domains, URLs) to the "
                    "threat intel platform for cross-environment hunting."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Host isolated, persistence removed (type, path), malicious "
                    "processes terminated, IOCs submitted to TI platform (count)."
                ),
                "attack_techniques": ["T1059.001"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["isolate_host"],
            },
            {
                "step_number": 5,
                "title": "Enforce PowerShell execution controls",
                "description": (
                    "Post-incident hardening: enable PowerShell Constrained Language Mode "
                    "via AppLocker or WDAC policy, enforce ScriptBlock logging (EID 4104) "
                    "and Module logging (EID 4103) via GPO, block PowerShell v2 engine "
                    "(prevents AMSI bypass via downgrade), and deploy AMSI integration "
                    "for all scripting engines. Consider restricting to signed scripts only."
                ),
                "requires_approval": False,
                "evidence_prompt": (
                    "CLM enabled (scope), ScriptBlock+Module logging confirmed active, "
                    "PS v2 disabled, AMSI integration status, execution policy applied."
                ),
                "attack_techniques": ["T1059.001"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 1440,
                "containment_actions": [],
            },
        ],
        "version": "1.0",
        "is_builtin": True,
        "source": "microsoft",
    },

    {
        "name": "Web Shell Detection and Response",
        "description": (
            "CERT-SG IRM-06 / CISA AA21-279A: Response to web shell deployment on "
            "internet-facing web servers or application servers. Web shells provide "
            "persistent remote access and lateral movement capability. Covers shell "
            "identification, server forensics, removal, and root-cause patching."
        ),
        "category": "web",
        "trigger_conditions": [
            "web shell",
            "T1505.003",
            "server-side script",
            "suspicious POST to static path",
            "T1190",
            "website defacement",
            "unauthorised file write",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Identify all web shell files on the server",
                "description": (
                    "Locate web shell files using multiple methods: file system scan for "
                    "recently modified web-accessible files (PHP, ASPX, JSP, ASP, CFML) "
                    "in the web root, web access log analysis for POST requests to "
                    "unusual paths or unexpected file extensions, and EDR hash comparison "
                    "against known-good baseline. Flag files containing dangerous dynamic "
                    "code evaluation patterns (base64_decode, passthru, system calls) "
                    "in web-accessible paths."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Web shell files identified (full path, SHA256, size, last-modified "
                    "timestamp, web-accessible URL, language/framework)."
                ),
                "attack_techniques": ["T1505.003"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Analyse web access logs for shell usage and attacker activity",
                "description": (
                    "Analyse web server access logs (Apache, IIS, nginx) for all requests "
                    "to the web shell URLs. Identify: attacker source IPs, user agents, "
                    "commands executed via shell (from POST body or query parameters), "
                    "files downloaded/uploaded through the shell, and lateral movement "
                    "attempts from the web server process. Build a timeline of attacker "
                    "activity from shell deployment to detection."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Shell access events (IP, timestamp, HTTP method, response code, "
                    "bytes transferred), commands/payloads sent (if visible in logs), "
                    "attacker activity timeline, files uploaded/downloaded."
                ),
                "attack_techniques": ["T1505.003", "T1059"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 120,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Determine initial access vector",
                "description": (
                    "Investigate how the web shell was planted: file upload vulnerability "
                    "(unrestricted upload, MIME type bypass), remote code execution in a "
                    "web application (deserialization, SSTI, SQL injection to file write), "
                    "CMS plugin exploitation, or compromised admin credentials used to "
                    "upload via legitimate CMS/FTP interface. Identify the CVE or "
                    "misconfiguration exploited to prevent re-entry after remediation."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Initial access vector identified (upload/RCE/credential abuse), "
                    "CVE or misconfiguration responsible, earliest evidence of exploitation "
                    "in access logs, attacker IP used for initial upload."
                ),
                "attack_techniques": ["T1190", "T1505.003"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 120,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Take server offline and remove shell files",
                "description": (
                    "If active exploitation is ongoing, take the web server offline or "
                    "block external access at the WAF/firewall while remediation proceeds. "
                    "Remove all identified web shell files. Restore modified web application "
                    "files from verified backups. Reset all web application passwords, "
                    "API keys, and database credentials (attacker may have exfiltrated "
                    "configuration files). Scan restored files before bringing server online."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Server taken offline (timestamp), all shell files removed (SHA256 list), "
                    "files restored from backup (source backup, verification method), "
                    "credentials rotated, WAF rules updated."
                ),
                "attack_techniques": ["T1505.003"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 240,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 5,
                "title": "Patch initial access vector and implement WAF rules",
                "description": (
                    "Patch the vulnerability used for initial access. For file upload "
                    "issues: enforce MIME validation, restrict upload directories from "
                    "execution. For CMS exploitation: update plugins/themes, rotate admin "
                    "credentials, enable 2FA. Add WAF rules blocking web shell command "
                    "patterns. Implement file integrity monitoring on web root directories."
                ),
                "requires_approval": False,
                "evidence_prompt": (
                    "Vulnerability patched (CVE, patch version), WAF rules added, "
                    "file integrity monitoring enabled, upload restrictions applied, "
                    "CMS hardening completed."
                ),
                "attack_techniques": ["T1190"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 1440,
                "containment_actions": [],
            },
        ],
        "version": "1.0",
        "is_builtin": True,
        "source": "cert_sg",
    },

    {
        "name": "Unauthorized Access / Privilege Escalation Response",
        "description": (
            "CERT-SG IRM-04: Response to confirmed unauthorized access to systems, "
            "applications, or data, including internal privilege escalation by authenticated "
            "users who exceed their authorized access level. Covers access log forensics, "
            "account containment, data impact assessment, and policy remediation."
        ),
        "category": "identity",
        "trigger_conditions": [
            "unauthorized access",
            "T1068",
            "privilege escalation",
            "T1548",
            "T1134",
            "account abuse",
            "unauthorized admin",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Establish what was accessed without authorization",
                "description": (
                    "Identify the specific resources accessed: systems (hostnames, IPs), "
                    "applications, databases, files, or data repositories. Determine the "
                    "access method: exploited vulnerability, stolen/shared credential, "
                    "misconfigured permission, or insider privilege abuse. Establish the "
                    "full access timeline from authentication logs and application audit logs."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Resources accessed (system/application/data, sensitivity level), "
                    "access method identified, account used, access timeline "
                    "(first-access to detection), data volume accessed."
                ),
                "attack_techniques": ["T1078", "T1068"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Disable or contain the account responsible",
                "description": (
                    "Immediately disable, lock, or revoke the account or credential used "
                    "for unauthorized access. If a shared account or service account was "
                    "abused, rotate credentials and restrict access scope. If privilege "
                    "escalation was via an exploited vulnerability, isolate the affected "
                    "host. Revoke all active sessions."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Account disabled/locked (UPN, timestamp), sessions revoked, "
                    "service account re-scoped (new permissions), host isolated (if exploit)."
                ),
                "attack_techniques": ["T1078", "T1134"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 30,
                "containment_actions": ["reset_credentials"],
            },
            {
                "step_number": 3,
                "title": "Classify and quantify data impact",
                "description": (
                    "Assess what data was viewed, copied, modified, or deleted during the "
                    "unauthorized access period. Classify data sensitivity (public, internal, "
                    "confidential, restricted, PII, PHI, PCI). Determine if data was "
                    "exfiltrated off-system (check DLP alerts, email, USB activity, cloud "
                    "uploads). Assess regulatory notification obligations based on data type."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Data accessed (type, volume, classification), exfiltration confirmed "
                    "(y/n, method if yes), PII/PHI/PCI involved (y/n), notification "
                    "obligation assessed (regulation, timeline)."
                ),
                "attack_techniques": ["T1530", "T1005"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 120,
                "containment_actions": ["preserve_evidence", "notify_management"],
            },
            {
                "step_number": 4,
                "title": "Remediate the access vulnerability or permission misconfiguration",
                "description": (
                    "Fix the root cause: patch the exploited vulnerability, correct the "
                    "over-permissive access control, revoke shared credential usage, or "
                    "enforce least-privilege for the account. If insider abuse: initiate "
                    "HR process and legal hold. Review access control lists and "
                    "role assignments for all affected resources to identify other "
                    "over-permissive grants."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Root cause fixed (patch applied / permission corrected / policy "
                    "updated), access review completed (resources reviewed, excessive "
                    "permissions removed), HR/legal process initiated (if insider)."
                ),
                "attack_techniques": ["T1068", "T1548"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 480,
                "containment_actions": [],
            },
        ],
        "version": "1.0",
        "is_builtin": True,
        "source": "cert_sg",
    },

    {
        "name": "DNS Tunneling / Covert Exfiltration Response",
        "description": (
            "Community IR Playbook (MITRE ATT&CK T1048.003): Response to DNS-based "
            "covert channel used for command-and-control or data exfiltration. DNS "
            "tunneling tools encapsulate data in DNS query labels to bypass network "
            "monitoring. Covers pattern detection, payload extraction, host attribution, "
            "and DNS monitoring hardening."
        ),
        "category": "network",
        "trigger_conditions": [
            "DNS tunneling",
            "DNS exfiltration",
            "T1048.003",
            "dnscat2",
            "iodine",
            "unusual DNS query length",
            "high DNS query rate",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Detect and confirm DNS anomaly pattern",
                "description": (
                    "Analyse DNS logs for tunneling indicators: unusually long subdomain "
                    "labels (>50 characters), high entropy subdomains (random-looking "
                    "hex or base64 strings), abnormally high query rates to a single "
                    "domain, consistent query intervals (beaconing), NXDOMAIN responses "
                    "with encoded subdomains, or TXT/NULL/CNAME record types used for "
                    "responses (data channel). Calculate entropy score for top queried "
                    "domains."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Domain(s) flagged, query rate (queries/minute), average subdomain "
                    "length, entropy score, record types used, first/last seen, "
                    "total queries, source host(s)."
                ),
                "attack_techniques": ["T1048.003", "T1071.004"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Decode tunnel payload to assess data scope",
                "description": (
                    "Attempt to decode the DNS tunnel content: base32/base64 decode "
                    "subdomain labels, reconstruct ordered data from sequential queries, "
                    "and identify the tunnel tool from response TXT record format (iodine "
                    "uses a specific handshake; dnscat2 has identifiable header bytes). "
                    "Even partial decoding reveals data type (command output, file, "
                    "credentials) and provides evidence for scope assessment."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Tunnel tool identified (iodine/dnscat2/dns2tcp/custom), payload "
                    "partially decoded (y/n), data type assessed (commands/file/credential/"
                    "unknown), data volume estimate (bytes)."
                ),
                "attack_techniques": ["T1048.003"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 120,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Block tunnel domain and enforce egress DNS controls",
                "description": (
                    "Block the identified tunnel domain(s) at the internal DNS resolver "
                    "(NXDOMAIN or sinkhole). Update egress firewall rules to restrict "
                    "outbound DNS to only authorised internal resolvers (preventing direct "
                    "UDP 53 to external resolvers which bypasses internal sinkholing). "
                    "Consider RPZ (Response Policy Zones) for automated threat blocking."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Domain(s) sinkholed (DNS resolver, record TTL, timestamp), "
                    "outbound UDP 53 restricted (firewall rule ID), RPZ configured (y/n)."
                ),
                "attack_techniques": ["T1048.003", "T1071.004"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 30,
                "containment_actions": ["block_domain"],
            },
            {
                "step_number": 4,
                "title": "Identify and isolate infected host",
                "description": (
                    "Identify the host(s) generating the tunnel traffic using DNS logs "
                    "correlated with DHCP lease records or endpoint DNS client logs. "
                    "Identify the process responsible for the DNS queries on the host "
                    "using EDR telemetry. Isolate the host and begin full malware triage — "
                    "DNS tunnel tools are typically delivered as implants following an "
                    "initial compromise."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Host(s) identified (hostname, IP, DNS correlation method), "
                    "responsible process identified (name, PID, hash), host isolated, "
                    "implant binary preserved for analysis."
                ),
                "attack_techniques": ["T1071.004"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["isolate_host", "preserve_evidence"],
            },
            {
                "step_number": 5,
                "title": "Harden DNS monitoring and egress controls",
                "description": (
                    "Implement long-term DNS monitoring hardening: deploy DNS-based threat "
                    "hunting rules (high entropy, long labels, TXT record response volume), "
                    "enable Zeek DNS logging with full query capture, integrate DNS data with "
                    "SIEM for anomaly detection, restrict DNS resolver to internal only, "
                    "and block port 53 outbound except to approved resolvers."
                ),
                "requires_approval": False,
                "evidence_prompt": (
                    "DNS anomaly detection rules deployed, Zeek DNS logging confirmed, "
                    "outbound DNS restriction applied, RPZ configured (y/n)."
                ),
                "attack_techniques": ["T1048.003"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 2880,
                "containment_actions": [],
            },
        ],
        "version": "1.0",
        "is_builtin": True,
        "source": "community",
    },

    {
        "name": "Social Engineering / Vishing Response",
        "description": (
            "CERT-SG IRM-09: Response to social engineering attacks including vishing "
            "(voice phishing), smishing (SMS phishing), physical impersonation, and "
            "pretext phone calls targeting employees to extract credentials, transfer "
            "funds, or install software. Covers employee interview, impact assessment, "
            "and awareness reinforcement."
        ),
        "category": "phishing",
        "trigger_conditions": [
            "social engineering",
            "vishing",
            "smishing",
            "T1598",
            "impersonation",
            "pretext call",
            "employee report",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Interview the targeted employee",
                "description": (
                    "Conduct a structured interview with the employee who was targeted. "
                    "Document: exact nature of the request (credentials, software install, "
                    "wire transfer, callback number), channel used (phone/SMS/in-person), "
                    "attacker persona (IT helpdesk, vendor, executive, law enforcement), "
                    "information provided or actions taken by the employee, and any "
                    "callback numbers, email addresses, or URLs provided by the attacker."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Employee name/role, attack channel, attacker persona, "
                    "information/credentials revealed by employee, actions taken by employee "
                    "(installed software/provided code/transferred funds), "
                    "attacker contact info (phone/email/URL)."
                ),
                "attack_techniques": ["T1598", "T1566"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Assess what the attacker gained and contain immediately",
                "description": (
                    "Based on the employee interview, determine the immediate impact: "
                    "credentials revealed (reset them immediately), MFA code provided "
                    "(revoke active sessions), software installed (isolate host for "
                    "malware analysis), funds transferred (notify finance team and bank), "
                    "access granted (audit systems accessed). For MFA bypass attempts, "
                    "check auth logs for logins using the provided code."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Credentials revealed and reset (accounts), MFA codes provided "
                    "and sessions revoked, software installed (host isolated y/n), "
                    "financial impact (amount, recipient account if known)."
                ),
                "attack_techniques": ["T1078", "T1566"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 30,
                "containment_actions": ["reset_credentials", "isolate_host"],
            },
            {
                "step_number": 3,
                "title": "Hunt for indicators of post-access activity",
                "description": (
                    "If credentials or MFA codes were provided, hunt for authentication "
                    "events using those credentials around the time of the call. "
                    "Correlate new logins, source IPs, and service access with the "
                    "social engineering timeline. If software was installed, analyse "
                    "the host for malware artifacts and active C2 connections."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Auth events post-social-engineering (account, IP, service, timestamp), "
                    "data accessed via gained credentials, C2 activity from installed software."
                ),
                "attack_techniques": ["T1078", "T1566"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 60,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Conduct targeted awareness training with affected employee",
                "description": (
                    "Provide the targeted employee with personalised awareness training "
                    "covering: how to verify IT/helpdesk identity requests (out-of-band "
                    "callback to known internal number), never providing MFA codes or "
                    "passwords over the phone, proper escalation process for suspicious "
                    "requests, and vishing recognition signs. Document training completion."
                ),
                "requires_approval": False,
                "evidence_prompt": (
                    "Training delivered (date, method, topics covered), "
                    "employee acknowledged training (y/n), manager notified (y/n)."
                ),
                "attack_techniques": ["T1598"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 1440,
                "containment_actions": ["notify_management"],
            },
        ],
        "version": "1.0",
        "is_builtin": True,
        "source": "cert_sg",
    },

    {
        "name": "S3 / Cloud Storage Exposure Response",
        "description": (
            "AWS Security Incident Response / CISA T1530: Response to inadvertent or "
            "attacker-induced public exposure of cloud storage (S3 buckets, Azure Blob, "
            "GCS). Covers immediate access restriction, data classification, exposure "
            "scope assessment, and regulatory notification triage."
        ),
        "category": "cloud",
        "trigger_conditions": [
            "S3 exposure",
            "public bucket",
            "T1530",
            "cloud storage leak",
            "Azure blob exposure",
            "GCS public bucket",
        ],
        "steps": [
            {
                "step_number": 1,
                "title": "Immediately remove public access from the bucket",
                "description": (
                    "As the first priority, remove the misconfiguration: disable S3 Block "
                    "Public Access bypass, remove public bucket ACL or policy (s3:GetObject "
                    "with Principal '*'), or remove the public-read ACL. For Azure: remove "
                    "Anonymous access from the storage account. For GCS: remove allUsers "
                    "or allAuthenticatedUsers IAM bindings. Confirm access is restricted "
                    "before proceeding with investigation."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Bucket name, cloud provider, misconfiguration type removed, "
                    "public access confirmed blocked (ACL/policy change confirmed), "
                    "timestamp of remediation."
                ),
                "attack_techniques": ["T1530"],
                "escalation_threshold": "high",
                "escalation_role": "SOC Manager",
                "time_sla_minutes": 15,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 2,
                "title": "Determine exposure window and access logs",
                "description": (
                    "Determine when the bucket was made public (look at CloudTrail "
                    "PutBucketPolicy, PutBucketAcl, or PutBucketPublicAccessBlock events). "
                    "Enable and retrieve S3 access logs or CloudTrail data events for the "
                    "exposure window. Count and characterise external GetObject requests: "
                    "source IPs, user agents, objects accessed, and data volume downloaded."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Exposure window (start time, end time), total external GetObject "
                    "requests, unique source IPs, objects accessed (list or count), "
                    "data volume downloaded (bytes), CloudTrail event that created exposure."
                ),
                "attack_techniques": ["T1530"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 120,
                "containment_actions": ["preserve_evidence"],
            },
            {
                "step_number": 3,
                "title": "Classify the exposed data and assess breach obligation",
                "description": (
                    "Classify all objects in the bucket by data sensitivity: PII (names, "
                    "emails, addresses, SSN, DOB), PHI (health records), PCI (card data), "
                    "credentials (API keys, passwords, certificates), proprietary source "
                    "code, or business confidential. Cross-reference with evidence of "
                    "actual access. Assess breach notification obligations under GDPR "
                    "(72-hour), CCPA, HIPAA, and applicable state laws."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Data types in bucket (classification), PII/PHI/PCI present (y/n), "
                    "credentials in bucket (y/n — rotate if yes), notification obligation "
                    "assessed (regulation, deadline), legal/DPO notified."
                ),
                "attack_techniques": ["T1530"],
                "escalation_threshold": "critical",
                "escalation_role": "CISO",
                "time_sla_minutes": 240,
                "containment_actions": ["notify_management", "preserve_evidence"],
            },
            {
                "step_number": 4,
                "title": "Rotate any exposed credentials and secrets",
                "description": (
                    "If any secrets (API keys, AWS access keys, database passwords, "
                    "OAuth secrets, certificates) were present in the exposed bucket, "
                    "immediately rotate all of them regardless of whether access evidence "
                    "exists — assume any exposed secret is compromised. Check code "
                    "repositories and CI/CD pipelines for hardcoded versions of the "
                    "same secrets."
                ),
                "requires_approval": True,
                "evidence_prompt": (
                    "Secrets/credentials found in bucket (type, count), "
                    "all rotated (y/n), CI/CD pipeline updated, hardcoded versions "
                    "found in repos (y/n, locations purged)."
                ),
                "attack_techniques": ["T1078.004", "T1530"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 60,
                "containment_actions": ["reset_credentials"],
            },
            {
                "step_number": 5,
                "title": "Implement preventive controls and SCM scanning",
                "description": (
                    "Prevent recurrence: enable AWS Config rule 's3-bucket-public-read-"
                    "prohibited', deploy AWS Security Hub S3 checks, use AWS Macie for "
                    "automated sensitive data discovery in S3. Implement organisation-level "
                    "S3 Block Public Access at the AWS Organisation level. Deploy "
                    "secret scanning in CI/CD (TruffleHog, Gitleaks) to prevent credentials "
                    "from being committed to code repositories."
                ),
                "requires_approval": False,
                "evidence_prompt": (
                    "AWS Config rules enabled, Security Hub S3 checks active, "
                    "Macie enabled (scope), org-level Block Public Access applied, "
                    "secret scanning deployed in CI/CD."
                ),
                "attack_techniques": ["T1530"],
                "escalation_threshold": None,
                "escalation_role": None,
                "time_sla_minutes": 2880,
                "containment_actions": [],
            },
        ],
        "version": "1.0",
        "is_builtin": True,
        "source": "aws",
    },
]
