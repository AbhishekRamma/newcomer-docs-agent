import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { answered, refused } from "../test/fixtures";
import { RefusalPanel } from "./RefusalPanel";
import { Result } from "./Result";

describe("RefusalPanel", () => {
  it("shows the route label and the raw route", () => {
    render(<RefusalPanel data={refused} />);
    expect(screen.getByTestId("route-label")).toHaveTextContent("Needs a professional · needs_professional");
    expect(screen.getByText(/licensed immigration consultant/)).toBeInTheDocument();
    expect(screen.getByRole("article", { name: "Refused: Needs a professional" })).toBeInTheDocument();
  });

  it("falls back to the route when there is no refusal reason", () => {
    render(<RefusalPanel data={{ ...refused, refusal_reason: null, route: "out_of_scope" }} />);
    expect(screen.getByTestId("route-label")).toHaveTextContent("Out of scope · out_of_scope");
  });

  it("is what Result shows for refused answers, and only for those", () => {
    const { rerender } = render(<Result data={refused} />);
    expect(screen.getByTestId("route-label")).toBeInTheDocument();
    rerender(<Result data={answered} />);
    expect(screen.queryByTestId("route-label")).not.toBeInTheDocument();
  });
});
