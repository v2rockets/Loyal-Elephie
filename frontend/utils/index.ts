import { Message, OpenAIModel } from "@/types";
import { createParser, ParsedEvent, ReconnectInterval } from "eventsource-parser";

export const OpenAIStream = async (messages: Message[], token: string) => {
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();

  const res = await fetch("http://localhost:5000/v1/chat/completions", {
    headers: {
      "Content-Type": "application/json",
       Authorization: "Bearer " + token
    },
    method: "POST",
    body: JSON.stringify({
      //model: "gpt-3.5-turbo",
      messages: [
        {
          role: "system",
          content: ``
        },
        ...messages
      ],
      max_tokens: 300,
      stream: true
    }),

  });

  if (res.status !== 200) {
    throw new Error("OpenAI API returned an error");
  }

  const abortController = new AbortController();

  const stream = new ReadableStream({
    async start(controller) {
      const onParse = (event: ParsedEvent | ReconnectInterval) => {
        if (abortController.signal.aborted) {
          console.log("aborted")
          controller.close();
          return;
        }
        if (event.type === "event") {
          const data = event.data;

          if (data === "[DONE]") {
            controller.close();

            return;
          }

          try {
            const json = JSON.parse(data);
            const text = json.choices[0].delta.content;
            const queue = encoder.encode(text);
            controller.enqueue(queue);
            // console.log(text);
			if (json.choices[0].finish_reason) {
              controller.close();
              return;
            }
          } catch (e) {
            //controller.error(e);
            const queue = encoder.encode("E");
            controller.enqueue(queue);
          }
        }
      };

      const parser = createParser(onParse);

      for await (const chunk of res.body as any) {
        parser.feed(decoder.decode(chunk));
      }
    }
  });

  return stream;
};
