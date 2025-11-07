import {
  CallSchema,
  CallsFilter,
  ObjectVersionFilter,
  ObjSchema,
  TableRowFilter,
  TableRowSchema,
  Api as TraceServerApi,
} from "./traceServerApi";

// Configuration for the API client
interface WeaveApiConfig {
  apiKey: string;
  baseUrl?: string;
}

let apiConfig: WeaveApiConfig | null = null;
let traceServerApi: TraceServerApi<unknown> | null = null;

/**
 * Configure the Weave API client with credentials.
 * This should be called once at the start of your application.
 */
export function configureWeaveApi(config: WeaveApiConfig) {
  apiConfig = config;

  // Create base64 encoded auth header for web environment
  const auth = btoa(`api:${config.apiKey}`);

  const headers: Record<string, string> = {
    "User-Agent": `W&B Internal JS Client`,
    Authorization: `Basic ${auth}`,
  };

  traceServerApi = new TraceServerApi({
    baseUrl: config.baseUrl || "https://trace.wandb.ai",
    baseApiParams: {
      headers: headers,
    },
  });
}

/**
 * Get the configured API client, throwing an error if not configured.
 */
function getApiClient(): TraceServerApi<unknown> {
  if (!traceServerApi) {
    throw new Error(
      "Weave API not configured. Call configureWeaveApi() with your API key first."
    );
  }
  return traceServerApi;
}

export interface WeaveCallsParams {
  projectId: string;
  filter: CallsFilter;
  expandColumns?: string[];
  limit?: number;
}

export function opRef(projectId: string, opName: string, opVersion?: string) {
  return `weave:///${projectId}/op/${opName}:${opVersion ?? "*"}`;
}

export function objRef(obj: ObjSchema) {
  return `weave:///${obj.project_id}/object/${obj.object_id}:${obj.digest}`;
}

export async function weaveCalls({
  projectId,
  filter,
  expandColumns,
  limit,
}: WeaveCallsParams): Promise<CallSchema[]> {
  if (filter.op_names) {
    filter = {
      ...filter,
      op_names: filter.op_names.map((opName) => opRef(projectId, opName)),
    };
  }
  const callsResponse =
    await getApiClient().calls.callsQueryStreamCallsStreamQueryPost({
      project_id: projectId,
      filter: filter ?? {},
      limit,
      expand_columns: expandColumns,
    });
  const reader = callsResponse.body!.getReader();
  let buffer = "";
  const decoder = new TextDecoder();

  const calls: CallSchema[] = [];

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    let newlineIndex;
    while ((newlineIndex = buffer.indexOf("\n")) !== -1) {
      const line = buffer.slice(0, newlineIndex);
      buffer = buffer.slice(newlineIndex + 1);

      if (line.trim() === "") continue;

      try {
        const jsonData = JSON.parse(line);
        calls.push(jsonData);
      } catch (error) {
        console.error("Error parsing JSON:", error);
        console.log("Problematic line:", line);
      }
    }
  }

  if (buffer.trim() !== "") {
    try {
      const jsonData = JSON.parse(buffer);
      calls.push(jsonData);
    } catch (error) {
      console.error("Error parsing JSON:", error);
      console.log("Problematic data:", buffer);
    }
  }

  return calls;
}

export async function weaveObjects(
  projectId: string,
  filter?: ObjectVersionFilter
): Promise<ObjSchema[]> {
  const response = await getApiClient().objs.objsQueryObjsQueryPost({
    project_id: projectId,
    filter: filter ?? {},
  });
  return response.data.objs;
}

export async function weaveTable(
  projectId: string,
  digest: string,
  filter?: TableRowFilter,
  limit?: number,
  offset?: number
): Promise<TableRowSchema[]> {
  const response = await getApiClient().table.tableQueryTableQueryPost({
    project_id: projectId,
    digest,
    filter: filter ?? {},
    limit,
    offset,
  });
  return response.data.rows;
}

export async function weaveEvaluationCalls(
  projectId: string
): Promise<CallSchema[]> {
  return weaveCalls({
    projectId,
    filter: {
      op_names: ["Evaluation.evaluate"],
    },
    expandColumns: ["inputs.self"],
  });
}
