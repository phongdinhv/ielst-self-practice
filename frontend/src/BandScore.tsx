import { Chip } from "@mui/material";

export function bandTone(band: number) {
  if (band >= 8) return { background: "#2b145c", text: "#ffffff" };
  if (band >= 6.5) return { background: "#81e2d3", text: "#222342" };
  return { background: "#eee8f6", text: "#43286d" };
}

export function BandScore({ band, label }: { band: number; label?: string }) {
  const colors = bandTone(band);
  return <Chip size="small" label={label ?? `Band ${band.toFixed(1)} · Unofficial`}
    sx={{ bgcolor: colors.background, color: colors.text, fontWeight: 600 }} />;
}
