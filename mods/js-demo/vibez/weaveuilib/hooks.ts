import { isEqual } from "lodash";
import { useEffect, useRef } from "react";

export function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T>();
  useEffect(() => {
    ref.current = value;
  });
  return ref.current;
}

export const useDeepMemo = <T>(
  value: T,
  equalityFn?: (a: T, b: T | undefined) => boolean
) => {
  equalityFn = equalityFn ?? isEqual;
  const ref = useRef<T>();
  const prev = usePrevious(value);
  if (!equalityFn(value, prev)) {
    ref.current = value;
  }
  return ref.current as T;
};

export function useTraceUpdate(name: string, props: any) {
  const prev = useRef(props);
  useEffect(() => {
    const changedProps = Object.entries(props).reduce((ps, [k, v]) => {
      if (prev.current[k] !== v) {
        (ps as any)[k] = {
          prev: prev.current[k],
          current: v,
          //   diff: prev.current[k] != null ? difference(prev.current[k], v) : v,
        };
      }
      return ps;
    }, {});
    if (Object.keys(changedProps).length > 0) {
      console.log("Changed props:", name, changedProps);
    }
    prev.current = props;
  });
}
