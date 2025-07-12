export interface Message {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
}

export interface ChatbotState {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
}
