'''
START
 ↓
POLICY
 ├── BLOCK → BLOCKED RESPONSE → END
 ↓ ALLOW
ROUTER
 ├── SQL → SQL SEARCH ─────────────┐
 │                                 ↓
 └── SEMANTIC → RAG SEARCH     RETRIEVAL GUARD
                 ↓                 ↓
             MERGE/RERANK       GENERATE
                                   ↓
                              FACTUAL GUARD
                                   ↓
                             REASONING GUARD
                                   ↓
                             CONTRACT VALIDATE
                              /      |      \
                           PASS    RETRY    FAIL
                            ↓        ↓        ↓
                           END    GENERATE  FALLBACK
                                             ↓
                                            END

State
→ Node functions
→ Routing functions
→ Add nodes
→ Add edges
→ Add conditional edges
→ Compile
→ Invoke


Semantic PATH: START
→ policy_check
→ route_query
→ rag_search
→ merge_rerank
→ retrieval_guard
→ generate_answer
→ factual_guard
→ reasoning_guard
→ validate_answer
→ END / retry / fallback

SQL PATH: START
→ policy_check
→ route_query
→ sql_search
→ retrieval_guard
→ generate_answer
→ factual_guard
→ reasoning_guard
→ validate_answer

'''

from typing import TypedDict
from langgraph.graph import StateGraph, START, END
'''
Question: query
Decisions: policy_action, route
Results: context, answer
Controls: validation_status, retry_count
'''
class GraphState(TypedDict,total = False):
    query:str
    policy_action:str
    retrieval_path:str

    uploaded_results: list[dict]
    source_results: list[dict]
    car_results: list[dict]

    context:str
    answer:str

    validate_state:str
    retry_count:int

#{"query": "What is the borrower’s current rating?", "retry_count": 0}
#receives state → performs one job → returns state updates
########## NODE FUNCTIONS ##########
'''
PolicyCheck
'''
def policy_check(state: GraphState) -> dict:
    query = state['query'].lower()
    blocked_terms = ["hack","password","confidential"]
    action = "BLOCK" if any( term in query for term in blocked_terms) else "ALLOW"
    return {"policy_action":action}

def blocked_response(state:GraphState)->dict:
    return { "answer": "This request cannot be processed"}

'''
RouteQuery
'''
def route_query(state:GraphState)->dict:
    query = state['query'].lower()
    sql_terms = ["count","total","average","how many"]
    route = "SQL" if any(term in query for term in sql_terms) else "SEMANTIC"
    return {"retrieval_path":route}

'''
RAG Search and 3 indexes 
'''
def search_uploaded_index(query):
    return [{
            "text":f"Uploaded document result for {query}",
            "source":"uploaded_doc",
            "score": 0.9
        }]
def search_source_index(query):
    return [{
            "text":f"Enterprise  source result for {query}",
            "source":"enterprise",
            "score": 0.9
        }]
def search_generated_car_index(query):
    return [{
            "text":f"Generated CAR result for {query}",
            "source":"generated_car",
            "score": 0.8
        }]
def rag_search(state:GraphState)->dict:
    query = state['query'].lower()
    return {
        "uploaded_results": search_uploaded_index(query),
        "source_results": search_source_index(query),
        "car_results": search_generated_car_index(query),
    }
'''
SQL Search
'''
def sql_search(state:GraphState)->dict:
    query = state['query'].lower()
    context = f"SQL search result for: {query}"
    return {
        "context":context
    }
'''
re-Rank
'''
def merge_rerank(state:GraphState)->dict:
    results = (state["uploaded_results"] +state["source_results"]+state["car_results"])
    for item in results:
        if item["source"] == "uploaded_doc":
            item["score"]+= .10
    ranked = sorted(results,key=lambda item: item["score"],reverse=True)
    return {
        "context": "\n".join(
            item["text"] for item in ranked[:5]
        )
    }
def retrieval_guard(state:GraphState)->dict:
    context = state.get("context", "")
    if  not context:
        return {"validate_state":"FAIL"}
    return {"validate_state":"PASS"}

def generate_answer(state:GraphState)->dict:
    context = state.get("context", "")
    query = state["query"]
    # Ideally this is where the LLM would be called
    answer = f"Generated Answer for '{query}' using: {context}"
    return {"answer":answer}

def factual_guard(state:GraphState)-> dict:
    answer = state.get("answer","")
    #In production, this node would compare critical generated facts against authoritative evidence.
    if not answer:
        return {"validate_state":"FAIL"}
    return {"validate_state":"PASS"}

def reasoning_guard(state:GraphState)-> dict:
    context = state.get("context","")
    answer = state.get("answer","")
    #In production, this node uses a smaller judge model to check whether the answer’s reasoning is supported by the retrieved evidence.
    if not context or not answer:
        return {"validate_state":"FAIL"}
    return  {"validate_state":"PASS"}
'''
VALIDATE
'''
def validate_answer(state: GraphState) -> dict:
    answer = state.get("answer", "")
    is_valid = bool(answer) and len(answer) <= 2000
    if is_valid :
        return {"validate_state": "PASS"}

    retry_count = state.get("retry_count", 0)

    if retry_count < 2:
        return {
            "validate_state": "RETRY",
            "retry_count": retry_count + 1,
        }

    return {"validate_state": "FAIL"}

'''
enterprise doc search : search only docs used to generate car
'''
def fallback(state: GraphState) -> dict:
    return {
        "answer": "I could not produce a reliable answer from the available information."
    }

########## ADD ROUTING FUNCTIONS ##########
def route_after_policy(state: GraphState)->str:
    if state["policy_action"]=="BLOCK":
        return "blocked_response"
    return "route_query"

def route_after_query(state: GraphState)->str:
    if state["retrieval_path"]=="SQL":
        return "sql_search"
    return "rag_search"

def route_after_validation(state: GraphState)->str:
    status = state["validate_state"]
    if status == "PASS":
        return END
    if status == "FAIL":
        return "fallback"
    return "generate_answer"

def after_retrieval_guard(state: GraphState)->str:
    if state["validate_state"]=="FAIL":
        return "fallback"
    return "generate_answer"
def after_factual_guard(state: GraphState)->str:
    if state["validate_state"]=="FAIL":
        return "fallback"
    return "reasoning_guard"
def after_reasoning_guard(state: GraphState)->str:
    if state["validate_state"]=="FAIL":
        return "fallback"
    return "validate_answer"
########## ADD NODES ##########
workflow = StateGraph(GraphState)
workflow.add_node("policy_check", policy_check)
workflow.add_node("blocked_response", blocked_response)
workflow.add_node("route_query", route_query)
workflow.add_node("rag_search", rag_search)
workflow.add_node("sql_search", sql_search)
workflow.add_node("fallback", fallback)
workflow.add_node("merge_rerank", merge_rerank)
workflow.add_node("retrieval_guard", retrieval_guard)
workflow.add_node("generate_answer", generate_answer)
workflow.add_node("factual_guard", factual_guard)
workflow.add_node("reasoning_guard", reasoning_guard)
workflow.add_node("validate_answer", validate_answer)

########## ADD CONDITIONAL EDGES ##########
'''
Policy validation → BLOCK or ALLOW
Query routing     → RAG or SQL

'''
workflow.add_edge(START,"policy_check")
workflow.add_conditional_edges("policy_check",route_after_policy)
workflow.add_conditional_edges("route_query",route_after_query)
workflow.add_conditional_edges("validate_answer",route_after_validation)
workflow.add_conditional_edges("retrieval_guard",after_retrieval_guard)
workflow.add_conditional_edges("factual_guard",after_factual_guard)
workflow.add_conditional_edges("reasoning_guard",after_reasoning_guard)

workflow.add_edge("rag_search","merge_rerank")
workflow.add_edge("merge_rerank","retrieval_guard")
workflow.add_edge("generate_answer","factual_guard")

workflow.add_edge("sql_search", "retrieval_guard")

########## ADD NORMAL EDGES ##########
workflow.add_edge("blocked_response", END)
workflow.add_edge("fallback",END)

########## COMPILE and INVOKE ##########

graph = workflow.compile()
result = graph.invoke({
    "query":"whats the borrowers' current rating",
    "retry_count":0
})
