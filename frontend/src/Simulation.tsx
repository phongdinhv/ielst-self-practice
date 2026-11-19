import { Box, Button, Card, CardContent, Stack, Typography } from "@mui/material";
import { alpha } from "@mui/material/styles";
import { skillLabels, skills, type Skill } from "./theme";

const sections: Record<Skill, string> = {
  listening: "Video practice",
  reading: "60-minute mock",
  writing: "60-minute test",
};

export function Simulation({ preview = false }: { preview?: boolean }) {
  return (
    <Card variant="outlined" sx={{ bgcolor: "primary.main", color: "primary.contrastText" }}>
      <CardContent sx={{ p: { xs: 2.5, sm: 3 } }}>
        <Stack spacing={2.5}>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}
            sx={{ alignItems: { sm: "center" }, justifyContent: "space-between" }}>
            <Box>
              {preview && <Typography variant="h5" component="h2" sx={{ fontWeight: 650 }}>
                Three-skill simulation
              </Typography>}
              <Typography variant="body2" sx={theme => ({ color: alpha(theme.palette.primary.contrastText, 0.87), mt: preview ? 0.5 : 0 })}>
                {preview ? "Practice all three skills in one sitting." : "Complete Listening, Reading, and Writing in order. Each section has its own timer."}
              </Typography>
            </Box>
            {preview && <Button variant="contained" href="/simulation" sx={theme => ({
              alignSelf: { xs: "flex-start", sm: "center" }, flexShrink: 0,
              bgcolor: "primary.contrastText", color: "primary.main",
              "&:hover": { bgcolor: alpha(theme.palette.primary.contrastText, 0.9) },
            })}>View simulation</Button>}
          </Stack>
          <Box component="ol" aria-label="Simulation sections" sx={{
            display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, minmax(0, 1fr))" },
            gap: 1.25, listStyle: "none", p: 0, m: 0,
          }}>
            {skills.map(skill => <Box component="li" key={skill} sx={{
              p: 1.5, borderRadius: 1, bgcolor: `${skill}.light`, color: `${skill}.dark`,
              borderLeft: "4px solid", borderLeftColor: `${skill}.main`,
            }}>
              <Typography component={preview ? "p" : "h2"} variant="body1" sx={{ fontWeight: 650 }}>
                {skillLabels[skill]}
              </Typography>
              <Typography variant="body2">{sections[skill]}</Typography>
            </Box>)}
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}
