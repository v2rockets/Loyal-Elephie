import { Chat } from "@/components/Chat/Chat";
import { Footer } from "@/components/Layout/Footer";
import { Navbar } from "@/components/Layout/Navbar";
import { Message } from "@/types";
import Head from "next/head";
import { useEffect, useRef, useState } from "react";
import { useRouter } from 'next/router';
import Cookies from 'js-cookie';

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [isButtonDisabled, setIsButtonDisabled] = useState<boolean>(false);
  const [content, setContent] = useState<string>("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const stopConversationRef = useRef<boolean>(false);
  const router = useRouter();

  const handleSend = async (message: Message) => {
    const updatedMessages = [...messages, message];

    setMessages(updatedMessages);
    setIsButtonDisabled(true);
    setLoading(true);
    const controller = new AbortController();
    //const token = Cookies.get("Authorization")

    const response = await fetch("/api/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            // "Authorization": `Bearer ${token}`
          },
          body: JSON.stringify({
            messages: updatedMessages
      }),
      signal: controller.signal
    });

    if (!response.ok) {
      setLoading(false);
      setIsButtonDisabled(false);
      throw new Error(response.statusText);
    }

    const data = response.body;

    if (!data) {
      return;
    }

    setLoading(false);
    scrollToBottom();

    const reader = data.getReader();
    const decoder = new TextDecoder();
    let done = false;
    let isFirst = true;

    while (!done) {
      if(stopConversationRef.current === true){
        controller.abort();
        done = true;
        break;
      }
      const { value, done: doneReading } = await reader.read();
      done = doneReading;
      const chunkValue = decoder.decode(value);

      if (isFirst) {
        isFirst = false;
        setMessages((messages) => [
          ...messages,
          {
            role: "assistant",
            content: chunkValue
          }
        ]);
      } else {
        setMessages((messages) => {
          const lastMessage = messages[messages.length - 1];
          const updatedMessage = {
            ...lastMessage,
            content: lastMessage.content + chunkValue
          };
          return [...messages.slice(0, -1), updatedMessage];
        });
      }
    }
    setIsButtonDisabled(false);
    scrollToBottom();
  };

  const handleSave = () => {
    if(messages.length >= 2){
      handleSend({ role: "user", content: "*SAVE* " + content});
      setContent("");
    }else{
      alert("No messages to save.");
    }
  }

  const handleRevert = () => {
    stopConversationRef.current = true;
    setTimeout(() => {
      stopConversationRef.current = false;

      // console.log(messages);
      let n = messages.length;
      while( n > 0 && messages[n-1].role!="user" ){
          n--;
      }
      if (n > 0){
          setContent(messages[n-1].content);
          setMessages(messages.slice(0, n-1));
      }else{
          setContent("");
      }
      setIsButtonDisabled(false);
    }, 500);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleReset = () => {
    setMessages([]);
  };

//  useEffect(() => {
//    scrollToBottom();
//  }, [messages]);

useEffect(() => {
  const verifyUser = async () => {
    try {

      // Send a request to the /api/chat endpoint for verification
      const response = await fetch('/api/verify', {
        method: 'GET',
      });

      // If the token is invalid or the request fails, redirect to the login page
      if (!response.ok) {
        router.push('/login');
      }


    } catch (error) {
      // In case of an error, redirect to the login page
      console.error(error);
      router.push('/login');
    }
  };

  verifyUser();
}, [router]);

  return (
    <>
      <Head>
        <title>Loyal Elephie</title>
        <meta
          name="description"
          content="A simple chatbot starter kit for OpenAI's chat model using Next.js, TypeScript, and Tailwind CSS."
        />
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1"
        />
        <link
          rel="icon"
          href="/favicon.ico"
        />
      </Head>

      <div className="flex flex-col h-screen">
        <Navbar onReset={handleReset} onSave={handleSave} />

        <div className="flex-1 overflow-auto sm:px-10 pb-4 sm:pb-10">
          <div className="max-w-[1200px] mx-auto mt-4 sm:mt-12">
            <Chat
              messages={messages}
              loading={loading}
              isButtonDisabled={isButtonDisabled}
              onSend={handleSend}
              onRevert={handleRevert}
              content={content}
              setContent={setContent}
            />
            <div ref={messagesEndRef} />
          </div>
        </div>
        <Footer />
      </div>
    </>
  );
}
