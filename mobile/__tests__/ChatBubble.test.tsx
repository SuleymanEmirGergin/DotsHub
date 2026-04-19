/**
 * ChatBubble render smoke.
 *
 * The component has two visual branches (user vs non-user role) plus
 * a conditional timestamp. We assert:
 *   - content always renders
 *   - AI/system rows include the stethoscope avatar; user rows don't
 *   - timestamp is rendered in Turkish locale HH:MM format when the
 *     prop is supplied, and omitted otherwise
 *
 * Same Fragment-shim + `react-dom/server` pattern as the other
 * render suites — see `mobile/__mocks__/react-native.js` for why.
 */
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import ChatBubble from "../components/ChatBubble";

function renderText(element: React.ReactElement): string {
  return renderToStaticMarkup(element)
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

describe("ChatBubble", () => {
  it("renders the message content for a user bubble", () => {
    expect(
      renderText(<ChatBubble role="user" content="Başım ağrıyor" />),
    ).toContain("Başım ağrıyor");
  });

  it("renders the message content + avatar for an AI bubble", () => {
    const out = renderText(
      <ChatBubble role="ai" content="Ne zaman başladı?" />,
    );
    expect(out).toContain("Ne zaman başladı?");
    // Stethoscope emoji used as a lightweight avatar.
    expect(out).toContain("🩺");
  });

  it("omits the avatar on a user row", () => {
    const out = renderText(<ChatBubble role="user" content="Dün akşam" />);
    expect(out).not.toContain("🩺");
  });

  it("includes a system-role bubble with the avatar (treated as non-user)", () => {
    const out = renderText(
      <ChatBubble role="system" content="Oturum başladı" />,
    );
    expect(out).toContain("Oturum başladı");
    expect(out).toContain("🩺");
  });

  it("renders the timestamp in HH:MM when provided", () => {
    const out = renderText(
      <ChatBubble
        role="user"
        content="test"
        // 14:30 local — `toLocaleTimeString('tr-TR', {hour, minute})`
        // formatting; assertion uses a regex to tolerate the Windows
        // vs Unix runtime formatting difference around the colon.
        timestamp="2026-04-19T14:30:00.000Z"
      />,
    );
    expect(out).toMatch(/\d{1,2}[:.]\d{2}/);
  });

  it("omits the timestamp block when the prop is absent", () => {
    const out = renderText(<ChatBubble role="ai" content="Test mesajı" />);
    // Turkish time separators — no digit pair like HH:MM should appear
    // in the rendered markup.
    expect(out).not.toMatch(/\d{1,2}[:.]\d{2}/);
  });
});
