import { useEffect, useRef, useState } from "react";
import { Alert, Box, Button, Card, Stack, Typography } from "@mui/material";

const videosUrl = "https://www.youtube.com/@TheIELTSListeningTest/videos";
const coursesUrl = "https://www.youtube.com/@TheIELTSListeningTest/courses";
const uploadsPlaylistId = "UUIgELCOfrcYA9jWF4TOJUnQ";

type PlaylistPlayer = {
  getPlaylist(): string[] | undefined;
  getPlaylistIndex(): number;
  playVideoAt(index: number): void;
  destroy(): void;
};

type YouTubeApi = {
  Player: new (iframe: HTMLIFrameElement, options: {
    events: { onReady: () => void; onError: () => void; onStateChange: (state: { data: number }) => void };
  }) => PlaylistPlayer;
};

type YouTubeWindow = Window & { YT?: YouTubeApi; onYouTubeIframeAPIReady?: () => void };
let playerApi: Promise<YouTubeApi> | undefined;

function loadPlayerApi(): Promise<YouTubeApi> {
  const youtube = window as YouTubeWindow;
  if (youtube.YT?.Player) return Promise.resolve(youtube.YT);
  if (playerApi) return playerApi;

  playerApi = new Promise<YouTubeApi>((resolve, reject) => {
    const script = document.createElement("script");
    const previousReady = youtube.onYouTubeIframeAPIReady;
    const timeout = window.setTimeout(fail, 12000);
    function fail() {
      window.clearTimeout(timeout);
      youtube.onYouTubeIframeAPIReady = previousReady;
      script.remove();
      reject(new Error("YouTube player controls could not load"));
    }
    youtube.onYouTubeIframeAPIReady = () => {
      window.clearTimeout(timeout);
      youtube.onYouTubeIframeAPIReady = previousReady;
      if (youtube.YT?.Player) resolve(youtube.YT);
      else fail();
      previousReady?.();
    };
    script.src = "https://www.youtube.com/iframe_api";
    script.onerror = fail;
    document.head.append(script);
  }).catch(error => {
    playerApi = undefined;
    throw error;
  });
  return playerApi;
}

export function Listening({ onStart, starting }: { onStart: (videoId: string) => void; starting: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const player = useRef<PlaylistPlayer | null>(null);
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState("");
  const [theater, setTheater] = useState(false);

  useEffect(() => {
    if (!host.current) return;
    let active = true;
    const iframe = document.createElement("iframe");
    const parameters = new URLSearchParams({
      listType: "playlist", list: uploadsPlaylistId, enablejsapi: "1", origin: window.location.origin,
    });
    iframe.title = "The IELTS Listening Test uploads playlist";
    iframe.src = `https://www.youtube.com/embed?${parameters}`;
    iframe.allow = "encrypted-media; picture-in-picture; fullscreen";
    iframe.allowFullscreen = true;
    iframe.referrerPolicy = "strict-origin-when-cross-origin";
    host.current.append(iframe);

    loadPlayerApi().then(api => {
      if (!active) return;
      player.current = new api.Player(iframe, { events: {
        onReady: () => { if (active) setReady(true); },
        onError: () => {
          if (active) setMessage("YouTube couldn’t play this video here. Try another test or open the channel directly.");
        },
        onStateChange: state => {
          if (active && state.data === 1) setMessage("");
        },
      } });
    }).catch(() => {
      if (active) setMessage("Random selection is unavailable. You can still use the playlist menu or open the channel.");
    });
    return () => {
      active = false;
      player.current?.destroy();
      player.current = null;
      iframe.remove();
    };
  }, []);

  function chooseRandomTest() {
    const currentPlayer = player.current;
    const playlist = currentPlayer?.getPlaylist();
    if (!currentPlayer || !playlist?.length) {
      setMessage("YouTube hasn’t loaded the playlist yet. Try playing a video, then select Random test again.");
      return;
    }
    const current = currentPlayer.getPlaylistIndex();
    const choices = playlist.map((_, index) => index).filter(index => index !== current);
    const next = choices.length ? choices[Math.floor(Math.random() * choices.length)] : 0;
    setMessage("");
    currentPlayer.playVideoAt(next);
  }

  return <Stack spacing={2}>
    <Typography>Choose a random test or browse the playlist from The IELTS Listening Test.</Typography>
    <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
      <Button color="listening" variant="outlined" disabled={!ready || starting}
        onClick={chooseRandomTest}>Random test</Button>
      <Button color="listening" variant="contained" disabled={!ready || starting} onClick={() => {
        const currentPlayer = player.current;
        const videoId = currentPlayer?.getPlaylist()?.[currentPlayer.getPlaylistIndex()];
        if (videoId) onStart(videoId);
        else setMessage("Select a video in the player before starting your timed session.");
      }}>Start 30-minute practice</Button>
      <Button color="listening" variant="outlined" aria-pressed={theater}
        onClick={() => setTheater(value => !value)}>Theater mode</Button>
    </Stack>
    {message && <Alert severity="info">{message}</Alert>}
    <Card variant="outlined" data-listening-theater={theater ? "" : undefined} sx={{ overflow: "hidden" }}>
      <Box ref={host} sx={{
        aspectRatio: "16 / 9", minHeight: 200,
        maxHeight: theater ? "calc(100dvh - var(--app-bar-height, 0px) - 24px)" : undefined,
        "& iframe": { display: "block", width: "100%", height: "100%", border: 0 },
      }} />
    </Card>
    <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
      <Button color="listening" variant="outlined" href={videosUrl}
        target="_blank" rel="noopener noreferrer">View all videos on YouTube</Button>
      <Button color="listening" href={coursesUrl} target="_blank" rel="noopener noreferrer">Browse channel courses</Button>
    </Stack>
  </Stack>;
}
