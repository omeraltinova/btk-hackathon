"""Safe AI illustration selection for monthly DOCX reports."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.services.image_gen import IllustrationService, IllustrationUnavailableError
from app.services.report_types import MonthlyReportData, ReportImage


def _provider_ready(settings: Settings) -> bool:
    if settings.llm_provider == "openrouter":
        return bool(settings.openrouter_api_key)
    return bool(settings.gemini_api_key)


def _concepts_for_report(data: MonthlyReportData, limit: int) -> list[str]:
    concepts = [
        "Türk aile bütçesi ve aylık para planı"
        if data.scope_type == "family"
        else "Kişisel aylık bütçe özeti",
    ]
    if data.category_totals:
        concepts.append(f"{data.category_totals[0].category_name} zarfı ve bilinçli harcama")
    if data.goal_summaries:
        concepts.append("Birikim hedefi, kumbara ve düzenli katkı")
    if data.subscriptions:
        concepts.append("Abonelikleri gözden geçirme ve aylık bütçe temizliği")
    return concepts[:limit]


def render_report_illustrations(
    data: MonthlyReportData,
    *,
    enabled: bool,
    settings: Settings | None = None,
) -> list[ReportImage]:
    """Generate non-personal, thematic illustrations for a report.

    The prompt intentionally uses generic concepts only. Names, amounts,
    merchants, receipt details, and raw user data never leave this process.
    """
    resolved_settings = settings or get_settings()
    if not enabled or not _provider_ready(resolved_settings):
        return []

    max_count = 3 if data.scope_type == "family" else 2
    audience = "child" if data.owner_finance_level == "child" else "adult"
    service = IllustrationService(resolved_settings)
    images: list[ReportImage] = []
    for concept in _concepts_for_report(data, max_count):
        try:
            illustration = service.illustrate(
                user_id=data.owner_user_id,
                concept=concept,
                audience=audience,
            )
        except IllustrationUnavailableError:
            continue
        images.append(
            ReportImage(
                title=concept,
                description="Rapor anlatımını güçlendiren güvenli AI illüstrasyonu.",
                content=illustration.content,
            ),
        )
    return images
