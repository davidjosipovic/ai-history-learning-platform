import { useState } from 'react';
import { Button } from '@/components/ui/button';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isLoading: boolean;
}

export function ChatInput({ onSendMessage, isLoading }: ChatInputProps) {
  const [input, setInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input.trim());
      setInput('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 p-4 bg-white dark:bg-slate-800 border-t border-slate-200 dark:border-slate-700">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Ask me about history..."
        disabled={isLoading}
        className="flex-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-slate-700 dark:text-white"
      />
      <Button 
        type="submit" 
        disabled={!input.trim() || isLoading}
        className="px-4 py-2"
      >
        {isLoading ? 'Sending...' : 'Send'}
      </Button>
    </form>
  );
}
