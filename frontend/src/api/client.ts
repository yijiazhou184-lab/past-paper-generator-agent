let csrf = "";
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public task_id?: string,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET")
    headers.set("X-CSRFToken", csrf);
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  const body = await response
    .json()
    .catch(() => ({
      message: "The service did not return a readable response.",
    }));
  if (!response.ok)
    throw new ApiError(
      response.status,
      body.code ?? "REQUEST_FAILED",
      body.message ?? "Request failed",
      body.task_id,
    );
  if (body.csrf_token) csrf = body.csrf_token;
  return body;
}
export const requestKey = () => crypto.randomUUID();
