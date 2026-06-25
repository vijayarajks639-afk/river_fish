# Market & Future: Enterprise Data Lineage and Text-to-SQL

> A practitioner + leadership synthesis for positioning, interviews, and upskilling decisions.
> Written for a senior banking data/AI leader. All claims are either web-verified (source linked)
> or marked **[directional]** where no verifiable citation was found.

---

## 1. Why Enterprise Text-to-SQL Is Genuinely Hard

The headline performance number everyone cites — frontier LLMs hitting ~91% on the Spider 1.0
benchmark — is a toy-schema artifact. Spider 1.0 tests against schemas with ~5 tables and
pre-cleaned queries. Real enterprise environments have thousands of columns, multi-dialect SQL
(BigQuery, Snowflake, Oracle), and business logic that requires deep domain context.

**Spider 2.0** (ICLR 2025 Oral, Yale/xlang-ai + RelationalAI) measures LLMs on 632 real-world
enterprise text-to-SQL workflow tasks drawn from actual enterprise schemas. Results:

| Model | Spider 1.0 | Spider 2.0 |
|---|---|---|
| o1-preview (agentic) | ~91% | **21.3%** |
| GPT-4o | ~91% | **15.6%** |
| DeepSeek-V3 | — | **15.6%** |
| OmniSQL-7B (specialist) | — | **10.4%** |

Sources:
- [Spider 2.0 paper — ICLR 2025 Proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/46c10f6c8ea5aa6f267bcdabcb123f97-Abstract-Conference.html)
- [Spider 2.0 site](https://spider2-sql.github.io/)
- [GitHub — xlang-ai/Spider2](https://github.com/xlang-ai/Spider2)

**What this means for a banking leader:** "AI understands your SQL" is a marketing claim, not
an engineering fact. In a multi-source credit-risk pipeline with BCBS 239 traceability
requirements, a purely LLM-driven lineage or NL-SQL system cannot be audit-grade. The correct
architecture is deterministic backbone + governed LLM assist — exactly the design in this repo.

---

## 2. The Converging Vendor Market

### Snowflake Cortex Analyst

Cortex Analyst converts natural language to SQL inside the Snowflake perimeter. Key governance
posture: **"no data, metadata, or prompts leave the governance boundary"** — the LLM is
Snowflake-hosted (Mistral and Meta models) and no Customer Data is used for model training.
Queries are generated from the semantic model YAML (column names, descriptions) and executed
inside your Snowflake virtual warehouse. RBAC policies apply to every generated query.

This is architecturally analogous to the river_fish design: metadata/SQL only into the LLM,
data stays in the warehouse, governance boundary is explicit and auditable.

Source: [Snowflake Cortex Analyst documentation](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst)

### Databricks Genie + Unity Catalog

Unity Catalog captures **automatic column-level lineage** at runtime via query-plan hooks (not
static SQL parsing). Column lineage is queryable in system tables
(`system.access.column_lineage`). Genie (AI/BI) can answer lineage questions in natural
language — "show me downstream lineages", "who queries this table most often."

2025 development: Genie's **knowledge mining** uses Unity Catalog lineage and query history to
identify recurring patterns while preserving governance guarantees. Column-level Popularity
(derived from historical query analysis) now feeds the Genie Ontology to sharpen column
relevance signals.

Sources:
- [Unity Catalog data lineage — Databricks AWS](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage)
- [AI/BI Genie GA announcement](https://www.databricks.com/blog/aibi-genie-now-generally-available)
- [What's new in Unity Catalog, Data+AI Summit 2025](https://www.databricks.com/blog/whats-new-databricks-unity-catalog-data-ai-summit-2025)

**Runtime vs static:** Databricks captures lineage as queries execute. The river_fish engine
parses static SQL text without executing the pipeline — both are legitimate designs; runtime
gives higher accuracy, static requires no query execution and is air-gap compatible.

### DataHub, OpenLineage / Marquez

**OpenLineage** (LF AI & Data Graduate project) is the open event schema for lineage capture
at runtime — Airflow, Spark, dbt, Flink all emit OpenLineage events. **Marquez** is the
reference implementation (metadata store + API). **DataHub** ingests OpenLineage events and
provides the catalog, graph model, and governance UI on top.

Column-level lineage is supported in the OpenLineage spec; coverage depends on which emitters
are wired in. DataHub and OpenMetadata both treat column-level lineage as a native capability.

The river_fish ADR explicitly positions the two approaches as **complementary**: emit
OpenLineage-format events from the DAG (P2 backlog item) so the output is interoperable with
Marquez/DataHub consumers without changing the parser.

Sources:
- [OpenLineage GitHub](https://github.com/OpenLineage/OpenLineage)
- [Marquez project](https://marquezproject.ai/)
- [DataHub on open-source lineage](https://datahub.com/blog/open-source-data-lineage/)

### Collibra / Atlan / Alation — Active Metadata

The data governance catalog market is reorienting around **active metadata** — metadata that
continuously monitors pipelines, triggers workflows, pushes context into downstream tools (dbt,
Slack, Snowflake), and enforces policies without manual human action.

Current positioning (as of mid-2026):
- **Atlan** — Gartner MQ Leader (advanced from Visionary in 2026); cloud-native; active
  metadata pushed into Snowflake, Databricks, dbt, Slack.
- **Alation** — Forrester Wave Leader (2025); acquired Numbers Station AI (May 2025, Stanford
  PhD-founded) to launch an Agentic Data Intelligence Platform; repositioning governance agents
  as active participants, not just passive catalogers.
- **Collibra** — entrenched enterprise standard; formal stewardship workflows; governance
  orchestration engine.

Gartner predicts the governance catalog market consolidates to **three commercial vendors and
two open-source projects by 2028**.

Sources:
- [Atlan on Collibra alternatives](https://atlan.com/collibra-alternatives-enterprise-data-governance/)
- [Data governance tools comparison](https://promethium.ai/guides/data-governance-tools-comparison-collibra-alation-atlan-purview/)
- [Catalog wars analysis](https://www.nidhivichare.com/blog/catalog-wars-part-3)

---

## 3. Open Table Format Convergence: Apache Iceberg Has Won

The format war is over. **Apache Iceberg is the settled interoperability layer**. As of mid-2026:
- Snowflake, Databricks (Delta Lake + Iceberg bridge), AWS (S3 Tables), Google BigLake, and
  Microsoft Fabric all read and write Iceberg v3 as generally available.
- **Apache Polaris** (co-created by Snowflake and Dremio, donated to Apache Foundation August
  2024, graduated to top-level project February 2026) is the emerging open catalog standard.
- Databricks is proposing Delta 5.0 adopt the same adaptive metadata tree as Iceberg v4,
  aiming for a single metadata layout that ends the Delta/Iceberg interoperability gap.

Why this matters for lineage: open table format metadata (partition specs, schema evolution
history, snapshot logs) is machine-readable lineage at the storage layer. A column-level
lineage engine built on Iceberg can read format evolution history as part of the DAG.

Sources:
- [Apache Iceberg v3 on Databricks](https://www.databricks.com/blog/next-era-open-lakehouse-apache-icebergtm-v3-public-preview-databricks)
- [State of Apache Iceberg Catalogs June 2026](https://dev.to/alexmercedcoder/the-state-of-apache-iceberg-catalogs-in-june-2026-265e)
- [Open table format revolution — Rill](https://www.rilldata.com/blog/the-open-table-format-revolution-why-hyperscalers-are-betting-on-managed-iceberg)

---

## 4. Active Metadata + Machine-Verifiable Data Contracts + Agentic Governance

Gartner's direction (top predictions, 2026):

> "By 2030, 50% of organizations will use autonomous AI agents to interpret governance policies
> and technical standards into machine-verifiable data contracts, automating compliance and
> governance policy enforcement."

The progression: passive catalog (2018–2022) → active metadata (2022–2025) → agentic
governance (2025–2030). Each step reduces the manual human-in-the-loop burden of governance.

**Data contracts** — machine-readable agreements between data producers and consumers about
schema, quality thresholds, SLAs, and ownership — are the enforcement substrate for agentic
governance. Gartner's 2026 MQ now explicitly evaluates vendors on marketplace experience, data
contracts, and lifecycle governance for data products.

For a banking leader: this is where BCBS 239 compliance moves from spreadsheet-driven audits
to programmatic, continuously-tested pipeline contracts. A lineage DAG (like river_fish's) is
the dependency graph that data contracts reference.

Sources:
- [Gartner D&A predictions for 2026](https://www.gartner.com/en/newsroom/press-releases/2026-03-11-gartner-announces-top-predictions-for-data-and-analytics-in-2026)
- [Gartner MQ D&A Governance 2026 — Ataccama analysis](https://www.ataccama.com/blog/gartner-magic-quadrant-for-data-and-analytics-governance-platforms-2026-explained-what-changed-this-year)
- [Gartner active metadata guide — Atlan](https://atlan.com/gartner-active-metadata-management/)

---

## 5. Regulatory Tailwind: BCBS 239 Principles 2 & 3 and the On-Prem Reality

**BCBS 239** (Basel Committee on Banking Supervision, 2013) sets 11 principles for Risk Data
Aggregation and Reporting (RDARR). For data engineers and platform leaders, the operative
requirements are in Principles 2 and 3:

- **Principle 2 (Data Architecture and IT Infrastructure):** End-to-end data traceability from
  report output back to originating systems, connecting each CDE (Critical Data Element) to its
  source table, **field (column)**, and transformation logic.
- **Principle 3 (Accuracy and Integrity):** Tracing risk exposures back to source systems to
  validate data accuracy and correct inconsistencies at source — which requires column-level
  lineage, not just table-level.

The ECB Guide (the European enforcement arm) now **explicitly requires attribute-level lineage
from data capture to final reporting**. Institutions that stop at system-level mapping fail
regulatory review. The ECB is actively intensifying its supervisory approach on BCBS 239
compliance.

**The on-prem / data-cannot-leave reality:** Global systemically important banks (G-SIBs)
and most large domestic banks run credit-risk and regulatory capital pipelines on on-premises
infrastructure or private cloud. Customer data, exposure data, and internal ratings cannot
transit third-party LLM APIs — not for privacy law reasons alone, but because internal policy
frameworks (based on regulatory guidance) classify this data as non-exportable. This constraint
is not going away; it shapes every architecture decision about where AI tooling can operate.

Sources:
- [BCBS 239 data lineage — Atlan](https://atlan.com/know/data-governance/bcbs-239-data-lineage/)
- [BCBS 239 data lineage — OvalEdge](https://www.ovaledge.com/blog/bcbs-239-data-lineage)
- [Four ways data lineage powers BCBS 239 — Collibra](https://www.collibra.com/blog/four-ways-data-lineage-powers-bcbs-239-compliance)
- [ECB intensifying supervisory approach on BCBS 239 — Solidatus](https://www.solidatus.com/blog/ecb-is-intensifying-its-supervisory-approach-on-bcbs239-compliance/)
- [Why BCBS 239 is essential in 2025 — EY Netherlands](https://www.ey.com/en_nl/industries/banking-capital-markets/why-bcbs-239-compliance-is-essential-in-2025)

---

## 6. MCP (Model Context Protocol) for On-Prem / Firewalled Tool Access

The **Model Context Protocol** (open standard, introduced by Anthropic November 2024; donated
to the Linux Foundation's Agentic AI Foundation in December 2025) standardizes how LLMs
integrate with external tools, data sources, and enterprise systems — without requiring bespoke
API connectors for every integration.

Adoption velocity: MCP server downloads grew from ~100,000 (November 2024) to over 8 million
by April 2025. OpenAI, Google, Microsoft, and AWS all adopted the standard. The MCP market is
projected at $1.8B in 2025.

**Enterprise relevance for on-prem banking:** MCP servers can run entirely inside the
firewall — exposing tools (SQL executors, metadata catalogs, lineage APIs) to an LLM agent
that also runs on-premises. This solves the core constraint: the LLM gets tool access without
data leaving the network boundary. For a bank building a governed NL lineage interface, an
on-prem MCP server wrapping the lineage DAG API is the production architecture to reach for
(M5+ on the river_fish roadmap).

2026 is characterized by analysts as the year MCP transitions from experimentation to
enterprise-wide deployment, with six required governance controls: OAuth 2.0 auth, per-operation
RBAC/ABAC, attribution-level audit logging, path/scope controls, rate limiting, and sensitivity
label evaluation.

Sources:
- [MCP Wikipedia](https://en.wikipedia.org/wiki/Model_Context_Protocol)
- [MCP enterprise adoption guide — Deepak Gupta](https://guptadeepak.com/the-complete-guide-to-model-context-protocol-mcp-enterprise-adoption-market-trends-and-implementation-strategies/)
- [2026: the year for enterprise-ready MCP — CData](https://www.cdata.com/blog/2026-year-enterprise-ready-mcp-adoption)
- [MCP enterprise security — Kiteworks](https://www.kiteworks.com/cybersecurity-risk-management/model-context-protocol-enterprise-security/)

---

## 7. Market Size and Growth Context

Column-level data lineage is a distinct and fast-growing segment:

- Column-level lineage market: **$872.6M (2025)**, growing at **~15.6% CAGR**
- Data Lineage Automation market: **$1.66B (2025) → $2.07B (2026)** at **24.4% CAGR**,
  projected $4.99B by 2030
- Dataset Lineage Tracking market: projected **$4.14B by 2030**

Growth is driven by AI pipeline governance requirements (lineage for AI/ML feature stores and
model outputs), multi-cloud compliance, real-time data contract enforcement, and intensifying
BCBS 239 / GDPR / DORA regulatory pressure.

Sources:
- [Column-Level Data Lineage Market — market.us](https://market.us/report/column-level-data-lineage-market/)
- [Data Lineage Automation Global Market Report 2026](https://www.giiresearch.com/report/tbrc1987647-data-lineage-automation-global-market-report.html)
- [Dataset Lineage Tracking Market $4.14B by 2030](https://natlawreview.com/press-releases/dataset-lineage-tracking-market-expected-reach-414-bn-2030-exclusive-report)

---

## 8. What a Senior Data Leader Should Do in 2025–2026

1. **Instrument column-level lineage now, not table-level.** Regulators (BCBS 239 / ECB) are
   moving from accepting table maps to requiring attribute-level traceability. If you don't have
   column-level lineage in your credit risk and regulatory capital pipelines, you have an open
   audit finding.

2. **Design for the on-prem constraint first.** Cloud-hosted LLM APIs are not an option for
   most banking data. Build NL and AI governance tooling that works with metadata/SQL only
   (not data rows) and can run inside the firewall. The Cortex Analyst / Genie models are the
   vendor reference architecture; MCP is the open-standard connector layer.

3. **Pick a table format and close that debate.** Apache Iceberg is the answer. Unify your
   lakehouse on it now so lineage, schema evolution, and catalog metadata are in one consistent
   format across Snowflake, Databricks, and AWS.

4. **Treat data contracts as the next governance layer to deliver.** Active metadata platforms
   enforce contracts; agentic governance interprets them. The lineage DAG is the dependency
   graph contracts reference. Get lineage right before attempting contracts.

5. **Position the hybrid design as your architectural signature.** Deterministic parser =
   audit-grade backbone. LLM = NL interface and explanation, clearly labelled as suggestion.
   This is exactly what both Snowflake Cortex Analyst and the best-practice literature
   prescribe. Knowing why and where to use each is the senior leader differentiator.

6. **Build the skills portfolio for agentic data governance.** The next 3 years will reward
   people who can design multi-agent lineage systems, write governed LLM prompts for metadata
   (not data), implement data contracts, and speak credibly to regulators about traceability
   architectures. Python + SQL + graph theory + LLM governance is the combination.

---

*Last updated: June 2026. Claims marked [directional] are based on analyst and practitioner
consensus rather than a specific verifiable source.*
