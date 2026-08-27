import { describe, expect, it } from "vitest";
import { formatPublicPhone } from "./api";

describe("formatPublicPhone", () => {
  it("joins number and extension", () => {
    expect(formatPublicPhone("269-555-0100", "12")).toBe("269-555-0100 ext. 12");
  });
  it("returns dash when empty", () => {
    expect(formatPublicPhone(null, null)).toBe("—");
  });
});
