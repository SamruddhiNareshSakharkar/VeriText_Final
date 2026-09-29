import { Component, type ReactNode } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

class PageErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="p-6 rounded-xl max-w-lg mx-auto text-center mt-10"
          style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
          <p className="font-semibold mb-2" style={{ color: "var(--color-red)" }}>This page could not be displayed</p>
          <p className="text-sm mb-4" style={{ color: "var(--color-text-3)" }}>
            {this.state.error.message || "An unexpected rendering error occurred."}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="px-3 py-1.5 rounded-lg text-sm font-medium"
            style={{ background: "var(--color-accent)", color: "white" }}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--color-canvas)" }}>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto overflow-x-hidden" style={{ padding: "24px 28px" }}>
          <PageErrorBoundary>
            <Outlet />
          </PageErrorBoundary>
        </main>
      </div>
    </div>
  );
}
