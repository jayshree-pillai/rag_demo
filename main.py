import re
import os
import json
from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator
from chunking import flat_chunks
from ingestion import DocumentInput, client, embed_chunks, embed_fn
from retrieval import build_context, build_prompt, retrieve_top_k
from azure.storage.queue import QueueClient

#owns the http Routing -
app = FastAPI()
queue_client = QueueClient.from_connection_string(
    conn_str=os.environ["AzureWebJobsStorage"],
    queue_name="ingest-queue",
)
# In-memory chunk store for the coding demo.
chunks = []

CAR_ALIASES = {
    "comprehensive analysis review": "CAR",
    "prior CAR": "previous CAR",
    "rating justification": "rating rationale",
}


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        cleaned = " ".join(value.split())

        if not cleaned:
            raise ValueError("query must not be empty")

        for alias, canonical in CAR_ALIASES.items():
            pattern = r"\b" + re.escape(alias) + r"\b"
            cleaned = re.sub(
                pattern,
                canonical,
                cleaned,
                flags=re.IGNORECASE,
            )

        return cleaned


class ChatResponse(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str) -> str:
        cleaned = " ".join(value.split())

        if not cleaned:
            raise ValueError("answer must not be empty")

        return cleaned


def call_llm(prompt):
    response = client.responses.create(
        model="gpt-5.5",
        input=prompt,
    )

    return response.output_text


@app.post("/ingest")
def ingest(request:DocumentInput):
    # producer
    message=json.dumps({
            "car_id":request.car_id,
            "document_id": request.document_id,
            "text": request.text})
    queue_client.send_message(message)
    return {"status":"queued"}

@app.post("/seq_ingest")
def seq_ingest(request: DocumentInput):
    # Sequential ingest
    new_chunks = flat_chunks(
        request.document_id,
        request.text,
    )

    embedded_chunks = embed_chunks(
        new_chunks,
        embed_fn,
    )

    chunks.extend(embedded_chunks)

    return {"chunks_indexed": len(embedded_chunks)}

'''
POST /generate-car
        ↓
Create CAR job / car_id
        ↓
Fan-out document ingestion
        ↓
ingest-queue
        ↓
parallel workers:
extract → chunk → embed → Azure AI Search
        ↓
fan-in:
all documents indexed?
        ↓ YES
Load questions.yaml
        ↓
FOR EACH QUESTION
        ↓
Retrieve Top-K from Azure AI Search
        ↓
Retrieval Guardrail
correct counterparty?
fresh/as-of?
correct source authority?
metadata scope valid?
        ↓
Rerank
        ↓
Build Context
        ↓
LLM answers question
        ↓
Factual Guardrail
        ↓
Reasoning Guardrail
        ↓
Behavior / Contract Guardrail
        ↓
validated answers
        ↓
Narrative assembly / stitching
        ↓
Final CAR report

'''
@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not chunks:
        return ChatResponse(
            answer="No documents have been ingested."
        )

    top_chunks = retrieve_top_k(
        request.query,
        chunks,
        embed_fn,
        5,
    )

    context = build_context(top_chunks)
    prompt = build_prompt(request.query, context)
    answer = call_llm(prompt)

    return ChatResponse(answer=answer)