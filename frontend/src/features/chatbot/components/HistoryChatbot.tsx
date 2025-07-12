import { useState, useRef, useEffect } from 'react';
import { type Message } from '../types';
import { sendMessage, generateMessageId } from '../api';
import { MessageBubble } from './MessageBubble';
import { ChatInput } from './ChatInput';

export function HistoryChatbot() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: generateMessageId(),
      text: "Hello! I'm your AI History assistant. Ask me anything about historical events, figures, or periods!",
      sender: 'bot',
      timestamp: new Date(),
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (text: string) => {
    const userMessage: Message = {
      id: generateMessageId(),
      text,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    try {
      const response = await sendMessage(text);
      const botMessage: Message = {
        id: generateMessageId(),
        text: response,
        sender: 'bot',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, botMessage]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      const errorMessage: Message = {
        id: generateMessageId(),
        text: "Sorry, I'm having trouble connecting to my knowledge base right now. Please try again later.",
        sender: 'bot',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto bg-white dark:bg-slate-900 rounded-lg shadow-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
      <div className="bg-gradient-to-r from-blue-500 to-purple-600 p-4">
        <h2 className="text-xl font-bold text-white">AI History Chatbot</h2>
        <p className="text-blue-100 text-sm">Ask me anything about history!</p>
      </div>
      
      <div className="h-96 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {isLoading && (
          <div className="flex justify-start mb-4">
            <div className="max-w-xs bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg rounded-bl-none px-4 py-2">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
          </div>
        )}
        {error && (
          <div className="text-center text-red-500 text-sm">
            Error: {error}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
    </div>
  );
}
