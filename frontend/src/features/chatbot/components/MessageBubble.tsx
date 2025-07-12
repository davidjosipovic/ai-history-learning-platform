import { type Message } from '../types';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.sender === 'user';
  
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
        isUser 
          ? 'bg-blue-500 text-white rounded-br-none' 
          : 'bg-white dark:bg-slate-700 text-slate-800 dark:text-white rounded-bl-none border border-slate-200 dark:border-slate-600'
      }`}>
        <p className="text-sm">{message.text}</p>
        <span className={`text-xs ${isUser ? 'text-blue-100' : 'text-slate-500 dark:text-slate-400'} mt-1 block`}>
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  );
}
