import { describe, expect, it } from "vitest";

import { chapterForStage, chapterIndex } from "./recoveryChapters";

describe("recoveryChapters", () => {
  it("maps safety terminal stages to protect chapter", () => {
    expect(chapterForStage("SAFETY_BLOCKED")).toBe("PROTECT");
    expect(chapterIndex("PROTECT")).toBe(6);
  });
});
