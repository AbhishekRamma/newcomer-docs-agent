import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ApiClient } from "../api";
import { historyItem, refused } from "../test/fixtures";
import { HistoryList } from "./HistoryList";
import { HistoryView } from "./HistoryView";

describe("HistoryList", () => {
  it("calls onDelete with the row id", async () => {
    const onDelete = vi.fn();
    const items = [historyItem(2, "Second question"), historyItem(1, "First question")];
    render(<HistoryList items={items} total={2} onDelete={onDelete} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete “First question”" }));
    expect(onDelete).toHaveBeenCalledWith(1);
    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it("shows the refusal label for refused entries and an empty state", () => {
    const { rerender } = render(
      <HistoryList items={[historyItem(3, "Refugee?", refused)]} total={1} onDelete={vi.fn()} />,
    );
    expect(screen.getByText("Needs a professional")).toBeInTheDocument();
    rerender(<HistoryList items={[]} total={0} onDelete={vi.fn()} />);
    expect(screen.getByText(/No saved questions yet/)).toBeInTheDocument();
  });
});

describe("HistoryView", () => {
  it("deletes through the API and removes the row", async () => {
    const deleteHistory = vi.fn<ApiClient["deleteHistory"]>().mockResolvedValue(undefined);
    const api: ApiClient = {
      ask: vi.fn(),
      listHistory: vi.fn().mockResolvedValue({
        items: [historyItem(5, "Keep me"), historyItem(4, "Delete me")], total: 2, limit: 10, offset: 0,
      }),
      deleteHistory,
    };
    render(<HistoryView api={api} />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete “Delete me”" }));
    expect(deleteHistory).toHaveBeenCalledWith(4);
    await waitFor(() => { expect(screen.queryByText("Delete me")).not.toBeInTheDocument(); });
    expect(screen.getByText("Keep me")).toBeInTheDocument();
    expect(screen.getByText("Showing 1 of 1, newest first.")).toBeInTheDocument();
  });
});
