import httpx
from app.database import supabase
from app.embeddings import get_embedding
from datetime import datetime

GRANTS_GOV_URL = "https://apply07.grants.gov/grantsws/rest/opportunities/search/"

ANIMAL_ENV_KEYWORDS = [
    "wildlife", "conservation", "marine", "ocean", "habitat",
    "endangered species", "animal welfare", "environmental",
    "climate", "ecosystem", "biodiversity", "coastal"
]

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
            
            # Only test first keyword for now
            

async def process_and_store(opportunities: list):
    for opp in opportunities:
        try:
            title = opp.get("title", "")
            description = opp.get("synopsis", "") or title
            funder = opp.get("agency", "US Government")
            deadline_str = opp.get("closeDate", None)
            opportunity_id = opp.get("id", "")
            url = f"https://www.grants.gov/search-results-detail/{opportunity_id}"

            if not title:
                continue

            # Parse deadline
            deadline = None
            if deadline_str:
                try:
                    deadline = datetime.strptime(deadline_str, "%m/%d/%Y").date().isoformat()
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
                "award_min": None,
                "award_max": None,
                "deadline": deadline,
                "application_url": url,
                "source": "grants.gov",
                "embedding": embedding
            }).execute()
            print(f"✓ Inserted: {title[:50]}")

        except Exception as e:
            print(f"Error processing grant '{opp.get('title', 'unknown')}': {e}")