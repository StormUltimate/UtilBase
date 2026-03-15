# Path: app/utils/pdf_generator.py
"""Генерация PDF документов. Поддерживает ReportLab (встроен) и WeasyPrint (если установлен)."""
from io import BytesIO
from datetime import date
import os


def generate_contract_pdf(contract, client):
    """Генерирует PDF договора. Использует ReportLab (всегда доступен)."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib import colors

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm, topMargin=2.5*cm, bottomMargin=2*cm
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=1,
            spaceAfter=20
        )
        normal_style = styles['Normal']
        normal_style.spaceAfter = 8
        brand_style = ParagraphStyle(
            'Brand',
            parent=styles['Normal'],
            fontSize=10,
            alignment=1,
            textColor=colors.HexColor('#333333'),
            spaceAfter=2
        )

        content = []

        # Шапка бренда: логотип (если есть) + текст
        logo_path = None
        try:
            from flask import current_app
            if current_app and hasattr(current_app, 'static_folder'):
                logo_path = os.path.join(current_app.static_folder, 'images', 'logo.png')
        except RuntimeError:
            pass
        if not logo_path or not os.path.isfile(logo_path):
            for base in ['app', '.']:
                p = os.path.join(base, 'static', 'images', 'logo.png')
                if os.path.isfile(p):
                    logo_path = p
                    break
        if logo_path and os.path.isfile(logo_path):
            try:
                img = Image(logo_path, width=2*cm, height=2*cm)
                content.append(img)
                content.append(Spacer(1, 0.2*cm))
            except Exception:
                pass
        content.append(Paragraph(
            "<b>UtilBase</b> — часть BaseofWork",
            brand_style
        ))
        content.append(Spacer(1, 0.5*cm))

        content.append(Paragraph(
            f"ДОГОВОР № {contract.id} на обслуживание инженерных систем",
            title_style
        ))
        content.append(Spacer(1, 0.5*cm))

        contract_type = contract.contract_type or '—'
        start_str = contract.start_date.strftime('%d.%m.%Y') if contract.start_date else '—'
        end_str = contract.end_date.strftime('%d.%m.%Y') if contract.end_date else '—'
        amount_str = f"{contract.total_price:,.0f}".replace(',', ' ') if contract.total_price else '0'

        data = [
            ['Клиент:', client.full_name or '—'],
            ['Адрес:', client.address or '—'],
            ['Телефон:', client.phone or '—'],
            ['Тип договора:', contract_type],
            ['Период действия:', f"{start_str} — {end_str}"],
            ['Сумма (руб):', amount_str],
        ]
        table = Table(data, colWidths=[4*cm, 12*cm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        content.append(table)
        content.append(Spacer(1, 1*cm))
        content.append(Paragraph(
            "Настоящий договор регулирует порядок обслуживания инженерных систем объекта.",
            normal_style
        ))
        content.append(Spacer(1, 1.5*cm))

        # Подписи сторон и дата
        today_str = date.today().strftime('%d.%m.%Y')
        sig_data = [
            ['Исполнитель: _________________', 'Заказчик: _________________'],
            ['', ''],
            ['Дата: ' + today_str, ''],
        ]
        sig_table = Table(sig_data, colWidths=[8*cm, 8*cm])
        sig_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
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
