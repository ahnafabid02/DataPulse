export type Identity = {
  id: string;
  username: string | null;
  kind: string;
  roles: string[];
};
export type Organization = {
  id: string;
  code: string;
  name: string;
  revision: number;
};
export type Source = {
  id: string;
  organization_id: string;
  code: string;
  ehr_product: string;
  ehr_version: string | null;
  database_vendor: string;
  database_name: string;
  status: string;
  revision: number;
};
export type Credential = { id: string; token: string; expires_at: string };
export type Saved = {
  organization: Organization;
  source: Source;
  credential: Credential;
};
export type AuditEvent = {
  id: string;
  actor_id: string | null;
  actor_kind: string;
  action: string;
  target_type: string;
  target_id: string | null;
  occurred_at: string;
  change_metadata: Record<string, unknown>;
};
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`/v1${path}`, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        "X-DataPulse-Request": "1",
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (response.status === 204) return undefined as T;
    const data = await response.json();
    if (!response.ok)
      throw new ApiError(
        data?.error?.message || "We couldn’t complete that action. Try again.",
        response.status,
      );
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      "We couldn’t reach DataPulse. Check the system status, then refresh before retrying a save.",
      0,
    );
  } finally {
    window.clearTimeout(timer);
  }
}
export async function allPages<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  let cursor: string | null = null;
  do {
    const page: { items: T[]; next_cursor: string | null } = await api(
      `${path}?limit=200${cursor ? `&cursor=${cursor}` : ""}`,
    );
    items.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  return items;
}
