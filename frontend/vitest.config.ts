import { defineConfig } from "vitest/config";

// Kept separate from vite.config.ts deliberately: this project's Vite
// version bundles a newer (rolldown-based) plugin API that conflicts with
// vitest's own nested Vite dependency's plugin types when merged into one
// config object. Since the current test suite is pure TS logic (no
// component rendering), this file doesn't need the app's plugins at all,
// so keeping it standalone avoids the conflict entirely rather than
// working around it.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
