from io import BytesIO
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)


# ── Palette ──────────────────────────────────────────────────────────────────
PRIMARY  = colors.HexColor('#1a1a2e')
ACCENT   = colors.HexColor('#4f46e5')
LIGHT_BG = colors.HexColor('#f8f8ff')
BORDER   = colors.HexColor('#e2e8f0')
MUTED    = colors.HexColor('#64748b')


def _styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'title', parent=base['Title'],
            fontSize=22, textColor=PRIMARY, spaceAfter=4,
        ),
        'subtitle': ParagraphStyle(
            'subtitle', parent=base['Normal'],
            fontSize=11, textColor=MUTED, spaceAfter=12,
        ),
        'section': ParagraphStyle(
            'section', parent=base['Heading2'],
            fontSize=13, textColor=ACCENT,
            spaceBefore=16, spaceAfter=6,
            borderPad=0,
        ),
        'normal': ParagraphStyle(
            'normal', parent=base['Normal'],
            fontSize=9, textColor=PRIMARY, spaceAfter=3,
        ),
        'muted': ParagraphStyle(
            'muted', parent=base['Normal'],
            fontSize=8, textColor=MUTED, spaceAfter=2,
        ),
        'footer': ParagraphStyle(
            'footer', parent=base['Normal'],
            fontSize=8, textColor=MUTED, alignment=1,
        ),
    }


def _table_style(header_color=ACCENT):
    return TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0),  header_color),
        ('TEXTCOLOR',   (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0),  9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING',    (0, 0), (-1, 0), 6),
        ('BACKGROUND',  (0, 1), (-1, -1), LIGHT_BG),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ('FONTNAME',    (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',    (0, 1), (-1, -1), 8),
        ('TOPPADDING',    (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('GRID',        (0, 0), (-1, -1), 0.4, BORDER),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
    ])


def generate_vehicle_pdf(vehicle, events, accessories) -> bytes:
    """Build a PDF summary for a vehicle and return it as bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=f"Informe {vehicle.brand} {vehicle.model}",
    )

    s = _styles()
    page_w = A4[0] - 4 * cm  # usable width
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph(f"{vehicle.brand} {vehicle.model} ({vehicle.year})", s['title']))
    vehicle_type = 'Motocicleta' if vehicle.vehicle_type == 'motorcycle' else 'Coche'
    usage_map = {'city': 'Ciudad', 'mixed': 'Mixto', 'highway': 'Carretera'}
    usage = usage_map.get(vehicle.usage_type, vehicle.usage_type)
    displacement = f" · {vehicle.displacement} cc" if vehicle.displacement else ''
    story.append(Paragraph(
        f"{vehicle_type}{displacement} · {usage} · {vehicle.current_km:,} km actuales",
        s['subtitle'],
    ))
    if vehicle.notes:
        story.append(Paragraph(vehicle.notes, s['muted']))
    story.append(HRFlowable(width='100%', thickness=1, color=ACCENT, spaceAfter=8))

    # ── Historial de mantenimiento ────────────────────────────────────────────
    story.append(Paragraph("Historial de mantenimiento", s['section']))
    if events:
        rows = [['Fecha', 'Tarea', 'Km', 'Coste', 'Notas']]
        for ev in events:
            task_name = ev.task_code
            rows.append([
                ev.date.strftime('%d/%m/%Y'),
                Paragraph(task_name, s['normal']),
                f"{ev.km_at_service:,}",
                f"{ev.cost} €" if ev.cost else '—',
                Paragraph(ev.notes or '—', s['muted']),
            ])
        col_w = [page_w * r for r in [0.14, 0.26, 0.13, 0.12, 0.35]]
        t = Table(rows, colWidths=col_w)
        t.setStyle(_table_style())
        story.append(t)

        total_cost = sum(float(ev.cost) for ev in events if ev.cost)
        if total_cost:
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"<b>Coste total en mantenimiento: {total_cost:,.2f} €</b>",
                s['muted'],
            ))
    else:
        story.append(Paragraph("Sin eventos registrados.", s['muted']))

    # ── Accesorios ────────────────────────────────────────────────────────────
    story.append(Paragraph("Accesorios instalados", s['section']))
    if accessories:
        rows = [['Accesorio', 'Precio', 'Notas']]
        for a in accessories:
            price_str = f"{float(a.price):,.2f} €" if a.price else '—'
            rows.append([
                Paragraph(a.name, s['normal']),
                price_str,
                Paragraph(a.notes or '—', s['muted']),
            ])
        col_w = [page_w * r for r in [0.35, 0.18, 0.47]]
        t = Table(rows, colWidths=col_w)
        t.setStyle(_table_style(header_color=colors.HexColor('#7c3aed')))
        story.append(t)

        total_acc = sum(float(a.price) for a in accessories if a.price)
        if total_acc:
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"<b>Total invertido en accesorios: {total_acc:,.2f} €</b>",
                s['muted'],
            ))
    else:
        story.append(Paragraph("Sin accesorios registrados.", s['muted']))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Informe generado el {date.today().strftime('%d/%m/%Y')} · WrenchBuddy",
        s['footer'],
    ))

    doc.build(story)
    return buf.getvalue()
