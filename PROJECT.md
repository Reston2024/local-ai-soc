\# PROJECT.md

\# Windows Desktop AI Cybersecurity Brain

\# Authoritative spec for Claude Code + GSD



\## 1. Mission



Build a \*\*Windows desktop-only, local-first AI cybersecurity brain\*\* that ingests host telemetry and analyst evidence, performs grounded retrieval and correlation, supports analyst Q\&A, and provides a \*\*visual end-to-end threat trace dashboard\*\*.



This system is for \*\*human-in-the-loop investigation and triage\*\*.

It must \*\*not\*\* autonomously block, quarantine, kill processes, alter firewall rules, or perform destructive response unless explicitly approved in a later phase.



The solution must be credible to experienced SecOps practitioners:

\- reproducible

\- modular

\- testable

\- explainable

\- locally operable

\- security-conscious

\- fast enough to use daily

\- designed to grow into a stronger SOC workstation without rework



This project is restricted to the \*\*Windows desktop AI brain only\*\*.

Do \*\*not\*\* scope-creep into the Linux collector, network appliance, or broader infrastructure unless a narrow desktop dependency requires it.



\---



\## 2. Non-Negotiable Constraints



1\. \*\*Windows desktop is the target host.\*\*

2\. \*\*Native Ollama on Windows\*\* is the primary local model runtime.

3\. \*\*Localhost HTTPS is already provided via Docker\*\* and must be preserved.

4\. Any containerized service that must reach native Ollama should prefer:

&#x20;  - `http://host.docker.internal:11434`

&#x20;  unless a better verified local path is proven.

5\. The system must include \*\*visual threat tracing end-to-end\*\*.

6\. Backend and UI are a \*\*single release surface\*\* and must be delivered together.

7\. No silent downscoping, no “minimal placeholder MVP” disguised as finished work.

8\. No unverifiable claims. Every major capability must have a test, receipt, or artifact.

9\. Prefer the \*\*smallest architecture that still looks serious\*\* to blue-team professionals.

10\. Avoid unnecessary enterprise sprawl.



\---



\## 3. Standards Alignment



Use these as actual design anchors, not decorative references:



\- \*\*NIST CSF 2.0\*\* for govern / identify / detect / respond thinking

\- \*\*NIST AI RMF 1.0\*\* for AI risk, traceability, explainability, and governance

\- \*\*NIST SP 800-61\*\* concepts for incident handling workflow

\- \*\*OWASP ASVS\*\* for local web app / API security controls where applicable

\- \*\*MITRE ATT\&CK\*\* for enrichment, technique mapping, and investigation context

\- \*\*Sigma\*\* ecosystem for portable detections and hunting content

\- \*\*CIS-style Windows hardening assumptions\*\* where relevant to deployment choices



When you make an architectural choice, map it to the applicable standard or control logic.



\---



\## 4. Ground Truth from Project Knowledge



Design choices must reflect the following validated project facts:



\- The user wants a \*\*Windows desktop AI brain\*\* as the active priority.

\- The user wants a \*\*visual dashboard that can trace threats end-to-end\*\*.

\- Localhost HTTPS is already handled through Docker on this project.

\- The user wants a system that can leverage strong open-source repos and modern local-model tooling.

\- The user wants industry-standard practices, strong verification, and no fake simplifications.



Technical grounding from source materials:



\- Cyber anomaly detection must account for \*\*point, group/collective, and contextual anomalies\*\*, not naive one-dimensional thresholding. :contentReference\[oaicite:1]{index=1}

\- Context is critical; anomalies must be evaluated relative to \*\*time, location, team, activity, and relation context\*\*, otherwise false positives become frivolous. :contentReference\[oaicite:2]{index=2}

\- Spatial / temporal anomaly detection depends on correct \*\*partitioning / neighborhood discovery\*\*, not just raw clustering. :contentReference\[oaicite:3]{index=3}

\- Graph-based cybersecurity analysis is valuable for \*\*communication graphs, attack graphs, threat similarity, and threat propagation\*\*, which supports the visual trace requirement. :contentReference\[oaicite:4]{index=4}

\- Deep learning can improve accuracy and reduce false positives, but only when data volume, tuning, and explainability are handled properly; it is not automatically the right first tool. :contentReference\[oaicite:5]{index=5}

\- In cyber analytics, many detections are \*\*exploratory and investigative\*\*, helping narrow the search space rather than “proving” attacks with certainty. :contentReference\[oaicite:6]{index=6}

\- On Windows, Dockerized GPU workflows commonly route through \*\*WSL2 / Linux VM mechanics\*\*, so keep native-vs-container decisions practical. :contentReference\[oaicite:7]{index=7}



Treat these as first principles for the implementation.



\---



\## 5. Required Outcome



Deliver a \*\*local Windows desktop cybersecurity analysis platform\*\* with these major capabilities:



\### A. Local AI / Retrieval

\- Local LLM serving via \*\*Ollama\*\*

\- Grounded retrieval over desktop-accessible cybersecurity content, notes, rules, and case artifacts

\- Prompt templates for:

&#x20; - analyst Q\&A

&#x20; - triage

&#x20; - threat hunt

&#x20; - incident summary

&#x20; - evidence explanation

\- Output must cite supporting local evidence in the app itself



\### B. Telemetry / Evidence Ingestion

Ingest and normalize desktop-relevant sources such as:

\- EVTX-derived exports or structured Windows log exports

\- JSON / CSV / NDJSON

\- osquery results

\- process / network snapshots

\- Sigma rules

\- analyst notes

\- evidence bundles

\- malware / IOC / URL / hash lists

\- case metadata



Normalization must preserve:

\- timestamp

\- host

\- user

\- process

\- file

\- network connection

\- detection source

\- ATT\&CK mapping if available

\- provenance

\- confidence / severity if present



\### C. Detection / Correlation

Support:

\- contextual anomaly logic

\- event clustering / relatedness

\- aggregation of related alerts

\- Sigma-based hunting / detection ingestion

\- ATT\&CK enrichment where useful

\- explainable correlations with evidence pointers



Do not spam simplistic alerts.

Favor \*\*correlated, contextual, analyst-usable findings\*\*.



\### D. Visual Investigation Surface

This is first-class, not optional.



Provide a local browser-based dashboard that supports:

\- graph / node-link view

\- timeline view

\- evidence panel

\- detection panel

\- search / filter / pivot

\- drilldown from finding → raw evidence

\- trace from origin → propagation / related entities → analyst conclusion



Required node / entity types:

\- host

\- user

\- process

\- file

\- network connection

\- domain / URL / IP

\- detection

\- evidence artifact

\- incident / case

\- ATT\&CK technique where justified



\### E. Security / Operations

\- preserve localhost HTTPS

\- externalize secrets

\- no hardcoded credentials

\- reproducible setup

\- startup / shutdown scripts

\- smoke tests

\- logs for backend and ingestion jobs

\- restore / rebuild documentation



\---



\## 6. Repo and Component Selection Mandate



You must evaluate existing open-source components and integrate the best ones instead of rewriting commodity layers.



\### Must evaluate immediately



\#### Primary workflow / runtime

\- `glittercowboy/get-shit-done`

\- `ollama/ollama`



\#### UI / orchestration / retrieval

\- `open-webui/open-webui`

\- `langchain-ai/langgraph`

\- `chroma-core/chroma`



\#### Telemetry / detection

\- `osquery/osquery`

\- `Velocidex/velociraptor`

\- `SigmaHQ/sigma`

\- `SigmaHQ/pySigma`

\- `SigmaHQ/sigma-cli`



\#### Optional / only if justified

\- `wazuh/wazuh`

\- graph DB alternatives

\- Timesketch / Plaso style approaches

\- lightweight local graph visualization libs

\- local case management components



\### Current repository facts to honor

\- GSD is a spec-driven system for Claude Code that starts with `/gsd:new-project`, produces `PROJECT.md`, `ROADMAP.md`, `STATE.md`, phase plans, and atomic execution tasks. :contentReference\[oaicite:8]{index=8}

\- Ollama provides a local REST API on `localhost:11434` and supports Windows installs plus local model management. :contentReference\[oaicite:9]{index=9}

\- Open WebUI explicitly documents deployment against local Ollama and uses `host.docker.internal` in the recommended Docker path. :contentReference\[oaicite:10]{index=10}

\- osquery is a Windows-capable SQL-powered host instrumentation framework. :contentReference\[oaicite:11]{index=11}

\- SigmaHQ provides a large portable rule corpus and official spec / conversion ecosystem via pySigma and sigma-cli. :contentReference\[oaicite:12]{index=12}



\### Decision rule

For each candidate, classify it as:

\- \*\*use now\*\*

\- \*\*defer\*\*

\- \*\*reject\*\*



For each classification, explain:

\- what problem it solves

\- why it beats simpler alternatives

\- performance impact

\- security impact

\- operational burden

\- integration plan

\- rollback path



Do not include tools just because they are popular.

Choose the \*\*leanest strong stack\*\*.



\---



\## 7. Model Strategy



Select models only after inspecting actual desktop hardware.



Initial candidates to evaluate:

\- a general local reasoning / analyst model available through Ollama

\- a coding / automation-capable local model if clearly useful

\- a local embedding model for retrieval



Selection criteria:

\- Windows compatibility

\- latency

\- VRAM / RAM footprint

\- context length

\- licensing

\- retrieval usefulness

\- operational simplicity

\- evidence-grounded output quality



Do not blindly choose the largest model.

Usability matters more than bragging rights.



\---



\## 8. Preferred Architecture Bias



Unless the environment inspection disproves it, bias toward this architecture:



\### Host-native

\- Ollama on native Windows

\- local project repo

\- local Python backend

\- local Node / frontend stack if needed

\- native filesystem for evidence / fixtures / exports



\### Containerized only where it clearly helps

\- localhost HTTPS / reverse proxy

\- optional Open WebUI

\- optional supporting services with clear reproducibility gains



\### Storage bias

Choose the smallest set of stores that still serves the mission:

\- structured event/evidence store: SQLite or DuckDB first

\- vector retrieval: Chroma or equivalent

\- graph representation:

&#x20; - start with a relational + derived graph approach or lightweight graph layer

&#x20; - only use heavier graph infrastructure if justified by real need



Do not introduce Postgres, Neo4j, Wazuh, Kafka, Elastic, or similar unless you prove they are worth the complexity on this desktop.



\---



\## 9. Engineering Rules



1\. Inspect the environment first:

&#x20;  - Windows version

&#x20;  - CPU

&#x20;  - RAM

&#x20;  - GPU / VRAM

&#x20;  - available disk

&#x20;  - Docker Desktop / WSL status

&#x20;  - Ollama status

&#x20;  - Python, Node, Git availability



2\. Then produce:

&#x20;  - architecture

&#x20;  - decision log

&#x20;  - threat model

&#x20;  - roadmap

&#x20;  - definition of done

&#x20;  - phase plan



3\. Then implement in phases.



4\. Every phase must include:

&#x20;  - exact files changed

&#x20;  - exact commands run

&#x20;  - expected outputs

&#x20;  - validation steps

&#x20;  - rollback notes



5\. Never claim something works until it is locally verified.



6\. Never silently remove requested functionality.



7\. If a lighter and heavier design both work, prefer the lighter one unless the heavier one materially improves:

&#x20;  - analyst utility

&#x20;  - evidence traceability

&#x20;  - performance

&#x20;  - maintainability



\---



\## 10. Mandatory Deliverables



Create and maintain at minimum:



\- `PROJECT.md`

\- `ARCHITECTURE.md`

\- `ROADMAP.md`

\- `STATE.md`

\- `DECISION\_LOG.md`

\- `THREAT\_MODEL.md`

\- `README.md`

\- `REPRODUCIBILITY\_RECEIPT.md`



And the implementation tree:



\- `/backend`

\- `/dashboard`

\- `/ingestion`

\- `/detections`

\- `/correlation`

\- `/graph`

\- `/prompts`

\- `/scripts`

\- `/config`

\- `/tests`

\- `/fixtures`



\---



\## 11. Required Repo Shape



Target something close to this unless inspection shows a better layout:



```text

.

├─ PROJECT.md

├─ ARCHITECTURE.md

├─ ROADMAP.md

├─ STATE.md

├─ DECISION\_LOG.md

├─ THREAT\_MODEL.md

├─ README.md

├─ REPRODUCIBILITY\_RECEIPT.md

├─ backend/

│  ├─ api/

│  ├─ services/

│  ├─ models/

│  ├─ storage/

│  └─ security/

├─ dashboard/

│  ├─ app/

│  ├─ components/

│  ├─ views/

│  └─ lib/

├─ ingestion/

│  ├─ parsers/

│  ├─ normalizers/

│  ├─ jobs/

│  └─ connectors/

├─ detections/

│  ├─ sigma/

│  ├─ anomaly/

│  └─ enrichment/

├─ correlation/

├─ graph/

├─ prompts/

├─ scripts/

├─ config/

├─ tests/

└─ fixtures/

