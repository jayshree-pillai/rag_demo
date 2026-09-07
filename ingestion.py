"""
HNSW is an approximate nearest-neighbor algorithm used by vector databases
and Azure AI Search.

The ingestion pipeline:
1. Defines the Chunk model
2. Defines the search-index schema
3. Creates the Azure AI Search index
4. Receives document text
5. Creates chunks
6. Embeds chunks in batches
7. Attaches embeddings and metadata
8. Uploads everything to the index
"""

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator


class Chunk(BaseModel):
    text: str
    chunk_id: str
    chunk_type: str
    doc_id: str
    parent_id: str | None = None
    page_number: int | None = None
    embedding: list[float] | None = None


def define_index_fields(vector_dim: int):
    fields = [
        SimpleField(
            name="chunk_id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        SimpleField(
            name="doc_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="chunk_type",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="parent_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="page_number",
            type=SearchFieldDataType.Int32,
            filterable=True,
        ),
        SimpleField(
            name="row_number",
            type=SearchFieldDataType.Int32,
            filterable=True,
        ),
        SearchableField(
            name="text",
            type=SearchFieldDataType.String,
        ),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(
                SearchFieldDataType.Single,
            ),
            searchable=True,
            vector_search_dimensions=vector_dim,
            vector_search_profile_name="vector-profile",
        ),
    ]

    return fields


def create_search_index(endpoint, key, index_name, vector_dim):
    client = SearchIndexClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(name="hnsw-config")
        ],
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm_configuration_name="hnsw-config",
            )
        ],
    )

    index = SearchIndex(
        name=index_name,
        fields=define_index_fields(vector_dim),
        vector_search=vector_search,
    )

    return client.create_or_update_index(index)


class DocumentInput(BaseModel):
    document_id: str
    text: str = Field(min_length=1, max_length=2000)
    strategy: str = Field(default="flat", min_length=1)
    car_id: str

    @field_validator("strategy")
    @classmethod
    def strategy_validator(cls, value: str) -> str:
        value = " ".join(value.split()).lower()

        if value in ("hierarchical", "flat"):
            return value

        raise ValueError("strategy must be flat or hierarchical")

    @field_validator("text")
    @classmethod
    def text_validator(cls, value: str) -> str:
        value = " ".join(value.split())

        if not value:
            raise ValueError("text must not be empty")

        return value


client = OpenAI()


def embed_fn(texts):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )

    return [item.embedding for item in response.data]


def embed_chunks(
    chunks,
    embedding_fn,
    text_key="text",
    batch_size=64,
):
    embedded_chunks = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [chunk[text_key] for chunk in batch]
        embeddings = embedding_fn(texts)

        for chunk, embedding in zip(batch, embeddings):
            new_chunk = chunk.copy()
            new_chunk["embedding"] = embedding
            embedded_chunks.append(new_chunk)

    return embedded_chunks


def upload_chunks(
    endpoint,
    key,
    index_name,
    embedded_chunks,
):
    search_client = SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(key),
    )

    return search_client.upload_documents(
        documents=embedded_chunks
    )


def embed_query(query, embed_fn):
    return embed_fn([query])[0]