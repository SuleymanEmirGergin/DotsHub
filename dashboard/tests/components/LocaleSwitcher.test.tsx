import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocaleSwitcher } from "@/app/LocaleSwitcher";

// useRouter mock is in vitest.setup.ts
const mockRefresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: mockRefresh, push: vi.fn() }),
}));

describe("LocaleSwitcher", () => {
  it("TR button has aria-pressed=true when locale is tr", () => {
    render(<LocaleSwitcher initialLocale="tr" />);
    const trBtn = screen.getByRole("button", { name: "TR" });
    expect(trBtn).toHaveAttribute("aria-pressed", "true");
  });

  it("EN button has aria-pressed=true when locale is en", () => {
    render(<LocaleSwitcher initialLocale="en" />);
    const enBtn = screen.getByRole("button", { name: "EN" });
    expect(enBtn).toHaveAttribute("aria-pressed", "true");
  });

  it("calls router.refresh() when switching to different locale", async () => {
    mockRefresh.mockClear();
    render(<LocaleSwitcher initialLocale="tr" />);
    await userEvent.click(screen.getByRole("button", { name: "EN" }));
    expect(mockRefresh).toHaveBeenCalledOnce();
  });

  it("does not call router.refresh() when clicking current locale", async () => {
    mockRefresh.mockClear();
    render(<LocaleSwitcher initialLocale="tr" />);
    await userEvent.click(screen.getByRole("button", { name: "TR" }));
    expect(mockRefresh).not.toHaveBeenCalled();
  });
});
