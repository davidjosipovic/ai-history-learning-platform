import { Controller, Post, Body, HttpCode, HttpStatus } from '@nestjs/common';
import { ChatService } from './chat.service';
import { ChatMessageDto, ChatResponseDto } from './dto/chat.dto';

@Controller('api/chat')
export class ChatController {
  constructor(private readonly chatService: ChatService) {}

  @Post()
  @HttpCode(HttpStatus.OK)
  async sendMessage(@Body() chatMessage: ChatMessageDto): Promise<ChatResponseDto> {
    return this.chatService.processMessage(chatMessage);
  }
}
