import { useEffect, useMemo, useRef } from "react";
import { Box, Card, CardContent, Stack, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";

export type WritingChart = {
  title: string;
  years: string[];
  series: { label: string; values: number[] }[];
  synthetic?: boolean;
  unit?: "%" | "count";
};

export type WritingVisualKind = "bar" | "line" | "pie" | "table" | "bar_table" | "process";

function chartMaximum(chart: WritingChart) {
  if (chart.unit !== "count") return 100;
  const largest = Math.max(5, ...chart.series.flatMap(series => series.values));
  const magnitude = 10 ** Math.floor(Math.log10(largest / 5));
  return Math.ceil(largest / (5 * magnitude)) * 5 * magnitude;
}

function formatValue(chart: WritingChart, value: number) {
  return chart.unit === "count" ? value.toLocaleString() : `${value}%`;
}

export function WritingDataTable({ rows, colors }: { rows: string[][]; colors?: string[] }) {
  return <Box sx={{ overflowX: "auto", alignSelf: "start", maxWidth: "100%" }}>
    <Box component="table" sx={{
      textAlign: "left", borderCollapse: "collapse", fontVariantNumeric: "tabular-nums",
      "& td, & th": { px: 1.25, py: 0.75, borderBottom: 1, borderColor: "divider" },
      "& td": { textAlign: "right", whiteSpace: "nowrap" },
    }}>
      <thead><tr>{rows[0].map(cell => <th key={cell} scope="col">{cell}</th>)}</tr></thead>
      <tbody>{rows.slice(1).map(([label, ...values], index) => <tr key={label}>
        <th scope="row">{colors && <Swatch color={colors[index]} />}{label}</th>
        {values.map((value, cell) => <td key={cell}>{value}</td>)}
      </tr>)}</tbody>
    </Box>
  </Box>;
}

function Swatch({ color }: { color: string }) {
  return <Box component="span" aria-hidden="true"
    sx={{ display: "inline-block", width: 10, height: 10, bgcolor: color, borderRadius: 0.25, mr: 0.75 }} />;
}

function SeriesGraph({ chart, colors, groupedBars }: { chart: WritingChart; colors: string[]; groupedBars: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const theme = useTheme();
  const { divider, text } = theme.palette;

  useEffect(() => {
    const node = canvas.current;
    const ctx = node?.getContext("2d");
    if (!node || !ctx) return;

    function draw() {
      if (!node || !ctx) return;
      const width = node.clientWidth;
      const height = node.clientHeight;
      if (!width || !height) return;
      const pixelRatio = window.devicePixelRatio || 1;
      node.width = width * pixelRatio;
      node.height = height * pixelRatio;
      ctx.scale(pixelRatio, pixelRatio);
      const left = chart.unit === "count" ? 52 : 40;
      const right = width - 24;
      const top = 16;
      const bottom = height - 30;
      const groupWidth = (right - left) / chart.years.length;
      const x = (index: number) => groupedBars ? left + (index + 0.5) * groupWidth :
        left + index * (right - left) / Math.max(1, chart.years.length - 1);
      const maximum = chartMaximum(chart);
      const y = (value: number) => bottom - (bottom - top) * value / maximum;
      ctx.font = "11px system-ui";
      ctx.fillStyle = text.secondary;
      ctx.strokeStyle = divider;
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      for (let fraction = 0; fraction <= 5; fraction++) {
        const tick = maximum / 5 * fraction;
        ctx.beginPath();
        ctx.moveTo(left, y(tick));
        ctx.lineTo(right, y(tick));
        ctx.stroke();
        const label = chart.unit === "count" ? tick.toLocaleString(undefined, { notation: "compact" }) : formatValue(chart, tick);
        ctx.fillText(label, left - 5, y(tick));
      }
      ctx.textBaseline = "top";
      ctx.textAlign = "center";
      chart.years.forEach((year, index) => ctx.fillText(year, x(index), bottom + 8));
      chart.series.forEach((series, index) => {
        ctx.fillStyle = colors[index];
        if (groupedBars) {
          const barWidth = Math.min(28, groupWidth * 0.8 / chart.series.length);
          const offset = (index - chart.series.length / 2) * barWidth;
          series.values.forEach((value, point) => {
            const top = y(value);
            ctx.fillRect(x(point) + offset, top, Math.max(1, barWidth - 1), bottom - top);
          });
          return;
        }
        ctx.strokeStyle = colors[index];
        ctx.lineWidth = 2;
        ctx.setLineDash([[], [6, 3], [2, 3], [8, 3, 2, 3]][index] ?? []);
        ctx.beginPath();
        series.values.forEach((value, point) => (point ? ctx.lineTo(x(point), y(value)) : ctx.moveTo(x(point), y(value))));
        ctx.stroke();
        series.values.forEach((value, point) => {
          ctx.beginPath();
          ctx.arc(x(point), y(value), 3, 0, Math.PI * 2);
          ctx.fill();
        });
      });
    }

    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(node);
    return () => observer.disconnect();
  }, [chart, colors, divider, groupedBars, text.secondary]);

  return <Box component="canvas" ref={canvas} aria-hidden="true" sx={{ display: "block", width: "100%", height: 240 }} />;
}

function PieCharts({ chart, colors }: { chart: WritingChart; colors: string[] }) {
  return <Stack direction="row" useFlexGap spacing={3} sx={{ flexWrap: "wrap", justifyContent: "center" }}>
    {chart.years.map((year, index) => {
      let end = 0;
      const stops = chart.series.map((series, slice) => {
        const start = end;
        end += series.values[index];
        return `${colors[slice]} ${start}% ${end}%`;
      });
      return <Stack spacing={1} key={year} sx={{ alignItems: "center" }}>
        <Box aria-hidden="true" sx={{
          width: { xs: 144, sm: 166 }, aspectRatio: "1", borderRadius: "50%",
          background: `conic-gradient(${stops.join(", ")})`,
        }} />
        <Typography variant="body2" sx={{ fontWeight: 600 }}>{year}</Typography>
      </Stack>;
    })}
  </Stack>;
}

export function TaskChart({ chart, kind = "bar" }: { chart: WritingChart; kind?: WritingVisualKind }) {
  const theme = useTheme();
  const colors = useMemo(() => [theme.palette.writing.main, theme.palette.reading.main, theme.palette.listening.main,
    theme.palette.primary.main, theme.palette.mode === "dark" ? "#f4a3b9" : "#a13763"], [theme]);
  const rows = [["Group", ...chart.years],
    ...chart.series.map(series => [series.label, ...series.values.map(value => formatValue(chart, value))])];
  return <Card component="figure" variant="outlined" sx={{ m: 0, width: "100%", maxWidth: 680 }}>
    <CardContent>
      <Typography component="figcaption" variant="subtitle1" sx={{ fontWeight: 600 }}>{chart.title}</Typography>
      {chart.synthetic && <Typography variant="caption" color="text.secondary">Illustrative practice data</Typography>}
      <Stack spacing={1.5} sx={{ mt: 2 }}>
        {kind === "pie" ? <PieCharts chart={chart} colors={colors} /> :
          <SeriesGraph chart={chart} colors={colors} groupedBars={kind !== "line"} />}
        <WritingDataTable rows={rows} colors={colors} />
      </Stack>
    </CardContent>
  </Card>;
}

export function WritingProcess({ title, stages }: { title: string; stages: string[] }) {
  return <Card component="figure" variant="outlined" sx={{ m: 0, width: "100%", maxWidth: 680 }}>
    <CardContent>
      <Typography component="figcaption" variant="subtitle1" sx={{ fontWeight: 600 }}>{title}</Typography>
      <Stack component="ol" spacing={1} sx={{ my: 1.5, pl: 3, "& li::marker": { color: "writing.main", fontWeight: 700 } }}>
        {stages.map((stage, index) => <Box component="li" key={stage} sx={{ pl: 0.75 }}>
          <Box sx={{ p: 1, bgcolor: "writing.light", borderRadius: 1 }}>{stage}</Box>
          {index < stages.length - 1 && <Typography aria-hidden="true" sx={{ textAlign: "center", color: "writing.main" }}>↓</Typography>}
        </Box>)}
      </Stack>
    </CardContent>
  </Card>;
}
