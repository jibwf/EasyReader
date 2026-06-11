const USER_ID_KEY = "reader_user_id";
const DEVICE_ID_KEY = "reader_device_id";

function randomId(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function getClientIdentity(): { userId: string; deviceId: string } {
  const storage = window.localStorage;
  let userId = storage.getItem(USER_ID_KEY);
  let deviceId = storage.getItem(DEVICE_ID_KEY);

  if (!userId) {
    userId = "demo-user";
    storage.setItem(USER_ID_KEY, userId);
  }

  if (!deviceId) {
    const ua = navigator.userAgent.toLowerCase();
    const platform = ua.includes("android") ? "android" : "web";
    deviceId = randomId(platform);
    storage.setItem(DEVICE_ID_KEY, deviceId);
  }

  return { userId, deviceId };
}

export function setClientUserId(nextUserId: string): string {
  const normalized = nextUserId.trim() || "demo-user";
  window.localStorage.setItem(USER_ID_KEY, normalized);
  return normalized;
}

export function regenerateClientDeviceId(): string {
  const ua = navigator.userAgent.toLowerCase();
  const platform = ua.includes("android") ? "android" : "web";
  const nextDeviceId = randomId(platform);
  window.localStorage.setItem(DEVICE_ID_KEY, nextDeviceId);
  return nextDeviceId;
}

export function resetClientIdentity(): { userId: string; deviceId: string } {
  window.localStorage.removeItem(USER_ID_KEY);
  window.localStorage.removeItem(DEVICE_ID_KEY);
  return getClientIdentity();
}
