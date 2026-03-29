from fastapi import APIRouter
from pydantic import BaseModel
from app.embeddings import get_embedding
from app.database import supabase
from app.config import GEMINI_API_KEY
from google import genai
import json
from datetime import date
from google.genai.errors import ClientError
import asyncio


class MatchRequest(BaseModel):
    mission: str
    areas: str
    

router = APIRouter()

# Two clients, same key — round robin across two model IDs to get 10 RPM
MODELS = [
    "gemma-3-12b-it",
    "gemma-3-27b-it",
    "gemini-3.1-flash-lite-preview",
]

client = genai.Client(api_key=GEMINI_API_KEY)
current_model_index = 0

def get_next_model() -> str:
    global current_model_index
    model = MODELS[current_model_index]
    current_model_index = (current_model_index + 1) % len(MODELS)
    return model

async def generate_fit_analysis(mission: str, areas: str, grant_title: str, grant_description: str) -> dict:
    prompt = f"""You are an expert grant matching assistant helping a nonprofit find funding.

Organization mission: {mission}
Focus areas: {areas}

Grant opportunity: {grant_title}
Grant description: {grant_description}

Respond ONLY with a JSON object, no markdown, no backticks, no explanation. Format:
{{
  "alignment_score": <integer 0-100 representing how well this grant fits the organization>,
  "summary": "exactly 60 words explaining why this grant is or isn't a good fit. Be specific and practical. Do not start with This grant.>"
}}

When scoring alignment consider:
- How well the grant's focus matches the organization's mission
- Whether the organization's work falls within the grant's eligible activities
- How strongly the focus areas overlap"""

    # Try each model, fall back if rate limited
    for attempt in range(len(MODELS)):
        model = get_next_model()
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            parsed = json.loads(raw.strip())
            return {
                "alignment": min(100, max(0, int(parsed.get("alignment_score", 50)))),
                "summary": parsed.get("summary", "This opportunity aligns with your organization's mission.")
            }

        except ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"Rate limited on {model}, trying next model...")
                await asyncio.sleep(1)
                continue
            raise e
        except Exception as e:
            print(f"Error on {model}: {e}")
            continue

    # All models exhausted
    return {
        "alignment": 50,
        "summary": "This grant opportunity aligns with your organization's mission and focus areas."
    }



@router.post("/api/match")
async def match_grants(req: MatchRequest):
    query_text = f"{req.mission}. Focus areas: {req.areas}"
    query_embedding = get_embedding(query_text)

    # Semantic search via pgvector — cast a wider net since AI will re-score
    response = supabase.rpc("match_grants", {
        "query_embedding": query_embedding,
        "match_threshold": 0.5,
        "match_count": 15
    }).execute()

    results = []
    today = date.today()

    for grant in response.data:
        # Calculate days left
        days_left = None
        if grant.get("deadline"):
            try:
                deadline_date = date.fromisoformat(grant["deadline"])
                days_left = (deadline_date - today).days
                if days_left < 0:
                    continue
            except:
                pass

        # Generate AI fit analysis (summary + alignment score)
        analysis = await generate_fit_analysis(
            mission=req.mission,
            areas=req.areas,
            grant_title=grant["title"],
            grant_description=grant["description"] or grant["title"]
        )

        results.append({
            "id": grant["id"],
            "title": grant["title"],
            "funder": grant["funder"] or "Unknown",
            "description": grant["description"] or "",
            "summary": analysis["summary"],
            "application_url": grant["application_url"] or "#",
            "deadline": grant.get("deadline"),
            "award_min": grant.get("award_min"),
            "award_max": grant.get("award_max"),
            "alignment": analysis["alignment"],
            "days_left": days_left
        })

    # Sort by AI alignment score
    results.sort(key=lambda x: x["alignment"], reverse=True)
    
    # Return top 10 after AI re-ranking
    return {"grants": results[:10]}