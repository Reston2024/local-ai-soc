# Feature Research

**Domain:** Local AI-powered cybersecurity SOC/investigation platform (Windows desktop, single analyst)
**Researched:** 2026-03-14
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features an experienced SecOps analyst assumes exist. Missing any of these and the tool feels like a toy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Structured log ingestion (EVTX, JSON, CSV, NDJSON)** | Every DFIR tool ingests logs. Without this, there is nothing to investigate. | MEDIUM | EVTX parsing is the hardest part -- use python-evtx or evtxtools. JSON/CSV/NDJSON are straightforward. Normalize to a common schema on ingest. |
| **Normalized event schema with timestamps** | Analysts need to correlate across sources. Different timestamp formats and field names make this impossible without normalization. | MEDIUM | Minimum fields: timestamp, host, user, process, file, network, source. Map to ECS (Elastic Common Schema) conventions -- analysts already know them. |
| **Full-text search across ingested events** | "Show me all events mentioning mimikatz" is the first thing any analyst tries. No search = useless. | LOW | DuckDB full-text search or simple LIKE queries suffice at desktop scale. Must be fast (<2s for 1M events). |
| **Sigma rule matching** | Sigma is the lingua franca of detection engineering. Analysts bring their own Sigma rules and expect them to work. Zircolite and Chainsaw prove this is standard. | HIGH | Use pySigma to compile Sigma YAML to DuckDB SQL. Run compiled rules against ingested events. Must support custom rules, not just bundled ones. |
| **MITRE ATT&CK technique tagging** | Every SOC tool maps detections to ATT&CK. Analysts think in terms of techniques (T1059, T1053). Missing this makes the tool feel disconnected from the profession. | MEDIUM | Enrich Sigma hits and anomalies with ATT&CK technique IDs and tactic phases. Use the ATT&CK STIX dataset for lookups. Display in detection results. |
| **Timeline view of events** | Timeline reconstruction is the core DFIR activity. Timesketch, Velociraptor timelines, and every SIEM have this. | MEDIUM | Chronological event display with zoom, filter, and color-coding by severity/source. Must handle 10K+ events without lag. KronoGraph-style aggregation at high zoom levels. |
| **Evidence drilldown (finding to raw event)** | Analysts never trust summaries alone. They must be able to click a detection and see the exact raw log entry that triggered it. | LOW | Every detection/alert links back to the source event(s) by ID. Display raw JSON/fields in a side panel. |
| **Detection/alert list with severity** | A list of all findings, sortable by severity, is the analyst's triage queue. Without it, they have to manually search for problems. | LOW | Table of detections with: rule name, severity, ATT&CK technique, timestamp, affected entities. Sortable and filterable. |
| **IOC ingestion and matching** | Analysts bring IOC lists (hashes, IPs, domains, URLs) from threat intel feeds and expect to check them against local data. | LOW | Ingest IOC lists (CSV/STIX/plain text). Match against event fields. Flag hits. This is basic but mandatory. |
| **Export/report generation** | Analysts must produce artifacts for their team, management, or legal. Copy-paste from a UI is unacceptable. | LOW | Export detections, timelines, and AI answers as JSON, CSV, or Markdown. Printable summary report with findings and evidence. |
| **Case/session management** | Analysts work multiple investigations. They need to separate evidence and findings by case, not dump everything in one pool. | MEDIUM | Cases as first-class objects. Each case has its own ingested data, detections, notes, and AI conversation history. Cases can be archived and reopened. |

### Differentiators (Competitive Advantage)

These are what make this tool better than "grep + Kibana + ChatGPT in three browser tabs." They align with the project's core value: ask a question, get a grounded answer with a visual trace.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Local AI Q&A with evidence citations** | No other local desktop tool does this. Analysts ask natural language questions ("What did this process do after spawning PowerShell?") and get answers grounded in their actual evidence, with citations to specific events. This is the killer feature. | HIGH | RAG pipeline: embed ingested events and notes into Chroma, retrieve relevant chunks on query, prompt local LLM (via Ollama) with retrieved context, return answer with source citations. RAGIntel (2025) and RAGnarok (BSides LV 2025) validate this approach. Must show which events support each claim. |
| **Graph-based investigation surface** | Analysts think in graphs: "this process spawned that process which connected to this IP which resolved from this domain." No local desktop tool offers interactive graph exploration of attack chains. Enterprise tools (Cambridge Intelligence, Linkurious) charge thousands. | HIGH | Node-link graph with entity types: host, user, process, file, network connection, domain/IP, detection, ATT&CK technique. Click to expand, filter, highlight paths. Must handle 500+ nodes without performance issues. |
| **Full attack trace visualization** | The "aha moment": seeing origin to propagation to conclusion in one view. Combines timeline + graph + detections into a coherent narrative. Enterprise SOCs have this in products costing six figures. A local desktop version is genuinely novel. | HIGH | Requires graph + timeline + detection data all linked. Trace view shows: initial access event, lateral movement, persistence, exfiltration (or whatever the attack chain is), with each step linked to evidence. |
| **Contextual anomaly detection (not naive thresholds)** | Most open-source tools do threshold-based alerting ("more than 5 failed logins"). Contextual anomaly detection partitions by time, user, host, and activity type to reduce false positives. This is what separates a credible tool from a noisy one. | HIGH | Statistical baselines per context partition (user+host+hour, process+parent, network+destination). Flag deviations. Must be explainable -- show what the baseline was and why this event deviates. Isolation Forest or similar for point anomalies. |
| **AI-generated triage summaries** | When an analyst opens a case with 50 detections, getting a 3-paragraph summary of "what probably happened" saves 30+ minutes. No local tool does this. | MEDIUM | Feed top detections + timeline + entity graph into LLM prompt. Generate structured summary: what happened, what evidence supports it, what is uncertain, recommended next steps. Clearly marked as AI-generated, not ground truth. |
| **Prompt templates for analyst workflows** | Pre-built prompts for common tasks: "Explain this detection," "Summarize this timeline," "What ATT&CK techniques are present?", "Generate a Sigma rule for this pattern," "Draft an incident summary." Turns the LLM from a chatbot into a workflow tool. | LOW | Curated prompt templates with variable substitution (inject current case context, selected events, etc.). Analyst can also write freeform queries. |
| **Event clustering and relatedness scoring** | Automatically group related events (same process tree, same timeframe, same network destination) to reduce alert fatigue. Analysts currently do this manually in their heads. | MEDIUM | Cluster by shared entities (process ID, parent PID, network connection, user). Score relatedness. Present clusters as "investigation threads" rather than flat alert lists. |
| **Analyst notes with AI-aware context** | Notes the analyst writes become part of the RAG corpus. The AI knows what the analyst has already concluded. This creates a feedback loop unique to local tools (cloud tools cannot safely embed analyst notes into LLM context). | LOW | Store analyst notes in Chroma alongside event embeddings. Tag notes with case ID and entity references. AI queries retrieve relevant notes alongside events. |
| **Offline-first, zero-cloud architecture** | Privacy-sensitive environments (government, defense, critical infrastructure) cannot use cloud AI. A fully local tool that never phones home is a genuine differentiator for this audience. | LOW | This is an architecture choice, not a feature to build. But it must be verified and verifiable -- no telemetry, no cloud calls, no update checks that leak data. |

### Anti-Features (Deliberately NOT Build)

Features that seem appealing but would hurt the project's credibility, scope, or usability.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Autonomous response actions (kill process, block IP, quarantine file)** | "AI should fix the problem, not just find it." | Autonomous response from a desktop tool is dangerous, untested, and destroys analyst trust. One wrong automated kill-process on a production system ends the tool's credibility forever. The project explicitly scopes this out. | Human-in-the-loop only. Show recommended actions with evidence. Analyst decides and executes manually. Response automation is a later phase IF ever. |
| **Real-time continuous monitoring / live agent** | "It should watch my system 24/7 like an EDR." | EDR is a solved problem (CrowdStrike, Defender, SentinelOne). Building a competing agent is years of work and outside scope. Continuous monitoring also requires a service architecture that conflicts with desktop-tool simplicity. | Ingest snapshots and exports from existing EDR/osquery. Be the analysis brain, not the collection agent. osquery scheduled queries can feed periodic snapshots. |
| **Multi-tenant / multi-user collaboration** | "My team should all use this." | Collaboration requires authentication, authorization, conflict resolution, networking, and server infrastructure. This is a single-analyst desktop tool. Multi-user turns it into TheHive (which already exists and went commercial). | Single analyst, multiple cases. Export findings for sharing. If team collaboration is needed, recommend TheHive or DFIR-IRIS alongside this tool. |
| **Cloud log ingestion (AWS CloudTrail, Azure AD, GCP audit)** | "We need cloud visibility too." | Cloud log formats, authentication, API pagination, and volume are each their own project. This bloats scope massively and the tool loses its "local desktop" identity. | Support importing pre-downloaded cloud logs as JSON/CSV. The analyst exports from their cloud console and imports here. Parsing cloud-native formats is a future phase at most. |
| **Custom ML model training UI** | "Analysts should train their own models." | ML training requires data science expertise most analysts lack. A training UI creates false confidence in untrained models. The tool should ship with good defaults, not offload model quality to the user. | Pre-configured anomaly detection with tunable sensitivity thresholds. Analyst feedback (mark as false positive / true positive) improves baselines over time without requiring ML knowledge. |
| **Natural language to SQL/query generation** | "Let me query my data in English." | NL-to-SQL is unreliable, hallucinates WHERE clauses, and gives analysts false confidence in incorrect queries. When the query is wrong, the analyst does not know because they cannot read the generated SQL. | Provide structured search/filter UI with clear semantics. Use AI Q&A (RAG) for natural language questions -- this grounds answers in retrieved evidence rather than generating unverifiable queries. |
| **Plugin/extension marketplace** | "Make it extensible with community plugins." | Plugin systems require stable APIs, security sandboxing, versioning, documentation, and community management. This is premature for a v1 tool and will slow down core development. | Ship with good built-in capabilities. Use config files for customization (custom Sigma rules, IOC lists, prompt templates). Plugin architecture is a v3+ concern. |
| **Fancy dashboards with KPI metrics** | "Show me MTTD, MTTR, alert volume trends." | Dashboards are for SOC managers monitoring team performance. This tool is for a single analyst doing investigations. KPI dashboards add UI complexity without helping the analyst find threats. | Case-level statistics: how many detections, what severity distribution, timeline span. No organizational metrics. |

## Feature Dependencies

```
[Log Ingestion + Normalization]
    |
    +---> [Full-Text Search]
    |
    +---> [Sigma Rule Matching] ---> [ATT&CK Technique Tagging]
    |
    +---> [IOC Matching]
    |
    +---> [Timeline View]
    |
    +---> [Detection/Alert List]
    |         |
    |         +---> [Event Clustering] ---> [AI Triage Summaries]
    |
    +---> [Embedding into Chroma] ---> [AI Q&A with Citations]
    |                                       |
    |                                       +---> [Analyst Notes in RAG]
    |                                       |
    |                                       +---> [Prompt Templates]
    |
    +---> [Entity Extraction] ---> [Graph View] ---> [Full Attack Trace]

[Case Management] --enhances--> [all features above]

[Export/Reports] --requires--> [Detections + Timeline + AI Answers]
```

### Dependency Notes

- **Everything requires Log Ingestion**: No feature works without normalized event data. This is Phase 1 foundation.
- **Sigma Matching requires normalized schema**: Sigma rules assume field names. Schema must match pySigma backend expectations.
- **Graph View requires Entity Extraction**: Nodes come from extracted entities (processes, users, IPs, files). Entity extraction runs during ingestion normalization.
- **AI Q&A requires Embedding pipeline**: Events must be chunked and embedded into Chroma before RAG queries work.
- **Full Attack Trace requires Graph + Timeline + Detections**: This is the capstone feature combining three independent subsystems.
- **AI Triage Summaries require Detection List + AI Q&A**: Summaries feed detections into the LLM via the RAG pipeline.
- **Case Management enhances everything**: Cases provide scoping (which events, detections, notes belong to this investigation) but features work without it at reduced usability.

## MVP Definition

### Launch With (v1)

Minimum viable product -- what proves the concept works and is useful.

- [ ] **EVTX + JSON/CSV ingestion with normalization** -- without data, nothing works
- [ ] **Full-text search across events** -- first thing any analyst tries
- [ ] **Sigma rule matching with ATT&CK tagging** -- proves detection capability, earns analyst trust
- [ ] **Detection list with severity and drilldown** -- the triage queue
- [ ] **Timeline view** -- core DFIR workflow
- [ ] **Local AI Q&A with evidence citations** -- the differentiator; without this, it is just another log viewer
- [ ] **Basic case/session separation** -- analysts need to keep investigations apart

### Add After Validation (v1.x)

Features to add once core ingestion + detection + AI Q&A are proven.

- [ ] **Graph-based investigation surface** -- add when entity extraction pipeline is solid
- [ ] **Event clustering and relatedness scoring** -- add when detection volume reveals the alert fatigue problem
- [ ] **IOC list ingestion and matching** -- straightforward extension of the matching engine
- [ ] **Contextual anomaly detection** -- add when baseline data and analyst feedback establish what "normal" looks like
- [ ] **AI triage summaries** -- add when Q&A quality is validated and prompts are tuned
- [ ] **Prompt templates for analyst workflows** -- add as analysts discover repeated query patterns
- [ ] **Analyst notes integrated into RAG** -- add when the note-taking workflow exists

### Future Consideration (v2+)

Features to defer until the tool is proven useful.

- [ ] **Full attack trace visualization** -- capstone feature requiring graph + timeline + detections all working well
- [ ] **Export/report generation** -- valuable but not needed to validate the core concept
- [ ] **osquery live integration** -- requires osquery installation and scheduled query management
- [ ] **Process/network snapshot ingestion** -- extends telemetry beyond logs
- [ ] **Sigma rule authoring assistance via AI** -- generate Sigma rules from observed patterns

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| EVTX/JSON/CSV ingestion + normalization | HIGH | MEDIUM | P1 |
| Full-text search | HIGH | LOW | P1 |
| Sigma rule matching | HIGH | HIGH | P1 |
| ATT&CK technique tagging | HIGH | MEDIUM | P1 |
| Detection list with drilldown | HIGH | LOW | P1 |
| Timeline view | HIGH | MEDIUM | P1 |
| Local AI Q&A with citations | HIGH | HIGH | P1 |
| Case/session management | MEDIUM | MEDIUM | P1 |
| Graph investigation surface | HIGH | HIGH | P2 |
| Event clustering | MEDIUM | MEDIUM | P2 |
| IOC matching | MEDIUM | LOW | P2 |
| Contextual anomaly detection | HIGH | HIGH | P2 |
| AI triage summaries | MEDIUM | MEDIUM | P2 |
| Prompt templates | MEDIUM | LOW | P2 |
| Analyst notes in RAG | MEDIUM | LOW | P2 |
| Full attack trace | HIGH | HIGH | P3 |
| Export/reports | MEDIUM | LOW | P3 |
| osquery integration | MEDIUM | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch -- proves the concept
- P2: Should have, add iteratively after core works
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Zircolite/Chainsaw | Timesketch | DFIR-IRIS | OpenCTI | This Tool |
|---------|-------------------|------------|-----------|---------|-----------|
| EVTX parsing | Native strength | Via Plaso import | Via import | No | Native (P1) |
| Sigma matching | Core feature | No | No | No | Core feature (P1) |
| ATT&CK mapping | Output includes technique IDs | Manual tagging | Manual | STIX-based | Automatic on detection (P1) |
| Timeline view | No (CLI output) | Core strength | Basic | No | Core feature (P1) |
| Graph visualization | No | No | No | Relationship graph (TI-focused) | Core differentiator (P2) |
| AI Q&A with citations | No | No | No | AI summaries (cloud) | Core differentiator (P1) |
| Case management | No | Sketches (limited) | Full case management | No | Basic (P1), full (P2) |
| Anomaly detection | No | Analyzers (basic) | No | No | Contextual (P2) |
| Local/offline | Yes | Requires Elasticsearch server | Requires server stack | Requires server stack | Yes, fully local |
| Collaboration | No | Yes | Yes | Yes | No (single analyst, by design) |

**Key insight:** No existing tool combines Sigma matching + AI Q&A + graph visualization + timeline in a single local desktop application. Zircolite/Chainsaw are CLI-only detection tools. Timesketch and DFIR-IRIS require server infrastructure. OpenCTI is threat intelligence, not investigation. The gap this tool fills is real.

## Sources

- [Zircolite - Standalone SIGMA-based detection tool](https://github.com/wagga40/Zircolite) - EVTX + Sigma matching reference implementation
- [Chainsaw by WithSecure](https://github.com/WithSecureLabs/chainsaw) - Fast EVTX hunting with Sigma rules
- [SigmaHQ - Main Sigma Rule Repository](https://github.com/SigmaHQ/sigma) - Detection rule ecosystem
- [RAGnarok - BSides Las Vegas 2025](https://pretalx.com/security-bsides-las-vegas-2025/talk/LDTD3E/) - Local LLM + RAG for threat hunting (validates approach)
- [RAGIntel - RAG for cyber attack investigation](https://peerj.com/articles/cs-3371/) - Academic validation of RAG for grounded CTI analysis
- [Cambridge Intelligence - Cybersecurity Visualization](https://cambridge-intelligence.com/use-cases/cybersecurity/) - Graph + timeline visualization patterns
- [KronoGraph - Timeline Visualization](https://cambridge-intelligence.com/kronograph/) - Timeline aggregation and drill-down patterns
- [Timesketch - Forensic Timeline Analysis](https://vulntech.com/tutorial/tutorial/learn-digital-forensics/timesketch-forensic-timeline-analysis/) - Timeline feature reference
- [Velociraptor Documentation](https://docs.velociraptor.app/docs/overview/) - Endpoint forensics feature reference
- [DFIR-IRIS - Collaborative IR Platform](https://www.dfir-iris.org/) - Case management and investigation features
- [TheHive / StrangeBee](https://strangebee.com/thehive/) - Case management (now commercial, validates market)
- [OpenCTI by Filigran](https://filigran.io/platforms/opencti/) - Threat intelligence platform features
- [Dropzone AI SOC Tool Selection Guide](https://www.dropzone.ai/resource-guide/soc-tools-buyers-guide-2025) - SOC tool table stakes
- [SOC Analyst Tools - TCM Security](https://tcm-sec.com/soc-analyst-tools/) - Analyst tool expectations
- [2025 DFIR Tools Year in Review](https://bakerstreetforensics.com/2025/12/05/2025-year-in-review-open-source-dfir-tools-and-malware-analysis-projects/) - Current open-source DFIR landscape
- [DFIR Trends 2025 - Belkasoft](https://belkasoft.com/dfir-trends-2025) - Industry trends and AI integration

---
*Feature research for: Local AI-powered cybersecurity SOC/investigation platform*
*Researched: 2026-03-14*
