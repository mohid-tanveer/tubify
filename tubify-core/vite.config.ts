import { defineConfig } from "vite"
import react from "@vitejs/plugin-react-swc"
import tailwindcss from "@tailwindcss/vite"
import fs from "fs"
import path from "path"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    https: {
      key: fs.readFileSync("./src/ssl/localhost-key.pem"),
      cert: fs.readFileSync("./src/ssl/localhost.pem"),
    },
    host: "localhost",
    port: 3000,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
