import { ChatHistoryClient } from "@/components/ChatHistoryClient";

export const metadata = {
  title: "Sohbet geçmişi — Cüzdan Koçu",
};

export default function ChatHistoryPage() {
  return (
    <div className="page-enter">
      <ChatHistoryClient />
    </div>
  );
}
