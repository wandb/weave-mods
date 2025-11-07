# Weave UI Library

A React library for accessing W&B Weave data with caching and hooks.

## Setup

Before using any Weave functions or hooks, you must configure the API client with your API key:

```typescript
import { configureWeaveApi } from "./weaveuilib/apiUtils";

// Configure the API client at the start of your application
configureWeaveApi({
  apiKey: "your-wandb-api-key-here", // Get this from your W&B settings
  baseUrl: "https://trace.wandb.ai", // Optional, defaults to this
});
```

### Safe API Key Handling for Web Apps

For web applications, **never hard-code API keys**. Here are recommended approaches:

#### Option 1: Environment Variables (Build-time)

```typescript
// For build-time configuration (most common)
configureWeaveApi({
  apiKey: process.env.REACT_APP_WANDB_API_KEY!,
});
```

#### Option 2: Runtime Configuration

```typescript
// For runtime configuration (user provides key)
function ApiKeySetup() {
  const [apiKey, setApiKey] = useState("");

  const handleSetup = () => {
    configureWeaveApi({ apiKey });
  };

  return (
    <div>
      <input
        type="password"
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        placeholder="Enter your W&B API key"
      />
      <button onClick={handleSetup}>Configure API</button>
    </div>
  );
}
```

#### Option 3: Server Proxy (Most Secure)

For production web applications, consider using a server proxy that handles the API key server-side:

```typescript
// Your API calls go through your server instead of directly to W&B
configureWeaveApi({
  apiKey: "not-needed-when-using-proxy",
  baseUrl: "https://your-server.com/api/weave-proxy",
});
```

## Usage

### Basic Hook Usage

```typescript
import { useWeaveCalls } from "./weaveuilib/weaveData";

function MyComponent() {
  const { loading, result } = useWeaveCalls({
    projectId: "your-project-id",
    filter: {
      op_names: ["your-operation-name"],
    },
  });

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      {result.map((call) => (
        <div key={call.id}>{call.op_name}</div>
      ))}
    </div>
  );
}
```

### Working with Operation Names

**Important:** The `op_name` field in call results contains full Weave references (e.g., `weave:///entity/project/op/function_name:v1`), not just the operation name. To extract the actual operation name or filter by operation regardless of version, use `parseWeaveRef`:

```typescript
import { useWeaveCalls } from "./weaveuilib/weaveData";
import { parseWeaveRef } from "./weaveuilib/parseRef";

function OperationFilter() {
  const { loading, result: calls } = useWeaveCalls({
    projectId: "your-project-id",
    filter: { trace_roots_only: true }
  });

  // Extract unique operation names from weave refs
  const uniqueOpNames = useMemo(() => {
    const opNames = new Set<string>();
    calls.forEach(call => {
      if (call.op_name) {
        try {
          const parsed = parseWeaveRef(call.op_name);
          if (parsed.artifactName) {
            opNames.add(parsed.artifactName);
          }
        } catch {
          opNames.add(call.op_name); // Fallback for non-ref names
        }
      }
    });
    return Array.from(opNames).sort();
  }, [calls]);

  // Filter calls by operation name (all versions)
  const filterByOpName = (targetOpName: string) => {
    return calls.filter(call => {
      if (!call.op_name) return false;
      try {
        const parsed = parseWeaveRef(call.op_name);
        return parsed.artifactName === targetOpName;
      } catch {
        return call.op_name === targetOpName;
      }
    });
  };

  // ... rest of component
}
```

### Multiple Queries

```typescript
import { useWeaveCallsMultiple } from "./weaveuilib/weaveData";

function MultipleQueriesComponent() {
  const { loading, results } = useWeaveCallsMultiple([
    { projectId: "project1", filter: { op_names: ["op1"] } },
    { projectId: "project2", filter: { op_names: ["op2"] } },
  ]);

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      {results.map((result, index) => (
        <div key={index}>
          Query {index + 1}: {result.length} calls
        </div>
      ))}
    </div>
  );
}
```

### Cache Management

```typescript
import { useClearWeaveCache } from "./weaveuilib/weaveData";

function CacheManagement() {
  const clearCache = useClearWeaveCache();

  return <button onClick={clearCache}>Clear Cache</button>;
}
```

## Features

- **Automatic Caching**: All API calls are cached in IndexedDB for better performance
- **React Hooks**: Easy-to-use hooks for data fetching
- **TypeScript Support**: Full type safety
- **Parallel Queries**: Support for multiple concurrent queries
- **Deep Memoization**: Efficient re-rendering only when data actually changes

## Installation Requirements

Make sure to install the required peer dependencies:

```bash
npm install react @types/react
```

## Important Notes

### CORS Configuration

**Web applications using this library must run on `localhost:3000`** due to CORS policies configured on the Weave API server. If you're using Vite, configure your development server to use port 3000:

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
  },
})
```

For other development servers, ensure they're configured to run on port 3000 to avoid CORS issues.
