import { describe, expect, it } from "@jest/globals";

import { createSseParser } from "./sse";

describe("createSseParser", () => {
  it("emits events however the bytes are split", () => {
    const seen: [string, string][] = [];
    const feed = createSseParser((event, data) => seen.push([event, data]));
    const stream =
      'id: 1\nevent: token\ndata: {"delta":"Hel"}\n\nevent: token\ndata: {"delta":"lo"}\n\n';
    for (const char of stream) feed(char);
    expect(seen).toEqual([
      ["token", '{"delta":"Hel"}'],
      ["token", '{"delta":"lo"}'],
    ]);
  });

  it("handles CRLF, comments, multi-line data and the default event name", () => {
    const seen: [string, string][] = [];
    const feed = createSseParser((event, data) => seen.push([event, data]));
    feed(": ping\r\n\r\ndata: a\r\ndata: b\r\n\r\nevent: done\ndata: {}\n\n");
    expect(seen).toEqual([
      ["message", "a\nb"],
      ["done", "{}"],
    ]);
  });

  it("keeps an incomplete event until it is finished", () => {
    const seen: string[] = [];
    const feed = createSseParser((event) => seen.push(event));
    feed("event: done\ndata: {}\n");
    expect(seen).toEqual([]);
    feed("\n");
    expect(seen).toEqual(["done"]);
  });
});
