You are the principal software architect and implementation engineer for my personal IELTS learning platform.

## Product vision

Build a holistic, AI-powered IELTS Academic self-learning web application focused on three modules: Listening, Reading, and Writing.

This is initially a single-user application, but the architecture should remain extensible.

### Learning targets
- Listening: Band 9.0
- Reading: Band 9.0
- Writing: Band 7.5–9.0

Speaking is explicitly out of scope.

## Module 1: Listening

Primary content source:
https://www.youtube.com/@TheIELTSListeningTest

Requirements:
- Integrate YouTube Data API v3.
- Resolve channel handles and synchronize uploaded videos.
- Store video metadata and ingestion status.
- Embed videos using the official YouTube player.
- Support IELTS-style question sets, answer submission, scoring, and explanations.
- Allow manual question and answer-key entry.
- Support AI-assisted question creation only when suitable authorized source material is available.
- Track attempts, accuracy, completion time, and recurring mistakes.
- Do not download or extract third-party audio or transcripts without appropriate authorization.

## Module 2: Reading

Primary content source: Wikipedia / MediaWiki API.

Requirements:
- Discover articles by topic and difficulty.
- Retrieve source content with attribution and license metadata.
- Generate original IELTS Academic-style reading passages.
- Generate multiple question types, including True/False/Not Given, Matching Headings, Multiple Choice, and Completion.
- Validate answers and supporting evidence.
- Support timed practice and detailed explanations.
- Track performance by question type.
- Distinguish AI-generated practice scores from calibrated IELTS mock-test results.

## Module 3: Writing

Requirements:
- Support Academic Writing Task 1 and Task 2.
- Provide prompts and a timed writing editor.
- Evaluate submissions against the four official IELTS Writing assessment criteria.
- Generate criterion-level feedback with supporting examples.
- Identify grammar, vocabulary, coherence, and task-response issues.
- Support revision and comparison between attempts.
- Preserve original submissions and assessment history.
- Clearly label AI-generated band estimates as unofficial.

## Shared capabilities

- Learning dashboard.
- Practice history.
- Progress analytics.
- Error classification.
- Adaptive practice recommendations.
- Configurable study goals.
- Content provenance and quality validation.

## Technical stack

Frontend:
- React + TypeScript + Vite
- Material UI (MUI)
- TanStack Query

Backend:
- Python FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL

AI:
- LLM API with structured outputs.
- Versioned prompts and grading rubrics.
- Validation of generated questions.

Architecture:
- Modular monolith.
- REST APIs.
- Shared assessment and progress tracking.
- Background jobs for content ingestion and generation.
- Docker-based local development.

## Engineering principles

- Prefer simplicity over premature abstraction.
- Keep domain logic independent of external providers.
- Design idempotent ingestion jobs.
- Store source provenance and licensing metadata.
- Use migrations for schema changes.
- Add automated tests for critical business logic.
- Never invent official IELTS band equivalences for AI-generated tests.
- Keep credentials out of source control.

## Initial assignment

1. Inspect the existing repository.
2. Create PROJECT.md documenting the complete product requirements.
3. Create AGENTS.md containing persistent development instructions.
4. Propose a modular architecture.
5. Design the initial PostgreSQL schema.
6. Define the REST API contracts.
7. Produce a phased implementation plan with acceptance criteria.

Do not implement the entire application immediately.

First present the architecture, key trade-offs, open questions, and proposed development milestones for review.
