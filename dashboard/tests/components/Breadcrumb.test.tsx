import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import type { BreadcrumbItem } from "@/app/components/Breadcrumb";

describe("Breadcrumb", () => {
  it("renders nothing when items array is empty", () => {
    const { container } = render(<Breadcrumb items={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders a single item without a link when href is absent", () => {
    const items: BreadcrumbItem[] = [{ label: "Dashboard" }];
    render(<Breadcrumb items={items} />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("renders a link when href is provided", () => {
    const items: BreadcrumbItem[] = [{ label: "Home", href: "/" }];
    render(<Breadcrumb items={items} />);
    const link = screen.getByRole("link", { name: "Home" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/");
  });

  it("renders multiple items with separators between them", () => {
    const items: BreadcrumbItem[] = [
      { label: "Home", href: "/" },
      { label: "Admin", href: "/admin" },
      { label: "Sessions" },
    ];
    render(<Breadcrumb items={items} />);
    expect(screen.getByRole("link", { name: "Home" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Admin" })).toBeInTheDocument();
    expect(screen.getByText("Sessions")).toBeInTheDocument();
    // Two separators for three items
    const separators = screen.getAllByText("/");
    expect(separators).toHaveLength(2);
  });

  it("renders nav with aria-label=Breadcrumb", () => {
    const items: BreadcrumbItem[] = [{ label: "Home" }];
    render(<Breadcrumb items={items} />);
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toBeInTheDocument();
  });

  it("last item without href renders as plain text, not a link", () => {
    const items: BreadcrumbItem[] = [
      { label: "Home", href: "/" },
      { label: "Current Page" },
    ];
    render(<Breadcrumb items={items} />);
    expect(screen.queryByRole("link", { name: "Current Page" })).toBeNull();
    expect(screen.getByText("Current Page")).toBeInTheDocument();
  });
});
