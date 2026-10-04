import { redirect } from "next/navigation";

// The app shell sends logged-out visitors on to /login.
export default function Home() {
  redirect("/dashboard");
}
