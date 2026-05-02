import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VoteHistoryTable } from "./VoteHistoryTable";
import type { VoteHistoryItem } from "../lib/api";

const resolvedVote: VoteHistoryItem = {
  vote_id: "vote-1",
  bill_title: "Infrastructure Investment Act",
  scheduled_at: "2025-03-01T12:00:00Z",
  resolved_at: "2025-03-01T14:00:00Z",
  rep_outcome: "yes",
  pledges: { yes_pool_cents: 5000, no_pool_cents: 2000 },
};

const unresolvedVote: VoteHistoryItem = {
  vote_id: "vote-2",
  bill_title: "Climate Policy Act",
  scheduled_at: "2025-04-15T12:00:00Z",
  resolved_at: null,
  rep_outcome: null,
  pledges: { yes_pool_cents: 0, no_pool_cents: 0 },
};

describe("VoteHistoryTable", () => {
  it("renders bill title", () => {
    render(<VoteHistoryTable votes={[resolvedVote]} />);
    expect(screen.getByText("Infrastructure Investment Act")).toBeInTheDocument();
  });

  it("renders rep outcome for resolved votes", () => {
    render(<VoteHistoryTable votes={[resolvedVote]} />);
    // "yes" appears in the vote outcome cell (lowercase, capitalized via CSS)
    const cells = screen.getAllByRole("cell");
    expect(cells.some((c) => c.textContent?.toLowerCase() === "yes")).toBe(true);
  });

  it("shows Pending for unresolved votes", () => {
    render(<VoteHistoryTable votes={[unresolvedVote]} />);
    expect(screen.getByText(/pending/i)).toBeInTheDocument();
  });

  it("formats yes pool as dollars", () => {
    render(<VoteHistoryTable votes={[resolvedVote]} />);
    expect(screen.getByText("$50.00")).toBeInTheDocument();
  });

  it("formats no pool as dollars", () => {
    render(<VoteHistoryTable votes={[resolvedVote]} />);
    expect(screen.getByText("$20.00")).toBeInTheDocument();
  });

  it("shows $0.00 when pledge pools are zero", () => {
    render(<VoteHistoryTable votes={[unresolvedVote]} />);
    const zeros = screen.getAllByText("$0.00");
    expect(zeros.length).toBeGreaterThanOrEqual(2);
  });

  it("renders empty state when no votes", () => {
    render(<VoteHistoryTable votes={[]} />);
    expect(screen.getByText(/no votes/i)).toBeInTheDocument();
  });
});
