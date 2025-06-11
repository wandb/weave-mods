import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { serveDir } from "https://deno.land/std@0.224.0/http/file_server.ts";

const PORT = parseInt(Deno.env.get("PORT") ?? "6637");
const HEALTH_PORT = parseInt(Deno.env.get("HEALTHCHECK_PORT") ?? "6638");
const API_KEY = Deno.env.get("WANDB_API_KEY") ?? "";
const WEAVE_HOST = "https://weave.wandb.ai";

serve((_) => new Response("healthy"), { port: HEALTH_PORT });

serve(async (req: Request) => {
  const url = new URL(req.url);
  if (url.pathname.startsWith("/__weave")) {
    const proxyUrl = `${WEAVE_HOST}${url.pathname}${url.search}`;
    const headers = new Headers(req.headers);
    headers.set("Authorization", "Basic " + btoa(`api:${API_KEY}`));
    return fetch(proxyUrl, { method: req.method, headers, body: req.body });
  }

  return serveDir(req, { fsRoot: "./dist", quiet: true });
}, { port: PORT });
