# GrantScope — Grant Opportunity Matcher

An AI-powered tool that matches animal advocacy and environmental organizations with relevant grant opportunities.

## Live Demo
- **Website:** https://tushar-metrani.github.io/Grant-match-making-tool
- **API:** https://grant-match-making-tool-production.up.railway.app/docs

## Architecture
```
Frontend (HTML/CSS/JS)
  └── POST /api/match → FastAPI (Railway)
      └── Gemini embeddings → pgvector similarity search (Supabase)
      └── Gemini re-scores + generates fit summary
      └── Returns ranked grants

Scheduler (APScheduler, every 24h)
  └── Grants.gov public API → relevance filter → embed → Supabase
```

## Tech Stack
- **Frontend:** Vanilla HTML/CSS/JS
- **Backend:** FastAPI (Python)
- **Database:** Supabase (PostgreSQL + pgvector)
- **AI:** Google Gemini (embeddings + fit analysis)
- **Data Source:** Grants.gov public API
- **Hosting:** Railway (API)

## How It Works
1. A scheduler scrapes Grants.gov every 24 hours using domain-specific keywords
2. Each grant is filtered for relevance using Gemini
3. Relevant grants are embedded using `gemini-embedding-001` and stored in Supabase with pgvector
4. When a user searches, their mission + focus areas are embedded and matched against the DB via cosine similarity
5. Top candidates are re-scored and summarized by Gemini for meaningful alignment scores

## Setup

### Prerequisites
- Python 3.11+
- Supabase account
- Google Gemini API key
- Railway or Render account

### Environment Variables
```
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_service_role_key
GEMINI_API_KEY=your_gemini_api_key
```

### Supabase Setup
Run these SQL commands in your Supabase SQL editor:
```sql
create extension if not exists vector;

create table grants (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  funder text,
  description text,
  focus_areas text[],
  award_min integer,
  award_max integer,
  deadline date,
  application_url text,
  source text,
  embedding vector(768),
  created_at timestamp default now(),
  updated_at timestamp default now()
);

create index on grants using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create or replace function match_grants(
  query_embedding vector(768),
  match_threshold float,
  match_count int
)
returns table(
  id uuid,
  title text,
  funder text,
  description text,
  application_url text,
  deadline date,
  award_min integer,
  award_max integer,
  similarity float
)
language sql stable
as $$
  select
    id, title, funder, description,
    application_url, deadline, award_min, award_max,
    1 - (embedding <=> query_embedding) as similarity
  from grants
  where 1 - (embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit match_count;
$$;
```

### Local Development
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Deployment
Add all environment variables in your hosting platform's dashboard.

## Project Structure
```
grant-matcher-api/
├── app/
│   ├── main.py          # FastAPI entry point
│   ├── config.py        # environment variables
│   ├── database.py      # Supabase client
│   ├── embeddings.py    # Gemini embedding logic
│   ├── scraper.py       # Grants.gov scraper + relevance filter
│   ├── scheduler.py     # 24h scrape scheduler
│   └── routes/
│       └── match.py     # /api/match endpoint
├── frontend/
│   └── index.html
├── requirements.txt
└── README.md
```