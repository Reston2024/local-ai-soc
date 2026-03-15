# Pitfalls Research

**Domain:** Local Windows Desktop AI Cybersecurity Investigation Platform
**Researched:** 2026-03-14
**Confidence:** HIGH (multiple primary sources verified per pitfall)

## Critical Pitfalls

### Pitfall 1: RTX 5080 Blackwell CUDA Incompatibility with Ollama

**What goes wrong:**
Ollama fails to use the GPU at all, falling back silently to CPU-only inference. Alternatively, vision/multimodal inference crashes with `cudaMemcpyAsyncReserve` errors specific to Blackwell's compute capability 12.0 (sm_120). Text inference may work while image/vision inference crashes. Multiple confirmed issues exist: GPU detection failures, CPU fallback without error messages, and CUDA "invalid argument" errors on RTX 5080 specifically.

**Why it happens:**
Blackwell (sm_120 / compute capability 12.0) is a new architecture. Ollama bundles its own CUDA dependencies, but these may target older compute capabilities. The CUDA kernels compiled for Ampere/Ada Lovelace do not execute on Blackwell silicon without recompilation. Additionally, if the system has an AMD iGPU alongside the NVIDIA GPU, Ollama's ROCm detection logic incorrectly triggers CPU fallback even when a valid NVIDIA GPU exists.

**How to avoid:**
1. Use Ollama version 0.13+ (or latest available) -- earlier versions had Blackwell regressions confirmed after November 2025.
2. Install NVIDIA Studio Drivers (not Game Ready) directly from nvidia.com -- Studio drivers receive more compute/professional workload testing.
3. Perform a clean driver installation (Custom Install > Clean Installation checkbox) to eliminate driver component mismatches.
4. Verify CUDA 12.8+ is available (supports all recent GPU architectures including Blackwell).
5. After installing Ollama, immediately run `ollama run llama3.2:1b` and check `nvidia-smi` to confirm GPU layers are loaded -- do not proceed if inference runs on CPU.
6. Set `CUDA_VISIBLE_DEVICES=0` explicitly if any iGPU is present to force Ollama to the discrete GPU.

**Warning signs:**
- `ollama ps` shows 0 GPU layers loaded.
- Inference is abnormally slow (CPU speed instead of GPU speed).
- `nvidia-smi` shows 0% GPU utilization during inference.
- Ollama logs contain "no compatible GPU found" or similar without an explicit error.

**Phase to address:** Phase 1 (Ollama installation). This is a day-one blocker. If GPU acceleration does not work, the entire project's inference performance premise fails. Validate before writing any other code.

**Sources:**
- [Ollama Issue #14446 - Vision crashes on RTX 5080 Blackwell](https://github.com/ollama/ollama/issues/14446)
- [Ollama Issue #11849 - RTX 5080 CPU fallback with AMD iGPU](https://github.com/ollama/ollama/issues/11849)
- [Ollama Issue #13163 - RTX 5070 Ti GPU not detected](https://github.com/ollama/ollama/issues/13163)
- [Ollama Hardware Support Docs](https://docs.ollama.com/gpu)
- [Blackwell CUDA Error Fix Guide](https://apatero.com/blog/blackwell-gpu-cuda-errors-fix-troubleshooting-guide-2025)

---

### Pitfall 2: LLM Hallucination on Security Evidence -- Fabricated IOCs and False Correlations

**What goes wrong:**
The LLM generates plausible-sounding but fabricated indicators of compromise (IOCs), invents file paths that do not exist in ingested evidence, attributes ATT&CK techniques without supporting data, or creates correlations between events that have no actual relationship. In a cybersecurity investigation context, this is not merely annoying -- it actively misleads analysts, wastes investigation time, and can cause real threats to go undetected while resources chase phantom leads.

**Why it happens:**
LLMs are probabilistic text generators. They will confidently produce output that "looks right" for cybersecurity analysis even when no supporting evidence exists in the retrieval context. RAG reduces but does not eliminate hallucination. Specific failure modes: (a) the retrieval step returns topically related but not answer-relevant chunks, (b) the prompt does not constrain the model to only use provided context, (c) too much context dilutes the relevant passage, (d) token limits cause truncation that removes critical evidence.

**How to avoid:**
1. Every LLM response must include explicit source citations pointing to specific ingested evidence records (event IDs, log lines, document references). If the model cannot cite a source, the response must say "insufficient evidence."
2. System prompts must contain hard constraints: "Answer ONLY based on the provided context. If the context does not contain relevant information, state that explicitly. Do NOT speculate or infer beyond what the evidence shows."
3. Implement a citation verification layer: after the LLM generates a response with citations, programmatically verify that each cited record exists in the database and that the quoted content matches.
4. Display a confidence indicator on every LLM response in the UI. Use retrieval similarity scores (from Chroma) as a proxy -- low similarity scores should trigger visible "low confidence" warnings.
5. Never auto-execute decisions based on LLM output. The UI must present findings for analyst review, not trigger automated responses.

**Warning signs:**
- LLM responses reference specific file paths, registry keys, or IP addresses not present in any ingested data.
- Responses contain ATT&CK technique IDs that do not map to any detection rule or event in the system.
- Analysts report "the AI said X but I cannot find the supporting evidence."
- Citation links lead to records that do not contain the quoted information.

**Phase to address:** Phase 1 (prompt template design) and Phase 3 (RAG pipeline). The prompt constraints must be baked in from the first `/query` endpoint. The citation verification layer should be built alongside the RAG pipeline.

**Sources:**
- [ScienceDirect - Hallucinations in AI-driven Cybersecurity Systems](https://www.sciencedirect.com/science/article/abs/pii/S0045790625002502)
- [Aryaka - AI Hallucinations in Cybersecurity](https://www.aryaka.com/blog/ai-hallucinations-in-cybersecurity/)
- [IronCore Labs - Security Risks with RAG](https://ironcorelabs.com/security-risks-rag/)
- [USENIX - Package Hallucinations](https://www.usenix.org/publications/loginonline/we-have-package-you-comprehensive-analysis-package-hallucinations-code)

---

### Pitfall 3: Docker-to-Native-Ollama Bridge Failures on Windows

**What goes wrong:**
Containerized services (Caddy reverse proxy, Open WebUI, or any future Docker-based component) cannot reach the native Ollama instance running on the Windows host. Connection refused errors occur even though Ollama is running and accessible from the host. The system appears configured correctly but silently fails.

**Why it happens:**
Ollama by default binds to `127.0.0.1:11434`, which means it only accepts connections from the loopback interface. Docker containers on Windows resolve `host.docker.internal` to a different interface (typically a virtual Ethernet adapter), so Ollama refuses the connection even though DNS resolution succeeds. Additional complications: IPv6 resolution of `localhost` when Ollama listens on IPv4 only; WSL2 uses yet another virtual network interface that differs from Docker Desktop's.

**How to avoid:**
1. Set `OLLAMA_HOST=0.0.0.0` as a Windows system environment variable before starting Ollama. This makes Ollama listen on all interfaces. A restart of Ollama is required after changing this.
2. Also set `OLLAMA_ORIGINS=*` to allow cross-origin requests from containerized web UIs.
3. In Docker Compose files, always use `http://host.docker.internal:11434` as the Ollama URL, never `localhost` or `127.0.0.1`.
4. Create a startup validation script that tests connectivity from inside a Docker container to the Ollama endpoint before declaring the system "ready."
5. If using WSL2 alongside Docker Desktop, be aware that WSL2's network interface IP differs from Docker's `host.docker.internal` -- do not mix them.

**Warning signs:**
- `curl http://host.docker.internal:11434` from inside a container returns "Connection refused."
- Ollama works from the Windows host but not from any container.
- Intermittent connectivity that seems to resolve after Windows network changes.

**Phase to address:** Phase 1 (infrastructure setup). This must be validated in the same phase where Ollama is installed, before any dependent services are built.

**Sources:**
- [Open WebUI - Connection Error Troubleshooting](https://docs.openwebui.com/troubleshooting/connection-error/)
- [Ollama Issue #5041 - Windows internal network connection refused](https://github.com/ollama/ollama/issues/5041)
- [Ollama Issue #3652 - Docker container cannot connect](https://github.com/ollama/ollama/issues/3652)

---

### Pitfall 4: Sigma Rule Silent Failures -- Rules Convert but Match Nothing

**What goes wrong:**
Sigma rules are converted to SQL queries via pySigma but produce zero matches against ingested log data, even when the logs clearly contain the events the rules describe. The conversion succeeds without errors, the queries execute without errors, but nothing is detected. This is the most insidious failure mode because it is completely silent -- you believe you have detection coverage when you have none.

**Why it happens:**
Three root causes: (a) Field name mismatch -- Sigma rules use canonical field names (e.g., `TargetUserName`, `Image`, `CommandLine`) but your ingested logs use different field names depending on the log source and normalization. Without a proper processing pipeline, the converted SQL queries reference columns that do not exist in your DuckDB tables. (b) Value representation differences -- Sigma rules may expect `HKLM\...` while your logs store `HKEY_LOCAL_MACHINE\...`, or path separators differ. (c) Log source mapping gaps -- Sigma's `logsource` category/product/service triplet must map to your specific log tables, and this mapping is not automatic.

**How to avoid:**
1. Build a field mapping processing pipeline before converting any rules. Map every Sigma canonical field name to your normalized DuckDB schema columns. This is the single most important step.
2. Use `--fail-unsupported` (not `--skip-unsupported`) during development so you see exactly which rules cannot convert, rather than silently dropping them.
3. Create a "Sigma smoke test" suite: pick 5-10 well-understood rules (e.g., Mimikatz execution, suspicious PowerShell), manually craft log entries that should trigger them, ingest those test entries, and verify the converted queries match. If any fail, your field mapping is wrong.
4. No pySigma DuckDB backend is mature/official yet. You will likely need to build or adapt one using the SQL backend base class and the Cookiecutter template. Budget time for this -- it is custom engineering, not configuration.
5. Aggregate function rules (e.g., `count() > 5`) are deprecated in pySigma and will not convert. Plan alternative detection logic for frequency-based rules.

**Warning signs:**
- Converted queries run without error but return 0 rows against known-bad test data.
- The number of converted rules is significantly lower than the number of input rules (many silently skipped).
- Field names in converted SQL do not appear in your DuckDB table schemas.
- No detection fires for days after deployment despite active system usage.

**Phase to address:** Phase 2 (telemetry ingestion schema design) and Phase 3 (detection/correlation). The schema must be designed with Sigma field mapping in mind. The smoke test suite should be built as part of detection implementation.

**Sources:**
- [pySigma Processing Pipelines Documentation](https://sigmahq-pysigma.readthedocs.io/en/latest/Processing_Pipelines.html)
- [pySigma Backends Documentation](https://sigmahq-pysigma.readthedocs.io/en/latest/Backends.html)
- [dogesec - Introduction to pySigma](https://www.dogesec.com/blog/beginners_guide_to_using_sigma_cli_pysigma/)
- [Sigma Detection Format - Backends](https://sigmahq.io/docs/digging-deeper/backends)

---

### Pitfall 5: Graph Visualization Hairball -- Unusable Node-Link Diagrams

**What goes wrong:**
The graph view becomes an incomprehensible tangle of overlapping nodes and crossing edges as soon as real investigation data is loaded. A single incident involving 50+ processes, network connections, files, and users produces a visual mess that is worse than useless -- it actively impedes understanding. The Microsoft Sentinel Investigation Graph is a well-known example of a security graph visualization whose usability remains "unproven" according to researchers.

**Why it happens:**
Security investigation data is inherently dense: one compromised host generates hundreds of process creations, each connecting to files and network endpoints. Naive force-directed layouts treat all nodes and edges equally, producing the classic "hairball." Developers build the graph to show all data rather than designing for the analyst's workflow. The visualization is optimized for data completeness rather than investigative utility.

**How to avoid:**
1. Design for workflow, not raw data: start with a single focal entity (the suspicious process, the alert, the IOC) and let the analyst expand outward. Never render the full graph on initial load.
2. Implement progressive disclosure: show 1-hop neighbors by default, let analysts click to expand to 2-hop, 3-hop. Each expansion should be a deliberate analyst action.
3. Use visual aggregation: collapse 50 child processes of svchost.exe into a single "svchost (50 children)" node. Let the analyst expand it only if relevant.
4. Implement entity type filtering: let analysts toggle visibility of entity types (hide all "file" nodes to focus on process-to-network relationships).
5. Use hierarchical or dagre layouts for temporal/causal chains (process trees), not force-directed. Force-directed is appropriate for relationship discovery; hierarchical is better for process execution chains.
6. Set hard limits: never render more than ~100 visible nodes at once. If the query returns more, aggregate or paginate.

**Warning signs:**
- Layout computation takes more than 2 seconds (graph is too large for the rendering approach).
- Analysts zoom in/out repeatedly without finding useful structure (layout is not conveying information).
- Analysts revert to text search instead of using the graph (the graph is not adding value).
- Demo looks great with 10 nodes; real data with 200 nodes is unreadable.

**Phase to address:** Phase 4 (visual investigation surface). This requires careful UX design work, not just dropping a graph library into the page. Prototype with realistic data volumes (hundreds of events from a real investigation), not toy examples.

**Sources:**
- [Cambridge Intelligence - Fixing Data Hairballs](https://cambridge-intelligence.com/how-to-fix-hairballs/)
- [Springer Open - Graph-based Visual Analytics for CTI](https://cybersecurity.springeropen.com/articles/10.1186/s42400-018-0017-4)
- [Cambridge Intelligence - Cybersecurity Graph Visualization](https://cambridge-intelligence.com/use-cases/cybersecurity/)
- [ResearchGate - Grooming the Hairball](https://www.researchgate.net/publication/281050201_Grooming_the_hairball_-_how_to_tidy_up_network_visualizations)

---

### Pitfall 6: Naive Anomaly Detection via Static Thresholds

**What goes wrong:**
The system flags "more than N failed logins" or "process created more than N child processes" as anomalous, generating massive false positive volumes that analysts learn to ignore. The detection system becomes an alert factory that destroys analyst trust within the first week of operation.

**Why it happens:**
Static thresholds are the easiest detection logic to implement and demo. They feel like "real detection." But they ignore context entirely: 50 failed logins from a service account running automated tests is normal; 3 failed logins from a user account at 3 AM on a Sunday is suspicious. Without contextual partitioning (time, user role, host function, historical baseline), every threshold produces unacceptable false positive rates.

**How to avoid:**
1. Implement contextual anomaly detection from the start. Partition by: time-of-day/day-of-week, user/account type, host role/function, historical baseline for that specific entity.
2. Use point anomalies (single unusual event), collective anomalies (group of events that are individually normal but collectively suspicious), and contextual anomalies (normal event in an unusual context) as the detection taxonomy -- per PROJECT.md requirements.
3. Start with explainable statistical methods (z-score relative to entity baseline, IQR) rather than black-box ML. Analysts need to understand WHY something was flagged.
4. Every detection must include an evidence chain: "This was flagged because X happened Y times, which is Z standard deviations above the baseline for this user/host during this time window."
5. Implement a feedback mechanism: analysts can mark detections as true/false positive, and this feeds back into baseline calculations.

**Warning signs:**
- More than 100 alerts per day on a single-desktop system (too many to review).
- Analysts stop checking the detection panel (alert fatigue).
- The same type of alert fires repeatedly for the same entity with no variation.
- Detection logic uses hardcoded numeric thresholds without entity-specific baselines.

**Phase to address:** Phase 3 (detection/correlation). The detection engine must be designed with contextual awareness from the beginning. Retrofitting context onto a threshold-based system is a near-complete rewrite.

**Sources:**
- PROJECT.md requirements (contextual anomaly detection, not naive thresholding)
- [Springer Open - Graph-based Visual Analytics for CTI](https://cybersecurity.springeropen.com/articles/10.1186/s42400-018-0017-4)

---

### Pitfall 7: DuckDB Concurrency Deadlocks Under FastAPI

**What goes wrong:**
The FastAPI backend freezes under moderate concurrent load -- no error messages, no exceptions, the process simply stops responding. This happens during stress testing or when multiple browser tabs hit the API simultaneously. The application appears to hang permanently.

**Why it happens:**
DuckDB enforces single-writer semantics: only one transaction can write at a time. While multiple concurrent readers are fine, if the ingestion pipeline is writing events while an analyst's API request also attempts a write (e.g., saving a note, updating case metadata), the second writer blocks. Under FastAPI with async workers, this blocking can deadlock the entire event loop because DuckDB's Python driver blocks the thread.

**How to avoid:**
1. Separate read and write connection patterns: use a dedicated write connection (single writer) and a pool of read-only connections for API queries. Never share a single connection across async FastAPI handlers.
2. Initialize the DuckDB connection at application startup and reuse it -- do not create connections per-request.
3. Route all writes through a single-threaded write queue (Python `asyncio.Queue` or similar). Ingestion jobs and API write operations both submit to this queue; a single consumer processes writes sequentially.
4. For the API read path, use `duckdb.connect(database='path.duckdb', read_only=True)` connections which can operate concurrently without contention.
5. Run FastAPI with a single worker for the initial build. Multiple workers with in-process DuckDB will each have their own database state and cause consistency issues.

**Warning signs:**
- API responses intermittently hang for 30+ seconds during data ingestion.
- Locust or similar load testing causes the FastAPI process to become unresponsive.
- DuckDB logs show "could not set lock" or write timeout errors.
- Multiple uvicorn workers produce inconsistent query results.

**Phase to address:** Phase 1 (backend architecture) and Phase 2 (ingestion pipeline). The connection management pattern must be established before any write-heavy operations are built.

**Sources:**
- [DuckDB Concurrency Documentation](https://duckdb.org/docs/stable/connect/concurrency)
- [DuckDB Discussion #13719 - FastAPI Concurrency](https://github.com/duckdb/duckdb/discussions/13719)
- [Orchestra - DuckDB Concurrent Writes](https://www.getorchestra.io/guides/is-duckdb-safe-for-concurrent-writes)

---

### Pitfall 8: ChromaDB Version Instability and Breaking Migrations

**What goes wrong:**
A ChromaDB upgrade destroys your vector store data or breaks LangChain/embedding integrations. The official migration tools fail on Python 3.14. Your carefully built RAG pipeline stops working after what appeared to be a routine dependency update.

**Why it happens:**
ChromaDB has undergone several breaking storage backend changes: DuckDB backend (pre-0.4), SQLite backend (0.4.x), schema changes (0.5.x), and the 1.x rewrite. Each migration is irreversible. The migration tooling itself depends on old DuckDB versions that do not build on Python 3.13+. LangChain's Chroma wrapper aggressively calls embedding backends during operations where you do not expect it, causing failures during migrations.

**How to avoid:**
1. Pin ChromaDB to a specific version in your requirements and do not upgrade without explicit testing. Use `chromadb==1.5.3` (latest as of March 2026, with Python 3.14 support and pydantic v1 compat layer removed).
2. Build an export/import mechanism from day one: a script that dumps all collections to JSON (documents, metadatas, embeddings, IDs) and can restore them. This is your insurance against any future migration issue.
3. Do not use LangChain's Chroma wrapper -- interact with ChromaDB directly via its Python client. The LangChain wrapper adds an abstraction layer that breaks independently of ChromaDB itself and re-embeds documents unexpectedly.
4. Store your embedding model identifier alongside the vector data so you know exactly which model produced each embedding. If you ever change embedding models, you must re-embed everything -- partial re-embedding produces garbage similarity scores.
5. Test ChromaDB with Python 3.14 specifically before committing. The 1.5.3 release explicitly added 3.14 support.

**Warning signs:**
- `pip install chromadb` pulls a different major version than expected.
- Import errors mentioning pydantic, DuckDB, or SQLite after upgrading.
- Embedding similarity scores suddenly drop for queries that previously worked.
- LangChain wrapper errors about "mismatched embedding dimensions."

**Phase to address:** Phase 1 (dependency pinning and initial setup) and Phase 2 (RAG pipeline). Pin the version immediately; build the export/import safety net alongside the first collection creation.

**Sources:**
- [When Your ChromaDB Mutates and You're Out of Luck](https://wwakabobik.github.io/2025/11/migrating_chroma_db/)
- [ChromaDB Migration Documentation](https://docs.trychroma.com/docs/overview/migration)
- [ChromaDB Changelog](https://www.trychroma.com/changelog)

---

### Pitfall 9: Python 3.14 Compatibility Breakage with Security/ML Libraries

**What goes wrong:**
Key dependencies fail to install or crash at runtime on Python 3.14. PyO3-based libraries (including pydantic-core) fail to build. Libraries relying on annotation introspection break due to PEP 649's deferred evaluation. C extension modules compiled for older Python ABIs produce segfaults or import errors.

**Why it happens:**
Python 3.14 introduced PEP 649 (deferred evaluation of annotations), PEP 765 (SyntaxWarning for control flow in finally blocks), and C API changes that break native extension modules. The security and ML library ecosystem typically lags 3-6 months behind new Python releases. PyO3 (the Rust-Python bridge used by pydantic-core, many crypto libraries) required updates for 3.14 compatibility.

**How to avoid:**
1. Before committing to Python 3.14, test every critical dependency: `pySigma`, `chromadb`, `duckdb`, `fastapi`, `pydantic`, `evtx` (pyevtx-rs), `sentence-transformers`, and any embedding model libraries.
2. Have Python 3.12 or 3.13 available as a fallback via `uv` -- you can create a venv with a specific Python version if 3.14 proves incompatible with a critical library.
3. Use `uv pip compile` to generate a lockfile and verify all dependencies resolve before starting development.
4. Watch for runtime errors, not just install errors. PEP 649's deferred annotations can cause libraries that install successfully to crash when type annotations are evaluated at runtime.

**Warning signs:**
- `pip install` or `uv pip install` fails with build errors mentioning PyO3, Rust, or C compilation.
- Import errors at runtime mentioning `__annotations__`, `get_type_hints`, or `typing.get_args`.
- FastAPI/Pydantic model validation fails with cryptic errors about type resolution.
- Libraries install but produce `DeprecationWarning` or `SyntaxWarning` on import.

**Phase to address:** Phase 0 / Pre-Phase 1. Validate the full dependency stack on Python 3.14 before writing any project code. If critical libraries fail, fall back to 3.12 or 3.13 immediately rather than fighting compatibility issues throughout the project.

**Sources:**
- [Astral Blog - Python 3.14](https://astral.sh/blog/python-3.14)
- [Python 3.14 What's New](https://docs.python.org/3/whatsnew/3.14.html)
- [PyO3 Issue #5000 - Python 3.14 Incompatibility](https://github.com/PyO3/pyo3/issues/5000)
- [Hacker News - Breaking Changes in Python 3.14](https://news.ycombinator.com/item?id=46319463)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skipping Sigma field mapping pipeline | Faster initial rule ingestion demo | Silent detection failures in production; complete rework when rules miss real threats | Never -- even a minimal mapping is better than none |
| Using LangChain for ChromaDB access | Faster initial RAG prototype | Wrapper breaks independently of ChromaDB; hides important configuration; prevents direct access to ChromaDB features | Never for this project -- the direct client is not much harder |
| Hardcoded detection thresholds | Quick "working" detection demo | Alert fatigue, analyst distrust, complete detection logic rewrite | Only in a throwaway prototype that is explicitly deleted before Phase 3 |
| Single DuckDB connection shared across async handlers | Simpler connection management | Deadlocks under concurrent load, data corruption risk | Only during initial single-developer testing, must be fixed before any multi-user scenario |
| Storing embeddings without model version metadata | Faster initial vector store setup | Cannot safely change embedding models; silent degradation of retrieval quality | Never -- one extra metadata field prevents weeks of debugging |
| Rendering full graph on load | Impressive demo screenshot | Unusable with real data; performance issues; analyst abandonment of the feature | Never -- progressive disclosure from the start |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Native Ollama to Docker containers | Leaving Ollama on default `127.0.0.1` binding | Set `OLLAMA_HOST=0.0.0.0` and `OLLAMA_ORIGINS=*` as Windows system environment variables; restart Ollama |
| pySigma to DuckDB | Assuming Sigma field names match your schema | Build an explicit processing pipeline mapping every Sigma field to your DuckDB column names |
| ChromaDB embedding ingestion | Using LangChain wrapper which re-embeds silently | Use ChromaDB's native Python client; pass pre-computed embeddings explicitly |
| FastAPI async + DuckDB sync | Calling DuckDB from async handlers without thread offloading | Use `asyncio.to_thread()` or `run_in_executor()` for DuckDB calls, or use sync endpoints with thread workers |
| EVTX parsing | Using pure Python `python-evtx` (extremely slow) | Use `pyevtx-rs` (Rust bindings via `pip install evtx`) -- 650x faster on large files |
| Chroma similarity scores to confidence display | Treating cosine similarity as a percentage | Normalize scores and establish empirical thresholds; 0.8 cosine similarity does not mean "80% confident" |
| Ollama model selection for 16GB VRAM | Loading a model that exceeds VRAM and silently offloads to CPU | Check model VRAM requirements before loading; use `ollama ps` to verify GPU layer count after loading |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading full EVTX files into memory before parsing | Memory spike to multi-GB, Python process killed | Stream-parse with pyevtx-rs; process records in batches of 1000 | Files > 100MB |
| Embedding all ingested text at ingestion time | Ingestion pipeline becomes bottleneck; hours to process a day's logs | Embed on demand or in background; only embed analyst-queryable content, not raw log lines | > 10,000 events per ingestion batch |
| Full graph render with force-directed layout on large datasets | Browser tab freezes; layout computation > 10 seconds | Limit visible nodes to ~100; use progressive disclosure; pre-compute layouts for common patterns | > 200 nodes / > 500 edges |
| DuckDB full-table scans on un-indexed timestamp columns | Queries take seconds instead of milliseconds | Create indexes on timestamp and frequently-filtered columns; use partitioned Parquet files for large datasets | > 1M rows in a single table |
| Chroma collection with no metadata filters | Every query scans entire collection; degraded relevance | Use metadata filters (source_type, time_range, case_id) to scope queries to relevant subsets | > 50,000 documents in a single collection |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Trusting LLM output for automated actions | LLM hallucinates a threat; system takes destructive action | Human-in-the-loop only (PROJECT.md requirement); never auto-execute based on LLM output |
| Ingesting untrusted documents into RAG without sanitization | Prompt injection via poisoned documents -- attacker plants instructions in a log entry that the LLM follows | Sanitize ingested text; strip potential prompt injection patterns; treat all ingested data as untrusted input |
| Ollama listening on 0.0.0.0 without firewall rules | Any device on the local network can access the LLM and all loaded models | Windows Firewall rule: allow 11434 only from localhost and Docker's virtual network interfaces |
| Storing raw EVTX / security logs without access controls | Sensitive security data accessible to any local process | Restrict DuckDB file permissions; consider encrypting at rest for sensitive case data |
| Embedding vectors leaking original content | Vector inversion attacks can reconstruct original text from embeddings | For this local-only desktop system, risk is low; but do not expose Chroma's API beyond localhost |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Alert spam without prioritization | Analyst sees 200 alerts of equal visual weight; ignores all of them | Severity-based visual hierarchy; critical alerts prominent, low-confidence alerts collapsed by default |
| LLM responses without evidence links | Analyst cannot verify the AI's claims; loses trust in the system | Every LLM claim is a hyperlink to the supporting evidence; clicking opens the raw event |
| Graph view as the default landing page | Overwhelming on first use; analyst does not know where to start | Default to timeline view or recent detections; graph is a drill-down tool, not a dashboard |
| No way to save/bookmark investigation state | Analyst loses context when switching tasks or closing browser | Persist investigation session state (expanded nodes, applied filters, notes) to local storage |
| Technical jargon in LLM responses | Junior analysts cannot interpret the output | Prompt templates should produce explanations at two levels: executive summary + technical detail |
| Query results without temporal context | Analyst cannot tell if an event happened 5 minutes ago or 5 months ago | Always display relative timestamps ("2 hours ago") alongside absolute timestamps |

## "Looks Done But Isn't" Checklist

- [ ] **Sigma rule ingestion:** Rules are loaded but field mapping pipeline is missing -- rules will never match real data. Verify by running rules against known-bad test events.
- [ ] **RAG query endpoint:** Returns LLM text but citations are not verified against actual stored records. Verify by checking that every citation ID resolves to a real record.
- [ ] **Graph visualization:** Works with 10 test nodes but becomes unusable with 200+ real-investigation nodes. Verify by loading a realistic dataset (e.g., process tree from a real incident).
- [ ] **Ollama GPU acceleration:** `ollama run` works but inference is actually running on CPU. Verify with `nvidia-smi` during inference and check `ollama ps` for GPU layer count.
- [ ] **Anomaly detection:** Detections fire but all use the same hardcoded threshold regardless of entity or context. Verify by checking if the same rule fires differently for different users/hosts/time-of-day.
- [ ] **DuckDB write path:** Single-user testing works but concurrent ingestion + query causes hangs. Verify with a simple load test: run ingestion while querying simultaneously.
- [ ] **ChromaDB persistence:** In-memory testing works but data is lost on restart. Verify by restarting the backend and confirming vector store contents survive.
- [ ] **EVTX parsing:** Parses small test files but chokes on large production EVTX exports (100MB+). Verify by parsing a full Security.evtx from a real Windows system.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| RTX 5080 CUDA failure | LOW | Driver reinstall (clean), Ollama update, environment variable fix -- hours, not days |
| LLM hallucination in production | MEDIUM | Add citation verification layer, tighten prompts, add confidence scoring -- 2-3 days of work |
| Docker-Ollama bridge failure | LOW | Set OLLAMA_HOST=0.0.0.0, restart -- minutes |
| Sigma silent match failures | HIGH | Requires building field mapping pipeline and re-testing all rules. If discovered late, weeks of rework |
| Graph hairball | HIGH | Requires UX redesign: progressive disclosure, aggregation, entity filtering. Near-complete rewrite of graph component |
| Alert fatigue from naive thresholds | HIGH | Requires rewriting detection engine with contextual baselines. Cannot be patched incrementally |
| DuckDB concurrency deadlocks | MEDIUM | Refactor to read/write connection separation and write queue -- 1-2 days if caught early |
| ChromaDB data loss on upgrade | LOW-HIGH | LOW if JSON export exists (restore in hours). HIGH if no backup (re-embed entire corpus) |
| Python 3.14 incompatibility | LOW | Switch to Python 3.12/3.13 via uv -- hours. Cost increases the longer you wait to discover it |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| RTX 5080 CUDA compat | Phase 1: Ollama installation | `nvidia-smi` shows GPU utilization during `ollama run`; `ollama ps` shows GPU layers > 0 |
| LLM hallucination | Phase 1: prompt design; Phase 3: RAG pipeline | Citation verification passes for 100% of test queries; no fabricated IOCs in automated test suite |
| Docker-Ollama bridge | Phase 1: infrastructure | `curl` from inside Docker container to `host.docker.internal:11434` returns 200 |
| Sigma silent failures | Phase 2: schema design; Phase 3: detection | Sigma smoke test suite: all 5-10 test rules match their corresponding test events |
| Graph hairball | Phase 4: visual investigation | Usability test with 200+ node dataset; analyst can identify key entities within 30 seconds |
| Naive thresholding | Phase 3: detection/correlation | Detection logic includes entity-specific baselines; same event count triggers differently for different entities |
| DuckDB concurrency | Phase 1: backend architecture | Load test: concurrent ingestion + queries complete without hangs for 60 seconds |
| ChromaDB version instability | Phase 1: dependency pinning | Version pinned in requirements; JSON export/import script exists and passes round-trip test |
| Python 3.14 compat | Phase 0 / Pre-Phase 1 | All dependencies install and pass import smoke test on Python 3.14 |

## Sources

- [Ollama GitHub Issues #14446, #11849, #13163, #13536](https://github.com/ollama/ollama/issues/14446)
- [Ollama Hardware Support Documentation](https://docs.ollama.com/gpu)
- [Blackwell CUDA Fix Guide - Apatero](https://apatero.com/blog/blackwell-gpu-cuda-errors-fix-troubleshooting-guide-2025)
- [ScienceDirect - Hallucinations in AI-driven Cybersecurity](https://www.sciencedirect.com/science/article/abs/pii/S0045790625002502)
- [IronCore Labs - RAG Security Risks](https://ironcorelabs.com/security-risks-rag/)
- [CSA - Mitigating RAG LLM Security Risks](https://cloudsecurityalliance.org/blog/2023/11/22/mitigating-security-risks-in-retrieval-augmented-generation-rag-llm-applications)
- [Open WebUI - Connection Error Docs](https://docs.openwebui.com/troubleshooting/connection-error/)
- [pySigma Processing Pipelines](https://sigmahq-pysigma.readthedocs.io/en/latest/Processing_Pipelines.html)
- [pySigma Backends](https://sigmahq-pysigma.readthedocs.io/en/latest/Backends.html)
- [Cambridge Intelligence - Fixing Hairballs](https://cambridge-intelligence.com/how-to-fix-hairballs/)
- [Cambridge Intelligence - Cybersecurity Visualization](https://cambridge-intelligence.com/use-cases/cybersecurity/)
- [DuckDB Concurrency Documentation](https://duckdb.org/docs/stable/connect/concurrency)
- [DuckDB Discussion #13719 - FastAPI Concurrency](https://github.com/duckdb/duckdb/discussions/13719)
- [ChromaDB Migration Docs](https://docs.trychroma.com/docs/overview/migration)
- [ChromaDB Migration Pitfalls Blog](https://wwakabobik.github.io/2025/11/migrating_chroma_db/)
- [Python 3.14 What's New](https://docs.python.org/3/whatsnew/3.14.html)
- [PyO3 Issue #5000](https://github.com/PyO3/pyo3/issues/5000)
- [pyevtx-rs - Rust EVTX Parser](https://github.com/omerbenamram/evtx)
- [dogesec - pySigma Introduction](https://www.dogesec.com/blog/beginners_guide_to_using_sigma_cli_pysigma/)

---
*Pitfalls research for: Local Windows Desktop AI Cybersecurity Investigation Platform*
*Researched: 2026-03-14*
