import azure.functions as func
#Azure Functions runtime owns triggers
import json
from chunking import flat_chunks
from ingestion import embed_chunks,embed_fn,upload_chunks
import os
from azure.cosmos import CosmosClient

#Azure Functions runtime owns triggers

app = func.FunctionApp()
'''
CosmosClient ->DatabaseClient->ContainerClient
'''
cosmos_client = CosmosClient(
    os.environ["COSMOS_ENDPOINT"],
    credential=os.environ["COSMOS_KEY"],
)
database = cosmos_client.get_database_client("car-db")
container = database.get_container_client("ingestion-state")
'''
Queue message
    ↓
flat_chunks()
    ↓
embed_chunks()
    ↓
upload_chunks()
    ↓
Azure AI Search
@app decorators are specific to Azure Functions Py v2 model and belong to functions registered with
app = func.FunctionApp() 
@app.queue_trigger triggers Azure funtime to start ingest_workder() when msg appears on ingest-queue
@app.Queue_output --- allows to write into post-ingest-queue
ingest-queue = distribute work.
post-ingest-queue = collect completion signals.
existing narrative queue = start the next business workflow.
'''
@app.queue_trigger(
    arg_name="msg",
    queue_name="ingest-queue",
    connection="AzureWebJobsStorage"
)
@app.queue_output(
    arg_name="done",
    queue_name="post-ingest-queue",
    connection="AzureWebJobsStorage",
)
def ingest_worker(msg: func.QueueMessage,done: func.Out[str]):
    job= json.loads(msg.get_body().decode())
    document_id = job["document_id"]
    text = job["text"]
    new_chunks = flat_chunks(doc_id=document_id,text=text,chunk_size=500)
    embedded_chunks = embed_chunks(new_chunks,embed_fn)
    print(f"Indexed {len(embedded_chunks)} chunks")
    upload_chunks(
        endpoint=os.environ["SEARCH_ENDPOINT"],
        key=os.environ["SEARCH_KEY"],
        index_name=os.environ["SEARCH_INDEX"],
        embedded_chunks=embedded_chunks,
    )
    done.set(json.dumps({
        "car_id": job["car_id"],
        "document_id": document_id,
        "status":"complete"
    }))

@app.queue_trigger(
    arg_name="msg",
    queue_name="post-ingest-queue",
    connection="AzureWebJobsStorage",
)
def post_ingest_worker(msg: func.QueueMessage):

    job = json.loads(msg.get_body().decode())
    car_id = job["car_id"]

    state = container.patch_item(
        item=car_id,
        partition_key=car_id,
        patch_operations=[
            {
                "op": "incr",
                "path": "/completed_docs",
                "value": 1,
            }
        ],
    )
    if state["completed_docs"]==state["expected_docs"]:
        print("All docs completed")

@app.queue_trigger(
    arg_name="msg",
    queue_name="car-request-queue",
    connection="AzureWebJobsStorage",
)
def car_worker(msg: func.QueueMessage):
    job = json.loads(msg.get_body().decode())
    car_id = job["car_id"]
    documents = job["documents"]
    print(
        f"Starting {car_id} with {len(documents)} documents"
    )
