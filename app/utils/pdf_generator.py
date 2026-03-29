# Path: app/utils/pdf_generator.py
"""Генерация PDF документов. Поддерживает ReportLab (встроен) и WeasyPrint (если установлен)."""

import json
import os
from datetime import date
from io import BytesIO


def generate_contract_pdf(contract, client):
    """Генерирует PDF договора. Использует ReportLab (всегда доступен)."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Image,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2.5 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle", parent=styles["Heading1"], fontSize=16, alignment=1, spaceAfter=20
        )
        normal_style = styles["Normal"]
        normal_style.spaceAfter = 8
        brand_style = ParagraphStyle(
            "Brand",
            parent=styles["Normal"],
            fontSize=10,
            alignment=1,
            textColor=colors.HexColor("#333333"),
            spaceAfter=2,
        )

        content = []

        # Шапка бренда: логотип (если есть) + текст
        logo_path = None
        try:
            from flask import current_app

            if current_app and hasattr(current_app, "static_folder"):
                logo_path = os.path.join(current_app.static_folder, "images", "logo.png")
        except RuntimeError:
            pass
        if not logo_path or not os.path.isfile(logo_path):
            for base in ["app", "."]:
                p = os.path.join(base, "static", "images", "logo.png")
                if os.path.isfile(p):
                    logo_path = p
                    break
        if logo_path and os.path.isfile(logo_path):
            try:
                img = Image(logo_path, width=2 * cm, height=2 * cm)
                content.append(img)
                content.append(Spacer(1, 0.2 * cm))
            except Exception:
                pass
        content.append(Paragraph("<b>UtilBase</b> — часть BaseofWork", brand_style))
        content.append(Spacer(1, 0.5 * cm))

        doc_no = (getattr(contract, "document_number", None) or "").strip() or str(contract.id)
        content.append(
            Paragraph(f"ДОГОВОР № {doc_no} на обслуживание инженерных систем", title_style)
        )
        content.append(Spacer(1, 0.5 * cm))

        contract_type = contract.contract_type or "—"
        start_str = contract.start_date.strftime("%d.%m.%Y") if contract.start_date else "—"
        end_str = contract.end_date.strftime("%d.%m.%Y") if contract.end_date else "—"
        amount_str = (
            f"{contract.total_price:,.0f}".replace(",", " ") if contract.total_price else "0"
        )
        kind_map = {
            "individual": "Физическое лицо",
            "sole_proprietor": "ИП",
            "legal_entity": "Юридическое лицо",
            "commercial_household": "Комбыт",
            "government": "Госучреждение",
        }
        kind_str = kind_map.get(getattr(contract, "counterparty_kind", None) or "", "—")
        if kind_str == "—" and getattr(contract, "counterparty_kind", None):
            kind_str = contract.counterparty_kind
        conclusion_str = (
            contract.conclusion_date.strftime("%d.%m.%Y")
            if getattr(contract, "conclusion_date", None)
            else "—"
        )

        data = [
            ["Клиент:", client.full_name or "—"],
            ["Адрес:", client.address or "—"],
            ["Телефон:", client.phone or "—"],
            ["Вид контрагента:", kind_str],
            ["Тип договора (системы):", contract_type],
            ["Дата заключения:", conclusion_str],
            ["Период действия:", f"{start_str} — {end_str}"],
            ["Сумма (руб):", amount_str],
        ]
        term_note = getattr(contract, "term_note", None) or ""
        if term_note.strip():
            data.append(["Срок / условия (текст):", term_note.strip()[:2000]])
        serv_p = getattr(contract, "service_periodicity", None) or ""
        if serv_p.strip():
            data.append(["Периодичность обслуживания:", serv_p.strip()[:2000]])
        eq_scope = getattr(contract, "equipment_scope", None) or ""
        if eq_scope.strip():
            data.append(["Перечень оборудования:", eq_scope.strip()[:2000]])
        wiz_raw = getattr(contract, "maintenance_wizard_json", None) or ""
        if wiz_raw.strip():
            try:
                wiz = json.loads(wiz_raw)
            except Exception:
                wiz = None
            if isinstance(wiz, dict):
                snap = wiz.get("client_snapshot") or {}
                if (snap.get("inn") or "").strip():
                    data.append(["ИНН:", snap.get("inn", "").strip()[:32]])
                if (snap.get("kpp") or "").strip():
                    data.append(["КПП:", snap.get("kpp", "").strip()[:16]])
                addr_obj = (wiz.get("service_object_address") or "").strip()
                if addr_obj:
                    data.append(["Адрес объекта (мастер):", addr_obj[:500]])
        table = Table(data, colWidths=[4 * cm, 12 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        content.append(table)
        content.append(Spacer(1, 1 * cm))
        content.append(
            Paragraph(
                "Настоящий договор регулирует порядок обслуживания инженерных систем объекта.",
                normal_style,
            )
        )
        content.append(Spacer(1, 1.5 * cm))

        # Подписи сторон и дата
        today_str = date.today().strftime("%d.%m.%Y")
        sig_data = [
            ["Исполнитель: _________________", "Заказчик: _________________"],
            ["", ""],
            ["Дата: " + today_str, ""],
        ]
        sig_table = Table(sig_data, colWidths=[8 * cm, 8 * cm])
        sig_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        content.append(sig_table)

        doc.build(content)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        import logging

        logging.getLogger(__name__).exception(f"Ошибка генерации PDF: {e}")
        return None


def init_pdf_generator(app):
    """Инициализация генератора PDF (заглушка)."""
    pass


def generate_equipment_checklist_pdf(
    equipment, rows, prepared_by="", accepted_by="", checklist_date=None
):
    """PDF чек-листа оборудования с местом под галочки и подписями."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ChecklistTitle",
            parent=styles["Heading1"],
            fontSize=14,
            alignment=1,
            spaceAfter=10,
        )
        normal = styles["Normal"]
        normal.spaceAfter = 4

        content = []
        content.append(Paragraph("ЧЕК-ЛИСТ ОБОРУДОВАНИЯ", title_style))
        content.append(
            Paragraph(
                f"Оборудование: #{equipment.id} / {equipment.type or '—'} / {equipment.brand or '—'} / {equipment.model or '—'}",
                normal,
            )
        )
        content.append(Paragraph(f"Серийный номер: {equipment.serial_number or '—'}", normal))
        if checklist_date:
            content.append(Paragraph(f"Дата: {checklist_date}", normal))
        content.append(Spacer(1, 0.4 * cm))

        data = [["#", "Пункт проверки", "Отметка", "Комментарий"]]
        for idx, row in enumerate(rows, 1):
            text = (row.get("text") or "").strip() or f"Пункт {idx}"
            mark = "☑" if row.get("checked") else "□"
            comment = (row.get("comment") or "").strip()
            data.append([str(idx), text, mark, comment])

        table = Table(data, colWidths=[1.2 * cm, 10.3 * cm, 2.0 * cm, 4.0 * cm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("ALIGN", (2, 1), (2, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f5f5")),
                    ("ROWHEIGHT", (0, 1), (-1, -1), 18),
                ]
            )
        )
        content.append(table)
        content.append(Spacer(1, 0.8 * cm))

        sig_data = [
            [
                "Подготовил:",
                prepared_by or "__________________________",
                "Принял:",
                accepted_by or "__________________________",
            ],
            ["Подпись:", "__________________________", "Подпись:", "__________________________"],
        ]
        sig_table = Table(sig_data, colWidths=[2.5 * cm, 5.5 * cm, 2.5 * cm, 5.5 * cm])
        sig_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        content.append(sig_table)

        doc.build(content)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Ошибка генерации PDF чек-листа оборудования")
        return None
