import { isOptionalWebUrl, normalizeWebUrl } from "./links";

describe("normalizeWebUrl", () => {
  it("keeps a full http(s) link", () => {
    expect(normalizeWebUrl("https://www.linkedin.com/in/riya")).toBe(
      "https://www.linkedin.com/in/riya",
    );
    expect(normalizeWebUrl("  http://acme.com/jobs/1  ")).toBe(
      "http://acme.com/jobs/1",
    );
  });

  it("adds https:// when it was left off", () => {
    expect(normalizeWebUrl("linkedin.com/in/riya")).toBe(
      "https://linkedin.com/in/riya",
    );
    expect(normalizeWebUrl("www.acme.com/careers?id=7")).toBe(
      "https://www.acme.com/careers?id=7",
    );
  });

  it("refuses other schemes, spaces and plain text", () => {
    for (const bad of [
      "javascript:alert(1)",
      "tel:+911234567890",
      "file:///etc/passwd",
      "mailto:a@b.co",
      "not a url",
      "riya",
      "https://",
      "",
      null,
      undefined,
    ]) {
      expect(normalizeWebUrl(bad)).toBeNull();
    }
  });
});

describe("isOptionalWebUrl", () => {
  it("accepts empty and valid, rejects the rest", () => {
    expect(isOptionalWebUrl("")).toBe(true);
    expect(isOptionalWebUrl("   ")).toBe(true);
    expect(isOptionalWebUrl("linkedin.com/in/riya")).toBe(true);
    expect(isOptionalWebUrl("javascript:alert(1)")).toBe(false);
  });
});
