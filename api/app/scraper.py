import httpx
from app.database import supabase
from app.embeddings import get_embedding
from datetime import datetime
from google import genai
from app.config import GEMINI_API_KEY
import time


genai_client = genai.Client(api_key=GEMINI_API_KEY)

def is_relevant_grant(title: str, description: str) -> bool:
    time.sleep(0.5)
    try:
        prompt = f"""You are a strict relevance filter for a vegan-aligned animal welfare and environmental sustainability grant database.

        Grant title: {title}
        Grant description: {description}

        Is this grant relevant to ANY of these domains?
        - Sustainable food system
        - Animal welfare
        - Environmental sustainability or climate change
        - Renewable energy or clean energy
        - Environmental justice or green infrastructure

        Exclude grants that:
        Support or improve animal agriculture without reducing harm (e.g., “sustainable livestock,” “humane meat,” welfare reforms that maintain exploitation)

        Respond with ONLY "yes" or "no". Nothing else.
        
        """

        response = genai_client.models.generate_content(
            model="gemma-3-27b-it",
            contents=prompt
        )
        answer = response.text.strip().lower()
        return answer == "yes"
    except Exception as e:
        print(f"Relevance check error: {e}")
        return True  # if unsure, keep it
    
def truncate_description(text: str, max_sentences: int = 4) -> str:
    if not text:
        return ""
    # Split on sentence endings
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return " ".join(sentences[:max_sentences])


GRANTS_GOV_URL = "https://apply07.grants.gov/grantsws/rest/opportunities/search/"


ANIMAL_ENV_KEYWORDS = [
    # Animal welfare
    "animal welfare",
    "animal advocacy",
    "vegan",
    
    # Environmental & sustainability
    "environmental sustainability",
    "climate change",
    
    # Energy & justice
    "renewable energy",
    "environmental justice",
    "clean energy",
]

async def fetch_opportunity_details(client: httpx.AsyncClient, opportunity_id: str) -> dict:
    try:
        response = await client.post(
            "https://api.grants.gov/v1/api/fetchOpportunity",
            json={"opportunityId": int(opportunity_id)}
        )
        data = response.json()
        if data.get("errorcode") == 0:
            detail = data.get("data", {})
            synopsis = detail.get("synopsis", {})
            
            # Safely parse award amounts
            def parse_amount(val):
                try:
                    if val is None or str(val).lower() in ("none", "", "tbd", "n/a"):
                        return None
                    return int(float(str(val)))
                except:
                    return None

            return {
                "description": synopsis.get("synopsisDesc", ""),
                "award_min": parse_amount(synopsis.get("awardFloor")),
                "award_max": parse_amount(synopsis.get("awardCeiling")),
            }
    except Exception as e:
        print(f"Error fetching details for {opportunity_id}: {e}")
    return {"description": "", "award_min": None, "award_max": None}



async def fetch_grants_gov():
    async with httpx.AsyncClient(timeout=30) as client:
        for keyword in ANIMAL_ENV_KEYWORDS:
            try:
                response = await client.post(GRANTS_GOV_URL, json={
                    "keyword": keyword,
                    "oppStatuses": "posted",
                    "rows": 25,
                    "startRecordNum": 0
                })
                print(f"Grants.gov response status: {response.status_code}")
                data = response.json()
                print(f"Top level keys: {list(data.keys())}")
                print(f"Raw sample: {str(data)[:500]}")
                opportunities = data.get("oppHits", [])
                print(f"Keyword '{keyword}': {len(opportunities)} grants found")
                await process_and_store(opportunities)
            except Exception as e:
                print(f"Error fetching keyword '{keyword}': {e}")
            
            

async def process_and_store(opportunities: list):
    async with httpx.AsyncClient(timeout=30) as detail_client:
        for opp in opportunities:
            try:
                title = opp.get("title", "")
                funder = opp.get("agency", "US Government")
                deadline_str = opp.get("closeDate", None)
                opportunity_id = opp.get("id", "")
                url = f"https://www.grants.gov/search-results-detail/{opportunity_id}"

                if not title:
                    continue

                # fetching more details from fetchOpportunity endpoint
                details = await fetch_opportunity_details(detail_client, opportunity_id)
                description = truncate_description(details["description"]) or title


                if not is_relevant_grant(title, description):
                    print(f"✗ Irrelevant, skipping: {title[:50]}")
                    continue


                # Parse deadline
                deadline = None
                if deadline_str:
                    try:
                        parsed_date = datetime.strptime(deadline_str, "%m/%d/%Y").date()
                        # Ignore obviously wrong dates
                        if parsed_date.year > 2020:
                            deadline = parsed_date.isoformat()
                    except Exception as e:
                        print(f"Deadline parse error: {e} for value: {deadline_str}")

                # Generate embedding
                print(f"Generating embedding for: {title[:50]}")
                text_to_embed = f"{title}. {description}"
                embedding = get_embedding(text_to_embed)
                print(f"Embedding generated, length: {len(embedding)}")

                # Check duplicate
                existing = supabase.table("grants")\
                    .select("id")\
                    .eq("application_url", url)\
                    .execute()

                if existing.data:
                    print(f"Skipping duplicate: {title[:50]}")
                    continue

                # Insert
                result = supabase.table("grants").insert({
                    "title": title,
                    "funder": funder,
                    "description": description,
                    "focus_areas": [],
                    "award_min": details["award_min"],
                    "award_max": details["award_max"],
                    "deadline": deadline,
                    "application_url": url,
                    "source": "grants.gov",
                    "embedding": embedding
                    }).execute()
                print(f"✓ Inserted: {title[:50]}")

            except Exception as e:
                print(f"Error processing grant '{opp.get('title', 'unknown')}': {e}")