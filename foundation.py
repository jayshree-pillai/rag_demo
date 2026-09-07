import re
from fastapi import FastAPI
from pydantic import BaseModel,Field,field_validator

app = FastAPI()

class ChatRequest(BaseModel):
    query: str = Field(min_length=1,max_length=2000)

    @field_validator('query')
    @classmethod
    def validate_query(cls, value):
        print(f"Step1: Validation of input happens")
        return " ".join(value.split())

class ChatResponse(BaseModel):
    answer: str = Field(min_length=1,max_length=2000)

    @field_validator('answer')
    @classmethod
    def validate_answer(cls, value):
        print(f"Step-1: validation of answer happens")
        return " ".join(value.split())


@app.post("/chat",response_model=ChatResponse)
async def chat(request:ChatRequest):
    print(f"step2: chat request is sent")
    return ChatResponse(answer=request.query)