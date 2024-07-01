import { Message } from "@/types";
import { FC } from "react";
import { ChatInput } from "./ChatInput";
import { ChatLoader } from "./ChatLoader";
import { ChatMessage } from "./ChatMessage";

interface Props {
  messages: Message[];
  loading: boolean;
  isButtonDisabled: boolean;
  onSend: (message: Message) => void;
  onRevert: () => void;
  content: string;
  setContent: (content:string) => void
}

export const Chat: FC<Props> = ({ messages, loading, isButtonDisabled, onSend, onRevert, content, setContent }) => {
  return (
    <>
      <div className="flex flex-col rounded-lg px-2 sm:p-4 sm:border border-neutral-300">
        {messages.map((message, index) => (
          <div
            key={index}
            className="my-1 sm:my-1.5"
          >
            <ChatMessage message={message} />
          </div>
        ))}

        {loading && (
          <div className="my-1 sm:my-1.5">
            <ChatLoader />
          </div>
        )}

        <div className="mt-4 sm:mt-8 bottom-[56px] left-0 w-full">
          <ChatInput onSend={onSend} onRevert={onRevert} isButtonDisabled={isButtonDisabled}
          content={content} setContent={setContent} loading={loading}/>
        </div>
      </div>
    </>
  );
};