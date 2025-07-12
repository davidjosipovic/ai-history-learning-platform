export const sendMessage = async (message: string): Promise<string> => {
  try {
    const response = await fetch('http://localhost:3000/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const data = await response.json();
    return data.response || 'No response from AI';
  } catch (error) {
    console.error('Chat API error:', error);
    throw error;
  }
};

export const generateMessageId = (): string => {
  return Date.now().toString() + Math.random().toString(36).substr(2, 9);
};
