import { useEffect, useMemo, useRef } from "react";
import { Box, Card, CardContent, Stack, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { ArcElement, BarController, BarElement, CategoryScale, Chart, LineController, LineElement,
  LinearScale, PieController, PointElement, Tooltip } from "chart.js";

Chart.register(BarController, LineController, PieController, BarElement, LineElement, PointElement,
  ArcElement, CategoryScale, LinearScale, Tooltip);

export type WritingChart = {
  title: string;
  years: string[];
  series: { label: string; values: number[] }[];
  synthetic?: boolean;
  unit?: "%" | "count";
};

export type WritingVisualKind = "bar" | "line" | "pie" | "table" | "bar_table" | "bar_line" | "process";

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

function NumericChart({ chart, colors, kind, column }: {
  chart: WritingChart; colors: string[]; kind: "bar" | "line" | "pie"; column?: number;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const theme = useTheme();

  useEffect(() => {
    const node = canvas.current;
    if (!node) return;
    const { divider, text, background } = theme.palette;
    const isPie = kind === "pie";
    const datasets = isPie ? [{
      label: column === undefined ? chart.title : chart.years[column],
      data: chart.series.map(series => series.values[column ?? 0]),
      backgroundColor: colors,
      borderColor: background.paper,
      borderWidth: 1.5,
    }] : chart.series.map((series, index) => ({
      label: series.label,
      data: series.values,
      backgroundColor: colors[index],
      borderColor: colors[index],
      borderDash: [[], [6, 3], [2, 3], [8, 3, 2, 3]][index] ?? [],
      borderWidth: 2,
      tension: 0,
    }));
    const instance = new Chart(node, {
      type: kind,
      data: { labels: isPie ? chart.series.map(series => series.label) : chart.years, datasets },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        color: text.primary,
        scales: isPie ? undefined : {
          x: { grid: { color: divider }, ticks: { color: text.secondary } },
          y: {
            beginAtZero: true, max: chartMaximum(chart),
            grid: { color: divider },
            title: { display: true, text: chart.unit === "count" ? "Count" : "Percentage", color: text.secondary },
            ticks: { color: text.secondary, callback: value => chart.unit === "count"
              ? Number(value).toLocaleString(undefined, { notation: "compact" }) : formatValue(chart, Number(value)) },
          },
        },
        plugins: {
          tooltip: {
            callbacks: {
              label: context => {
                const label = isPie ? context.label : context.dataset.label;
                return (label ? label + ": " : "") + formatValue(chart, Number(context.raw));
              },
            },
          },
        },
      },
    });
    return () => instance.destroy();
  }, [chart, colors, kind, column, theme]);

  return <Box sx={{ position: "relative", width: kind === "pie" ? { xs: 144, sm: 166 } : "100%",
    height: kind === "pie" ? { xs: 144, sm: 166 } : 240, minWidth: 0 }}>
    <canvas ref={canvas} aria-hidden="true" />
  </Box>;
}

function PieCharts({ chart, colors }: { chart: WritingChart; colors: string[] }) {
  return <Stack direction="row" useFlexGap spacing={3} sx={{ flexWrap: "wrap", justifyContent: "center" }}>
    {chart.years.map((year, index) => <Stack spacing={1} key={year} sx={{ alignItems: "center" }}>
      <NumericChart chart={chart} colors={colors} kind="pie" column={index} />
      <Typography variant="body2" sx={{ fontWeight: 600 }}>{year}</Typography>
    </Stack>)}
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
          <NumericChart chart={chart} colors={colors} kind={kind === "line" ? "line" : "bar"} />}
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
