/**
 * Incremental parser for server-sent events read from a fetch body.
 *
 * `EventSource` cannot POST or send headers (the CSRF token), so the chat stream is read
 * with fetch and fed through this. Feed it text as it arrives; it calls `onEvent` once per
 * complete event, however the network split the bytes.
 */
export function createSseParser(
  onEvent: (event: string, data: string) => void,
) {
  let buffer = "";
  return (chunk: string) => {
    buffer += chunk.replace(/\r\n?/g, "\n");
    let end = buffer.indexOf("\n\n");
    while (end >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith(":")) continue; // comment / keep-alive
        const colon = line.indexOf(":");
        const field = colon < 0 ? line : line.slice(0, colon);
        const value = colon < 0 ? "" : line.slice(colon + 1).replace(/^ /, "");
        if (field === "event") event = value;
        else if (field === "data") data.push(value);
      }
      if (data.length) onEvent(event, data.join("\n"));
      end = buffer.indexOf("\n\n");
    }
  };
}
