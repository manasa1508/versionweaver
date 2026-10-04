import { afterEach, describe, expect, it, vi } from "vitest";
import { riskLabel, shortId, timeAgo, titleCase } from "./format";

afterEach(() => vi.useRealTimers());

describe("format helpers", () => {
  it("formats identifiers and labels", () => {
    expect(shortId("1234567890")).toBe("12345678");
    expect(titleCase("dead_letter")).toBe("Dead Letter");
  });

  it("maps risk boundaries consistently", () => {
    expect(riskLabel(34)).toBe("low");
    expect(riskLabel(35)).toBe("medium");
    expect(riskLabel(70)).toBe("high");
  });

  it("treats timezone-less API timestamps as UTC", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-04T15:10:00Z"));
    expect(timeAgo("2026-10-04T15:09:00")).toBe("1 minute ago");
  });
});
