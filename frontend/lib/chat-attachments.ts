import type { ChatChartSpec, ChatToolPayload, ConversationAttachment } from "@/lib/types";

export type ChatAttachmentItem =
  | {
      id: string;
      type: "chart";
      spec: ChatChartSpec;
    }
  | {
      id: string;
      type: "image";
      imageUrl: string;
      altText: string;
    }
  | {
      id: string;
      type: "report";
      reportId: string;
      downloadUrl: string;
      filename: string;
      title: string;
      format: string;
    };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readChartType(value: unknown): ChatChartSpec["type"] | null {
  if (value === "pie") return "pie";
  if (value === "bar") return "bar";
  if (value === "monthly") return "monthly";
  return null;
}

export function extractChart(result: ChatToolPayload): ChatChartSpec | null {
  const candidate = result.chart;
  if (!isRecord(candidate)) return null;
  const type = readChartType(candidate.type);
  if (!type) return null;
  if (typeof candidate.title !== "string") return null;
  if (!Array.isArray(candidate.data)) return null;
  const points: ChatChartSpec["data"] = [];
  for (const entry of candidate.data) {
    if (!isRecord(entry)) continue;
    const label = typeof entry.label === "string" ? entry.label : null;
    const rawValue = entry.value;
    const value =
      typeof rawValue === "number"
        ? rawValue
        : typeof rawValue === "string"
          ? Number(rawValue)
          : null;
    const valueFormatted = typeof entry.value_formatted === "string" ? entry.value_formatted : null;
    if (label === null || value === null || !Number.isFinite(value) || valueFormatted === null) {
      continue;
    }
    points.push({
      label,
      value,
      value_formatted: valueFormatted,
      series: typeof entry.series === "string" ? entry.series : null,
    });
  }
  if (points.length === 0) return null;
  return {
    type,
    title: candidate.title,
    subtitle: typeof candidate.subtitle === "string" ? candidate.subtitle : null,
    data: points,
    value_label: typeof candidate.value_label === "string" ? candidate.value_label : null,
    currency: typeof candidate.currency === "string" ? candidate.currency : null,
  };
}

export function chatAttachmentsFromHistory(
  attachments: ConversationAttachment[],
): ChatAttachmentItem[] {
  const items: ChatAttachmentItem[] = [];
  attachments.forEach((attachment, index) => {
    if (attachment.type === "chart" && attachment.chart) {
      const chart = extractChart({ chart: attachment.chart });
      if (chart) items.push({ id: `chart-${index}`, type: "chart", spec: chart });
      return;
    }
    if (attachment.type === "image" && attachment.image_url) {
      items.push({
        id: `image-${index}`,
        type: "image",
        imageUrl: attachment.image_url,
        altText: attachment.alt_text ?? "Finansal kavram görseli",
      });
      return;
    }
    if (attachment.type === "report" && attachment.report_id && attachment.download_url) {
      items.push({
        id: `report-${index}`,
        type: "report",
        reportId: attachment.report_id,
        downloadUrl: attachment.download_url,
        filename: attachment.filename,
        title: attachment.title ?? "Aylık Koç Raporu",
        format: attachment.format ?? "docx",
      });
    }
  });
  return items;
}
