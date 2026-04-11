---
status: complete
phase: 38-cisa-playbook-content
source: 38-02-SUMMARY.md, 38-03-SUMMARY.md
started: 2026-04-11T00:00:00Z
updated: 2026-04-11T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Backend restarted with new seed_builtin_playbooks() logic. SQLite migrations ran (source, escalation_acknowledged, active_case_id columns added). 4 CISA playbooks seeded. /api/playbooks returns 200 with playbook data. No startup errors.
result: pass

### 2. CISA Playbooks Replace NIST
expected: Playbooks / SOAR view shows exactly 4 playbooks — "Phishing / BEC Response", "Ransomware Response", "Credential / Account Compromise Response", "Malware / Intrusion Response". No NIST playbooks (Phishing Initial Triage, Lateral Movement Investigation, etc.) visible.
result: pass

### 3. Source Badges on Playbook Cards
expected: Each CISA playbook card shows a small amber/orange "CISA" badge. Any custom (analyst-created) playbook shows a blue "Custom" badge. Badges are visible without opening the playbook.
result: pass

### 4. ATT&CK Technique Chips on Steps
expected: When a playbook is open and a step is visible, each step shows violet pill chips for ATT&CK techniques (e.g. "T1566", "T1078"). Clicking a chip opens attack.mitre.org/techniques/T1566 in a new browser tab.
result: pass

### 5. SLA Badge on Steps
expected: Each step header shows a grey "Xmin SLA" badge indicating how long the analyst has to complete the step (e.g. "30min SLA").
result: pass

### 6. Escalation Banner + Acknowledge Gate
expected: On a step with escalation_threshold set (e.g. steps requiring CISO/SOC Manager notification), an amber inline warning banner appears reading something like "Escalation Required". The Confirm Step and Skip buttons are disabled until the analyst clicks an Acknowledge button on the banner.
result: pass

### 7. Containment Action Dropdown at Step Completion
expected: When completing a step (clicking Confirm Step or at the step completion modal), a dropdown appears with controlled-vocabulary options (isolate_host, reset_credentials, block_ip, block_domain, preserve_evidence, notify_management, engage_ir_team). Selecting one records the action.
result: pass

### 8. Suggested Playbook CTA in DetectionsView
expected: In the Detections view, a detection that has an ATT&CK technique matching one of the CISA playbook trigger conditions shows a "Suggested: [Playbook Name]" CTA in the Actions column. Clicking it navigates to PlaybooksView.
result: pass

### 9. Deep-Link Scroll to Matching Step
expected: When navigating from a detection to a suggested playbook, PlaybooksView opens the correct playbook and scrolls to the step whose ATT&CK techniques match the detection's technique — not always step 1.
result: skipped
reason: Requires live detection data with matching technique to observe deep-link scroll behavior

### 10. Run Completion PDF Prompt
expected: After completing all steps of a playbook run (all steps confirmed/skipped), a prompt appears: "Generate Playbook Execution Log PDF?" with a Generate Report button.
result: pass

## Summary

total: 10
passed: 9
issues: 0
pending: 0
skipped: 1

## Gaps

[none yet]
