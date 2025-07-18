from fastapi import APIRouter, HTTPException
from app.schemas.ai import AIRequest, AIResponse
import openai
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
 
router = APIRouter()

@router.post("/", response_model=AIResponse)
def ai_generate(request: AIRequest):
    prompt = f"Answer the following question using the provided context.\nContext: {request.context}\nQuestion: {request.question}"
    try:
        response = openai.responses.create(
            model="gpt-4.1-nano",
            input=[
                {"role": "system", "content": "You are a helpful history assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        answer = response.output_text
        return AIResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
