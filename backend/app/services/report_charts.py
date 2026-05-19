"""PNG chart rendering for DOCX monthly reports."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import matplotlib
from matplotlib.figure import Figure

from app.services.report_types import MonthlyReportData, ReportImage

matplotlib.use("Agg")


def _png_from_figure(fig: Figure) -> bytes:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor="white")
    fig.clear()
    return buffer.getvalue()


def _lira_value(value: Decimal) -> int:
    return max(int(value), 0)


def _category_chart(data: MonthlyReportData) -> ReportImage | None:
    rows = data.category_totals[:6]
    if not rows:
        return None
    fig = Figure(figsize=(7.2, 3.6), dpi=160)
    ax = fig.add_subplot(1, 1, 1)
    labels = [row.category_name for row in rows]
    values = [_lira_value(row.amount) for row in rows]
    ax.barh(labels, values, color="#2f7d5f")
    ax.invert_yaxis()
    ax.set_title("Kategori Bazında Harcama", fontweight="bold")
    ax.set_xlabel("TL")
    ax.grid(axis="x", alpha=0.2)
    return ReportImage(
        title="Kategori harcama grafiği",
        description="Bu ayki giderlerin kategori bazında dağılımı.",
        content=_png_from_figure(fig),
    )


def _member_chart(data: MonthlyReportData) -> ReportImage | None:
    if data.scope_type != "family" or len(data.members) < 2:
        return None
    rows = data.members[:8]
    fig = Figure(figsize=(7.2, 3.6), dpi=160)
    ax = fig.add_subplot(1, 1, 1)
    labels = [row.name for row in rows]
    expenses = [_lira_value(row.expense) for row in rows]
    ax.bar(labels, expenses, color="#b8752b")
    ax.set_title("Aile Üyelerine Göre Gider", fontweight="bold")
    ax.set_ylabel("TL")
    ax.tick_params(axis="x", rotation=18)
    ax.grid(axis="y", alpha=0.2)
    return ReportImage(
        title="Aile gider grafiği",
        description="Aile üyelerinin bu ayki gider karşılaştırması.",
        content=_png_from_figure(fig),
    )


def _goal_chart(data: MonthlyReportData) -> ReportImage | None:
    rows = data.goal_summaries[:6]
    if not rows:
        return None
    fig = Figure(figsize=(7.2, 3.6), dpi=160)
    ax = fig.add_subplot(1, 1, 1)
    labels = [row.title[:28] for row in rows]
    values = [min(max(int(row.progress_percent), 0), 100) for row in rows]
    ax.barh(labels, values, color="#5a62c8")
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_title("Hedef İlerlemesi", fontweight="bold")
    ax.set_xlabel("%")
    ax.grid(axis="x", alpha=0.2)
    return ReportImage(
        title="Hedef ilerleme grafiği",
        description="Aktif birikim ve tasarruf hedeflerinin ilerleme yüzdesi.",
        content=_png_from_figure(fig),
    )


def render_report_charts(data: MonthlyReportData) -> list[ReportImage]:
    """Render deterministic charts from already-scoped report data."""
    charts = [_category_chart(data), _member_chart(data), _goal_chart(data)]
    return [chart for chart in charts if chart is not None]
