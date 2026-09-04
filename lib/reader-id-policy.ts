import { randomUUID } from "node:crypto";

export const READER_COOKIE_NAME = "bluntly_rid";
export const READER_COOKIE_MAX_AGE = 86_400;

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** True only for canonical RFC 4122 version-four UUIDs. */
export function validReaderId(value: unknown): value is string {
  return typeof value === "string" && UUID_V4.test(value);
}

/** Creates an opaque first-party pseudonym from the operating system CSPRNG. */
export function mintReaderId(): string {
  return randomUUID();
}
