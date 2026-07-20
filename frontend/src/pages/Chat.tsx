import { useSearchParams } from "react-router-dom";

import ChatPanel from "@/components/ChatPanel";

export default function ChatPage() {
  const [searchParams] = useSearchParams();
  const prompt = searchParams.get("prompt") ?? undefined;
  const voice = searchParams.get("voice") === "1";

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-hidden p-4">
      <ChatPanel autoPrompt={prompt} autoVoice={voice} />
    </main>
  );
}
