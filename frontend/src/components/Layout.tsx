import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";

export function Layout({ children }: { children: ReactNode }) {
  // The Workstation (Section 45) is a self-contained cockpit with its own
  // left rail - the global nav sidebar would just be a fourth column.
  const fullBleed = useLocation().pathname.endsWith("/workstation");
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-vajra-bg">
      {!fullBleed && <Sidebar />}
      <main className={`flex-1 ${fullBleed ? "overflow-hidden" : "overflow-y-auto"}`}>{children}</main>
    </div>
  );
}
