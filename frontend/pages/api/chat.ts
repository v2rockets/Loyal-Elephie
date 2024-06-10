import { Message } from "@/types";
import { OpenAIStream } from "@/utils";
import { parse } from 'cookie';

export const config = {
  runtime: "edge"
};

const handler = async (req: Request): Promise<Response> => {
  try {
    const cookies = req.headers.get("cookie") ? parse(req.headers.get("cookie")!) : {};
    // get the token from cookies:
    const token = cookies["Authorization"];

    const { messages } = (await req.json()) as {
      messages: Message[];
    };

    const charLimit = 12000;
    let charCount = 0;
    let messagesToSend = [];

    // Collect the most recent messages that fit within the character limit, preserving their original order
    for (let i = messages.length - 1; i >= 0; i--) {
      const message = messages[i];
      if (charCount + message.content.length > charLimit) {
        break;
      }
      charCount += message.content.length;
      messagesToSend.push(message);
    }
    
    messagesToSend.reverse();

    const stream = await OpenAIStream(messagesToSend, token);

    return new Response(stream);
  } catch (error) {
    console.error(error);
    return new Response("Error", { status: 500 });
  }
};

export default handler;
