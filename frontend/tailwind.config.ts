import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      maxWidth: {
        reader: "640px",
        app: "960px",
      },
    },
  },
  plugins: [],
} satisfies Config;
