import type { Metadata } from "next";

import { UserManagement } from "@/components/admin/UserManagement";

export const metadata: Metadata = { title: "User management — bluntly admin" };

/** Owner-directed admin-shell extension; no dedicated Figma frame exists. */
export default function UserManagementPage() {
  return <UserManagement />;
}
