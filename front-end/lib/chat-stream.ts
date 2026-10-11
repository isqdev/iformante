export type SseEvent = { data: string; event: string };
export async function* readChatStream(
  response: Response,
): AsyncGenerator<SseEvent> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += done
        ? decoder.decode()
        : decoder.decode(value, { stream: true });
      const events: SseEvent[] = [];
      buffer = processSseBuffer(buffer, (event) => events.push(event));
      for (const event of events) yield event;
      if (done) break;
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
function processSseBuffer(buffer: string, onEvent: (event: SseEvent) => void) {
  const blocks = buffer.split("\n\n");
  const nextBuffer = blocks.pop() ?? "";

  for (const block of blocks) {
    const event = parseSseEvent(block);

    if (event) {
      onEvent(event);
    }
  }

  return nextBuffer;
}

function parseSseEvent(block: string): SseEvent | null {
  const eventLine = block
    .split("\n")
    .find((line) => line.startsWith("event: "));
  const dataLine = block.split("\n").find((line) => line.startsWith("data: "));

  if (!eventLine || !dataLine) {
    return null;
  }

  return {
    event: eventLine.slice("event: ".length),
    data: dataLine.slice("data: ".length),
  };
}
