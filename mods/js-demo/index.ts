import { serveFile } from "jsr:@std/http@^1.0.17/file-server";
import { join } from "jsr:@std/path@^1.1.0";
import { Pty } from "jsr:@sigma/pty-ffi";

const PORT = parseInt(Deno.env.get("PORT") ?? "8000");

// Store active Claude Code sessions
const claudeSessions = new Map<string, {
  pty: Pty;
  websocket: WebSocket;
  workingDirectory: string;
}>();

// Get Wandb configuration from environment
const wandbProject = Deno.env.get("WANDB_PROJECT");
const wandbEntity = Deno.env.get("WANDB_ENTITY");
const wandbApiKey = Deno.env.get("WANDB_API_KEY");

if (!wandbProject || !wandbEntity || !wandbApiKey) {
  console.warn("⚠️ Wandb configuration incomplete. OTEL metrics will not be exported.");
  console.warn("Required env vars: WANDB_PROJECT, WANDB_ENTITY, WANDB_API_KEY");
}

function generateSessionId(): string {
  return crypto.randomUUID();
}

// Spawn Claude Code CLI process using PTY for proper interactive terminal
async function spawnClaudeProcess(workingDirectory: string, cols: number = 120, rows: number = 30) {
  const claudeCliPath = join("..", "node_modules", "@anthropic-ai", "claude-code", "cli.js");

  // Configure OTEL environment for Claude process
  let otelEnv: Record<string, string> = {
    // Enable telemetry
    CLAUDE_CODE_ENABLE_TELEMETRY: "1",
    SENTRY_DEBUG: "1",
    OTEL_LOG_USER_PROMPTS: "1",

    // Configure OTLP exporter
    OTEL_METRICS_EXPORTER: "otlp",
    OTEL_LOGS_EXPORTER: "console",
    OTEL_EXPORTER_OTLP_PROTOCOL: "http/protobuf",
    OTEL_EXPORTER_OTLP_ENDPOINT: "https://trace.wandb.ai/v1/traces",

    // Configure export intervals
    OTEL_METRIC_EXPORT_INTERVAL: "10000", // 60 seconds
    OTEL_LOGS_EXPORT_INTERVAL: "5000",    // 5 seconds

    // Include all metric attributes
    OTEL_METRICS_INCLUDE_SESSION_ID: "true",
    OTEL_METRICS_INCLUDE_VERSION: "true",
    OTEL_METRICS_INCLUDE_ACCOUNT_UUID: "true"
  };

  // Add auth headers only if Wandb config is available
  if (wandbApiKey && wandbProject && wandbEntity) {
    otelEnv.OTEL_EXPORTER_OTLP_HEADERS = `authorization=Basic ${btoa(wandbApiKey)},project_id=${wandbEntity}/${wandbProject}`;
  } else {
    otelEnv = {};
  }

  // Build the command to run the CLI
  const cmd = [
    "deno",
    "run",
    "--allow-all",
    claudeCliPath
  ];

  // Create the PTY
  const pty = new Pty(cmd[0], {
    args: cmd.slice(1),
    cwd: workingDirectory,
    env: {
      ...Deno.env.toObject(),
      ...otelEnv,
      TERM: "xterm-256color",
      COLUMNS: cols.toString(),
      LINES: rows.toString(),
      FORCE_COLOR: "1"
    },
  });
  console.log("🔧 Spawned Claude Code process with PTY in", workingDirectory);
  if (wandbApiKey) {
    console.log("📊 OTEL metrics will be exported to Wandb Weave");
  }
  return { pty, workingDirectory };
}

async function handleWebSocket(request: Request): Promise<Response> {
  const { socket, response } = Deno.upgradeWebSocket(request);
  const sessionId = generateSessionId();
  socket.addEventListener("open", async () => {
    console.log(`🔌 WebSocket opened for session: ${sessionId}`);
  });
  socket.addEventListener("message", async (event) => {
    try {
      const message = JSON.parse(event.data);
      let session = claudeSessions.get(sessionId);
      if (message.type === "resize") {
        const { cols, rows } = message;
        console.log(`📏 Terminal resize requested: ${cols}x${rows}`);
        if (!session) {
          // Start Claude Code process with PTY
          try {
            const workingDirectory = join(".", "vibez");
            const { pty } = await spawnClaudeProcess(workingDirectory, cols, rows);
            session = {
              pty,
              websocket: socket,
              workingDirectory
            };
            claudeSessions.set(sessionId, session);
            console.log("🚀 Started Claude Code process with PTY");
            // Set up output handlers
            setupPtyStreams(pty, socket, sessionId);
            // Send welcome message
            socket.send(JSON.stringify({
              type: "output",
              data: "\x1b[32m✓ Connected to Claude Code (Interactive PTY Mode)\x1b[0m\r\n"
            }));
          } catch (err) {
            console.error("❌ Error starting Claude Code process:", err);
            socket.send(JSON.stringify({
              type: "error",
              data: `\x1b[31mError starting Claude Code: ${(err as Error).message}\x1b[0m\r\n`
            }));
          }
        } else {
          // Resize PTY
          try {
            session.pty.resize({cols, rows});
            console.log(`📏 Terminal resized to ${cols}x${rows} for existing session`);
          } catch (err) {
            console.error("Error handling resize:", err);
          }
        }
        return;
      }
      if (message.type === "input") {
        if (!session) {
          console.error("No session found for input, sessionId:", sessionId);
          return;
        }
        const input = message.data;
        try {
          // Write input to PTY
          await session.pty.write(input);
        } catch (err) {
          console.error("Error writing to Claude Code PTY:", err);
          socket.send(JSON.stringify({
            type: "error",
            data: `\x1b[31mError sending input: ${(err as Error).message}\x1b[0m\r\n`
          }));
        }
      }
    } catch (err) {
      console.error("❌ Error handling WebSocket message:", err);
    }
  });
  socket.addEventListener("close", () => {
    console.log(`🔌 WebSocket closed for session: ${sessionId}`);
    const session = claudeSessions.get(sessionId);
    if (session) {
      try {
        session.pty.close();
      } catch (err) {
        console.error("Error cleaning up Claude Code PTY:", err);
      }
      claudeSessions.delete(sessionId);
    }
  });
  return response;
}

// Setup PTY output streaming to WebSocket
function setupPtyStreams(pty: Pty, socket: WebSocket, sessionId: string) {
  const decoder = new TextDecoder("utf-8", { fatal: false });
  (async () => {
    try {
      for await (const chunk of pty.readable) {
        if (socket.readyState === WebSocket.OPEN) {
          const text = typeof chunk === "string"
            ? chunk
            : decoder.decode(chunk);
          socket.send(JSON.stringify({
            type: "output",
            data: text
          }));
        }
      }
    } catch (err) {
      console.error("Error reading Claude Code PTY output:", err);
    }
    // PTY closed
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        type: "exit",
        code: 0,
        data: `\r\n\x1b[33mClaude Code session ended (PTY closed)\x1b[0m\r\n`
      }));
    }
    claudeSessions.delete(sessionId);
  })();
}

// Function to create tar.gz of directory
async function createTarGz(sourceDir: string): Promise<Uint8Array> {
  try {
    // Create a temporary file for the tar.gz
    const tempFile = await Deno.makeTempFile({ suffix: ".tar.gz" });

    // Use tar command to create the archive
    const tarCommand = new Deno.Command("tar", {
      args: [
        "-czf", tempFile,
        "-C", sourceDir,
        "--exclude=node_modules",
        "--exclude=.git",
        "--exclude=*.log",
        "--exclude=.DS_Store",
        "--exclude=dist",
        "--exclude=build",
        "."
      ],
      stdout: "piped",
      stderr: "piped"
    });

    const tarProcess = tarCommand.spawn();
    const { code } = await tarProcess.status;

    if (code !== 0) {
      throw new Error(`tar command failed with code ${code}`);
    }

    // Read the tar.gz file
    const archiveData = await Deno.readFile(tempFile);

    // Clean up temp file
    await Deno.remove(tempFile);

    return archiveData;
  } catch (error) {
    console.error("Error creating tar.gz:", error);
    throw error;
  }
}

// Function to get the working directory from any active session
function getWorkingDirectory(): string {
  for (const session of claudeSessions.values()) {
    if (session.workingDirectory) {
      return session.workingDirectory;
    }
  }
  // Fallback to the vibez directory
  return join(".", "vibez");
}

async function handleDownload(request: Request): Promise<Response> {
  try {
    console.log("📦 Creating project archive...");

    const workingDir = getWorkingDirectory();
    const archiveData = await createTarGz(workingDir);

    // Generate filename based on directory name and timestamp
    const dirName = workingDir.split("/").pop() || "project";
    const timestamp = new Date().toISOString().slice(0, 16).replace(/:/g, "-");
    const filename = `${dirName}-${timestamp}.tar.gz`;

    console.log(`📦 Archive created: ${filename} (${archiveData.length} bytes)`);

    return new Response(archiveData, {
      headers: {
        "Content-Type": "application/gzip",
        "Content-Disposition": `attachment; filename="${filename}"`,
        "Content-Length": archiveData.length.toString(),
      },
    });
  } catch (error) {
    console.error("❌ Error creating archive:", error);
    return new Response(
      JSON.stringify({ error: "Failed to create archive: " + (error as Error).message }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}

console.log(`✅ Server listening on http://localhost:${PORT}`);

// Run 'claude config set -g theme dark' at server startup using the node_modules entrypoint
(async () => {
  try {
    const claudeCliPath = join(".", "node_modules", "@anthropic-ai", "claude-code", "cli.js");
    const cmd = new Deno.Command("deno", {
      args: [
        "run",
        "--allow-all",
        claudeCliPath,
        "config",
        "set",
        "-g",
        "theme",
        "dark"
      ],
      stdout: "piped",
      stderr: "piped"
    });
    const proc = cmd.spawn();
    const { code, stdout, stderr } = await proc.output();
    const outStr = new TextDecoder().decode(stdout);
    const errStr = new TextDecoder().decode(stderr);
    if (code === 0) {
      console.log("[claude config]", outStr.trim());
    } else {
      console.error("[claude config error]", errStr.trim());
    }
  } catch (err) {
    console.error("[claude config exception]", err);
  }
})();

Deno.serve({ port: PORT }, async (req: Request) => {
  const url = new URL(req.url);
  const pathname = url.pathname;
  console.log(`📥 ${req.method} ${pathname}`);

  try {
    // Handle WebSocket upgrade for terminal
    if (pathname === "/ws" && req.headers.get("upgrade") === "websocket") {
      return handleWebSocket(req);
    }

    // Handle download requests
    if (pathname === "/download" && req.method === "GET") {
      return handleDownload(req);
    }

    // Serve static files
    const targetPath = pathname === "/" ? "/index.html" : pathname;
    const filePath = join(".", targetPath);

    return await serveFile(req, filePath);

  } catch (err) {
    console.error("❌ Error handling request:", err);
    return new Response("File not found", { status: 404 });
  }
});
