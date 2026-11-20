# IELTS Academic learning platform

## Product scope

A personal web app for IELTS Academic Listening, Reading, and Writing. Initial goals are Listening 9.0, Reading 9.0, and Writing 7.5–9.0. Speaking is out of scope. Start with one learner and carry learner ownership through the data model and API.

- **Listening.** Synchronize the uploads of [The IELTS Listening Test](https://www.youtube.com/@TheIELTSListeningTest) via YouTube Data API v3. Resolve the handle to a channel ID, page through its uploads playlist, and upsert video metadata and availability by video ID. Use the official player and show an unavailable state if a video cannot be embedded. Attach manually authored IELTS-style questions, accepted answers, and explanations to videos. Enable AI question drafting only for source material explicitly authorized for that use. Require appropriate authorization before downloading or extracting third-party audio or transcripts. Track timing, accuracy, completion, and recurring errors. [YouTube uploads API](https://developers.google.com/youtube/data/sample_requests)
- **Reading.** Discover Wikipedia articles by topic and estimated difficulty. Record page and revision IDs, attribution, applicable licensing, and source links. Generate original IELTS Academic-style passages and True/False/Not Given, Matching Headings, Multiple Choice, and Completion questions. Validate answer keys, evidence, ambiguity, and completion word limits before publication. For Not Given, record a rationale grounded in what the passage covers. Support timers, item explanations, and trends by question type. Display raw practice scores separately from mock results with documented calibration. [MediaWiki rights metadata](https://www.mediawiki.org/wiki/API%3ASiteinfo)
- **Writing.** Provide Task 1 prompts with the relevant chart, table, or diagram and Task 2 essay prompts. Include a timed, autosaving editor. Assess Task Achievement for Task 1 or Task Response for Task 2, plus Coherence and Cohesion, Lexical Resource, and Grammatical Range and Accuracy. Provide examples anchored to the submitted text and actionable feedback on grammar, vocabulary, coherence, and task fulfillment. Label AI band estimates unofficial. Preserve submitted text and every assessment. Let the learner revise and compare linked submissions and their feedback. [IELTS Academic Writing format](https://ielts.org/take-a-test/test-types/ielts-academic-test/ielts-academic-format-writing)
- **Shared experience.** Provide a dashboard, practice history, progress trends, labeled mistakes, adaptive recommendations with reasons, configurable goals, and visible content provenance and validation status. Start recommendations with rules based on recent weaknesses, sample size, and goals.

## Proposed architecture and trade-offs

Listening Theater mode spans the available page width, with the video above the 40 answer fields in a single scrolling page. Listening self-marking displays the raw score and a practice band estimate from IDP's Listening conversion ranges. Scores below 11 correct display an estimated band below 4.0. [IDP Listening reference ranges](https://ielts.idp.com/vietnam/results/scores/listening/)

### Full Academic Reading mock

The primary Reading action is **Generate mock**. The worker randomly samples three distinct, suitable English Wikipedia topics from a filtered candidate pool and records each article revision and attribution. Generate one original passage per topic and validate the complete mock before it can be taken. The format is three passages totaling 2,150–2,750 words, 40 one-point questions, and 60 minutes. Include at least one passage with a developed argument and vary question formats across the test. [Official Academic Reading format](https://ielts.org/take-a-test/test-types/ielts-academic-test/ielts-academic-format-reading)

The countdown starts when the learner selects **Start test** after generation and review. Show passage and question panes, passage tabs, a numbered question navigator with answered and unanswered states, and a **Submit** button. Autosave answers, restore them on refresh, and calculate time remaining from the server deadline. At expiry finalize the last server-accepted answers.

Offer random discovery and 26 selectable topics grouped under Environment, Science, Health, Technology, and Society and Culture. A selected topic guides the Wikipedia search for all three passages. Show queued, running, and ready states, restore generation status when the learner returns to Reading, and let them start a previously completed mock while the next one runs.

Reading and Writing practice support pause and resume. Pausing saves the draft, freezes the server timer, and hides the test content until resumed. Use a wider, equal-width split for Reading passages and questions on desktop and stack the panes on smaller screens. Offer selectable Reading text size and Writing editor height.

Standalone Writing shares Reading’s broad categories and adds Writing themes such as education, work, housing, and public services. Learners can choose a category per task or let the app choose. A background job generates original prompts. Task 1 varies the number of series and observations and can use grouped bars, multiple lines, two or three pies, a table, or a paired bar chart and table. The paired layout displays original counts in the bar chart and calculates the matching percentage shares for the table. Consecutive generated Task 1 prompts use different layouts. The timer starts when the learner opens the completed test. Three-skill simulations select prompts automatically, and rewrites retain the original prompt. [British Council chart samples](https://takeielts.britishcouncil.org/sites/default/files/writing_task_1_-_which_graphics.pdf) [IDP Academic Writing Task 1 materials](https://info.ielts.idp.com/rs/561-EIU-022/images/IELTS%20Focus%20-%20AC%20Writing%20T1%20-%20Student%20Updated.pdf)

Generated Task 1 exercises render validated numerical data through Chart.js. Paired layouts can present counts and calculated shares as a bar chart with a table or a line graph. Dataset analysis and the 170–200 word sample response become available after submission. Writing feedback provides three or four topic-specific example sentences that can be added to the draft during a retry.

Grade immediately against the stored answer key. Show the raw score out of 40, highlight incorrect and unanswered items with text labels, and display the learner’s answer, accepted answer, explanation, and relevant passage evidence. Generated mocks also show an unofficial band estimate from the IDP Academic Reading reference ranges. Scores outside the published range display an upper bound. A calibrated band requires a documented mapping for the exact test version. [IELTS scoring guidance](https://www.ielts.org/take-a-test/your-results/ielts-scoring-in-detail) [IDP Academic Reading reference ranges](https://ielts.idp.com/saudiarabia/results/scores/reading/en-gb)

Model the three ordered passages within an immutable activity version and link each question to its passage. Allow the Reading generation request to omit explicit sources for a random full mock. Display generation and review status before starting the attempt. Phase 3 acceptance includes a complete mock, refresh-safe countdown, expiry submission, immediate grading, and evidence-linked review.

Reading generation uses an evidence-first item blueprint and requires an explanation for each multiple-choice distractor. Store passage and question IDs, evidence spans, targeted skills, provisional difficulty labels, and validation results. Learners see the answer metadata after submitting.

Generate passage text and question groups in separate requests. Report validated drafts and question groups as they finish. Bound model requests by a shared 10-minute generation window and stop starting sibling requests when an error ends the attempt. Split a draft after an output token limit or a second validation failure. Size the second half using the first half’s actual word count, then validate the assembled passage before generating questions. Question batches reuse their passage and shared option bank. Store evidence using the original contiguous passage quote, including when the model alters whitespace or typography.

Use React, TypeScript, Vite, Material UI (MUI), and TanStack Query. Use a FastAPI modular monolith with SQLAlchemy, Alembic, and PostgreSQL. Docker Compose runs the UI, API, PostgreSQL, and a worker built from the backend codebase. Begin with one seeded learner behind a server-side identity dependency for local-only use. Require authentication and ownership enforcement before remote exposure.

- **Content modules** own Listening catalog sync and authoring, Reading discovery and generation, and Writing prompts. A shared content workflow handles drafts, validation, review, publication, and provenance.
- **Assessment** owns attempt state, timing, deterministic objective grading, and stored writing assessments. **Progress** reads submitted attempts and assessment records to build history, aggregates, and recommendations.
- **Provider adapters** isolate YouTube, MediaWiki, and the structured-output LLM API. Domain scoring and validation run independently of those providers. Keep prompts, rubrics, and output schemas versioned. Validate model output server-side and verify feedback references against source text.
- **Jobs** use PostgreSQL for ingestion, generation, and writing assessment. Claim work with transactional row locking and a lease. Use bounded retries, backoff, and recoverable expired leases. Deduplicate enqueue requests and make result writes idempotent. This avoids a separate broker in local development and leaves queue throughput and monitoring to be revisited if workload increases.
- **Quality and scoring.** Require manual approval of generated drafts initially. Score objective work server-side using explicit normalization, accepted variants, and configured word limits. Use a calibrated conversion only when the exact test version has a documented mapping. Compute time from server timestamps and keep model estimates separate from objective scores. [IELTS scoring guidance](https://ielts.org/take-a-test/your-results/ielts-scoring-in-detail)

## Initial PostgreSQL schema

Use UUID primary keys, foreign keys, and UTC timestamps. Use enums or check constraints for bounded states and required fields. Use JSONB for typed, validated payloads that vary by question or job type.

| Table | Principal fields and constraints |
| --- | --- |
| `learners`, `study_goals` | Learner profile and per-module band target, weekly practice target, optional deadline. Unique learner and module per goal. |
| `sources`, `source_versions` | Provider, external ID, canonical URL, metadata, ingestion status, and last sync. Unique provider and external ID. Versions store revision identifier, attribution, license, authorization scope or evidence, retrieval timestamp, and optional permitted content reference. Unique source and revision. |
| `activities`, `activity_versions` | Logical activity with module and title. Version stores status, origin, difficulty estimate, time limit, passage or prompt, Task 1 visual reference, and validation report. Unique activity and version. Published versions are immutable. |
| `activity_sources` | Links activity versions to source versions with a role. Unique version pair and role. |
| `questions` | Activity version, position, type, prompt, public options, private answer rules, evidence anchors, explanation, and points. Unique activity version and position. |
| `score_calibrations` | Unique activity version, documented mapping provenance, and raw-to-band mapping. Only designated mock activity versions qualify. |
| `attempts` | Learner, activity version, status, start/deadline/submission timestamps, optional parent attempt for revisions, draft revision, and submission idempotency key. |
| `responses` | Attempt, question, submitted value, awarded points, and feedback. Unique attempt and question. Enforce that the question belongs to the pinned activity version. |
| `writing_submissions` | One per writing attempt, with draft and final text. Final text is frozen at submission. |
| `assessments` | Attempt, score kind, raw and maximum points or estimated band, criterion details, model, prompt/rubric versions, optional calibration reference, and optional unique producing job. Append new rows for reassessments. |
| `attempt_errors` | Assessment, optional question, error category, evidence, and feedback. |
| `jobs` | Kind, request payload, deduplication key, state, retry count, next eligible time, lease expiry, result reference, and sanitized error. Unique kind and deduplication key. |

Index learner attempt history by submission time, published activities by module and difficulty, and claimable jobs by state and scheduled time. Finalize objective submissions and grades in one transaction. Finalize writing text and enqueue assessment in one transaction.

## REST contracts

Use `/api/v1`, JSON, ISO 8601 UTC timestamps, and cursor pagination for collections (`{items, next_cursor}`). Errors use `{code, message, details}`. Return 422 for invalid inputs and 409 for incompatible state or stale edits. Scope practice records to the active learner.

| Method and path | Request and response |
| --- | --- |
| `GET /activities`, `GET /activities/{id}` | Filter published activities by module, difficulty, or topic. Detail returns version ID, timing, public questions or prompt, and attribution. Answer keys and evidence are withheld until submission. |
| `POST /attempts` | Accept `activity_version_id` and optional `parent_attempt_id` for a writing revision on the same prompt. Return 201 with attempt ID, status, and server timing. |
| `GET /attempts`, `GET /attempts/{id}` | Filter history by module and status. Detail returns saved work and timing, then score kind, results, explanations, errors, and writing assessment history once available. |
| `PUT /attempts/{id}/draft` | Replace saved answers or writing text using the current draft revision. Return the new revision. Reject stale saves and edits after finalization. |
| `POST /attempts/{id}/submit` | Accept the final responses or text and an idempotency key. Return 200 with objective results or 202 with the writing assessment job ID. Same-key retries replay the result. Conflicting submissions return 409. Close expired attempts using the last accepted draft. |
| `GET /attempts/{id}/comparison` | Return linked previous and current writing submissions with criterion feedback where available. |
| `POST /attempts/{id}/assessments` | Queue an explicit reassessment of frozen writing text. Return 202 and a job ID. |
| `GET /dashboard`, `GET /progress` | Dashboard returns goals, recent work, and recommendations with reasons. Progress accepts module and date filters and returns accuracy, timing, errors, and distinct score series. |
| `GET /goals`, `PUT /goals/{module}` | Read goals or replace a module goal. Return effective targets. |
| `GET /content/videos`, `GET /content/reading-sources` | List synced videos and their availability, or discover article candidates by topic and estimated difficulty. |
| `POST /content/listening/sync`, `POST /content/generation` | Accept a channel handle or generation input with source revision and options. Return 202 and a job ID. Validate source authorization before Listening generation. |
| `POST /content/activities`, `GET /content/versions/{id}`, `PUT /content/versions/{id}`, `POST /content/versions/{id}/publish` | Create a draft for a new or existing activity, review private answers and validation, replace draft content, and publish a validated version with recorded approval. |
| `GET /jobs/{id}` | Return queued, running, succeeded, or failed state with result reference or sanitized error. |

Content editing, generation, and private review routes require author access. The local seeded learner also acts as author.

## Implementation milestones

Prioritize the Reading and Writing end-to-end flows before Listening. Include History and Progress in the first usable release of each module. History opens saved submissions and feedback. Progress shows dated Reading raw scores and unofficial Writing estimates in distinct series, with Writing task types identified.

### Run the foundation locally

From the repository root, run `docker compose up --build -d` and open `http://localhost:5173`. The migration service creates the schema and seeds the learner and study goals before the API and worker start. The database volume persists across restarts.

Run `uv run python -m pytest -q` for the migration, dashboard, and worker smoke test. Run `npm ci --prefix frontend` followed by `npm run build --prefix frontend` to check the frontend.

For live Reading generation and Writing feedback, copy `.env.example` to `.env`, fill in the provider settings, and recreate the API and worker with Docker Compose. Python loads the project-root `.env` via python-dotenv when the backend runs directly. Exported environment values take precedence. The provider must support Structured Outputs. The local app uses GPT-6 Luna with `LLM_API_STYLE=responses` and `LLM_REASONING_EFFORT=xhigh`. Leave `LLM_API_STYLE` blank to use Chat Completions. Set `WIKIPEDIA_USER_AGENT` to identify this app and provide your contact email or project URL. When Wikipedia rate-limits a request, Reading generation waits until the retry time. Writing submissions are sent to the configured provider for feedback.

| Phase | Work and acceptance criteria |
| --- | --- |
| 1. Foundation | Compose starts UI, API, worker, and database from a clean checkout. Alembic builds the schema from an empty database. A seeded learner can open the app and the worker processes a test job. |
| 2. Listening practice | Sync the configured channel twice without duplicate video records. Embed an available video and handle one that is unavailable. Author and publish a set, complete a timed attempt, and verify score, explanations, and history. Check normalization, expiry, and duplicate submission behavior. |
| 3. Reading generation | Discover a source and review its revision and attribution. Generate and validate a passage with all four required types. Invalid keys or unsupported evidence block publication. An approved set supports a timed attempt with explanations and per-type results. Show raw practice scores. Accept calibrated mock scores only when a mapping is explicitly attached. |
| 4. Writing feedback | Submit both tasks, including a Task 1 visual. Each assessment shows four criteria, text-grounded feedback, and unofficial labeling. Verify failed-job recovery, reassessment history, and revision comparison without loss of original text. |
| 5. Dashboard and adaptive practice | Unified history and analytics reflect actual attempts and keep score kinds distinct. Goal changes persist, recommendations explain which performance signals drove them, and the view handles sparse data. |

## Open decisions for review

- Is local-only use sufficient for the first release, or should remote access and sign-in be included?
- Which LLM provider and budget should generation and writing feedback use?
- Is there authorized Listening material for AI drafting? Manual authoring can ship independently.
- Which mock tests have usable calibration data and documented rights? Until identified, show raw scores.
- Should Writing use learning mode with a soft timer or exam mode with a hard deadline? The API above assumes a hard deadline in timed mode.
Reading generation also supports a source choice. Wikipedia supplies article extracts. The Conversation, Scientific American, BBC Future, Smithsonian Magazine, NASA, Our World in Data, Nature, and Project Gutenberg supply editorially curated reference briefs and, where available, public feed titles and links. These guide original practice passages, and the app labels them as topic or headline references. Random source chooses an eligible provider for a mock.
