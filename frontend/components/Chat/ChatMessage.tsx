import { Message } from "@/types";
import { FC } from "react";
import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/cjs/styles/prism';


interface Props {
  message: Message;
}

export const ChatMessage: FC<Props> = ({ message }) => {

  // Split the text by ```
  const divisions = message.role === "assistant"?message.content.split('\n###'):[message.content]
  const sections = message.role === "assistant"?divisions[0].split('```'):divisions;
  const linkText = divisions[1];
  
  const parseMarkdownLinks = (text: string) => {
    const markdownLinkRegex = /\[([^\[]+)\]\(([^\)]+)\)/g;
    const links = [];
    let match;
    while ((match = markdownLinkRegex.exec(text)) !== null) {
      links.push({ text: match[1], url: match[2] });
    }
    return links.map((link, index) => (
      <p key={index}>
      <a key={index} href={link.url} target="_blank" rel="noopener noreferrer">
        {link.text}
      </a>
      </p>
    ));
  };

  return (
    <div className={`flex flex-col ${message.role === "assistant" ? "items-start" : "items-end"}`}>
      <div
        className={`flex flex-col ${message.role === "assistant" ? "bg-neutral-200 text-neutral-900" : "bg-blue-500 text-white"} rounded-2xl px-3 py-2 max-w-[67%] whitespace-pre-wrap`}
        style={{ overflowWrap: "anywhere" }}
      >
        <div className={`flex flex-col items-center`}>
        {sections.map((section, index) => {
          // Alternating sections are code
          const isCode = index % 2 === 1;

          return isCode ? (
            <div style={{ maxWidth: '100%', overflowX: 'auto' }}>
            <SyntaxHighlighter language="python" style={oneLight}>
              {section}
            </SyntaxHighlighter>
            </div>
          ) : (
            <p>{section}</p>
          );
        })}
        </div>
        {message.role === "assistant" && linkText && (
        <div className={`flex flex-col items-left`}>
        <details>
          <summary>References</summary>
          {parseMarkdownLinks(linkText)}
        </details>
        </div>
      )}
      </div>
    </div>
  );
};
