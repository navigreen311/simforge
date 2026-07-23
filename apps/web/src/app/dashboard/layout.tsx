import { Header } from "@/components/shell/Header";
import { CommandK } from "@/components/shell/CommandK";
import { Sidebar } from "@/components/shell/Sidebar";
import { StubModeBanner } from "@/components/shell/StubModeBanner";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <CommandK />
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header />
        <StubModeBanner />
        <main className="flex-1 overflow-y-auto p-8">{children}</main>
      </div>
    </div>
  );
}
