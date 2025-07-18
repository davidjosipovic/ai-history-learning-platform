import { Injectable } from '@nestjs/common';
import { ChatMessageDto, ChatResponseDto } from './dto/chat.dto';

@Injectable()
export class ChatService {
  private aiRagUrl = process.env.AI_RAG_URL || 'http://localhost:8000/ai/';

  async processMessage(chatMessage: ChatMessageDto): Promise<ChatResponseDto> {
    try {
      // Pozovi AI/RAG servis (FastAPI)
      const response = await fetch(this.aiRagUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: chatMessage.message, context: null }),
      });

      if (!response.ok) {
        throw new Error(`AI/RAG service error: ${response.status}`);
      }

      const data = await response.json();

      return {
        response: data.answer || 'No response from AI/RAG service.',
        timestamp: new Date().toISOString(),
      };
    } catch (error) {
      console.error('AI/RAG service error:', error);

      // Fallback poruka
      return {
        response: `Message received! You asked: "${chatMessage.message}". (AI/RAG service unavailable)`,
        timestamp: new Date().toISOString(),
      };
    }
  }
}