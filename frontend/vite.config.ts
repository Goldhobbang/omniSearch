import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// 기본 빌드: Flask 패키지의 static/ 으로 나가고 /static/ 아래에서 서빙된다.
// 파일명에 해시를 붙이지 않아 재빌드해도 커밋 diff가 파일 단위로만 바뀐다.
// demo 빌드(--mode demo): GitHub Pages(/omniSearch/)용. 서버 없이 브라우저에서 검색한다.
// dev 서버(npm run dev)는 /api 를 로컬 Flask(omnisearch-web)로 넘긴다.
export default defineConfig(({ command, mode }) => {
  const demo = mode === "demo"
  return {
    base: demo ? "/omniSearch/" : command === "build" ? "/static/" : "/",
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": resolve(import.meta.dirname, "./src"),
      },
    },
    server: {
      proxy: { "/api": "http://127.0.0.1:5000" },
    },
    build: {
      outDir: demo ? "dist" : "../src/omnisearch/static",
      emptyOutDir: true,
      rollupOptions: {
        output: {
          entryFileNames: "assets/app.js",
          chunkFileNames: "assets/[name].js",
          assetFileNames: "assets/[name][extname]",
        },
      },
    },
  }
})
