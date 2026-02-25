from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# This is just to check API is alive
@app.get("/")
def read_root():
    return {"message": "API is running"}


# Step 1: Define what input we expect
class QueryRequest(BaseModel):
    query: str


# Step 2: Create POST endpoint
@app.post("/api/query")
def query_api(request: QueryRequest):
    return {
        "answer": f"You asked: {request.query}",
        "query_type": "demo",
        "confidence_score": 0.99
    }