import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RepCard } from "./RepCard";
import type { RepSummary } from "../lib/api";

const baseRep: RepSummary = {
  id: "abc-123",
  bioguide_id: "H000001",
  name: "Jane Smith",
  party: "D",
  chamber: "house",
  state: "VA",
  district: 5,
  photo_url: null,
  is_active: true,
};

describe("RepCard", () => {
  it("renders rep name", () => {
    render(<RepCard rep={baseRep} />);
    expect(screen.getByText("Jane Smith")).toBeInTheDocument();
  });

  it("renders party and state", () => {
    render(<RepCard rep={baseRep} />);
    expect(screen.getByText("VA")).toBeInTheDocument();
    expect(screen.getByText("D")).toBeInTheDocument();
  });

  it("renders district for house members", () => {
    render(<RepCard rep={baseRep} />);
    expect(screen.getByText(/District 5/i)).toBeInTheDocument();
  });

  it("does not render district for senators", () => {
    render(<RepCard rep={{ ...baseRep, chamber: "senate", district: null }} />);
    expect(screen.queryByText(/District/i)).not.toBeInTheDocument();
  });

  it("renders photo when photo_url provided", () => {
    render(<RepCard rep={{ ...baseRep, photo_url: "https://example.com/photo.jpg" }} />);
    expect(screen.getByRole("img")).toHaveAttribute("src", "https://example.com/photo.jpg");
  });

  it("renders initials placeholder when no photo_url", () => {
    render(<RepCard rep={baseRep} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("JS")).toBeInTheDocument();
  });
});
