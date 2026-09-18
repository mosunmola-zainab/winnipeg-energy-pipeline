# CLAUDE.md

## Project Context

This repository is the Winnipeg Energy Pipeline.

The project is evolving from a simple ETL pipeline into a more complete data system with:

- layered data architecture
- analytical modelling
- stronger orchestration
- data quality
- observability
- testing
- eventually an agentic data-operations layer

Do not assume planned architecture has already been implemented.

Before making architectural or modelling changes, read:

- `README.md`
- `docs/technical_history.md`
- `docs/data_modeling_decisions.md`

Treat documented decisions as the current source of truth unless they are explicitly changed.

---

## Project Development Principles

Work in small, reviewable increments.

Before implementing a significant change:

1. inspect the relevant existing code and documentation
2. understand the current behaviour
3. identify the smallest required change
4. preserve unrelated behaviour
5. state important assumptions
6. implement only the agreed scope
7. run appropriate tests or validation
8. review the resulting diff

Do not broaden a focused task into a repository-wide refactor without a clear reason.

If a change requires a new architectural, modelling, or business decision that has not already been documented, surface the decision rather than making it implicitly.

Do not introduce technology simply to demonstrate it.

Prefer the simplest design that solves the actual system problem clearly and correctly.

---

## Data Engineering Rules

Preserve source fidelity before applying business transformations.

Do not deduplicate records based on assumed business keys.

`hydro_gas_id` is currently preserved as the raw row-level identifier based on profiling evidence.

Do not assume any of the following independently represents a physical facility:

- `account_number`
- `meter_number`
- `service_address`
- `customer_name`

The source does not contain a verified facility identifier.

A facility may later be derived through enrichment or entity resolution using multiple source attributes and reliable external reference data.

Do not implement facility resolution until the approach is explicitly designed.

Do not invent business rules from patterns in the data.

Prefer explicit data-quality handling over silent mutation.

Where practical, malformed or suspicious values should be:

- flagged
- counted
- logged
- quarantined
- or handled through documented transformation rules

rather than silently converted or discarded.

---

## Layered Architecture

Bronze, Silver, and Gold are the intended architectural direction.

Do not create tables merely because a medallion architecture is being used.

Each layer must have a clear purpose.

### Bronze

Bronze should prioritize:

- source fidelity
- traceability
- reproducibility
- ingestion metadata

Avoid unnecessary business transformations in Bronze.

### Silver

Silver should contain cleaned, typed, standardized, and quality-aware records.

Cleaning and standardization rules must be documented.

Do not silently remove source records unless there is a documented reason.

### Gold

Gold should support actual analytical or business use cases.

Dimensional models, marts, and aggregates should be driven by real downstream questions rather than by a desire to create more tables.

---

## Architecture Rules

Before introducing a major new component, explain:

1. what problem it solves
2. why the current system cannot solve that problem adequately
3. the simplest alternative
4. the operational complexity introduced
5. new failure modes introduced
6. whether the current workload actually requires it

This applies especially to:

- Kafka
- Redis
- Kubernetes
- queues
- caching layers
- microservices
- additional databases
- vector databases
- additional orchestration systems
- agent frameworks
- multi-agent architectures

Do not add infrastructure for hypothetical future scale without evidence that it is needed.

---

## Airflow

Airflow should provide meaningful orchestration and observability.

Avoid wrapping the entire pipeline in one opaque task when the workflow contains operationally meaningful stages.

Task boundaries should correspond to useful execution and failure boundaries.

Do not split tasks merely to create a visually impressive DAG.

---

## CI/CD

CI should validate code and configuration.

Relevant checks may include:

- unit tests
- integration tests
- DAG validation
- SQL validation
- configuration checks
- linting where useful

A code push should not automatically trigger a full operational data refresh unless that behaviour is explicitly intended.

Software validation and operational pipeline execution are separate concerns.

---

## Testing

Add tests for meaningful behaviour and known failure modes.

Relevant test categories may include:

- unit tests
- integration tests
- data-quality tests
- DAG import and structure tests
- end-to-end tests

Do not add tests solely to increase coverage numbers or test count.

Prefer tests that protect behaviour relied on by users or downstream systems.

---

## Dependencies

Do not add a dependency when:

- the standard library is sufficient
- an existing dependency already solves the problem
- the package only saves a few trivial lines of code

When adding a dependency, explain why it is needed.

Do not upgrade unrelated dependencies during a focused task.

---

## Security

Never hard-code:

- passwords
- tokens
- credentials
- secrets

Prefer least-privilege access.

Do not expose services publicly merely to simplify development.

If existing code contains an insecure pattern, identify it clearly rather than silently carrying it into redesigned components.

---

## Agentic AI Principles

The eventual agentic layer should solve a real operational problem.

Do not add an agent merely because Agentic AI is part of the long-term project direction.

Use deterministic automation when the task has:

- known inputs
- known rules
- predictable outputs

Use agentic reasoning where there is genuine ambiguity, investigation, tool selection, contextual reasoning, or adaptive decision-making.

Potential agent responsibilities may include:

- investigating pipeline failures
- interpreting data-quality failures
- querying run metadata
- inspecting logs
- reading runbooks
- proposing likely causes
- recommending recovery actions

Agents should not automatically perform destructive or high-impact actions without an explicitly designed approval boundary.

Multi-agent architecture requires justification.

A workflow divided into named agents is not automatically a meaningful multi-agent system.

---

## Documentation Principles

Documentation should accurately reflect the implementation.

Clearly distinguish between:

- confirmed facts
- profiling results
- modelling decisions
- architectural decisions
- assumptions
- inferences
- unresolved questions
- planned work

Do not describe planned functionality as implemented.

Do not invent business meaning for source fields where that meaning has not been established.

Keep documentation focused on important system behaviour, reasoning, decisions, and limitations.

Exploratory analysis does not need to become permanent public documentation unless it provides lasting value to the project.