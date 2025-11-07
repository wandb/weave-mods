import { serveFile } from "jsr:@std/http@^1.0.17/file-server";
import { join } from "jsr:@std/path@^1.1.0";
import { exists } from "jsr:@std/fs@^1.0.0";

// Global error handlers
addEventListener("unhandledrejection", (event) => {
  console.error("🔥 Unhandled rejection:", event.reason);
});

addEventListener("error", (event) => {
  console.error("🔥 Uncaught error:", event.error);
});

const PORT = parseInt(Deno.env.get("PORT") ?? "6637");
const HEALTH_PORT = parseInt(Deno.env.get("HEALTHCHECK_PORT") ?? "6638");
const API_KEY = Deno.env.get("WANDB_API_KEY") ?? "";
const WEAVE_HOST = "https://weave.wandb.ai";

// Dynamic server handler
let customHandler: ((req: Request) => Response | Promise<Response>) | null = null;

// Helper to read staticDir from package.json
function getStaticDir(): string {
  try {
    const pkgRaw = Deno.readFileSync("./package.json");
    const pkg = JSON.parse(new TextDecoder().decode(pkgRaw));
    return pkg?.weave?.mod?.staticDir || "static";
  } catch (e) {
    return "static";
  }
}

const STATIC_DIR = getStaticDir();

// Check if index.ts or index.js exists and load it
async function loadCustomHandler() {
  try {
    let entry = null;
    if (await exists("./index.ts")) {
      entry = "./index.ts";
    } else if (await exists("./index.js")) {
      entry = "./index.js";
    }
    if (entry) {
      console.log(`📦 Found ${entry}, loading custom handler...`);
      // Store the original Deno.serve function
      const originalServe = Deno.serve;
      let capturedHandler: ((req: Request) => Response | Promise<Response>) | null = null;
      // Override Deno.serve to capture the handler
      Deno.serve = ((options: any, handler?: any) => {
        let actualHandler: ((req: Request) => Response | Promise<Response>) | null = null;
        if (typeof options === 'function') {
          actualHandler = options;
        } else if (typeof handler === 'function') {
          actualHandler = handler;
        } else if (options && typeof options.fetch === 'function') {
          actualHandler = options.fetch;
        }
        if (actualHandler) {
          capturedHandler = actualHandler;
          console.log("🎯 Captured handler from Deno.serve call");
        } else {
          console.warn("⚠️  Deno.serve called but no handler function found");
        }
        return {
          finished: Promise.resolve(),
          shutdown: () => Promise.resolve(),
          ref: () => {},
          unref: () => {},
        } as any;
      }) as any;
      try {
        // Import the module (this will execute the code and trigger our overridden Deno.serve)
        const modulePath = `${Deno.cwd()}/${entry}`;
        await import(modulePath);
        // Check if we captured a handler
        if (capturedHandler) {
          customHandler = capturedHandler;
          console.log("✅ Successfully captured handler from Deno.serve call");
        } else {
          // Fallback to checking for exported functions
          console.log("🔄 No handler captured, trying export patterns...");
          const module = await import(modulePath);
          if (typeof module.default === "function") {
            customHandler = module.default;
            console.log(`✅ Loaded default export from ${entry}`);
          } else if (typeof module.handler === "function") {
            customHandler = module.handler;
            console.log(`✅ Loaded handler export from ${entry}`);
          } else if (typeof module.handle === "function") {
            customHandler = module.handle;
            console.log(`✅ Loaded handle export from ${entry}`);
          } else {
            console.log(`⚠️  No compatible handler found in ${entry}`);
          }
        }
      } finally {
        // Always restore the original Deno.serve function
        Deno.serve = originalServe;
      }
    } else {
      console.log("ℹ️  No index.ts or index.js found, using static file serving only");
    }
  } catch (error) {
    console.error("❌ Error loading entry file:", error);
  }
}

await loadCustomHandler();

// Healthcheck server
Deno.serve({ port: HEALTH_PORT }, () => new Response("healthy"));

console.log(`✅ Healthcheck listening on http://localhost:${HEALTH_PORT}`);
console.log(`✅ Main server listening on http://localhost:${PORT}`);

Deno.serve({ port: PORT }, async (req: Request) => {
  const url = new URL(req.url);
  const pathname = url.pathname;
  console.log(`📥 Incoming request: ${req.method} ${pathname}`);

  try {
    // Handle Weave proxy requests
    if (pathname.startsWith("/__weave")) {
      const proxyUrl = `${WEAVE_HOST}${url.pathname}${url.search}`;
      const headers = new Headers(req.headers);
      headers.set("Authorization", "Basic " + btoa(`api:${API_KEY}`));
      console.log(`🔁 Proxying to: ${proxyUrl}`);
      return await fetch(proxyUrl, {
        method: req.method,
        headers,
        body: req.body,
      });
    }

    // Try custom handler first if available
    if (customHandler) {
      try {
        console.log(`🎯 Trying custom handler for: ${pathname}`);
        const response = await customHandler(req);
        if (response) {
          console.log(`✅ Custom handler responded for: ${pathname}`);
          return response;
        }
      } catch (error) {
        console.warn(`⚠️  Custom handler failed for ${pathname}:`, error);
        // Fall through to static file serving
      }
    }

    // Static file resolution (fallback)
    const fsRoot = `./${STATIC_DIR}`;
    const targetPath = pathname === "/" ? "/index.html" : pathname;
    const filePath = join(fsRoot, targetPath);

    console.log(`📄 Attempting to serve static file: ${filePath} (cwd: ${Deno.cwd()})`);
    return await serveFile(req, filePath);

  } catch (err) {
    console.error("❌ Error handling request:", err);
    return new Response("Internal Server Error", { status: 500 });
  }
});
