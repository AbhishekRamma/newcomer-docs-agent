import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { answered } from "../test/fixtures";
import { Answer } from "./Answer";

describe("Answer", () => {
  it("renders inline citations as numbered links to the source pages", () => {
    render(<Answer data={answered} />);
    const links = screen.getAllByRole("link", { name: /^Source \d/ });
    expect(links.map((a) => a.textContent)).toEqual(["1", "2", "1"]);
    expect(links[0]).toHaveAttribute("href", answered.citations[0]!.url);
    expect(links[1]).toHaveAttribute("href", answered.citations[1]!.url);
    for (const a of links) {
      expect(a).toHaveAttribute("target", "_blank");
      expect(a).toHaveAttribute("rel", "noopener noreferrer");
    }
    expect(screen.queryByText(/\[s17-c500-000\]/)).not.toBeInTheDocument();
  });

  it("lists each cited source once, in citation order, with its fetch date", () => {
    render(<Answer data={answered} />);
    const list = screen.getByRole("list");
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[0]!).getByRole("link", { name: "Apply for a SIN" }))
      .toHaveAttribute("href", answered.citations[0]!.url);
    expect(items[0]).toHaveTextContent("fetched 2026-10-01");
    expect(screen.getByText("Answer · answer")).toBeInTheDocument();
  });

  it("never renders model output as HTML", () => {
    const evil = { ...answered, answer: "<img src=x onerror=alert(1)> hi", citations: [] };
    const { container } = render(<Answer data={evil} />);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText(/<img src=x/)).toBeInTheDocument();
  });
});
