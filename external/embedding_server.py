import os
import json
from typing import List, Optional, Literal, Union, Iterator, Dict
from typing_extensions import TypedDict

import llama_cpp

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from sse_starlette.sse import EventSourceResponse
from sentence_transformers import SentenceTransformer

app = FastAPI(
    title="Embeddings API",
    version="0.0.1",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EMBEDDING_MODEL_NAME = 'BAAI/bge-base-en-v1.5' # Choose a custom embedding model
embeddings = SentenceTransformer(EMBEDDING_MODEL_NAME)


class Embedding(BaseModel):
    object: str
    embedding: List[float]
    index: int


class Usage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class CreateEmbeddingRequest(BaseModel):
    model: Optional[str]
    input: Union[str, List[str]]
    user: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "input": "The food was delicious and the waiter...",
            }
        }


class CreateEmbeddingResponse(BaseModel):
    object: str
    data: List[Embedding]
    model: str
    usage: Usage


@app.post(
    "/v1/embeddings",
    response_model=CreateEmbeddingResponse,
)
def create_embedding(request: CreateEmbeddingRequest):
    result = _create_embedding(**request.dict(exclude={"user", "model", "model_config"}))
    return result


def _create_embedding(input: Union[str, List[str]]):
    print(">embedding called")
    global embeddings
    model_name = EMBEDDING_MODEL_NAME
    model_name_short = model_name.split("/")[-1]
    if isinstance(input, str):
        return CreateEmbeddingResponse(data=[Embedding(embedding=embeddings.encode(input).tolist(), object="embedding", index=0)],
                                       model=model_name_short, object='list',
                                       usage=Usage(prompt_tokens=len(input), total_tokens=len(input))) # MARK; could change to tokens, just for test now
    else:
        print(">batch call")
        data = [Embedding(embedding=embedding, object="embedding", index=i)
                for i, embedding in enumerate(embeddings.encode(input).tolist())]
        total_tokens = 0
        for text in input:
            total_tokens += len(text) # MARK; could change to tokens, just for test now
        return CreateEmbeddingResponse(data=data, model=model_name_short, object='list',
                                       usage=Usage(prompt_tokens=total_tokens, total_tokens=total_tokens))


if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=os.getenv("PORT", 8001))
