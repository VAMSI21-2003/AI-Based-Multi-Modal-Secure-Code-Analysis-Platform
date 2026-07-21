import { defineConfig } from "vitest/config";

// Kept separate from vite.config.ts deliberately: this project's Vite
// version bundles a newer (rolldown-based) plugin API that conflicts with
// vitest's own nested Vite dependency's plugin types when merged into one
// config object. jsdom is needed (not just "node") now that component smoke
// tests render real React components; no app plugins are needed for that,
// so keeping this file standalone still avoids the conflict entirely.
export default defineConfig({
  // Plain esbuild transform options (not a Vite plugin object), so this
  // does not reintroduce the vite/vitest plugin-type conflict noted above --
  // needed because .tsx test files render JSX and this standalone config
  // has no react plugin to configure the automatic runtime otherwise.
  esbuild: {
    jsx: "automatic",
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    setupFiles: ["./vitest.setup.ts"],
    // Required for @testing-library/react's automatic afterEach(cleanup) to
    // register -- without it, a component rendered in one test stays
    // attached to the DOM for the next test (caught by a real test failure:
    // the Dashboard's error-state test saw the PREVIOUS test's "42" leaking
    // through, not a bug in Dashboard.tsx itself).
    globals: true,
  },
});
