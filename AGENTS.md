# Development instructions

- Read PROJECT.md and requirements.md before changing product behavior. Keep Speaking outside the product scope.
- Preserve the modular monolith and stack described in PROJECT.md. Keep provider calls in adapters and business rules in the backend. Use Alembic for schema changes and Docker Compose for local development.
- Keep credentials out of source control. Scope learner records and return only public activity fields during practice. Keep author operations behind an explicit authorization dependency.
- Use the official YouTube player. Require authorization before downloading or extracting audio or transcripts and before generating questions from third-party Listening material. Record provenance, attribution, licensing, and rights for imported and derived content.
- Validate typed AI results and the referenced evidence. Version prompts, rubrics, and activity content. Preserve submitted work and historical assessments. Label Writing estimates unofficial and require documented calibration for mock band conversions.
- Use transactions for submission and job enqueueing. Design ingestion and workers for idempotent retries. Test scoring, attempt transitions, provenance gates, and job failure recovery with deterministic fixtures.
- Keep changes scoped to the active milestone. Verify its acceptance criteria before advancing.
- Use the named MUI skill palettes in `frontend/src/theme.ts` for module headings, actions, badges, and progress. Pair color with a visible skill label. Use MUI status colors for errors, warnings, and successful outcomes.
