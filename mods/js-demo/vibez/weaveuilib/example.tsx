import React, { useState } from "react";
import { configureWeaveApi } from "./apiUtils";
import { useClearWeaveCache, useWeaveCalls } from "./weaveData";

// Example component showing API key configuration
export function WeaveApiSetup() {
  const [isConfigured, setIsConfigured] = useState(false);
  const [apiKey, setApiKey] = useState("");

  const handleConfigure = () => {
    if (!apiKey.trim()) {
      alert("Please enter an API key");
      return;
    }

    try {
      configureWeaveApi({
        apiKey: apiKey.trim(),
        baseUrl: "https://trace.wandb.ai", // Optional
      });
      setIsConfigured(true);
      console.log("Weave API configured successfully!");
    } catch (error) {
      console.error("Failed to configure Weave API:", error);
      alert("Failed to configure API. Check console for details.");
    }
  };

  if (!isConfigured) {
    return (
      <div style={{ padding: "20px", maxWidth: "400px" }}>
        <h2>Configure Weave API</h2>
        <p>Enter your W&B API key to start using Weave data.</p>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="Enter your W&B API key"
          style={{
            width: "100%",
            padding: "8px",
            marginBottom: "10px",
            border: "1px solid #ccc",
            borderRadius: "4px",
          }}
        />
        <button
          onClick={handleConfigure}
          style={{
            width: "100%",
            padding: "10px",
            backgroundColor: "#007bff",
            color: "white",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
          }}
        >
          Configure API
        </button>
        <p style={{ fontSize: "12px", color: "#666", marginTop: "10px" }}>
          Your API key will be used to authenticate requests to W&B Weave. You
          can find your API key in your W&B settings.
        </p>
      </div>
    );
  }

  return <WeaveDataExample />;
}

// Example component using the configured API
function WeaveDataExample() {
  const [projectId, setProjectId] = useState("your-project-id");
  const clearCache = useClearWeaveCache();

  // Use the Weave calls hook
  const { loading, result } = useWeaveCalls({
    projectId,
    filter: {
      op_names: ["your-operation-name"], // Replace with actual operation names
    },
    expandColumns: ["inputs", "output"],
  });

  const handleClearCache = async () => {
    await clearCache();
    alert("Cache cleared!");
  };

  return (
    <div style={{ padding: "20px" }}>
      <h2>Weave Data Example</h2>

      <div style={{ marginBottom: "20px" }}>
        <label>
          Project ID:
          <input
            type="text"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            style={{
              marginLeft: "10px",
              padding: "4px",
              border: "1px solid #ccc",
              borderRadius: "4px",
            }}
          />
        </label>
      </div>

      <div style={{ marginBottom: "20px" }}>
        <button onClick={handleClearCache} style={{ marginRight: "10px" }}>
          Clear Cache
        </button>
        <span>{loading ? "Loading..." : `${result.length} calls loaded`}</span>
      </div>

      {loading ? (
        <div>Loading Weave calls...</div>
      ) : (
        <div>
          <h3>Calls ({result.length})</h3>
          {result.length === 0 ? (
            <p>No calls found. Check your project ID and operation names.</p>
          ) : (
            <div style={{ maxHeight: "400px", overflowY: "auto" }}>
              {result.map((call) => (
                <div
                  key={call.id}
                  style={{
                    border: "1px solid #eee",
                    padding: "10px",
                    marginBottom: "10px",
                    borderRadius: "4px",
                  }}
                >
                  <div>
                    <strong>ID:</strong> {call.id}
                  </div>
                  <div>
                    <strong>Operation:</strong> {call.op_name}
                  </div>
                  <div>
                    <strong>Started At:</strong>{" "}
                    {new Date(call.started_at).toLocaleString()}
                  </div>
                  {call.ended_at && (
                    <div>
                      <strong>Ended At:</strong>{" "}
                      {new Date(call.ended_at).toLocaleString()}
                    </div>
                  )}
                  {call.exception && (
                    <div style={{ color: "red" }}>
                      <strong>Exception:</strong> {call.exception}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Alternative initialization for apps that use environment variables
export function initializeWeaveFromEnv() {
  const apiKey = process.env.REACT_APP_WANDB_API_KEY;

  if (!apiKey) {
    throw new Error(
      "REACT_APP_WANDB_API_KEY environment variable is required. " +
        "Set it in your .env file or environment."
    );
  }

  configureWeaveApi({
    apiKey,
    baseUrl: process.env.REACT_APP_WEAVE_BASE_URL || "https://trace.wandb.ai",
  });

  console.log("Weave API initialized from environment variables");
}

export default WeaveApiSetup;
