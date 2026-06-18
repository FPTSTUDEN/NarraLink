import json
from io import BytesIO

import requests
from fastapi import FastAPI, Request, Response

app = FastAPI()

# Direct Ollama endpoint
OLLAMA_URL = "http://localhost:11434/api/generate"

MODEL_MAP = {
    "ollama/tinyllama": "tinyllama",
    "anthropic.claude-3-sonnet-20240229-v1:0": "tinyllama",
    # Add more mappings as needed
}


@app.post("/model/{model_id:path}/invoke")
async def invoke_model(model_id: str, request: Request):
    body = await request.json()

    # Extract messages from the request
    messages = body.get("messages", [])
    
    # Convert OpenAI-style messages to a single prompt
    # (Ollama's /api/generate expects a single prompt)
    prompt = ""
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            prompt += f"System: {content}\n\n"
        elif role == "user":
            prompt += f"User: {content}\n"
        elif role == "assistant":
            prompt += f"Assistant: {content}\n"
    
    # Get the Ollama model name from mapping
    ollama_model = MODEL_MAP.get(model_id, "tinyllama")
    
    # Call Ollama directly
    ollama_response = requests.post(
        OLLAMA_URL,
        json={
            "model": ollama_model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.7,
        },
        timeout=120,
    )
    
    ollama_response.raise_for_status()
    result = ollama_response.json()
    
    # Extract the generated text
    text = result.get("response", "")
    
    # Format response to match Bedrock API format
    bedrock_response = {
        "content": [
            {
                "type": "text",
                "text": text
            }
        ]
    }
    
    return Response(
        content=json.dumps(bedrock_response),
        media_type="application/json"
    )