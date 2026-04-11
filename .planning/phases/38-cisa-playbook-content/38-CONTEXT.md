# Phase 38: CISA Playbook Content - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the 5 NIST starter playbooks with CISA-derived response flows covering four incident classes (Phishing/BEC, Ransomware, Credential/Account Compromise, Malware/Intrusion). Enrich the PlaybookStep model with containment actions, severity-based escalation gates, and ATT&CK technique mappings. Update PlaybooksView to surface all new fields. Creating new incident classes or adding playbook authoring UI are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Playbook scope
- Replace all 5 NIST starters with CISA-derived playbooks (do not keep NIST starters)
- Four incident classes: Phishing/BEC, Ransomware, Credential/Account Compromise, Malware/Intrusion
- CISA playbooks are locked (read-only, source="cisa") — analysts cannot modify steps
- Custom analyst-created playbooks remain editable as before

### Step model enhancements
- Use industry standard IR fields — Claude's discretion for exact field names and schema
- containment_action: controlled vocabulary — isolate_host, reset_credentials, block_ip, block_domain, preserve_evidence, notify_management, engage_ir_team — selected on step completion
- escalation_threshold: severity level (critical/high/null) — when active detection severity ≥ threshold, step shows yellow escalation warning banner
- time_sla_minutes: how long analyst has to complete the step (informational, shown as badge)
- User deferred to industry standards for any additional step fields

### Escalation gates
- Warning banner inline on the step (not a modal, not a hard block)
- Banner text: "Escalation Required — severity meets threshold. Notify [role] before proceeding."
- Analyst acknowledges with a button before step can be marked complete
- Escalation gate auto-associates the playbook run with the active investigation case if one exists

### ATT&CK technique mapping
- Each PlaybookStep has a list of ATT&CK technique IDs (e.g., ["T1566", "T1078"])
- Displayed as badge chips on the step card — same pill style as DetectionsView
- Badges are clickable links → attack.mitre.org/techniques/T1566 (new tab)
- When analyst navigates from a detection to a suggested playbook, open at the step whose techniques match the detection's ATT&CK technique (not always step 1)

### Playbook suggestion / auto-trigger
- Detections view shows "Suggested: [Playbook Name]" prompt when detection's ATT&CK technique or event type matches playbook trigger_conditions
- Analyst clicks to launch a run — no auto-launch
- Suggestion displayed in the detection panel as a soft CTA, not a banner

### Dashboard presentation
- CISA playbooks show a small "CISA" source badge on the playbook card in PlaybooksView
- Custom playbooks show "Custom" badge
- Escalation gate: yellow inline warning banner with acknowledge button
- Containment action: dropdown shown at step completion time (not upfront)
- Run completion: prompt "Generate Playbook Execution Log PDF?" linking to Phase 37 template

### Claude's Discretion
- Exact PlaybookStep schema field names and types for new fields
- How to detect existing NIST starters at startup and replace them cleanly
- Exact CISA response flow content (steps, titles, descriptions, evidence prompts)
- ATT&CK technique IDs mapped to each step per incident class
- SLA minutes per step (use CISA guidance where available)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/models/playbook.py`: PlaybookStep, Playbook, PlaybookCreate, PlaybookRun, PlaybookRunAdvance — extend PlaybookStep with new fields
- `backend/data/builtin_playbooks.py`: BUILTIN_PLAYBOOKS list seeded at startup — replace contents here, same pattern
- `backend/api/playbooks.py`: seed_builtin_playbooks() function — handles deduplication on startup
- `dashboard/src/lib/api.ts`: playbook API group already typed — extend for new fields
- DetectionsView: technique badge chips pattern already exists — reuse in PlaybooksView

### Established Patterns
- Svelte 5 runes ($state, $derived, $effect) — no stores
- Navy theme CSS variables (--bg-secondary, --border, --accent-blue etc.)
- Badge chips: small rounded pill with color-coded background — used for severity and technique IDs
- Step completion modal already exists in PlaybooksView — extend to include containment_action dropdown

### Integration Points
- `backend/main.py`: seed_builtin_playbooks() called at startup — replacement logic goes here
- `backend/api/detect` response: add "suggested_playbook" field when TTP match found
- `backend/stores/sqlite.py`: playbook_runs table — add escalation_acknowledged column
- Phase 37 report_templates.py: playbook execution log template already accepts playbook_run data

</code_context>

<specifics>
## Specific Ideas

- Source badge ("CISA" / "Custom") should be visually distinct — CISA badge in orange/amber to signal authoritative external content, Custom in blue to match the SOC Brain brand
- "Suggest playbook" in detection panel should feel like a soft recommendation, not an alert — similar to how Linear suggests related issues
- Containment action vocabulary from CISA IR guidance: isolate, reset, block, preserve, notify, engage — keeps terminology consistent with federal IR language

</specifics>

<deferred>
## Deferred Ideas

- Playbook authoring UI (create/edit custom playbooks in dashboard) — future phase
- Lateral Movement playbook (NIST class not covered by CISA scope here) — note for Phase 38+ backlog
- Automated containment actions (actually executing block_ip via firewall API) — separate SOAR automation phase
- CISA Vulnerability Response Playbook — separate from IR playbooks, note for later

</deferred>

---

*Phase: 38-cisa-playbook-content*
*Context gathered: 2026-04-11*
