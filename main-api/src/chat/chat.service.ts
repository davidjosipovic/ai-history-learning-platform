import { Injectable } from '@nestjs/common';
import { ChatMessageDto, ChatResponseDto } from './dto/chat.dto';

@Injectable()
export class ChatService {
  async processMessage(chatMessage: ChatMessageDto): Promise<ChatResponseDto> {
    // For now, we'll send a confirmation message
    // Later this can be enhanced with actual AI integration
    const response = this.generateHistoryResponse(chatMessage.message);
    
    return {
      response,
      timestamp: new Date().toISOString(),
    };
  }

  private generateHistoryResponse(message: string): string {
    const lowerMessage = message.toLowerCase();
    
    // Simple keyword-based responses for testing
    if (lowerMessage.includes('hello') || lowerMessage.includes('hi')) {
      return "Hello! I'm your AI History assistant. I've received your message and I'm ready to help you explore the fascinating world of history!";
    }
    
    if (lowerMessage.includes('rome') || lowerMessage.includes('roman')) {
      return "Message received! The Roman Empire was one of the most influential civilizations in history, lasting from 27 BC to 476/1453 AD. What specific aspect of Roman history would you like to explore?";
    }
    
    if (lowerMessage.includes('egypt') || lowerMessage.includes('pyramid')) {
      return "Message received! Ancient Egypt is fascinating! The pyramids of Giza were built around 2580-2510 BC and remain one of the Seven Wonders of the Ancient World. What would you like to know more about?";
    }
    
    if (lowerMessage.includes('world war') || lowerMessage.includes('ww')) {
      return "Message received! World Wars were pivotal events in modern history. World War I (1914-1918) and World War II (1939-1945) shaped the 20th century. Which aspects interest you most?";
    }
    
    // Default response confirming message receipt
    return `Message received! You asked: "${message}". I'm processing your history question and will provide you with detailed historical information. This is a confirmation that your message was successfully received by the AI History Learning Platform!`;
  }
}
