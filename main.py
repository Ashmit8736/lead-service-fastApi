from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import logging
from google import genai
from google.genai import types
from groq import Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Smart Lead Scoring AI API")

# ---------- Gemini Client ----------
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if not gemini_api_key:
    logger.warning("GEMINI_API_KEY missing.")
gemini_client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

# ---------- Groq Client (fallback) ----------
groq_api_key = os.environ.get("GROQ_API_KEY")
if not groq_api_key:
    logger.warning("GROQ_API_KEY missing.")
groq_client = Groq(api_key=groq_api_key) if groq_api_key else None


class AiScoreRequest(BaseModel):
    id: str
    name: Optional[str] = None
    contact: Optional[str] = None
    message: Optional[str] = None
    source: Optional[str] = None
    budget: Optional[float] = None
    company: Optional[str] = None


class AiScoreResponse(BaseModel):
    id: str
    score: int
    category: str
    reason: str
    raw_response: dict
    model_used: str


def build_prompt(req: AiScoreRequest) -> str:
    return f"""
    Analyze the following lead data and provide a score between 0 and 100, a category (HOT, WARM, or COLD), and a short reason.
    Return ONLY a valid JSON object with keys: "score", "category", "reason".

    Lead Data:
    Name: {req.name}
    Contact: {req.contact}
    Message: {req.message}
    Source: {req.source}
    Budget: {req.budget}
    Company: {req.company}
    """


def generate_mock_score(req: AiScoreRequest) -> AiScoreResponse:
    score = 50
    if req.budget and req.budget > 10000:
        score += 30
    if req.message and len(req.message) > 50:
        score += 10

    score = min(100, score)
    category = "HOT" if score >= 80 else "WARM" if score >= 40 else "COLD"

    return AiScoreResponse(
        id=req.id,
        score=score,
        category=category,
        reason="Mock logic (both AI providers unavailable)",
        raw_response={"mock_score": score, "logic": "budget > 10000 -> +30"},
        model_used="mock"
    )


def parse_json_response(result_text: str) -> dict:
    result_text = result_text.strip()
    if result_text.startswith("```json"):
        result_text = result_text[7:-3].strip()
    elif result_text.startswith("```"):
        result_text = result_text[3:-3].strip()
    return json.loads(result_text)


def call_gemini(req: AiScoreRequest) -> Optional[AiScoreResponse]:
    if not gemini_client:
        return None

    prompt = build_prompt(req)
    try:
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        data = parse_json_response(response.text)

        return AiScoreResponse(
            id=req.id,
            score=data.get("score", 0),
            category=data.get("category", "COLD"),
            reason=data.get("reason", "No reason provided"),
            raw_response=data,
            model_used="gemini-2.5-flash"
        )
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return None


def call_groq(req: AiScoreRequest) -> Optional[AiScoreResponse]:
    if not groq_client:
        return None

    prompt = build_prompt(req)
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a JSON-only response generator. Respond ONLY with valid JSON, no markdown, no extra text."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        result_text = response.choices[0].message.content
        data = parse_json_response(result_text)

        return AiScoreResponse(
            id=req.id,
            score=data.get("score", 0),
            category=data.get("category", "COLD"),
            reason=data.get("reason", "No reason provided"),
            raw_response=data,
            model_used="llama-3.3-70b-versatile (groq)"
        )
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return None


def call_ai(req: AiScoreRequest) -> AiScoreResponse:
    # 1st try: Gemini
    result = call_gemini(req)
    if result:
        return result

    logger.warning(f"Gemini failed for lead {req.id}, falling back to Groq...")

    # 2nd try: Groq
    result = call_groq(req)
    if result:
        return result

    logger.warning(f"Groq also failed for lead {req.id}, falling back to mock...")

    # 3rd try: Mock (last resort so app never crashes)
    return generate_mock_score(req)


@app.post("/api/ai/score", response_model=AiScoreResponse)
async def score_single_lead(req: AiScoreRequest):
    return call_ai(req)


@app.post("/api/ai/score/batch", response_model=List[AiScoreResponse])
async def score_batch_leads(requests: List[AiScoreRequest]):
    if len(requests) > 50:
        raise HTTPException(status_code=400, detail="Batch size cannot exceed 50")

    responses = []
    for req in requests:
        responses.append(call_ai(req))

    return responses