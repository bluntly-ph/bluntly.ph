import "server-only";

import { apiFetch } from "./api/client";
import { getSessionToken } from "./session";
import type { NotificationItem } from "@/components/site/notification-model";

export type { NotificationItem };

/** The signed-in account's notifications, newest first. Null means unreachable. */
export async function getNotifications(limit = 50): Promise<NotificationItem[] | null> {
  try {
    return await apiFetch<NotificationItem[]>(`/api/v1/notifications?limit=${limit}`, {
      token: await getSessionToken(),
    });
  } catch {
    return null;
  }
}
