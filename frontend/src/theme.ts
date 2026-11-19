import { createTheme } from "@mui/material/styles";

export const skills = ["listening", "reading", "writing"] as const;
export type Skill = typeof skills[number];

export const skillLabels: Record<Skill, string> = {
  listening: "Listening",
  reading: "Reading",
  writing: "Writing",
};

declare module "@mui/material/styles" {
  interface Palette {
    listening: Palette["primary"];
    reading: Palette["primary"];
    writing: Palette["primary"];
  }
  interface PaletteOptions {
    listening?: PaletteOptions["primary"];
    reading?: PaletteOptions["primary"];
    writing?: PaletteOptions["primary"];
  }
}

interface SkillColorOverrides extends Record<Skill, true> {}

declare module "@mui/material/Button" {
  interface ButtonPropsColorOverrides extends SkillColorOverrides {}
}
declare module "@mui/material/Chip" {
  interface ChipPropsColorOverrides extends SkillColorOverrides {}
}
declare module "@mui/material/LinearProgress" {
  interface LinearProgressPropsColorOverrides extends SkillColorOverrides {}
}

export const theme = createTheme({
  palette: {
    primary: { main: "#29354b" },
    background: { default: "#f5f5f4" },
    contrastThreshold: 4.5,
    listening: { main: "#85490b", light: "#fff1dd", dark: "#643506", contrastText: "#ffffff" },
    reading: { main: "#08645d", light: "#e6f6f2", dark: "#064a45", contrastText: "#ffffff" },
    writing: { main: "#6941a5", light: "#f3ebff", dark: "#502e81", contrastText: "#ffffff" },
  },
  shape: { borderRadius: 12 },
});

export const darkTheme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#bbcbf3", contrastText: "#141b2c" },
    background: { default: "#10141d", paper: "#1a202c" },
    contrastThreshold: 4.5,
    listening: { main: "#f4bb76", light: "#332719", dark: "#f7d5a7", contrastText: "#241707" },
    reading: { main: "#81d7ca", light: "#193330", dark: "#b2ede4", contrastText: "#0e2824" },
    writing: { main: "#cbb1f8", light: "#302440", dark: "#e2d0ff", contrastText: "#241733" },
  },
  shape: { borderRadius: 12 },
});
