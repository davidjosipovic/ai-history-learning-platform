
import { Layout } from '@/components/layout/Layout';
import { HistoryChatbot } from '@/features/chatbot';

function App() {
  return (
    <Layout>
      <div className="space-y-8">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-slate-800 dark:text-white mb-4">
            Welcome to AI History Learning Platform
          </h2>
          <p className="text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
            Explore history through AI-powered conversations. Ask questions about historical events, 
            famous figures, ancient civilizations, and more!
          </p>
        </div>
        
        <HistoryChatbot />
      </div>
    </Layout>
  );
}

export default App;
