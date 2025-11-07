// Example custom server handler for deno_server.ts
// This file demonstrates how to create a custom handler that integrates with the wrapper

export default async function handler(req: Request): Promise<Response | null> {
  const url = new URL(req.url);
  const pathname = url.pathname;

  // Handle API routes
  if (pathname.startsWith("/api/")) {
    return handleApiRoute(req, pathname);
  }

  // Handle custom routes
  if (pathname === "/hello") {
    return new Response("Hello from custom handler!", {
      headers: { "Content-Type": "text/plain" },
    });
  }

  if (pathname === "/info") {
    return Response.json({
      message: "Custom Deno server handler",
      timestamp: new Date().toISOString(),
      url: req.url,
      method: req.method,
    });
  }

  // Return null to let the wrapper handle static files
  return null;
}

async function handleApiRoute(req: Request, pathname: string): Promise<Response> {
  // Remove /api prefix
  const route = pathname.replace("/api", "");

  switch (route) {
    case "/status":
      return Response.json({ status: "ok", server: "custom-handler" });

    case "/echo":
      if (req.method === "POST") {
        try {
          const body = await req.json();
          return Response.json({ echo: body });
        } catch {
          return Response.json({ error: "Invalid JSON" }, { status: 400 });
        }
      }
      return Response.json({ error: "Method not allowed" }, { status: 405 });

    case "/headers":
      const headers: Record<string, string> = {};
      req.headers.forEach((value, key) => {
        headers[key] = value;
      });
      return Response.json({ headers });

    default:
      return Response.json({ error: "API route not found" }, { status: 404 });
  }
}

// Alternative export patterns (you can use any of these):
// export { handler }; // if you prefer named export
// export const handle = handler; // if you prefer 'handle' name
