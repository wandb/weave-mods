import { useCallback, useEffect, useState } from "react";
import { weaveCalls, weaveObjects, weaveTable } from "./apiUtils";
import { clearCache, createIndexedDBMemoizer } from "./cache";
import { useDeepMemo } from "./hooks";
import {
  CallSchema,
  CallsFilter,
  ObjectVersionFilter,
  ObjSchema,
  TableRowSchema,
} from "./traceServerApi";

/**
 * Example interface for the parameters we pass to `weaveCalls`.
 * Customize fields to match your actual usage.
 */
export interface WeaveCallParams {
  projectId: string;
  filter?: CallsFilter;
  expandColumns?: string[];
  key?: number;
}

const WEAVE_CALLS_DB = "weaveCalls";
const WEAVE_CALLS_STORE = "weaveCalls";

/** Create a memoized version of `weaveCalls` backed by IndexedDB. */
const weaveCallsMemoizer = await createIndexedDBMemoizer(
  WEAVE_CALLS_DB,
  WEAVE_CALLS_STORE
);

// This is our "query function" that returns an array of results.
export async function memoizedWeaveCalls(
  params: WeaveCallParams
): Promise<CallSchema[]> {
  // Because of how createIndexedDBMemoizer works, `weaveCallsMemoizer(weaveCalls)`
  // returns a function that does the caching.
  return weaveCallsMemoizer(weaveCalls)(params) as Promise<CallSchema[]>;
}

/**
 * Make a single-argument hook for a single "query call."
 *
 * `P` is the parameter type, `R` is the result type.
 */
function makeQueryHook<P, R>(
  queryFn: (params: P) => Promise<R>,
  initialResult: R
) {
  return function useQuery(params: P) {
    // We only want to trigger fetch if `params` changes deeply
    const memoParams = useDeepMemo(params);

    const [loading, setLoading] = useState(true);
    const [result, setResult] = useState<R>(initialResult);

    useEffect(() => {
      let active = true;
      setLoading(true);
      queryFn(memoParams)
        .then((r) => {
          if (!active) return;
          setResult(r);
        })
        .finally(() => {
          if (active) {
            setLoading(false);
          }
        });
      return () => {
        // If this effect re-runs, let's mark the old fetch "stale"
        active = false;
      };
    }, [memoParams]);

    return { loading, result };
  };
}

/**
 * Make a multi-argument hook that fetches multiple sets of data in parallel.
 *
 * If you call:
 *   `useMultiple([...arrayOfParams])`
 * you get back an array of results (one per param).
 */
function makeMultipleQueryHook<P, R>(queryFn: (params: P) => Promise<R>) {
  return function useMultiple(paramsArray: P[]) {
    const memoParamsArray = useDeepMemo(paramsArray);

    const [loading, setLoading] = useState(true);
    const [results, setResults] = useState<R[]>([]);

    useEffect(() => {
      let active = true;
      setLoading(true);

      Promise.all(memoParamsArray.map((p) => queryFn(p)))
        .then((res) => {
          if (!active) return;
          setResults(res);
        })
        .finally(() => {
          if (active) {
            setLoading(false);
          }
        });
      return () => {
        // Cancel stale fetches
        active = false;
      };
    }, [memoParamsArray]);

    return { loading, results };
  };
}

/** Our exported hooks that call the above factories. */
export const useWeaveCalls = makeQueryHook<WeaveCallParams, CallSchema[]>(
  memoizedWeaveCalls,
  []
);

export const useWeaveCallsMultiple = makeMultipleQueryHook<
  WeaveCallParams,
  CallSchema[]
>(memoizedWeaveCalls);

/**
 * Hook to clear the IndexedDB cache for Weave calls.
 */
export function useClearWeaveCache() {
  return useCallback(async () => {
    await clearCache(WEAVE_CALLS_DB, WEAVE_CALLS_STORE);
  }, []);
}

export function useWeaveObjects({
  projectId,
  filter,
}: {
  projectId: string;
  filter?: ObjectVersionFilter;
}) {
  filter = useDeepMemo(filter);
  const [result, setResult] = useState<ObjSchema[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    const fetchData = async () => {
      try {
        setLoading(true);
        const data = await weaveObjects(projectId, filter);
        if (mounted) {
          setResult(data);
        }
      } catch (error) {
        console.error("Error fetching objects:", error);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    fetchData();
    return () => {
      mounted = false;
    };
  }, [projectId, filter]);

  return { loading, result };
}

export function useWeaveTable(
  tableDigest: string | undefined,
  { projectId }: { projectId: string }
) {
  const [result, setResult] = useState<TableRowSchema[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;

    const fetchData = async () => {
      if (!tableDigest) {
        setResult([]);
        return;
      }

      try {
        setLoading(true);
        const data = await weaveTable(projectId, tableDigest);
        if (mounted) {
          setResult(data);
        }
      } catch (error) {
        console.error("Error fetching table:", error);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    fetchData();
    return () => {
      mounted = false;
    };
  }, [projectId, tableDigest]);

  return { loading, result };
}
