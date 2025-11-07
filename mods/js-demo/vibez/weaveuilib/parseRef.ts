export const WEAVE_REF_SCHEME = "weave";
export const WEAVE_REF_PREFIX = `${WEAVE_REF_SCHEME}:///`;

interface LocalArtifactRef {
  scheme: "local-artifact";
  artifactName: string;
  artifactVersion: string;
  artifactPath: string;
}

export interface WandbArtifactRef {
  scheme: "wandb-artifact";
  entityName: string;
  projectName: string;
  artifactName: string;
  artifactVersion: string;
  artifactPath: string;
  artifactRefExtra?: string;
}

export type WeaveKind = "object" | "op" | "table" | "call";
export interface WeaveObjectRef {
  scheme: "weave";
  entityName: string;
  projectName: string;
  weaveKind: WeaveKind;
  artifactName: string;
  artifactVersion: string;
  artifactRefExtra?: string;
}

export type ArtifactRef = LocalArtifactRef | WandbArtifactRef;

type ArtifactObjectRef = ArtifactRef & {
  artifactRefExtra?: string;
};

export type ObjectRef = ArtifactObjectRef | WeaveObjectRef;

export const isWandbArtifactRef = (ref: ObjectRef): ref is WandbArtifactRef => {
  return ref.scheme === "wandb-artifact";
};

export const isWeaveObjectRef = (ref: ObjectRef): ref is WeaveObjectRef => {
  return ref.scheme === "weave";
};

// Entity name should be lowercase, digits, dash, underscore
// Unfortunately many teams have been created that violate this.
const PATTERN_ENTITY = "([^/]+)";
const PATTERN_PROJECT = "([^\\#?%:]{1,128})"; // Project name
const PATTERN_REF_EXTRA = "([a-zA-Z0-9_.~/%-]*)"; // Optional ref extra (valid chars are result of python urllib.parse.quote and javascript encodeURIComponent)
const RE_WEAVE_OBJECT_REF_PATHNAME = new RegExp(
  [
    "^", // Start of the string
    PATTERN_ENTITY,
    "/",
    PATTERN_PROJECT,
    "/",
    "(object|op)", // Weave kind
    "/",
    "([a-zA-Z0-9-_/. ]{1,128})", // Artifact name
    ":",
    "([*]|[a-zA-Z0-9]+)", // Artifact version, allowing '*' for any version
    "/?", // Ref extra portion is optional
    PATTERN_REF_EXTRA, // Optional ref extra
    "$", // End of the string
  ].join("")
);
const RE_WEAVE_TABLE_REF_PATHNAME = new RegExp(
  [
    "^", // Start of the string
    PATTERN_ENTITY,
    "/",
    PATTERN_PROJECT,
    "/table/",
    "([a-f0-9]+)", // Digest
    "/?", // Ref extra portion is optional
    PATTERN_REF_EXTRA, // Optional ref extra
    "$", // End of the string
  ].join("")
);
const RE_WEAVE_CALL_REF_PATHNAME = new RegExp(
  [
    "^", // Start of the string
    PATTERN_ENTITY,
    "/",
    PATTERN_PROJECT,
    "/call/",
    "([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", // Call UUID
    "/?", // Ref extra portion is optional
    PATTERN_REF_EXTRA, // Optional ref extra
    "$", // End of the string
  ].join("")
);

export const parseWeaveRef = (ref: string): WeaveObjectRef => {
  const trimmed = ref.slice(WEAVE_REF_PREFIX.length);
  const tableMatch = trimmed.match(RE_WEAVE_TABLE_REF_PATHNAME);
  if (tableMatch !== null) {
    const [entity, project, digest] = tableMatch.slice(1);
    return {
      scheme: "weave",
      entityName: entity,
      projectName: project,
      weaveKind: "table" as WeaveKind,
      artifactName: "",
      artifactVersion: digest,
      artifactRefExtra: "",
    };
  }
  const callMatch = trimmed.match(RE_WEAVE_CALL_REF_PATHNAME);
  if (callMatch !== null) {
    const [entity, project, callId] = callMatch.slice(1);
    return {
      scheme: "weave",
      entityName: entity,
      projectName: project,
      weaveKind: "call" as WeaveKind,
      artifactName: callId,
      artifactVersion: "",
      artifactRefExtra: "",
    };
  }
  const match = trimmed.match(RE_WEAVE_OBJECT_REF_PATHNAME);
  if (match === null) {
    throw new Error("Invalid weave ref uri: " + ref);
  }
  const [
    entityName,
    projectName,
    weaveKind,
    artifactName,
    artifactVersion,
    artifactRefExtra,
  ] = match.slice(1);
  return {
    scheme: "weave",
    entityName,
    projectName,
    weaveKind: weaveKind as WeaveKind,
    artifactName,
    artifactVersion,
    artifactRefExtra: artifactRefExtra ?? "",
  };
};

export const objectRefWithExtra = (
  objRef: ObjectRef,
  extra: string
): ObjectRef => {
  let newExtra = "";
  if (objRef.artifactRefExtra != null && objRef.artifactRefExtra !== "") {
    newExtra = objRef.artifactRefExtra + "/";
  }
  newExtra += extra;
  return {
    ...objRef,
    artifactRefExtra: newExtra,
  };
};

export const refUri = (ref: ObjectRef): string => {
  if (isWandbArtifactRef(ref)) {
    let uri = `wandb-artifact:///${ref.entityName}/${ref.projectName}/${ref.artifactName}:${ref.artifactVersion}`;
    if (ref.artifactPath) {
      uri = `${uri}/${ref.artifactPath}`;
      if (ref.artifactRefExtra) {
        uri = `${uri}#${ref.artifactRefExtra}`;
      }
    }
    return uri;
  } else if (isWeaveObjectRef(ref)) {
    let name = `${ref.artifactName}:${ref.artifactVersion}`;
    if (ref.artifactName === "" && ref.weaveKind === "table") {
      name = ref.artifactVersion;
    }
    let uri = `weave:///${ref.entityName}/${ref.projectName}/${ref.weaveKind}/${name}`;
    if (ref.artifactRefExtra != null && ref.artifactRefExtra !== "") {
      if (ref.artifactRefExtra.startsWith("/")) {
        // UGG Why does this happen???
        uri = `${uri}${ref.artifactRefExtra}`;
      } else {
        uri = `${uri}/${ref.artifactRefExtra}`;
      }
    }
    if (uri.endsWith("/")) {
      uri = uri.slice(0, -1);
    }
    return uri;
  } else {
    return `local-artifact:///${ref.artifactName}/${ref.artifactPath}`;
  }
};
