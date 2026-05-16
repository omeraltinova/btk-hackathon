import { MemoryViewer } from "@/components/MemoryViewer";

export const metadata = {
  title: "Koç hafızası — Cüzdan Koçu",
};

export default function MemoryPage() {
  return (
    <div className="page-enter">
      <MemoryViewer />
    </div>
  );
}
