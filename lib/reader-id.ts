import "server-only";

import { READER_COOKIE_NAME } from "./reader-id-policy";

type CookieStore = {
  delete(name: string): void;
};

/** Removes the anonymous identity at an authentication boundary. */
export function clearReaderId(cookieStore: CookieStore): void {
  cookieStore.delete(READER_COOKIE_NAME);
}
