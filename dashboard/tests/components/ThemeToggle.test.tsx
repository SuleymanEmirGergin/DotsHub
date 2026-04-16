import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeToggle } from "@/app/ThemeToggle";

// matchMedia mock
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

describe("ThemeToggle", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.classList.remove("dark");
  });

  it("renders a button after mount", async () => {
    render(<ThemeToggle />);
    // Component renders null until mounted (useEffect), so we wait
    await act(async () => {});
    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("toggles from light to dark on click", async () => {
    render(<ThemeToggle />);
    await act(async () => {});
    const btn = screen.getByRole("button");
    await userEvent.click(btn);
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });

  it("persists theme to localStorage on toggle", async () => {
    render(<ThemeToggle />);
    await act(async () => {});
    await userEvent.click(screen.getByRole("button"));
    expect(localStorage.getItem("pretriage-dashboard-theme")).toBe("dark");
  });

  it("toggles back to light from dark", async () => {
    localStorage.setItem("pretriage-dashboard-theme", "dark");
    render(<ThemeToggle />);
    await act(async () => {});
    await userEvent.click(screen.getByRole("button"));
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
  });
});
