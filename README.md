# Enterprise RAG / CAR Architecture Demo

A compact, interview-focused Python project that demonstrates the core building blocks of a production-style Retrieval-Augmented Generation (RAG) platform for credit-analysis / CAR workflows.

The goal of this repo is **not** to be a full production application. It is intentionally kept small enough to explain and reproduce during a technical interview while still showing real architectural patterns: API contracts, asynchronous ingestion, vector indexing, multi-source retrieval, LangGraph orchestration, reranking, guardrails, evaluation, retry/fallback logic, and CAR-generation workflow design.

---

## Architecture at a Glance

### Dynamic Chat

```text
User question
    ↓
FastAPI
    ↓
LangGraph
    ↓
Policy Check
    ↓
Router
    ├── SQL Search
    │
    └── Semantic RAG
          ↓
      Uploaded Docs Index
      Enterprise / Source Docs Index
      Generated CAR Index
          ↓
      Merge + Rerank
          ↓
      Retrieval Guard
          ↓
        Generate
          ↓
      Factual Guard
          ↓
      Reasoning Guard
          ↓
      Contract Validation
          ↓
      PASS / RETRY / FALLBACK
```

### Asynchronous Document Ingestion

```text
POST /ingest
    ↓
ingest-queue
    ↓
Azure Function workers
    ↓
chunk
→ embed
→ Azure AI Search
    ↓
post-ingest-queue
    ↓
Cosmos completion state
```

The queue separates API traffic from document-processing work and allows document-level fan-out across Azure Function workers.

---

## Main Components

### `main.py`

FastAPI entry point.

Demonstrates:

- Pydantic request / response validation
- input normalization
- `/chat`
- sequential ingestion for comparison
- queue-based asynchronous ingestion
- reusable RAG flow:
  - retrieve
  - build context
  - build grounded prompt
  - call LLM

---

### `function_app.py`

Azure Functions background processing.

Demonstrates:

- queue-triggered ingestion worker
- document-level parallel ingestion
- chunk → embed → index pipeline
- post-ingestion completion messages
- Cosmos DB completion tracking

Conceptually:

```text
one queue message = one document job
```

This allows the Functions runtime to process multiple documents concurrently.

---

### `ingestion.py`

Azure AI Search ingestion primitives.

Includes:

- search-index schema
- HNSW vector configuration
- chunk metadata
- batched embedding generation
- Azure AI Search upload
- query embedding helper

---

### `chunking.py`

Simple, recallable chunking strategies:

- `flat_chunks()`
- `hierarchical_chunking()`
- `table_chunks()`

The production CAR platform relies on richer document extraction, but these functions provide interview-friendly representations of the major chunking strategies.

---

### `lanGraph.py`

KISS LangGraph orchestration example.

The graph demonstrates:

```text
State
→ Node functions
→ Routing functions
→ Add nodes
→ Add edges
→ Add conditional edges
→ Compile
→ Invoke
```

Runtime flow:

```text
START
 ↓
POLICY
 ↓
ROUTER
 ├── SQL
 └── SEMANTIC
      ↓
  3 search indexes
      ↓
  MERGE / RERANK
      ↓
  RETRIEVAL GUARD
      ↓
  GENERATE
      ↓
  FACTUAL GUARD
      ↓
  REASONING GUARD
      ↓
  CONTRACT VALIDATE
      ↓
  PASS / RETRY / FALLBACK
```

The semantic path searches three logical sources:

1. user-uploaded documents
2. enterprise/source documents used for analysis
3. generated CAR reports

Uploaded documents receive a source preference before final context selection.

---

## Guardrail Model

The runtime quality model is intentionally separated into four concerns.

### Retrieval Guard

**Did we retrieve usable evidence?**

Production extensions can check:

- correct counterparty
- current / as-of date
- source authority
- metadata scope
- stale or conflicting evidence

### Factual Guard

**Did the generated answer preserve critical facts?**

The factual-eval demo uses a frozen set of atomic questions and asks the same questions against:

```text
Previous CAR text
        vs
Current generated answer
```

The extracted answers are then compared deterministically.

### Reasoning Guard

**Is the generated explanation supported by the evidence?**

A smaller judge model can be used to check whether material reasoning claims are supported by the supplied context.

### Contract Validation

**Did the application return a valid response?**

Examples:

- answer exists
- response length is valid
- expected schema is respected
- required fields / citations are present

The final validation node controls:

```text
PASS  → return
RETRY → regenerate
FAIL  → fallback
```

---

## Evaluation Strategy

The project separates **offline evaluation** from **online guardrails**.

### Offline Retrieval Evaluation

Representative golden questions are created across important retrieval dimensions such as:

- source type
- question type
- retrieval difficulty

Known relevant evidence (qrels) can be used to calculate:

- Recall@K
- MRR
- nDCG

### Offline Factual Evaluation

Broad narrative questions are decomposed offline into a frozen set of atomic factual questions.

```text
Narrative question
    ↓
Atomic golden questions
    ↓
Prev CAR answers
    vs
Current CAR answers
    ↓
Deterministic comparison
```

### Live Guardrails

The live path does not run the full offline benchmark for every request.

Instead:

```text
retrieval guard
→ factual guard
→ reasoning guard
→ contract guard
```

protect individual requests at runtime.

---

## Target CAR Generation Flow

The next extension of the project is a queued CAR-generation workflow:

```text
POST /generate-car
        ↓
car-request-queue
        ↓
CAR worker
        ↓
fan-out document ingestion
        ↓
parallel extract → chunk → embed → index
        ↓
fan-in / completion
        ↓
load questions.yaml
        ↓
retrieve + rerank
        ↓
retrieval guard
        ↓
generate section answers
        ↓
factual + reasoning guards
        ↓
contract validation
        ↓
narrative assembly
        ↓
final CAR report
```

This keeps the HTTP request short-lived while the longer CAR workflow continues asynchronously.

---

## Production-Readiness Concepts Demonstrated

This repo is intentionally small, but it is structured around production concerns:

- async queue-based ingestion
- fan-out / fan-in workflow design
- Azure AI Search vector retrieval
- multiple retrieval sources
- source-aware reranking
- SQL vs semantic routing
- runtime guardrails
- retries and fallbacks
- factual and reasoning evaluation
- Cosmos DB workflow state
- Pydantic API contracts
- LangGraph conditional orchestration

Additional production concerns discussed alongside this implementation include:

- Application Insights / OpenTelemetry
- KQL-based operational metrics
- p95 latency / error-rate alerts
- Azure AI Search replicas and partitions
- Azure OpenAI TPM / deployment capacity
- APIM-based model routing
- retry backoff / jitter / circuit breakers

---

## Repository Structure

```text
rag_demo/
├── main.py
├── function_app.py
├── ingestion.py
├── retrieval.py
├── chunking.py
├── lanGraph.py
├── factual_eval.py
├── reasoning_eval.py
└── README.md
```

---

## Running Locally

Create and activate a virtual environment, then install the required packages.

Example:

```bash
pip install fastapi uvicorn pydantic
pip install openai
pip install azure-search-documents
pip install azure-storage-queue
pip install azure-functions
pip install azure-cosmos
pip install langgraph
```

Run the FastAPI app:

```bash
uvicorn main:app --reload
```

---

## Environment Variables

Depending on which modules you run, configure values such as:

```text
AzureWebJobsStorage
SEARCH_ENDPOINT
SEARCH_KEY
SEARCH_INDEX
COSMOS_ENDPOINT
COSMOS_KEY
```

Do not commit secrets or connection strings to source control.

---

## Design Principle

The project follows one simple production-RAG idea:

```text
Right evidence
→ right facts
→ right reasoning
→ right response contract
```

The code is deliberately KISS so each architectural concept can be written, explained, and defended during an interview without hiding behind framework abstractions.
