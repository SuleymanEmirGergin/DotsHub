import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

describe("Card", () => {
  it("renders children inside Card", () => {
    render(<Card><p>Content</p></Card>);
    expect(screen.getByText("Content")).toBeInTheDocument();
  });

  it("renders CardHeader with CardTitle and CardContent", () => {
    render(
      <Card>
        <CardHeader><CardTitle>My Title</CardTitle></CardHeader>
        <CardContent><p>Body text</p></CardContent>
      </Card>
    );
    expect(screen.getByText("My Title")).toBeInTheDocument();
    expect(screen.getByText("Body text")).toBeInTheDocument();
  });

  it("applies custom className to Card", () => {
    render(<Card className="custom-card">test</Card>);
    const card = screen.getByText("test").closest("div");
    expect(card).toHaveClass("custom-card");
  });
});
