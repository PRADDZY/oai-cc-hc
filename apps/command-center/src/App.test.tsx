import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("Command center", () => {
  it("shows simulation and provenance labels", () => {
    render(<App />);

    expect(screen.getByText(/simulation only/i)).toBeInTheDocument();
    expect(screen.getAllByText(/model generated/i).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/local map fallback/i)).toBeInTheDocument();
  });

  it("renders all eight drones and the approval gate", () => {
    render(<App />);

    const roster = screen.getByRole("heading", { name: /swarm roster/i }).closest("section");
    expect(roster).not.toBeNull();
    expect(within(roster!).getAllByText(/^drone_\d$/i)).toHaveLength(8);
    expect(screen.getByText(/human approval required/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /approve after visual confirmation/i }),
    ).toBeInTheDocument();
  });
});
