# Approach & Technical Thinking

## Finding Grant Data Sources

The first challenge was identifying reliable, structured sources for open grant 
opportunities relevant to animal advocacy and environmental organizations. 
I evaluated three approaches:

- **Pulling data from APIs** (e.g. Grants.gov) and storing to DB
- **Scraping grant listing websites** (e.g. fundsforngos.org) and storing to DB
- **An AI agent** that periodically crawls the web for opportunities, with human 
  verification before storing

I chose Grants.gov because it provides a well-documented public API, is 
authoritative, and is a reliable long-term source. Web scraping was ruled out early 
due to time constraints, though it remains a viable approach for sourcing grants from 
foundation websites that don't provide an API. The AI agent approach was 
interesting but too complex and slow for a prototype.

One honest limitation: Grants.gov is heavily skewed toward government funding, 
which means animal advocacy grants are underrepresented. Environmental 
sustainability grants are well covered.

## Database & Search Strategy

Rather than keyword search, I used semantic similarity via pgvector in Supabase. 
This means "sustainability initiatives" correctly matches "environmental stewardship" 
even when the exact words differ, which is critical for grant 
matching where organizations and funders describe the same work differently.

I chose Supabase because it provides managed PostgreSQL with pgvector built-in, 
a generous free tier, and a dashboard to inspect data, reducing infrastructure 
overhead for a prototype.

## AI Models

I used Google Gemini's `gemini-embedding-001` model with `output_dimensionality=768`.
Gemini was chosen over OpenAI embeddings because it has a generous free tier.

During matching, since the free tier has limited RPM per model, the system 
alternates between a few models in a round-robin fashion on every request, 
effectively increasing the available RPM. If one model hits a rate limit (429 
error), the system automatically falls back to another, making the pipeline more 
resilient without requiring a paid API tier.

## Two-Stage Matching Pipeline

Matching happens in two stages:

1. **Vector similarity (pgvector)** -- fast first pass that retrieves the top 15 
   most semantically similar grants from the database using cosine similarity
2. **AI re-scoring (Gemini)** -- each candidate is then evaluated by Gemini, which 
   generates a meaningful alignment score (0-100) and a one-paragraph fit summary 
   explaining specifically why the grant does or doesn't fit the organization

## Data Quality Decisions

A few decisions were made to improve data quality:

- **Domain-specific keywords** -- instead of broad terms like "wildlife" or "environment", 
  I used targeted phrases like "animal advocacy" and "environmental sustainability" to 
  pull more relevant results from Grants.gov's search API.
- **Relevance filtering** -- before storing any grant, Gemini checks 
  whether it's relevant to animal advocacy or environmental sustainability. This 
  prevents noisy, unrelated grants from polluting the database and affecting 
  search quality.
- **Full detail fetch** -- the Grants.gov search API returns minimal data, so for 
  each result I make a second call to `fetchOpportunity` to retrieve the description 
  and award ceiling/floor amounts.
- **Description truncation** -- full grant descriptions can be very long. I truncate 
  to the first 4 sentences to keep embeddings focused and storage efficient.

## Architecture Decisions

**Frontend:** Kept as vanilla HTML/CSS/JS. The UI is a single page with two inputs 
and a results grid. Adding React would introduce a build step and bundling overhead 
with no real benefit at this scope.

**Scheduler:** APScheduler runs inside FastAPI and re-fetches Grants.gov every 24 
hours. Grant data doesn't change by the minute, so daily refresh is sufficient 
while keeping API usage low.

**Hosting:** Railway for the API (auto-deploys from GitHub), Supabase for the 
database. Both have free tiers sufficient for a prototype.

## Known Limitations

**Grant relevance filtering is imperfect** -- the two-step filter (domain-specific 
keywords + Gemini relevance check) significantly reduces noise but does not 
eliminate it entirely. Some irrelevant grants still make it into the database, 
primarily because Grants.gov descriptions can be vague or overlap with unrelated 
fields. A stricter filtering threshold or a more detailed relevance prompt would 
help but risks filtering out legitimate grants.

**Matching is not perfect and can be slow** -- the two-stage matching pipeline 
(vector similarity + Gemini re-scoring) produces reasonable results but is constrained 
by the quality of grant descriptions available from Grants.gov.Additionally, since 
Gemini generates a fresh summary and alignment score for each matched grant sequentially, 
and the API is on a free tier with rate limits results can take 20-40 seconds to complete. 
A production system would cache generated summaries, use a paid API tier for higher rate 
limits, and benefit from richer grant data sources and potentially fine-tuned embeddings 
trained specifically on grant and nonprofit language.

## What I Would Do To Improve It

- **Add more data sources** -- implement scraping for foundation websites and 
  grant listing platforms like fundsforngos.org to significantly improve coverage, 
  especially for animal advocacy grants which are underrepresented on Grants.gov.

- **AI agent for grant discovery** -- build an agent that periodically crawls 
  the web for new grant opportunities, with a human verification step before 
  storing to ensure data quality.

- **Manual entry UI** -- a simple interface for staff to manually add grant 
  opportunities from sources that can't be scraped or accessed via API.

- **Improve filtering and matching quality** -- use a higher embedding dimension 
  (currently 768), upgrade to better LLM models on a paid tier, and fine-tune the 
  relevance filtering prompt to reduce noise in the database.
