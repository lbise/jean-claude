# Jean-Claude - Project Foundation

## 1) Vision

Jean-Claude is a media management and discovery agent.
Its long-term purpose is to scout the internet and suggest new TV series and movies based on each user's preferences, with clear explanations for why each recommendation fits.

## 2) Product Direction

- **Deployment model:** self-hosted
- **User interface:** web interface is a core requirement
- **Initial build strategy:** start with a minimal CLI app, then expand to web
- **Core capability to establish first:** reliable LLM integration

## 3) Key Decisions (Current)

### Language and stack

- **Backend / agent core:** Python
- **Web frontend (long-term):** React
- **Backend API (long-term):** FastAPI
- **Background processing (long-term):** worker queue + scheduler
- **Self-hosting baseline (long-term):** Docker Compose

Rationale:
- Python is best suited for agent logic, metadata processing, and recommendation workflows.
- React provides a strong path for a user-friendly self-hosted UI.
- This split keeps the recommendation engine flexible and UI-independent.

### LLM strategy

- Introduce an internal `LLMClient` interface from day one.
- Implement OpenAI-compatible provider first.
- Keep provider configuration externalized (model, key, base URL, timeout, retries).
- Preserve portability for future local/self-hosted models (e.g., OpenAI-compatible gateways).

## 4) Architecture Roadmap

### Phase 0 (Now): CLI-only MVP

Goal: prove core recommendation loop with minimal complexity.

Scope:
- CLI commands for:
  - loading user preferences
  - running recommendation generation
  - printing ranked suggestions with reasons
- LLM-backed ranking/explanation
- simple local storage (JSON/YAML/SQLite)
- deterministic tests via mocked LLM responses

Out of scope:
- web UI
- authentication
- multi-user tenancy
- distributed workers

### Phase 1 (Next): Web-enabled self-hosted platform

Scope:
- FastAPI backend exposing recommendation endpoints
- React web interface for preferences + recommendation feed
- background scout jobs (scheduled internet discovery)
- persistent metadata + recommendation history
- containerized deployment for self-hosting

## 5) CLI MVP Functional Spec

### Inputs

- User taste profile (genres, tone, languages, release recency, disliked themes)
- Candidate titles dataset (initially local/static source)

### Processing

1. Normalize preferences and candidate metadata
2. Score/rank candidates with LLM assistance
3. Generate concise recommendation reasons
4. Return top-N list

### Output

- Ranked titles with:
  - title
  - type (movie/series)
  - score
  - short "why this matches you" explanation

## 6) Proposed Initial CLI Commands

- `jc prefs init` - create default preference profile
- `jc prefs edit` - update profile fields
- `jc recommend --top 10` - run recommendation pipeline
- `jc recommend --json` - machine-readable output

(Exact command names can be adjusted during implementation.)

## 7) Suggested Project Structure (Initial)

```text
jean-claude/
  src/jean_claude/
    cli.py
    config.py
    domain/
      models.py
    llm/
      base.py
      openai_client.py
    recommend/
      engine.py
      prompts.py
    storage/
      prefs_store.py
      candidate_store.py
  data/
    candidates.sample.json
  tests/
    test_recommend_engine.py
    test_cli.py
  pyproject.toml
  README.md
  .env.example
```

## 8) Non-Functional Requirements

- clear provider abstraction (avoid LLM vendor lock-in)
- robust timeout/retry behavior
- deterministic test path without network calls
- low-friction local run experience for self-host users
- explicit configuration via environment variables

## 9) Milestones

1. **M1 - Foundation**
   - Python project scaffold
   - CLI skeleton
   - config loading
2. **M2 - LLM Access**
   - `LLMClient` interface
   - OpenAI-compatible provider implementation
   - connectivity smoke test
3. **M3 - Recommendation Loop**
   - preferences + candidate ingestion
   - ranking/explanation pipeline
   - top-N CLI output
4. **M4 - Test and Hardening**
   - mocked unit tests
   - basic error handling and UX polish
5. **M5 - Web Transition**
   - FastAPI + React plan execution

## 10) Immediate Next Step

Implement the CLI-first MVP (Phase 0), while keeping module boundaries ready for Phase 1 web integration.
