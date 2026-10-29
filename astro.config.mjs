// @ts-check
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  // Public address of the landing; used for absolute URLs (canonical, Open Graph)
  site: "https://завяжи-узелок.рф",
  output: "static",
  // The dev toolbar injects client JS into the page; the landing must work without JS
  devToolbar: { enabled: false },
  vite: {
    plugins: [tailwindcss()],
  },
});
