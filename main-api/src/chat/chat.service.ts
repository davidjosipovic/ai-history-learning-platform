import { Injectable } from '@nestjs/common';
import OpenAI from 'openai';
import { ChatMessageDto, ChatResponseDto } from './dto/chat.dto';

@Injectable()
export class ChatService {
  private openai: OpenAI;

  constructor() {
    this.openai = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY || '', // Make sure to set this in your .env
    });
  }

  async processMessage(chatMessage: ChatMessageDto): Promise<ChatResponseDto> {
    try {
      // Use OpenAI to generate a history-focused response
      const response = await this.openai.chat.completions.create({
        model: "gpt-4.1-nano",
        messages: [
          {
            role: "system",
            content: "You are an expert AI History assistant for the AI History Learning Platform. Your role is to provide accurate, engaging, and educational responses about historical topics. Always be informative, cite historical facts when possible, and encourage further learning. Keep responses concise but comprehensive."
          },
          {
            role: "user",
            content: chatMessage.message
          }
        ],
        max_tokens: 300,
        temperature: 0.7,
      });

      const aiResponse = response.choices[0]?.message?.content || 'I apologize, but I could not generate a response at this time.';

      return {
        response: aiResponse,
        timestamp: new Date().toISOString(),
      };
    } catch (error) {
      console.error('OpenAI API error:', error);
      
      // Fallback to our previous keyword-based system if OpenAI fails
      const fallbackResponse = this.generateHistoryResponse(chatMessage.message);
      
      return {
        response: fallbackResponse,
        timestamp: new Date().toISOString(),
      };
    }
  }

  private generateHistoryResponse(message: string): string {
    const lowerMessage = message.toLowerCase();
    
    // Simple keyword-based responses for testing (fallback)
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
