/**
 * Talking to the local CA-Guard API.
 *
 * Everything is same-origin: Next proxies `/api` to the Python process on this
 * machine, so nothing needs CORS opened up and no request ever leaves the box.
 */

import type {
  Decision,
  Engagement,
  Explanation,
  Finding,
  Queue,
  ReviewAction,
  SignupState,
  SourceFile,
  SourcePreview,
  User,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { cache: "no-store", ...init });
  } catch {
    throw new ApiError(
      "Cannot reach CA-Guard. Is it running? Start it with: uv run caguard serve",
      0,
    );
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      /* keep the status text */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export const auth = {
  me: () => request<User>("/api/auth/me"),

  signupState: () => request<SignupState>("/api/auth/signup-state"),

  signup: (body: {
    email: string;
    name: string;
    password: string;
    invite_code?: string;
  }) =>
    request<User>("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  login: (email: string, password: string) =>
    request<User>("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),

  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
};

export const api = {
  health: () =>
    request<{ status: string; model: string; model_available: boolean }>("/api/health"),

  engagements: () => request<Engagement[]>("/api/engagements"),

  upload: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<Queue>("/api/engagements", { method: "POST", body });
  },

  queue: (id: string) => request<Queue>(`/api/engagements/${id}/queue`),

  finding: (id: string, voucher: string) =>
    request<Finding>(`/api/engagements/${id}/findings/${voucher}`),

  explanation: (id: string, voucher: string) =>
    request<Explanation>(`/api/engagements/${id}/findings/${voucher}/explanation`),

  decide: (
    id: string,
    // No reviewer field: the server takes it from the signed-in session, so a
    // decision cannot be attributed to somebody who did not make it.
    payload: { voucher_id: string; action: ReviewAction; note?: string },
  ) =>
    request<Decision>(`/api/engagements/${id}/decisions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  trail: (id: string, voucher?: string) =>
    request<Decision[]>(
      `/api/engagements/${id}/trail${voucher ? `?voucher_id=${voucher}` : ""}`,
    ),

  reportUrl: (id: string, format: "csv" | "html") =>
    `/api/engagements/${id}/report.${format}`,

  sources: (id: string) => request<SourceFile[]>(`/api/engagements/${id}/sources`),

  /** The exact uploaded bytes. A plain link, so the browser handles the download. */
  originalUrl: (id: string, sourceId: string) =>
    `/api/engagements/${id}/sources/${sourceId}/original`,

  preview: (id: string, sourceId: string, offset: number, limit = 50) =>
    request<SourcePreview>(
      `/api/engagements/${id}/sources/${sourceId}/preview?offset=${offset}&limit=${limit}`,
    ),

  deleteSource: (id: string, sourceId: string) =>
    request<SourceFile>(`/api/engagements/${id}/sources/${sourceId}`, { method: "DELETE" }),
};
