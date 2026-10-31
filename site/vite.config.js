import { resolve } from "node:path";
import { execSync } from "node:child_process";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

/** Hash do git disponível no build; Netlify e Vercel expõem por variável. */
function git(comando, alternativa) {
  try {
    return execSync(comando, { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
  } catch {
    return alternativa;
  }
}

const commit =
  process.env.COMMIT_REF?.slice(0, 7) ||
  process.env.VERCEL_GIT_COMMIT_SHA?.slice(0, 7) ||
  git("git rev-parse --short HEAD", "local");

const inicial =
  git("git rev-list --max-parents=0 --abbrev-commit HEAD", "local");

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, "index.html"),
        inmet: resolve(import.meta.dirname, "inmet.html"),
        inmettodas: resolve(import.meta.dirname, "inmettodas.html"),
      },
    },
  },
  // Metadados do rodapé: commit atual, commit raiz e data do build.
  define: {
    __COMMIT__: JSON.stringify(commit),
    __COMMIT_INICIAL__: JSON.stringify(inicial),
    __BUILD__: JSON.stringify(new Date().toISOString().slice(0, 16).replace("T", " ")),
  },
});
