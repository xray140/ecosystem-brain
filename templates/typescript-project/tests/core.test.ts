import { describe, expect, it } from "vitest";
import { greet } from "../src/core.js";

describe("greet", () => {
  it("returns a greeting", () => {
    expect(greet("Alice")).toBe("Hello, Alice!");
  });

  it("throws on blank name", () => {
    expect(() => greet("  ")).toThrow("name must not be blank");
  });
});
