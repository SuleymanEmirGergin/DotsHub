import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

// sessions-v5 canonical sürüme yönlendir
export default function SessionsPage() {
  redirect("/admin/sessions-v5");
}
