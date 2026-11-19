import { Alert, AppBar, Avatar, Box, Button, Card, CardContent, Container, CssBaseline, IconButton, Menu, MenuItem, Stack, Toolbar, Typography, useMediaQuery } from "@mui/material";
import { ThemeProvider } from "@mui/material/styles";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
import { useEffect, useRef, useState } from "react";
import { DashboardProgress, Practice } from "./Practice";
import { darkTheme, skillLabels, skills, theme, type Skill } from "./theme";
import { BandScore } from "./BandScore";

const paths: Record<string, string> = {
  home: "/", listening: "/listening", reading: "/reading", writing: "/writing",
  readingMocks: "/reading/mocks",
  simulation: "/simulation", history: "/history", progress: "/progress",
};
const appearanceModes = ["system", "light", "dark"] as const;
type AppearanceMode = typeof appearanceModes[number];
const modeLabels: Record<AppearanceMode, string> = { system: "System", light: "Light", dark: "Dark" };
const appearanceKey = "ielts-appearance";
const timerRailWidth = { xs: 68, sm: 108 };

function currentPath() {
  return window.location.pathname.replace(/\/$/, "") || "/";
}

interface Dashboard {
  estimates: {
    overall: number | null;
    missing: Skill[];
    modules: Partial<Record<Skill, {
      value: number; unit: "band" | "raw_40"; count: number; task?: number; estimated?: boolean; raw_average?: number;
    }>>;
    sample_limit: number;
  };
}

async function loadDashboard(): Promise<Dashboard> {
  const response = await fetch("/api/v1/dashboard");
  if (!response.ok) throw new Error("Could not load study goals.");
  return response.json();
}

function DashboardPage({ appearance, setAppearance }: {
  appearance: AppearanceMode; setAppearance: (mode: AppearanceMode) => void;
}) {
  const [path, setPath] = useState(currentPath);
  const [inFullscreen, setInFullscreen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const [topBarHeight, setTopBarHeight] = useState(64);
  const [timerSlot, setTimerSlot] = useState<HTMLDivElement | null>(null);
  const topBar = useRef<HTMLElement>(null);
  const saveAndGoHome = useRef<(() => void) | null>(null);
  useEffect(() => {
    const update = () => setPath(currentPath());
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);
  const sessionId = /^\/sessions\/([0-9a-f-]+)$/i.exec(path)?.[1];
  const view = sessionId ? "attempt" : Object.keys(paths).find(key => paths[key] === path) ?? "missing";
  const canFocus = view === "attempt" || skills.some(skill => skill === view);
  const focused = canFocus && (inFullscreen || expanded);
  const focusedAttempt = focused && view === "attempt";
  const showTopBar = !focused || focusedAttempt;
  useEffect(() => {
    const bar = topBar.current;
    if (!bar) return;
    const measure = () => setTopBarHeight(bar.offsetHeight);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(bar);
    return () => observer.disconnect();
  }, [showTopBar]);
  useEffect(() => {
    const onFullscreenChange = () => setInFullscreen(document.fullscreenElement === document.documentElement);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, []);
  useEffect(() => {
    if (canFocus) return;
    setExpanded(false);
    if (document.fullscreenElement === document.documentElement) {
      void document.exitFullscreen().catch(() => {});
    }
  }, [canFocus]);

  async function toggleFullscreen() {
    if (expanded) {
      setExpanded(false);
    } else if (inFullscreen) {
      await document.exitFullscreen();
    } else if (document.fullscreenEnabled) {
      try {
        await document.documentElement.requestFullscreen();
      } catch {
        setExpanded(true);
      }
    } else {
      setExpanded(true);
    }
  }
  function navigate(destination: string) {
    window.history.pushState(null, "", destination);
    setPath(destination);
    window.scrollTo(0, 0);
  }
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: loadDashboard });
  const titles: Record<string, string> = {
    home: "Practice", reading: "Reading practice", writing: "Writing practice",
    listening: "Listening practice", simulation: "Three-skill simulation",
    readingMocks: "Reading mocks",
    attempt: "Practice session", history: "Session history", progress: "Progress",
    missing: "Page not found",
  };
  return (
    <>
      {showTopBar && <AppBar ref={topBar} position="sticky" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Toolbar sx={{ flexWrap: "wrap", justifyContent: "space-between", gap: 1, py: 1 }}>
          {!focusedAttempt && <Button href="/" color="inherit" aria-label="IELTS Academic Practice home"
            onClick={event => {
              if (view === "attempt" && saveAndGoHome.current && !event.metaKey && !event.ctrlKey && !event.altKey && !event.shiftKey) {
                event.preventDefault();
                saveAndGoHome.current();
              }
            }}
            sx={{ gap: 1.25, textTransform: "none", textAlign: "left", px: 0.75 }}>
            <Box component="span" aria-hidden="true" sx={{
              display: "grid", placeItems: "center", width: 36, height: 36, borderRadius: 0.75,
              bgcolor: "primary.contrastText", color: "primary.main",
              fontFamily: "Georgia, serif", fontWeight: 700, fontSize: 18, lineHeight: 1,
            }}>IA</Box>
            <Typography variant="h6" component="span"
              sx={{ display: { xs: view === "attempt" ? "none" : "inline", sm: "inline" } }}>IELTS Academic Practice</Typography>
          </Button>}
          {view === "attempt" && <Box ref={setTimerSlot} data-timer-placement={focusedAttempt ? "rail" : "header"}
            sx={{
              display: "flex", justifyContent: "center",
              "&:empty": { display: "none" },
              ...(focusedAttempt ? {
                "& [data-practice-timer]": {
                  position: "fixed", left: 0, top: "50%", transform: "translateY(-50%)", width: timerRailWidth,
                  bgcolor: "background.paper", color: "text.primary", border: 1, borderLeft: 0, borderColor: "divider",
                  borderRadius: "0 8px 8px 0", py: 1.25, display: "grid", placeItems: "center",
                },
              } : { order: { xs: 1, md: 0 }, flexBasis: { xs: "100%", md: "auto" } }),
            }} />}
          {focusedAttempt ? <Button color="inherit" size="small" aria-pressed sx={{ ml: "auto" }}
            onClick={() => void toggleFullscreen()}>Exit full screen</Button> :
          <Stack direction="row" component="nav" aria-label="Main navigation"
            sx={{ alignItems: "center", ml: view === "attempt" ? 0 : "auto" }}>
            <Button color="inherit" href="/history">History</Button>
            <IconButton id="appearance-button" color="inherit" aria-label="Appearance settings"
              aria-haspopup="menu" aria-controls={menuAnchor ? "appearance-menu" : undefined}
              aria-expanded={!!menuAnchor} onClick={event => setMenuAnchor(event.currentTarget)}>
              <Avatar sx={{ width: 34, height: 34, bgcolor: "background.paper", color: "text.primary", fontSize: 15 }}>
                PV
              </Avatar>
            </IconButton>
            <Menu id="appearance-menu" anchorEl={menuAnchor} open={!!menuAnchor} onClose={() => setMenuAnchor(null)}
              anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
              transformOrigin={{ vertical: "top", horizontal: "right" }}
              slotProps={{ list: { "aria-labelledby": "appearance-button" } }}>
              {appearanceModes.map(mode => <MenuItem key={mode} role="menuitemradio"
                aria-checked={appearance === mode} selected={appearance === mode} onClick={() => {
                  setAppearance(mode);
                  setMenuAnchor(null);
                }}>{modeLabels[mode]}</MenuItem>)}
            </Menu>
          </Stack>}
        </Toolbar>
      </AppBar>}
      <Container component="main" maxWidth={view === "attempt" || focused ? "xl" : "md"}
        sx={{
          "--app-bar-height": showTopBar ? `${topBarHeight}px` : "0px", py: focused ? 2 : { xs: 4, sm: 6 },
          "header:has([data-timer-placement='rail'] [role='timer']) + &": {
            pl: { xs: `${timerRailWidth.xs + 8}px`, sm: `${timerRailWidth.sm + 16}px` },
          },
        }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}
          sx={{ alignItems: { sm: "center" }, justifyContent: "space-between" }}>
          <Typography variant={focused ? "h5" : "h3"} component="h1" sx={{
            fontFamily: "Georgia, serif",
            color: skills.find(skill => skill === view) ? `${view}.main` : "text.primary",
          }}>{titles[view]}</Typography>
          {canFocus && !focusedAttempt && <Button variant="outlined" size="small" aria-pressed={focused}
            sx={{ alignSelf: { xs: "flex-start", sm: "center" }, flexShrink: 0 }}
            onClick={() => void toggleFullscreen()}>
            {focused ? "Exit full screen" : "Full screen"}
          </Button>}
        </Stack>
        {view === "history" && <Button href="/progress" variant="outlined" sx={{ mt: 2 }}>View progress</Button>}
        {view === "missing" ? <Button href="/">Back to practice</Button> :
          <Practice view={view} sessionId={sessionId} navigate={navigate} saveAndGoHome={saveAndGoHome} timerSlot={timerSlot} />}
        {view === "home" && <Stack direction="row" sx={{ mt: 5, justifyContent: "space-between", alignItems: "center", gap: 2 }}>
          <Typography variant="h5" component="h2">Current average bands</Typography>
          <Button href="/progress" sx={{ flexShrink: 0 }}>View progress</Button>
        </Stack>}
        {view === "home" && dashboard.isPending && <Typography sx={{ mt: 3 }} role="status">Loading score averages…</Typography>}
        {view === "home" && dashboard.isError && (
          <Alert severity="error" sx={{ mt: 3 }} action={
            <Button color="inherit" onClick={() => dashboard.refetch()}>Try again</Button>
          }>{dashboard.error.message}</Alert>
        )}
        {view === "home" && dashboard.data && (
          <>
            {dashboard.data.estimates.overall !== null && <Card variant="outlined" sx={{ mt: 2 }}>
              <CardContent sx={{ display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap" }}>
                <Typography variant="subtitle1" component="h3" sx={{ fontWeight: 600 }}>
                  Overall practice prediction
                </Typography>
                <BandScore band={dashboard.data.estimates.overall} />
              </CardContent>
            </Card>}
            <Box component="ul" sx={{
              mt: 2, mb: 0, p: 0, listStyle: "none", display: "grid", gap: 2,
              gridTemplateColumns: { xs: "1fr", sm: "repeat(3, minmax(0, 1fr))" },
            }}>
            {skills.map(module => {
              const estimate = dashboard.data.estimates.modules[module];
              return (
              <Card component="li" key={module} variant="outlined">
                <CardContent>
                <Typography variant="h6" component="h2" sx={{ color: `${module}.main` }}>{skillLabels[module]}</Typography>
                <Box sx={{ mt: 1.5 }}>
                  {estimate?.unit === "band" ? <BandScore band={estimate.value}
                    label={estimate.estimated ? `Estimated band ${estimate.value.toFixed(1)}` :
                      estimate.task ? `Task ${estimate.task} · Band ${estimate.value.toFixed(1)} · Unofficial` : undefined} /> :
                    <Typography variant="body2">{estimate
                      ? `Raw average ${estimate.value}/40${module === "listening" ? " · Self-scored" : ""}` : "—"}</Typography>}
                </Box>
                {estimate?.raw_average !== undefined &&
                  <Typography variant="body2" sx={{ mt: 0.75 }}>Raw average {estimate.raw_average}/40</Typography>}
                {estimate && <Typography variant="caption" color="text.secondary">
                  Based on {estimate.count} {estimate.count === 1 ? "attempt" : "attempts"}
                </Typography>}
                </CardContent>
              </Card>
              );
            })}
            </Box>
          </>
        )}
        {view === "home" && <Stack component="section" spacing={2} sx={{ mt: 4 }} aria-labelledby="score-trends">
          <Typography id="score-trends" component="h2" variant="h5">Scores over time</Typography>
          <DashboardProgress />
        </Stack>}
      </Container>
    </>
  );
}

function App() {
  const [appearance, setAppearance] = useState<AppearanceMode>(() => {
    const saved = window.localStorage.getItem(appearanceKey);
    return saved === "light" || saved === "dark" ? saved : "system";
  });
  const systemDark = useMediaQuery("(prefers-color-scheme: dark)");
  const dark = appearance === "dark" || (appearance === "system" && systemDark);

  function selectMode(mode: AppearanceMode) {
    window.localStorage.setItem(appearanceKey, mode);
    setAppearance(mode);
  }

  return <ThemeProvider theme={dark ? darkTheme : theme}>
    <CssBaseline enableColorScheme />
    <DashboardPage appearance={appearance} setAppearance={selectMode} />
  </ThemeProvider>;
}

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider>,
);
