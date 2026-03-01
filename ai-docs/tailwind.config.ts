import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {},
  },
  plugins: [typography],
};

export default config;
