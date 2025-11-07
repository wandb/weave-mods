export interface WeaveRef {
  entity: string;
  project: string;
  opName: string;
  opVersion: string;
}

export function parseWeaveRef(ref: string): WeaveRef | null {
  const regex = /^weave:\/\/\/([^/]+)\/([^/]+)\/op\/([^:]+):(.+)$/;
  const match = ref.match(regex);

  if (!match) {
    return null;
  }

  return {
    entity: match[1],
    project: match[2],
    opName: match[3],
    opVersion: match[4],
  };
}

export function flattenObject(obj: any, prefix = ""): any {
  return Object.keys(obj).reduce((acc: any, k: string) => {
    const pre = prefix.length ? prefix + "." : "";
    if (
      typeof obj[k] === "object" &&
      obj[k] !== null &&
      !Array.isArray(obj[k])
    ) {
      Object.assign(acc, flattenObject(obj[k], pre + k));
    } else {
      acc[pre + k] = obj[k];
    }
    return acc;
  }, {});
}
