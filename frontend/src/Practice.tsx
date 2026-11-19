import { Fragment, useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { createPortal } from "react-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert, Box, Button, Card, CardContent, Chip, LinearProgress, Link, MenuItem,
  Dialog, DialogActions, DialogContent, DialogTitle, Stack, Tab, Tabs, TextField, ToggleButton,
  ToggleButtonGroup, Typography,
} from "@mui/material";
import { skillLabels, skills, type Skill } from "./theme";
import { Listening } from "./Listening";
import { Simulation } from "./Simulation";
import { BandScore, bandTone } from "./BandScore";
import { TaskChart, WritingDataTable, WritingProcess, type WritingChart, type WritingVisualKind } from "./WritingVisual";

type Module = Skill;
type Question = {
  type?: string; prompt: string; options: string[]; word_limit?: number;
  answers?: string[]; explanation?: string; evidence?: string;
};

function readingOptions(question: Question, shuffleSeed?: string) {
  const values = [...question.options];
  if (!shuffleSeed || question.type !== "multiple_choice" || values.length !== 4) {
    return values.map(value => ({ value, label: value }));
  }

  // Seed the shuffle so saved answers and review use the same labels after a reload.
  let state = 2166136261;
  for (const character of shuffleSeed) {
    state = Math.imul(state ^ character.charCodeAt(0), 16777619);
  }
  for (let index = values.length - 1; index > 0; index--) {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    const swap = Math.floor(state / 2 ** 32 * (index + 1));
    [values[index], values[swap]] = [values[swap], values[index]];
  }
  return values.map((value, index) => ({
    value, label: "ABCD"[index] + ". " + value.replace(/^[A-D][.):]\s+/i, ""),
  }));
}
type ReadingQuestionGroup = {
  type: string; start: number; count: number; title: string; instructions: string;
  options: string[]; word_limit: number | null;
};
type Work = { answers: Record<number, string>; essay: string; essay_task2: string };
type Criterion = { band: number; feedback: string; quote: string };
type WritingTask = {
  title: string; task?: number | "full"; prompt?: string; table?: string[][]; chart?: WritingChart;
  mode?: "exam" | "learning"; category?: string; visual_kind?: WritingVisualKind; process?: string[];
};
type VocabularyHint = { term: string; meaning: string; phrase: string };
type RevisionPlan = {
  plan: string[]; develop: string[]; check: string[];
  example?: { type: "opening_paraphrase" | "sentence"; text: string } | null;
};
type WritingFeedback = { band?: number; criteria?: Record<string, Criterion>; unanswered?: boolean; revision_plan?: RevisionPlan };
type ReadingBand = { band?: number | null; band_estimated?: boolean; band_upper_bound?: number };

function ReadingBandBadge({ grade }: { grade: ReadingBand }) {
  if (grade.band != null) {
    return <BandScore band={grade.band} label={grade.band_estimated ? `Estimated band ${grade.band.toFixed(1)}` : undefined} />;
  }
  return grade.band_upper_bound !== undefined
    ? <Chip size="small" label={`Estimated band below ${grade.band_upper_bound.toFixed(1)}`} /> : null;
}
type ReadingReference = {
  url: string; title: string; license?: string; license_url?: string;
  attribution?: string; provider?: string; kind?: "headline" | "reference_brief";
};

function readingCitationUrl({ url, kind, provider }: ReadingReference) {
  try {
    const { protocol, pathname } = new URL(url);
    if (protocol !== "https:" && protocol !== "http:") return undefined;
    const path = pathname.replace(/\/$/, "");
    if (!path || path === "/future" || path === "/nature") return undefined;
    if (kind === "reference_brief" && provider === "NASA" &&
        ["/mars", "/exoplanets", "/climate-change"].includes(path)) return undefined;
    return url;
  } catch {
    return undefined;
  }
}

function ReadingCitation({ reference }: { reference: ReadingReference }) {
  const url = readingCitationUrl(reference);
  const label = reference.kind === "headline" ? "Headline reference" :
    reference.kind === "reference_brief" ? "Topic reference" : "Source";
  return <Typography variant="caption" component="div">
    {label} · {reference.title}
    {reference.attribution && ` · ${reference.attribution}`}
    {url ? <Link href={url} target="_blank" rel="noopener noreferrer" sx={{ display: "block", overflowWrap: "anywhere" }}>
      {url}
    </Link> : <Box component="span" sx={{ display: "block", color: "text.secondary" }}>Specific source URL unavailable.</Box>}
    {reference.license_url && <Link href={reference.license_url} target="_blank" rel="noopener noreferrer">
      {reference.license}
    </Link>}
  </Typography>;
}
type RevisionHistory = {
  remaining: number; retry_limit: number; latest_id: string;
  items: { id: string; number: number; submitted: boolean; band: number | null; task_bands: number[] }[];
};
type Attempt = {
  id: string; module: Module; deadline: string; submitted_at: string | null; parent_id: string | null;
  paused_at: string | null;
  content: WritingTask & {
    video_id?: string;
    simulation_id?: string;
    reading_topic?: string;
    reading_option_order?: "shuffled-v1";
    tasks?: WritingTask[];
    passages?: {
      title: string; text: string; source: ReadingReference; questions: Question[]; question_groups?: ReadingQuestionGroup[];
    }[];
  };
  draft: Partial<Work>;
  result: null | WritingFeedback & ReadingBand & {
    kind: string; score?: number; maximum?: number; job_id?: string;
    items?: { status: "correct" | "incorrect" | "unanswered"; number: number; answer?: string; accepted?: string[] }[];
    tasks?: WritingFeedback[];
  };
};
type HistoryItem = ReadingBand & {
  id: string; module: Module; task?: number | "full"; title: string;
  mode: "exam" | "learning";
  started_at: string | null; paused_at: string | null; submitted_at: string | null; deadline: string;
  score: number | null; maximum: number | null; band: number | null;
};

async function api<T>(path: string, method = "GET", data?: unknown): Promise<T> {
  const response = await fetch("/api/v1" + path, {
    method, headers: { "Content-Type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "The request failed. Try again.");
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

type SimulationSection = ReadingBand & { id: string; module: Module; submitted: boolean; score: number | null; band: number | null };
type SavedMock = { id: string; title: string; topic: string | null; first_passage: string | null; date: string; completed: boolean; source_name: string };
type ReadingChoices = {
  groups: { name: string; topics: { id: string; label: string }[] }[];
  sources: { id: string; label: string; description: string; topic_ids: string[] }[];
};
type WritingSetup = {
  task: 1 | 2 | "full"; mode: "exam" | "learning"; categories: Partial<Record<1 | 2, string>>; jobId: string;
};
const writingSetupKey = "ielts-writing-generation";

function readWritingSetup(): WritingSetup | null {
  try {
    return JSON.parse(localStorage.getItem(writingSetupKey) ?? "null");
  } catch {
    return null;
  }
}
type JobStatus = {
  state: string; error: string | null; retry_at: string | null;
  topic: string | null; source_name: string | null;
  replacement_required?: boolean;
  progress?: {
    stage: "finding_sources" | "generating_passages" | "checking_mock";
    completed_passages: number; started_at: string; drafted_passages?: number; completed_groups?: number;
  } | null;
};

function readingJobMessage(job?: JobStatus) {
  const error = jobMessage(job);
  if (error) return error;
  if (job?.state !== "running") return "Waiting for the worker…";
  switch (job.progress?.stage) {
    case "finding_sources":
      return "Finding three source pages…";
    case "checking_mock":
      return "Checking the complete mock…";
    case "generating_passages":
      return `Generating passages · ${job.progress.completed_passages} of 3 validated`;
    default:
      return "The worker is generating your mock…";
  }
}

function jobMessage(job?: JobStatus) {
  if (!job?.error) return undefined;
  if (!job.retry_at) return job.error;
  const retry = new Date(job.retry_at);
  if (Number.isNaN(retry.getTime())) return job.error;
  const time = retry.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", second: "2-digit" });
  const date = retry.toDateString() === new Date().toDateString() ? "" : `${retry.toLocaleDateString()} at `;
  return `${job.error} Retry after ${date}${time} (local time).`;
}
const READING_MOCK_PREVIEW_LIMIT = 5;

export function Practice({ view, sessionId, navigate, saveAndGoHome, timerSlot }: {
  view: string; sessionId?: string; navigate: (path: string) => void; saveAndGoHome: Ref<() => void>;
  timerSlot: HTMLElement | null;
}) {
  const [savedWritingSetup] = useState(readWritingSetup);
  const [task, setTask] = useState<1 | 2 | "full">(savedWritingSetup?.task ?? "full");
  const [writingCategories, setWritingCategories] = useState(savedWritingSetup?.categories ?? {});
  const [writingMode, setWritingMode] = useState<"exam" | "learning">(savedWritingSetup?.mode ?? "exam");
  const [writingJob, setWritingJob] = useState(savedWritingSetup?.jobId ?? "");
  const [topic, setTopic] = useState("");
  const [readingSource, setReadingSource] = useState("wikipedia");
  const [requestedJob, setRequestedJob] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [historyTab, setHistoryTab] = useState<"active" | "finished">("active");
  const [pendingDelete, setPendingDelete] = useState<HistoryItem>();
  const [pendingMockDelete, setPendingMockDelete] = useState<SavedMock>();
  const cache = useQueryClient();
  const params = new URLSearchParams(window.location.search);
  const simulationId = (view === "reading" || view === "writing") ? params.get("simulation") ?? undefined : undefined;
  const simulationRun = view === "simulation" ? params.get("run") : null;
  const writingTasks: (1 | 2)[] = task === "full" ? [1, 2] : [task];
  const writingChoices = useQuery({
    queryKey: ["writing-topics"], enabled: view === "writing" && !simulationId,
    queryFn: () => api<{ categories: string[] }>("/practice/writing/topics"), staleTime: Infinity,
  });
  const writingGeneration = useQuery({
    queryKey: ["writing-generation", writingJob], enabled: view === "writing" && !!writingJob && !simulationId,
    queryFn: () => api<JobStatus>(`/jobs/${writingJob}`),
    refetchInterval: query => ["succeeded", "failed"].includes(query.state.data?.state ?? "") ? false : 2000,
  });
  const generatingWriting = !!writingJob && !writingGeneration.isError &&
    !["succeeded", "failed"].includes(writingGeneration.data?.state ?? "");
  const writingReady = writingGeneration.data?.state === "succeeded" && !writingGeneration.data.replacement_required;
  const simulation = useQuery({
    queryKey: ["simulation", simulationRun], enabled: !!simulationRun,
    queryFn: () => api<{ items: SimulationSection[] }>(`/practice/simulation/${simulationRun}`),
  });
  const session = useQuery({
    queryKey: ["practice-session", sessionId], enabled: !!sessionId,
    queryFn: () => api<Attempt>(`/practice/sessions/${sessionId}`),
    staleTime: Infinity,
  });
  const history = useQuery({
    queryKey: ["practice-history"], enabled: view === "home" || view === "history" || view === "progress",
    queryFn: () => api<{ items: HistoryItem[] }>("/practice/sessions"),
  });
  const mocks = useQuery({
    queryKey: ["recent-reading-mocks"], enabled: view === "home" || view === "reading" || view === "readingMocks",
    queryFn: () => api<{ latest_id: string | null; ready_id: string | null; items: SavedMock[] }>("/practice/reading/mocks"),
  });
  const topics = useQuery({
    queryKey: ["reading-topics"], enabled: view === "reading",
    queryFn: () => api<ReadingChoices>("/practice/reading/topics"),
  });
  const selectedSource = topics.data?.sources.find(source => source.id === readingSource);
  const sourceTopicGroups = topics.data?.groups.map(group => ({
    ...group, topics: group.topics.filter(item => selectedSource?.topic_ids.includes(item.id)),
  })).filter(group => group.topics.length > 0);
  const selectedMockId = view === "reading" ? params.get("mock") : null;
  const readingJob = requestedJob || selectedMockId || mocks.data?.latest_id;
  const selectedMock = mocks.data?.items.find(item => item.id === readingJob);
  const generation = useQuery({
    queryKey: ["reading-job", readingJob], enabled: view === "reading" && !!readingJob,
    queryFn: () => api<JobStatus>(`/jobs/${readingJob}`),
    refetchInterval: query => ["succeeded", "failed"].includes(query.state.data?.state ?? "") ? false : 2000,
  });
  const generating = !!readingJob && !generation.isError &&
    !["succeeded", "failed"].includes(generation.data?.state ?? "");
  const generationProgress = generation.data?.progress;
  const generationStart = generationProgress?.started_at;
  useEffect(() => {
    if (generation.data?.state === "succeeded") {
      void cache.invalidateQueries({ queryKey: ["recent-reading-mocks"] });
    }
  }, [cache, generation.data?.state, readingJob]);
  useEffect(() => {
    setElapsed(0);
    if (!generating || view !== "reading" || !generationStart) return;
    const start = Date.parse(generationStart);
    const tick = () => setElapsed(Math.max(0, Math.floor((Date.now() - start) / 1000)));
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [generating, generationStart, view]);

  async function run(action: () => Promise<void>) {
    setError("");
    setBusy(true);
    try {
      await action();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "The request failed.");
    } finally {
      setBusy(false);
    }
  }

  function requestMockDeletion(mock: SavedMock) {
    setError("");
    setPendingMockDelete(mock);
  }

  function forgetWritingJob() {
    setWritingJob("");
    localStorage.removeItem(writingSetupKey);
  }

  function generateWriting() {
    return run(async () => {
      const categories = Object.fromEntries(writingTasks.filter(part => writingCategories[part])
        .map(part => [part, writingCategories[part]]));
      const job = await api<{ job_id: string }>("/practice/writing/generate", "POST", { task, mode: writingMode, categories });
      setWritingJob(job.job_id);
      localStorage.setItem(writingSetupKey, JSON.stringify({ task, mode: writingMode, categories, jobId: job.job_id }));
    });
  }

  function start(module: Module, parent_id?: string, mockId = readingJob, videoId?: string, simulate = false) {
    return run(async () => {
      const started = await api<Attempt>(`/practice/${module}/start`, "POST", {
        task: simulationId ? "full" : task, mode: simulationId ? "exam" : writingMode, parent_id,
        writing_job_id: module === "writing" && !simulationId && !parent_id
          ? writingJob
          : undefined,
        reading_job_id: module === "reading" ? mockId : undefined, video_id: videoId,
        simulate, simulation_id: simulationId,
      });
      cache.setQueryData(["practice-session", started.id], started);
      if (module === "writing" && !simulationId && !parent_id) forgetWritingJob();
      navigate(`/sessions/${started.id}`);
      cache.invalidateQueries({ queryKey: ["practice-history"] });
    });
  }

  return (
    <Stack spacing={3} sx={{ mt: 4 }}>
      {error && <Alert severity="error">{error}</Alert>}
      {view === "home" && <>
        <ContinuePractice items={history.data?.items ?? []} mocks={mocks.data?.items ?? []}
          onDeleteMock={requestMockDeletion} />
        <Stack spacing={1.5} component="section" aria-labelledby="start-practice">
          <Typography id="start-practice" variant="h5" component="h2">Start practice</Typography>
          <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { sm: "repeat(3, 1fr)" } }}>
          {skills.map(module => <Card key={module} variant="outlined" sx={{ bgcolor: `${module}.light` }}><CardContent>
            <Typography variant="h6" component="h2" sx={{ color: `${module}.main` }}>{skillLabels[module]}</Typography>
            <Button sx={{ mt: 1 }} color={module} variant="contained" href={`/${module}`}
              aria-label={`Start practicing ${module}`}>Start practicing</Button>
          </CardContent></Card>)}
          </Box>
        </Stack>
        <Simulation preview />
      </>}
      {view === "listening" && <Listening starting={busy} onStart={videoId => start("listening", undefined, undefined, videoId)} />}
      {view === "readingMocks" && <>
        {mocks.isPending && <LinearProgress color="reading" />}
        {mocks.isError && <Alert severity="error">{mocks.error.message}</Alert>}
        {mocks.data && <ReadingMockLibrary mocks={mocks.data.items.filter(mock => !mock.completed)}
          onDelete={requestMockDeletion} />}
      </>}
      {view === "simulation" && <>
        <Simulation />
        {!simulationRun && <Listening starting={busy} onStart={videoId =>
          start("listening", undefined, undefined, videoId, true)} />}
        {simulation.isError && <Alert severity="error">{simulation.error.message}</Alert>}
        {simulation.data && <Stack spacing={1.5}>
          <Typography variant="h6" component="h2">Simulation results</Typography>
          {simulation.data.items.map(item => <Card variant="outlined" key={item.id}><CardContent>
            <Stack direction="row" spacing={2} sx={{ alignItems: "center", justifyContent: "space-between" }}>
              <Chip size="small" color={item.module} label={skillLabels[item.module]} />
              {item.module === "reading" && item.score !== null ? <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
                <Chip size="small" color="reading" label={`${item.score}/40`} />
                <ReadingBandBadge grade={item} />
              </Stack> : item.band !== null ? <BandScore band={item.band} /> :
                <Typography>{item.score !== null ? `${item.score}/40` : item.submitted ? "Score pending" : "In progress"}</Typography>}
              <Button color={item.module} href={`/sessions/${item.id}`}>{item.submitted ? "Review" : "Continue"}</Button>
            </Stack>
          </CardContent></Card>)}
          <Button href="/simulation" sx={{ alignSelf: "start" }}>New simulation</Button>
        </Stack>}
      </>}
      {view === "reading" && <>
        {simulationId && <Alert severity="info">Simulation · Reading section</Alert>}
        {selectedMockId && selectedMock && <Box>
          <Typography variant="h6" component="h2">{selectedMock.title}</Typography>
          {selectedMock.topic && <Typography variant="body2">{selectedMock.topic}</Typography>}
          {selectedMock.first_passage && <Typography variant="body2" color="text.secondary">
            First passage · {selectedMock.first_passage}
          </Typography>}
        </Box>}
        <Typography>Three passages · 40 questions · 60 minutes</Typography>
        <TextField select label="Reading source" value={readingSource} sx={{ maxWidth: 420 }}
          disabled={generating || busy || !topics.data}
          helperText={selectedSource?.description}
          onChange={event => {
            const nextSource = topics.data?.sources.find(source => source.id === event.target.value);
            setReadingSource(event.target.value);
            if (!nextSource?.topic_ids.includes(topic)) setTopic("");
          }}>
          {(topics.data?.sources ?? [{ id: "wikipedia", label: "Wikipedia" }]).map(source =>
            <MenuItem key={source.id} value={source.id}>{source.label}</MenuItem>)}
        </TextField>
        <TextField select label="Reading topic" value={topic} sx={{ maxWidth: 420 }}
          disabled={generating || busy} slotProps={{ select: { native: true }, inputLabel: { shrink: true } }}
          onChange={event => setTopic(event.target.value)}>
          <option value="">Random topics</option>
          {sourceTopicGroups?.map(group => <optgroup key={group.name} label={group.name}>
            {group.topics.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
          </optgroup>)}
        </TextField>
        {topics.isError && <Alert severity="warning">Could not load the topic list. Random topics are still available.</Alert>}
        <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
          <Button variant="outlined" color="reading" disabled={busy || mocks.isPending || generating}
            onClick={() => run(async () => {
              const job = await api<{ job_id: string }>("/practice/reading/generate", "POST", {
                topic: topic || null, source: readingSource,
              });
              setRequestedJob(job.job_id);
            })}>Generate mock</Button>
          <Button variant="contained" color="reading" disabled={busy || generation.data?.state !== "succeeded"}
            onClick={() => start("reading")}>Start test</Button>
          {mocks.data?.ready_id && mocks.data.ready_id !== readingJob &&
            generation.data?.state !== "succeeded" && <Button color="reading" disabled={busy}
              onClick={() => start("reading", undefined, mocks.data?.ready_id ?? undefined)}>Start previous mock</Button>}
        </Stack>
        {generating && <Box>
          {generation.data?.topic && <Typography sx={{ fontWeight: 600 }}>{generation.data.topic}</Typography>}
          <Typography role="status">{readingJobMessage(generation.data)}</Typography>
          {generationProgress?.stage === "generating_passages" && generationProgress.drafted_passages !== undefined &&
            <Typography variant="body2" color="text.secondary">
              {generationProgress.drafted_passages}/3 passage drafts · {generationProgress.completed_groups}/6 question groups
            </Typography>}
          <Typography variant="body2" color="text.secondary">
            {generationStart && `Elapsed ${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}. `}
            You can return to Reading while the mock runs.
          </Typography>
          <LinearProgress color="reading" aria-label="Reading mock generation" sx={{ mt: 1 }}
            variant={generationProgress?.stage === "generating_passages" ? "determinate" : "indeterminate"}
            value={generationProgress ? (generationProgress.drafted_passages === undefined
              ? generationProgress.completed_passages / 3
              : (generationProgress.drafted_passages + (generationProgress.completed_groups ?? 0)) / 9) * 100 : undefined} />
        </Box>}
        {generation.data?.state === "succeeded" && <Alert severity="success">
          {generation.data.topic ? `${generation.data.topic} mock ready.` : "Your mock is ready."}
          {generation.data.source_name && ` Source · ${generation.data.source_name}.`} Select Start test to begin the timer.
        </Alert>}
        {(generation.data?.state === "failed" || generation.isError) &&
          <Alert severity="error">{jobMessage(generation.data) ?? "Could not check mock generation. Try again."}</Alert>}
      </>}
      {view === "writing" && <Stack spacing={2} sx={{ alignItems: "flex-start" }}>
        {simulationId ? <Alert severity="info">Simulation · Full Writing test · 60 minutes</Alert> : <>
        <TextField select label="Practice mode" value={writingMode} disabled={busy || generatingWriting}
          onChange={event => {
            forgetWritingJob();
            setWritingMode(event.target.value === "learning" ? "learning" : "exam");
          }}>
          <MenuItem value="exam">Exam practice</MenuItem>
          <MenuItem value="learning">Writing learning</MenuItem>
        </TextField>
        {writingMode === "learning" && <Typography color="text.secondary">Get vocabulary hints while you write.</Typography>}
        <TextField select label="Writing task" value={task} disabled={busy || generatingWriting}
          onChange={event => {
            forgetWritingJob();
            setTask(event.target.value === "full" ? "full" : Number(event.target.value) === 1 ? 1 : 2);
          }}>
          <MenuItem value="full">Full Writing test · 60 minutes</MenuItem>
          <MenuItem value={1}>Task 1 · 20 minutes</MenuItem>
          <MenuItem value={2}>Task 2 · 40 minutes</MenuItem>
        </TextField>
        {writingChoices.isError && <Alert severity="warning">Could not load Writing categories. You can still generate with automatic categories.</Alert>}
        {writingTasks.map(part => <TextField select key={part} label={`Task ${part} category`}
          value={writingCategories[part] ?? ""} disabled={busy || generatingWriting || writingChoices.isPending || writingChoices.isError}
          onChange={event => {
            forgetWritingJob();
            setWritingCategories(current => ({ ...current, [part]: event.target.value }));
          }}
          sx={{ width: "100%", maxWidth: 380 }}>
          <MenuItem value="">Automatic category</MenuItem>
          {writingChoices.data?.categories.map(category => <MenuItem key={category} value={category}>{category}</MenuItem>)}
        </TextField>)}
        {generatingWriting && <Box sx={{ width: "100%", maxWidth: 380 }}>
          <Typography role="status">{jobMessage(writingGeneration.data) ?? (writingGeneration.data?.state === "running"
            ? "Generating Writing prompts…" : "Waiting for the worker…")}</Typography>
          <LinearProgress color="writing" aria-label="Writing prompt generation" sx={{ mt: 1 }} />
        </Box>}
        {writingReady &&
          <Alert severity="success">Your Writing prompts are ready. The timer starts when you begin.</Alert>}
        {writingGeneration.data?.replacement_required &&
          <Alert severity="info">Generate a new Writing prompt to get a visual with numerical data.</Alert>}
        {(writingGeneration.data?.state === "failed" || writingGeneration.isError) &&
          <Alert severity="error">{jobMessage(writingGeneration.data) ?? "Could not check Writing prompt generation."}</Alert>}
        </>}
        <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: "wrap" }}>
          {!simulationId && <Button variant="outlined" color="writing" disabled={busy || generatingWriting} onClick={generateWriting}>
            {task === "full" ? "Generate prompts" : "Generate prompt"}
          </Button>}
          <Button variant="contained" color="writing"
            disabled={busy || (!simulationId && !writingReady)} onClick={() => start("writing")}>
            {!simulationId && writingMode === "learning" ? "Start learning" : "Start test"}
          </Button>
        </Stack>
      </Stack>}
      {view === "attempt" && session.isPending && <LinearProgress />}
      {view === "attempt" && session.isError && <>
        <Alert severity="error">{session.error.message}</Alert>
        <Button href="/" sx={{ alignSelf: "start" }}>Back to home</Button>
      </>}
      {view === "attempt" && session.data && <Session key={session.data.id} attempt={session.data} onChange={updated => {
        cache.setQueryData(["practice-session", updated.id], updated);
        cache.invalidateQueries({ queryKey: ["practice-history"] });
        if (updated.submitted_at) cache.invalidateQueries({ queryKey: ["dashboard"] });
        if (updated.module === "reading" && updated.submitted_at) {
          cache.invalidateQueries({ queryKey: ["recent-reading-mocks"] });
        }
      }} onRevise={() => start("writing", sessionId)} onHome={() => navigate("/")} saveAndGoHome={saveAndGoHome}
        timerSlot={timerSlot}
        startingRevision={busy} />}
      {(view === "history" || view === "progress") && history.isPending && <LinearProgress />}
      {(view === "history" || view === "progress") && history.isError && <Alert severity="error">Could not load sessions.</Alert>}
      {view === "history" && history.data && <>
        <Tabs value={historyTab} onChange={(_, next) => setHistoryTab(next)} aria-label="Session status">
          <Tab value="active" label="In progress" />
          <Tab value="finished" label="Finished" />
        </Tabs>
        {skills.map(skill => <HistorySection key={skill} skill={skill}
          items={history.data.items.filter(item => item.module === skill && !!item.submitted_at === (historyTab === "finished"))}
          onDelete={item => { setError(""); setPendingDelete(item); }} />)}
        <Dialog open={!!pendingDelete} onClose={() => { if (!busy) { setError(""); setPendingDelete(undefined); } }}>
          <DialogTitle>Delete this session?</DialogTitle>
          <DialogContent>
            {pendingDelete?.submitted_at
              ? "This removes the session and its score from History and Progress."
              : "Your saved answers for this session will be deleted."}
            {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
          </DialogContent>
          <DialogActions>
            <Button disabled={busy} onClick={() => { setError(""); setPendingDelete(undefined); }}>Cancel</Button>
            <Button color="error" disabled={busy} onClick={() => pendingDelete && run(async () => {
              await api(`/practice/sessions/${pendingDelete.id}`, "DELETE");
              cache.removeQueries({ queryKey: ["practice-session", pendingDelete.id] });
              cache.removeQueries({ queryKey: ["revision-parent", pendingDelete.id] });
              await Promise.all([
                cache.invalidateQueries({ queryKey: ["practice-history"] }),
                cache.invalidateQueries({ queryKey: ["dashboard"] }),
                cache.invalidateQueries({ queryKey: ["writing-revisions"] }),
                cache.invalidateQueries({ queryKey: ["simulation"] }),
              ]);
              setPendingDelete(undefined);
            })}>Delete</Button>
          </DialogActions>
        </Dialog>
      </>}
      {view === "progress" && history.data && <ProgressCharts items={history.data.items} />}
      <Dialog open={!!pendingMockDelete} onClose={() => {
        if (!busy) { setPendingMockDelete(undefined); setError(""); }
      }}>
        <DialogTitle>Delete this Reading mock?</DialogTitle>
        <DialogContent>
          This removes the mock from your library. Existing practice sessions remain in History.
          {error && pendingMockDelete && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button disabled={busy} onClick={() => { setPendingMockDelete(undefined); setError(""); }}>Cancel</Button>
          <Button color="error" disabled={busy} onClick={() => pendingMockDelete && run(async () => {
            await api(`/practice/reading/mocks/${pendingMockDelete.id}`, "DELETE");
            cache.removeQueries({ queryKey: ["reading-job", pendingMockDelete.id] });
            await cache.invalidateQueries({ queryKey: ["recent-reading-mocks"] });
            setPendingMockDelete(undefined);
          })}>Delete</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

function ContinuePractice({ items, mocks, onDeleteMock }: {
  items: HistoryItem[]; mocks: SavedMock[]; onDeleteMock: (mock: SavedMock) => void;
}) {
  const active = items.filter(item => item.module !== "writing" &&
    (!item.submitted_at || (item.module === "listening" && item.score === null)));
  const writing = items.filter(item => item.module === "writing" && !item.submitted_at);
  const unfinishedMocks = mocks.filter(mock => !mock.completed);
  if (!active.length && !unfinishedMocks.length && !writing.length) return null;

  return <Stack component="section" spacing={1.5} aria-labelledby="continue-practice">
    <Typography id="continue-practice" component="h2" variant="h5">Continue where you left off</Typography>
    {active.map(item => <SavedSession key={item.id} item={item} />)}
    {writing.length > 0 && <Stack spacing={1}>
      <Typography component="h3" variant="subtitle1" sx={{ color: "writing.main" }}>Writing sessions ({writing.length})</Typography>
      {writing.map(item => <SavedSession key={item.id} item={item} />)}
    </Stack>}
    {unfinishedMocks.length > 0 && <Stack spacing={1}>
      <Typography component="h3" variant="subtitle1" sx={{ color: "reading.main" }}>
        Saved Reading mocks ({unfinishedMocks.length})
      </Typography>
      {unfinishedMocks.slice(0, READING_MOCK_PREVIEW_LIMIT).map(mock => <ReadingMockCard key={mock.id}
        mock={mock} onDelete={onDeleteMock} />)}
      {unfinishedMocks.length > READING_MOCK_PREVIEW_LIMIT &&
        <Button color="reading" href="/reading/mocks" sx={{ alignSelf: "start" }}>View all Reading mocks</Button>}
    </Stack>}
  </Stack>;
}

function ReadingMockCard({ mock, grouped = false, onDelete }: {
  mock: SavedMock; grouped?: boolean; onDelete: (mock: SavedMock) => void;
}) {
  return <Card variant="outlined">
    <CardContent sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
      <Box>
        <Typography sx={{ fontWeight: 600 }}>{grouped ? mock.first_passage || mock.title : mock.title}</Typography>
        <Typography variant="body2" color="text.secondary">
          {!grouped && [mock.topic, mock.first_passage].filter(Boolean).map(label => `${label} · `)}
          {mock.source_name} ·{" "}
          <time dateTime={mock.date}>{new Date(mock.date).toLocaleDateString()}</time>
        </Typography>
      </Box>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={0.5} sx={{ flexShrink: 0 }}>
        <Button color="reading" href={`/reading?mock=${mock.id}`}>Open mock</Button>
        <Button color="error" onClick={() => onDelete(mock)}>Delete</Button>
      </Stack>
    </CardContent>
  </Card>;
}

function ReadingMockLibrary({ mocks, onDelete }: { mocks: SavedMock[]; onDelete: (mock: SavedMock) => void }) {
  const categories = new Map<string, Map<string | null, SavedMock[]>>();
  for (const mock of mocks) {
    const topics = categories.get(mock.title) ?? new Map<string | null, SavedMock[]>();
    const items = topics.get(mock.topic) ?? [];
    items.push(mock);
    topics.set(mock.topic, items);
    categories.set(mock.title, topics);
  }
  if (!categories.size) return <Alert severity="info">No unfinished Reading mocks.</Alert>;

  return <Stack spacing={3}>
    {Array.from(categories, ([category, topics]) => <Stack key={category} component="section" spacing={1.5}>
      <Typography variant="h6" component="h2" sx={{ color: "reading.main" }}>{category}</Typography>
      {Array.from(topics, ([topic, items]) => <Stack key={topic ?? category} spacing={1}>
        {topic && <Typography variant="subtitle1" component="h3">{topic}</Typography>}
        {items.map(mock => <ReadingMockCard key={mock.id} mock={mock} grouped onDelete={onDelete} />)}
      </Stack>)}
    </Stack>)}
  </Stack>;
}

function SavedSession({ item }: { item: HistoryItem }) {
  const scoringPending = item.module === "listening" && !!item.submitted_at && item.score === null;
  const status = scoringPending ? "Ready to self-score" : item.paused_at ? "Paused" : "In progress";
  const date = item.submitted_at ?? item.started_at;
  return <Card variant="outlined" sx={{ borderLeft: "4px solid", borderLeftColor: `${item.module}.main` }}>
    <CardContent sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
      <Box>
        {item.module !== "writing" && <Typography variant="subtitle2" sx={{ color: `${item.module}.main` }}>
          {skillLabels[item.module]}
        </Typography>}
        <Typography sx={{ fontWeight: 600 }}>{item.title}</Typography>
        <Typography variant="body2" color="text.secondary">
          {status}{date && <> · <time dateTime={date}>{new Date(date).toLocaleDateString()}</time></>}
        </Typography>
      </Box>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ alignItems: "center", flexShrink: 0 }}>
        <Button color={item.module} variant="outlined" href={`/sessions/${item.id}`}>
          {scoringPending ? "Self-score" : "Continue"}
        </Button>
      </Stack>
    </CardContent>
  </Card>;
}

function HistorySection({ skill, items, onDelete }: {
  skill: Skill; items: HistoryItem[]; onDelete?: (item: HistoryItem) => void;
}) {
  return <Stack component="section" spacing={1.5}>
    <Typography component="h2" variant="h6" sx={{ color: `${skill}.main` }}>
      {skillLabels[skill]} ({items.length})
    </Typography>
    {items.length === 0 && <Typography color="text.secondary">No sessions.</Typography>}
    {items.map((item, index) => {
      const grade = item.score !== null ? `${item.score}/${item.maximum ?? 40}` : null;
      const dates = [
        item.started_at && ["Started", item.started_at],
        item.submitted_at && ["Submitted", item.submitted_at],
        item.paused_at && ["Paused", item.paused_at],
        !item.started_at && !item.submitted_at && !item.paused_at && ["Deadline", item.deadline],
      ];
      return <Card key={item.id} variant="outlined"><CardContent sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
        <Box>
          <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: "center", flexWrap: "wrap" }}>
            <Typography component="span" variant="body2" color="text.secondary"
              sx={{ fontVariantNumeric: "tabular-nums" }}>#{index + 1}</Typography>
            <Typography sx={{ fontWeight: 600 }}>{item.title}</Typography>
            <Chip color={item.module} variant="outlined" size="small" label={skillLabels[item.module]} />
            {item.mode === "learning" && <Chip size="small" variant="outlined" label="Learning" />}
            {item.module === "reading" && <ReadingBandBadge grade={item} />}
            {item.module !== "reading" && item.band !== null
              ? <BandScore band={item.band} label={`Estimated band ${item.band.toFixed(1)}`} /> : grade &&
              <Chip color={item.module} size="small" label={item.module === "listening" ? `${grade} · Self-scored` : grade} />}
          </Stack>
          {dates.map(date => date && <Typography key={date[0]} variant="body2" color="text.secondary">
            {date[0]} <time dateTime={date[1]}>{new Date(date[1]).toLocaleString()}</time>
          </Typography>)}
        </Box>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={0.5}>
          <Button color={item.module} href={`/sessions/${item.id}`}>
            {item.submitted_at ? item.module === "listening" && item.score === null ? "Self-score" : "Review" : "Continue"}
          </Button>
          {onDelete && <Button color="error" onClick={() => onDelete(item)}>Delete</Button>}
        </Stack>
      </CardContent></Card>;
    })}
  </Stack>;
}

export function DashboardProgress() {
  const history = useQuery({
    queryKey: ["practice-history"], queryFn: () => api<{ items: HistoryItem[] }>("/practice/sessions"),
  });
  return <Stack spacing={2}>
    {history.isPending && <LinearProgress />}
    {history.isError && <Alert severity="error">Could not load score history.</Alert>}
    {history.data && <ProgressCharts items={history.data.items} />}
  </Stack>;
}

function ProgressCharts({ items }: { items: HistoryItem[] }) {
  const reading = items.filter(item => item.module === "reading");
  const writing = items.filter(item => item.module === "writing" && item.mode !== "learning");
  const latest = writing.find(item => item.band !== null)?.task ?? "full";
  const [selectedTask, setSelectedTask] = useState<number | "full">();
  const [selectedReadingUnit, setSelectedReadingUnit] = useState<"band" | "raw">();
  const task = selectedTask ?? latest;
  const readingUnit = selectedReadingUnit ?? (reading.some(item => item.band !== null) ? "band" : "raw");
  return <Stack spacing={2}>
    <Trend skill="listening" title="Listening · Self-scored" maximum={40}
      items={items.filter(item => item.module === "listening")} value={item => item.score} />
    <Trend skill="reading" title={readingUnit === "band" ? "Reading · Estimated band" : "Reading · Raw score"}
      maximum={readingUnit === "band" ? 9 : 40} items={reading}
      value={item => readingUnit === "band" ? item.band : item.score}
      action={<TextField select size="small" label="Reading score" value={readingUnit} sx={{ minWidth: 150 }}
        onChange={event => setSelectedReadingUnit(event.target.value === "band" ? "band" : "raw")}>
        <MenuItem value="band">Estimated band</MenuItem>
        <MenuItem value="raw">Raw score</MenuItem>
      </TextField>} />
    <Trend skill="writing" title="Writing · Unofficial band" maximum={9}
      items={writing.filter(item => item.task === task)} value={item => item.band}
      action={<TextField select size="small" label="Writing test" value={task} sx={{ minWidth: 150 }}
        onChange={event => setSelectedTask(event.target.value === "full" ? "full" : Number(event.target.value))}>
        <MenuItem value="full">Full test</MenuItem>
        <MenuItem value={1}>Task 1</MenuItem>
        <MenuItem value={2}>Task 2</MenuItem>
      </TextField>}
    />
  </Stack>;
}

function Trend({ skill, title, maximum, items, value, action }: {
  skill: Skill; title: string; maximum: number; items: HistoryItem[]; value: (item: HistoryItem) => number | null;
  action?: React.ReactNode;
}) {
  const scored = items.filter(item => item.submitted_at && value(item) !== null).slice(0, 12).reverse();
  return <Card variant="outlined"><CardContent>
    <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ alignItems: { sm: "center" }, justifyContent: "space-between" }}>
      <Typography variant="h6" component="h3" sx={{ color: `${skill}.main` }}>{title}</Typography>{action}
    </Stack>
    {scored.length ? <Box component="ol" aria-label={`${title} over time`} sx={{
      mt: 2, mb: 0, p: 0, overflowX: "auto", display: "flex", gap: 1.5,
      listStyle: "none",
    }}>
      {scored.map(item => {
        const score = value(item)!;
        const date = new Date(item.submitted_at!);
        return <Box component="li" key={item.id} sx={{ minWidth: 58, textAlign: "center" }}
          title={date.toLocaleString()}>
          {maximum === 9 ? <BandScore band={score} label={score.toFixed(1)} /> :
            <Typography variant="caption" sx={{ fontWeight: 600 }}>{score}/{maximum}</Typography>}
          <Box aria-hidden="true" sx={{
            height: 92, width: 24, my: 0.5, mx: "auto", bgcolor: `${skill}.light`,
            borderRadius: 0.5, display: "flex", alignItems: "flex-end",
          }}>
            <Box sx={{ height: `${score / maximum * 100}%`, width: "100%",
              bgcolor: maximum === 9 ? bandTone(score).background : `${skill}.main`,
              border: maximum === 9 && score > 0 ? "1px solid currentColor" : 0,
              color: maximum === 9 ? bandTone(score).text : undefined, borderRadius: 0.5 }} />
          </Box>
          <Typography component="time" dateTime={item.submitted_at!} variant="caption" color="text.secondary">
            {date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}
          </Typography>
        </Box>;
      })}
    </Box> : <Typography color="text.secondary">Complete a scored session to see progress.</Typography>}
  </CardContent></Card>;
}

function RevisionSuggestions({ assessment, previous = false }: { assessment: WritingFeedback; previous?: boolean }) {
  const items: [string, string[]][] = assessment.revision_plan ? [
    ["Plan your response", assessment.revision_plan.plan.slice(0, 1)],
    ["What to develop", assessment.revision_plan.develop.slice(0, 1)],
    ["Before you submit", assessment.revision_plan.check.slice(0, 1)],
  ] : [
    ["Plan your response", [assessment.criteria?.task?.feedback, assessment.criteria?.coherence?.feedback].filter((item): item is string => !!item)],
    ["Before you submit", [assessment.criteria?.vocabulary?.feedback, assessment.criteria?.grammar?.feedback].filter((item): item is string => !!item)],
  ];
  if (!items.some(([, entries]) => entries.length)) return null;
  return <Card variant="outlined" sx={{ bgcolor: "writing.light" }}><CardContent>
    <Typography component="h3" variant="h6" sx={{ color: "writing.dark" }}>
      {previous ? "Rewrite plan from your last attempt" : "Suggested rewrite plan"}
    </Typography>
    {assessment.revision_plan && "example" in assessment.revision_plan && <Typography variant="body2" color="text.secondary">
      Three improvements to work toward Band 8.0+
    </Typography>}
    <Stack spacing={1.25} sx={{ mt: 1 }}>
      {items.filter(([, entries]) => entries.length > 0).map(([title, entries]) => (
        <Box key={title}>
          <Typography component="h4" sx={{ fontWeight: 600 }}>{title}</Typography>
          <Box component="ul" sx={{ my: 0.5, pl: 2.5 }}>
            {entries.map((entry, index) => <li key={index}>{entry}</li>)}
          </Box>
        </Box>
      ))}
      {assessment.revision_plan?.example && <Box sx={{ borderLeft: "3px solid", borderColor: "writing.main", pl: 1.5 }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {assessment.revision_plan.example.type === "opening_paraphrase" ? "Example opening paraphrase" : "Example sentence"}
        </Typography>
        <Typography>{assessment.revision_plan.example.text}</Typography>
      </Box>}
    </Stack>
  </CardContent></Card>;
}

function Session({ attempt, onChange, onRevise, onHome, saveAndGoHome, startingRevision, timerSlot }: {
  attempt: Attempt; onChange: (attempt: Attempt) => void; onRevise: () => void; onHome: () => void;
  saveAndGoHome: Ref<() => void>;
  startingRevision: boolean;
  timerSlot: HTMLElement | null;
}) {
  const [work, setWork] = useState<Work>({
    answers: attempt.draft.answers ?? {}, essay: attempt.draft.essay ?? "",
    essay_task2: attempt.draft.essay_task2 ?? "",
  });
  const [passageIndex, setPassageIndex] = useState(0);
  const [writingTask, setWritingTask] = useState(0);
  const [remaining, setRemaining] = useState(() => {
    const currentTime = attempt.paused_at ? Date.parse(attempt.paused_at) : Date.now();
    return Math.max(0, Math.ceil((Date.parse(attempt.deadline) - currentTime) / 1000));
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [readingSize, setReadingSize] = useState(1);
  const [editorRows, setEditorRows] = useState(14);
  const [hints, setHints] = useState<Partial<Record<number, VocabularyHint[]>>>({});
  const [hintRequest, setHintRequest] = useState<number>();
  const [hintError, setHintError] = useState<{ task: number; message: string }>();
  const [listeningMarks, setListeningMarks] = useState<Record<number, "correct" | "incorrect" | null>>({});
  const markedCount = Object.values(listeningMarks).filter(mark => mark !== null).length;
  const saveQueue = useRef<Promise<unknown>>(Promise.resolve());
  const path = `/practice/sessions/${attempt.id}`;
  const finished = !!attempt.submitted_at;
  const paused = !!attempt.paused_at;
  const pendingJob = attempt.result?.job_id;
  const feedback = useQuery({
    queryKey: ["writing-feedback", pendingJob], enabled: !!pendingJob,
    queryFn: () => api<JobStatus>(`/jobs/${pendingJob}`),
    refetchInterval: query => ["succeeded", "failed"].includes(query.state.data?.state ?? "") ? false : 2000,
  });
  const previous = useQuery({
    queryKey: ["revision-parent", attempt.parent_id], enabled: !!attempt.parent_id,
    queryFn: () => api<Attempt>(`/practice/sessions/${attempt.parent_id}`),
  });
  const revisions = useQuery({
    queryKey: ["writing-revisions", attempt.id, attempt.result?.kind],
    enabled: attempt.module === "writing" && (finished || !!attempt.parent_id),
    queryFn: () => api<RevisionHistory>(`${path}/revisions`),
  });

  useEffect(() => {
    if (feedback.data?.state === "succeeded") {
      api<Attempt>(path).then(onChange).catch(() => setError("Could not refresh feedback. Reopen this session from History."));
    }
  }, [feedback.data?.state, path]); // Refresh once when the job completes.

  useEffect(() => {
    if (finished) return;
    if (attempt.paused_at) {
      setRemaining(Math.max(0, Math.ceil((Date.parse(attempt.deadline) - Date.parse(attempt.paused_at)) / 1000)));
      return;
    }
    const tick = () => {
      const seconds = Math.max(0, Math.ceil((Date.parse(attempt.deadline) - Date.now()) / 1000));
      setRemaining(seconds);
      if (!seconds) {
        api<Attempt>(path).then(result => {
          if (result.submitted_at) onChange(result);
        }).catch(() => setError("Could not finalize the expired session. Try Submit again."));
      }
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [attempt.deadline, attempt.paused_at, finished, path]);

  useEffect(() => {
    if (finished || paused || submitting) return;
    const timer = window.setTimeout(() => {
      saveQueue.current = saveQueue.current.then(() => api(`${path}/draft`, "PUT", work))
        .catch(() => setError("Autosave failed. Try submitting before the timer expires."));
    }, 350);
    return () => window.clearTimeout(timer);
  }, [work, path, finished, paused, submitting]);

  async function submit() {
    setError("");
    setSubmitting(true);
    try {
      onChange(await api<Attempt>(`${path}/submit`, "POST", work));
    } catch {
      setError("Could not submit. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function saveListeningScore() {
    setError("");
    setSubmitting(true);
    try {
      const correct = Array.from({ length: 40 }, (_, index) => listeningMarks[index + 1] === "correct");
      onChange(await api<Attempt>(`${path}/listening-score`, "POST", { correct }));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not save your Listening score.");
    } finally {
      setSubmitting(false);
    }
  }

  async function togglePause(goHome = false) {
    if (goHome && (paused || finished)) {
      onHome();
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await saveQueue.current;
      onChange(await api<Attempt>(`${path}/${paused ? "resume" : "pause"}`, "POST", paused ? undefined : work));
      if (goHome) onHome();
    } catch {
      setError(paused ? "Could not resume. Try again." : "Could not pause. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  useImperativeHandle(saveAndGoHome, () => () => {
    if (!submitting) void togglePause(true);
  });

  const passages = attempt.content.passages ?? [];
  const passage = passages[passageIndex];
  const offset = passages.slice(0, passageIndex).reduce((total, item) => total + item.questions.length, 0);
  const fullWriting = attempt.content.task === "full";
  const prompt = attempt.content.tasks?.[writingTask] ?? attempt.content;
  const essayField = fullWriting && writingTask === 1 ? "essay_task2" : "essay";
  const assessment = fullWriting ? attempt.result?.tasks?.[writingTask] : attempt.result;
  const previousAssessment = fullWriting ? previous.data?.result?.tasks?.[writingTask] : previous.data?.result;
  const learning = attempt.content.mode === "learning";
  const hintTask = typeof prompt.task === "number" ? prompt.task : undefined;
  const simulation = attempt.content.simulation_id;

  async function requestHints(task: number) {
    setHintError(undefined);
    setHintRequest(task);
    try {
      const suggested = await api<{ words: VocabularyHint[] }>(`${path}/vocabulary`, "POST", {
        task, draft: work[essayField],
      });
      setHints(current => ({ ...current, [task]: suggested.words }));
    } catch (failure) {
      setHintError({ task, message: failure instanceof Error ? failure.message : "Could not load vocabulary hints." });
    } finally {
      setHintRequest(undefined);
    }
  }
  return <Stack spacing={2}>
    <Button sx={{ alignSelf: "start" }} disabled={submitting} onClick={() => togglePause(true)}>
      {finished || paused ? "Back to home" : "Save and go home"}
    </Button>
    <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: "center", flexWrap: "wrap" }}>
      <Chip variant="outlined" color={attempt.module} size="small" label={skillLabels[attempt.module]} />
      {learning && <Chip variant="outlined" size="small" label="Writing learning" />}
      <Typography variant="h5" component="h2" sx={{ color: `${attempt.module}.main` }}>{attempt.content.title}</Typography>
    </Stack>
    {attempt.content.reading_topic && <Typography color="text.secondary">{attempt.content.reading_topic}</Typography>}
    {!finished && timerSlot && createPortal(
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Box data-practice-timer>
          <Chip role="timer" variant="outlined"
            label={<Box component="span" sx={{ display: "flex", alignItems: "center", gap: 0.5,
              "[data-timer-placement='rail'] &": { flexDirection: "column", gap: 0 } }}>
              <Box component="span" sx={{ fontWeight: 700, fontVariantNumeric: "tabular-nums",
                "[data-timer-placement='rail'] &": { fontSize: { xs: "1rem", sm: "1.35rem" }, lineHeight: 1.2 } }}>
                {Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")}
              </Box>{" "}
              <Box component="span" sx={{ "[data-timer-placement='rail'] &": { fontSize: "0.7rem", color: "text.secondary" } }}>
                {paused ? "paused" : "remaining"}
              </Box>
            </Box>}
            sx={{ color: "inherit", borderColor: "currentColor",
              "[data-timer-placement='rail'] &": { height: "auto", border: 0, "& .MuiChip-label": { px: 0.5 } } }} />
        </Box>
        <Stack component="section" aria-label="Practice controls" direction="row" spacing={0.75}>
          <Button size="small" color={paused ? attempt.module : "inherit"} variant={paused ? "contained" : "outlined"}
            disabled={submitting} onClick={() => togglePause()}>
            {paused ? "Resume" : "Pause"}
          </Button>
          {!paused && <Button size="small" color={attempt.module} variant="contained" disabled={submitting} onClick={submit}>
            Submit
          </Button>}
        </Stack>
      </Stack>,
      timerSlot,
    )}
    {error && <Alert severity="error">{error}</Alert>}
    {paused && <Alert severity="info">Session paused. Your draft and remaining time are saved. Select Resume to continue.</Alert>}
    {finished && simulation && (attempt.module !== "listening" || !!attempt.result) &&
      <Button color={attempt.module} variant="contained" sx={{ alignSelf: "start" }}
        href={attempt.module === "listening" ? `/reading?simulation=${simulation}` :
          attempt.module === "reading" ? `/writing?simulation=${simulation}` : `/simulation?run=${simulation}`}>
        {attempt.module === "listening" ? "Continue to Reading" :
          attempt.module === "reading" ? "Continue to Writing" : "View simulation results"}
      </Button>}
    {!paused && attempt.module === "listening" && <>
      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { md: "repeat(2, minmax(0, 1fr))" }, alignItems: "start" }}>
        <Card variant="outlined" sx={{ position: { md: "sticky" }, top: "calc(var(--app-bar-height, 0px) + 16px)", overflow: "hidden" }}>
          <Box component="iframe" title="Listening test video"
            src={`https://www.youtube.com/embed/${attempt.content.video_id}`}
            allow="encrypted-media; picture-in-picture; fullscreen" allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
            sx={{ display: "block", width: "100%", aspectRatio: "16 / 9", border: 0, minHeight: 200 }} />
        </Card>
        <Stack spacing={2}>
          {!finished ? <Typography variant="h6" component="h3">Your answers</Typography> :
            attempt.result?.kind === "listening_self_scored" ?
              <Alert severity="info">Self-scored Listening result {attempt.result.score}/40</Alert> :
              <Box>
                <Typography variant="h6" component="h3">Mark your answers</Typography>
                <Typography variant="body2" color="text.secondary">
                  Compare your answers with the video’s key and mark each one Correct or Incorrect.
                </Typography>
                <Typography variant="body2" role="status" sx={{ mt: 1 }}>{markedCount}/40 marked</Typography>
              </Box>}
          <Stack component="ol" aria-label="Listening answers" spacing={1} sx={{ listStyle: "none", m: 0, p: 0 }}>
            {Array.from({ length: 40 }, (_, index) => {
              const number = index + 1;
              const answer = attempt.draft.answers?.[number];
              const result = attempt.result?.items?.[index];
              return <Box component="li" key={number}>
              {result ? <Alert severity={result.status === "correct" ? "success" : "warning"}>
                <strong>{number}. {result.status}</strong><br />
                Yours {result.answer || "—"}
                {result.accepted?.length ? <><br />Accepted {result.accepted.join(" / ")}</> : null}
              </Alert> : finished ? <Card variant="outlined" sx={{
                p: 1, display: "flex", alignItems: "center", justifyContent: "space-between",
                flexWrap: "wrap", gap: 1,
              }}>
                <Typography variant="body2" sx={{ flex: "1 1 8rem", overflowWrap: "anywhere" }}>
                  <strong>{number}.</strong> {answer || "No answer"}
                </Typography>
                <ToggleButtonGroup exclusive size="small" value={listeningMarks[number] ?? null}
                  aria-label={`Mark answer ${number}`}
                  onChange={(_, mark: "correct" | "incorrect" | null) =>
                    setListeningMarks(current => ({ ...current, [number]: mark }))}>
                  <ToggleButton color="success" value="correct">Correct</ToggleButton>
                  <ToggleButton color="error" value="incorrect">Incorrect</ToggleButton>
                </ToggleButtonGroup>
              </Card> : <TextField fullWidth size="small" label={`Answer ${number}`} value={work.answers[number] ?? ""}
                onChange={event => setWork({ ...work, answers: { ...work.answers, [number]: event.target.value } })} />}
              </Box>;
            })}
          </Stack>
          {finished && !attempt.result && <Button color="listening" variant="contained" sx={{ alignSelf: "start" }}
            disabled={submitting || markedCount !== 40}
            onClick={saveListeningScore}>Save self-score</Button>}
        </Stack>
      </Box>
    </>}
    {attempt.result?.kind === "reading_raw" && <Alert severity="info">
      <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: "center", flexWrap: "wrap" }}>
        <Typography variant="body2">Reading score {attempt.result.score}/{attempt.result.maximum}</Typography>
        <ReadingBandBadge grade={attempt.result} />
      </Stack>
    </Alert>}
    {!paused && passage && <>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ justifyContent: "space-between" }}>
        <Tabs value={passageIndex} onChange={(_, index) => setPassageIndex(index)} aria-label="Reading passages">
          {passages.map((_, index) => <Tab key={index} label={`Passage ${index + 1}`} />)}
        </Tabs>
        <TextField size="small" select label="Passage text size" value={readingSize}
          onChange={event => setReadingSize(Number(event.target.value))} sx={{ minWidth: 150 }}>
          <MenuItem value={0.875}>Small</MenuItem><MenuItem value={1}>Standard</MenuItem><MenuItem value={1.25}>Large</MenuItem>
        </TextField>
      </Stack>
      <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }} aria-label="Question navigator">
        {passages.flatMap((item, index) => item.questions.map((_, questionIndex) => {
          const number = passages.slice(0, index).reduce((total, entry) => total + entry.questions.length, 0) + questionIndex + 1;
          const status = attempt.result?.items?.[number - 1]?.status ?? (work.answers[number]?.trim() ? "answered" : "unanswered");
          return <Button key={number} size="small" aria-label={`Question ${number}, ${status}`}
            variant={status === "unanswered" ? "outlined" : "contained"}
            color={status === "incorrect" ? "error" : status === "correct" ? "success" : "reading"} sx={{ minWidth: 36 }}
            onClick={() => {
              setPassageIndex(index);
              window.requestAnimationFrame(() => document.getElementById(`question-${number}`)?.scrollIntoView({ block: "center" }));
            }}>{number}</Button>;
        }))}
      </Stack>
      <Box sx={{ display: "grid", gap: { xs: 2, md: 3 }, gridTemplateColumns: { md: "repeat(2, minmax(0, 1fr))" }, alignItems: "start" }}>
        <Card key={passageIndex} variant="outlined" sx={{
          position: { md: "sticky" }, top: "calc(var(--app-bar-height, 0px) + 16px)",
          height: "calc(100dvh - var(--app-bar-height, 0px) - 32px)", minHeight: 200,
        }}><CardContent component="section" tabIndex={0} aria-label={`Passage ${passageIndex + 1}`}
          sx={{ height: "100%", overflowY: "auto" }}>
          <Typography variant="h6">{passage.title}</Typography>
          <Typography sx={{ whiteSpace: "pre-wrap", my: 2, fontSize: `${readingSize}rem`, lineHeight: 1.7 }}>{passage.text}</Typography>
          <ReadingCitation reference={passage.source} />
        </CardContent></Card>
        <Stack spacing={2}>{passage.questions.map((question, index) => {
          const number = offset + index + 1;
          const options = readingOptions(question, attempt.content.reading_option_order === "shuffled-v1"
            ? attempt.id + ":" + number : undefined);
          const answerLabel = (value: string) => options.find(option => option.value === value)?.label ?? value;
          const status = attempt.result?.items?.[number - 1]?.status;
          const group = passage.question_groups?.find(item => index >= item.start && index < item.start + item.count);
          const summary = group?.type === "summary_completion";
          return <Fragment key={number}>
            {group?.start === index && <Box component="section" aria-label={group.title} sx={{ mt: 1 }}>
              <Typography component="h3" variant="subtitle1" sx={{ fontWeight: 700, color: "reading.main" }}>
                Questions {number}–{number + group.count - 1} · {group.title}
              </Typography>
              <Typography variant="body2" sx={{ mt: 0.5 }}>{group.instructions}</Typography>
              {group.word_limit && <Typography variant="body2" sx={{ mt: 0.5, fontWeight: 600 }}>
                Use no more than {group.word_limit} {group.word_limit === 1 ? "word" : "words"} per answer.
              </Typography>}
              {summary && <Typography variant="body2" sx={{ mt: 1, lineHeight: 1.8 }}>
                {passage.questions.slice(index, index + group.count)
                  .map((item, i) => item.prompt.replace(/_{3,}/, `[${number + i}] ___`)).join(" ")}
              </Typography>}
              {group.options.length > 0 && <Box component="ul" sx={{ m: 0, mt: 1, pl: 2.5 }}>
                {group.options.map(option => <Typography component="li" variant="body2" key={option}>{option}</Typography>)}
              </Box>}
            </Box>}
            <Card id={`question-${number}`} variant="outlined"><CardContent>
              {(!summary || finished) && <Typography sx={{ fontWeight: 600 }}>{number}. {question.prompt}</Typography>}
              {finished ? <Alert sx={{ mt: 1 }} severity={status === "correct" ? "success" : "error"}>
                <Typography sx={{ textTransform: "capitalize" }}>{status}</Typography>
                <Typography>Your answer: {answerLabel(attempt.draft.answers?.[number] || "—")}</Typography>
                <Typography>Accepted: {question.answers?.map(answerLabel).join(" / ")}</Typography>
                <Typography>{question.explanation}</Typography>
                {question.evidence && <Typography component="blockquote" sx={{ mx: 0 }}>{question.evidence}</Typography>}
              </Alert> : <TextField fullWidth sx={{ mt: 2 }} size="small" label={`Answer ${number}`}
                helperText={!group && question.word_limit ? `Maximum ${question.word_limit} words` : undefined}
                select={options.length > 0} value={work.answers[number] ?? ""}
                onChange={event => setWork({ ...work, answers: { ...work.answers, [number]: event.target.value } })}>
                {options.length > 0 && [<MenuItem key="" value="">Unanswered</MenuItem>, ...options.map(option =>
                  <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>)]}
              </TextField>}
            </CardContent></Card>
          </Fragment>;
        })}</Stack>
      </Box>
    </>}
    {!paused && attempt.module === "writing" && <>
      {fullWriting && <>
        {attempt.result?.kind === "unofficial_full_writing_estimate" && attempt.result.band !== undefined &&
          <Box><BandScore band={attempt.result.band} label={`Writing band ${attempt.result.band.toFixed(1)} · Unofficial`} /></Box>}
        <Tabs value={writingTask} onChange={(_, taskIndex) => setWritingTask(taskIndex)}
          aria-label="Writing tasks" textColor="inherit" sx={{ color: "writing.main" }}>
          <Tab label="Task 1 · 150 words" />
          <Tab label="Task 2 · 250 words" />
        </Tabs>
        <Typography variant="h6" component="h3">{prompt.title}</Typography>
      </>}
      {prompt.category && <Typography variant="body2" color="text.secondary">{prompt.category}</Typography>}
      <Typography>{prompt.prompt}</Typography>
      {prompt.chart && <TaskChart chart={prompt.chart} kind={prompt.visual_kind} />}
      {prompt.table && <Stack spacing={0.75}>
        {prompt.visual_kind === "bar_table" && <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          Share of the total by group (%)
        </Typography>}
        {prompt.visual_kind === "table" &&
          <Typography variant="caption" color="text.secondary">Illustrative practice data</Typography>}
        <WritingDataTable rows={prompt.table} />
      </Stack>}
      {prompt.process && <WritingProcess title={prompt.title} stages={prompt.process} />}
      {!finished && previousAssessment && <RevisionSuggestions assessment={previousAssessment} previous />}
      {finished ? <Card variant="outlined"><CardContent>
        <Typography variant="h6">Your submission</Typography>
        <Typography sx={{ whiteSpace: "pre-wrap" }}>{attempt.draft[essayField] || "No answer submitted."}</Typography>
      </CardContent></Card> : <>
        <TextField select size="small" label="Editor height" value={editorRows} sx={{ alignSelf: "start", minWidth: 150 }}
          onChange={event => setEditorRows(Number(event.target.value))}>
          <MenuItem value={8}>Compact</MenuItem><MenuItem value={14}>Standard</MenuItem><MenuItem value={22}>Large</MenuItem>
        </TextField>
        <TextField label={fullWriting ? `Your Task ${writingTask + 1} response` : "Your response"} multiline minRows={editorRows}
          value={work[essayField]} helperText={`${work[essayField].trim().match(/\S+/g)?.length ?? 0} words`}
          onChange={event => setWork({ ...work, [essayField]: event.target.value })} />
        {learning && hintTask !== undefined && (
          <Stack spacing={1.5} sx={{ alignItems: "flex-start" }}>
            <Button color="writing" variant="outlined" disabled={hintRequest !== undefined}
              onClick={() => requestHints(hintTask)}>
              {hintRequest === hintTask ? "Finding vocabulary…" : hints[hintTask] ? "Refresh vocabulary hints" : "Get vocabulary hints"}
            </Button>
            {hintError?.task === hintTask && <Alert severity="error">{hintError.message}</Alert>}
            {hints[hintTask] && <Card variant="outlined" sx={{ width: "100%" }}><CardContent>
              <Typography component="h3" variant="h6">Vocabulary hints</Typography>
              <Stack component="ul" spacing={1.25} sx={{ m: 0, pl: 2.5, pt: 1 }}>
                {hints[hintTask]?.map(hint => <Box component="li" key={hint.term}>
                  <Typography><strong>{hint.term}</strong> · {hint.meaning}</Typography>
                  <Typography variant="body2" color="text.secondary">{hint.phrase}</Typography>
                </Box>)}
              </Stack>
            </CardContent></Card>}
          </Stack>
        )}
      </>}
      {pendingJob && <Alert severity={feedback.data?.state === "failed" || feedback.isError ? "error" : "info"}>
        {jobMessage(feedback.data) ??
          (feedback.data?.state === "failed" || feedback.isError ? "Feedback is unavailable. Your submission is saved." : "Preparing feedback…")}
      </Alert>}
      {assessment?.unanswered && <Alert severity="warning">This task was left unanswered.</Alert>}
      {finished && assessment && <RevisionSuggestions assessment={assessment} />}
      {assessment?.criteria && !assessment.unanswered && <>
        {assessment.band !== undefined && <Box><BandScore band={assessment.band}
          label={`${fullWriting ? `Task ${writingTask + 1}` : "Writing"} band ${assessment.band.toFixed(1)} · Unofficial`} /></Box>}
        {Object.entries(assessment.criteria).map(([key, value]) => {
          const labels: Record<string, string> = {
            task: prompt.task === 1 ? "Task Achievement" : "Task Response",
            coherence: "Coherence and Cohesion", vocabulary: "Lexical Resource", grammar: "Grammatical Range and Accuracy",
          };
          return <Card key={key} variant="outlined"><CardContent>
            <Typography variant="h6">{labels[key]} · {value.band.toFixed(1)}</Typography>
            <Typography>{value.feedback}</Typography>
            {value.quote && <Typography component="blockquote" sx={{ mx: 0 }}>{value.quote}</Typography>}
            {previousAssessment?.criteria?.[key] && <Typography color="text.secondary">
              Previous {previousAssessment.criteria[key].band.toFixed(1)} · {previousAssessment.criteria[key].feedback}
            </Typography>}
          </CardContent></Card>;
        })}
      </>}
      {previous.data && <Card component="details" variant="outlined">
        <Typography component="summary" sx={{ cursor: "pointer", p: 2 }}>Previous submission</Typography>
        <CardContent sx={{ pt: 0 }}>
          <Typography sx={{ whiteSpace: "pre-wrap" }}>{previous.data.draft[essayField]}</Typography>
        </CardContent>
      </Card>}
      {revisions.isError && <Alert severity="error">Could not load rewrite history.</Alert>}
      {revisions.data && <Card variant="outlined"><CardContent>
        <Typography component="h3" variant="h6">Writing attempts</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {revisions.data.remaining} of {revisions.data.retry_limit} rewrites remaining
        </Typography>
        <Stack component="ol" spacing={1} sx={{ listStyle: "none", p: 0, m: 0 }}>
          {revisions.data.items.map(item => <Stack component="li" key={item.id} direction="row"
            spacing={1} useFlexGap sx={{ alignItems: "center", flexWrap: "wrap" }}>
            <Typography>{item.number === 0 ? "Original" : `Rewrite ${item.number}`}</Typography>
            {item.band === null ? <Chip size="small" variant="outlined" label={item.submitted ? "Score unavailable" : "In progress"} /> :
              <BandScore band={item.band} />}
            {item.task_bands.map((band, index) => <Typography key={index} variant="body2" color="text.secondary">
              Task {index + 1} {band.toFixed(1)}
            </Typography>)}
            {item.id !== attempt.id && <Button size="small" color="writing" href={`/sessions/${item.id}`}>
              {item.submitted ? "Review" : "Continue"}
            </Button>}
          </Stack>)}
        </Stack>
        {finished && revisions.data.latest_id === attempt.id && revisions.data.remaining > 0 &&
          <Button variant="contained" color="writing" sx={{ mt: 2 }}
            disabled={startingRevision || (!!pendingJob && feedback.data?.state !== "failed" && !feedback.isError)}
            onClick={onRevise}>Rewrite this task</Button>}
      </CardContent></Card>}
    </>}
  </Stack>;
}
