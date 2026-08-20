"""
Generation de documents PDF brandes INTELYA HAVEN (recus de loyer,
mandats de gestion, etc.) -- reportlab est deja une dependance du projet.
"""
import io
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

BRAND_COLOR = colors.HexColor('#0F4C3A')
BRAND_NAME = getattr(settings, 'PLATFORM_NAME', 'INTELYA HAVEN')


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='BrandTitle', fontSize=20, textColor=BRAND_COLOR,
        fontName='Helvetica-Bold', spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name='DocTitle', fontSize=14, spaceBefore=10, spaceAfter=10,
        fontName='Helvetica-Bold',
    ))
    styles.add(ParagraphStyle(
        name='Small', fontSize=8, textColor=colors.grey,
    ))
    return styles


def _header(elements, styles, document_title, reference):
    elements.append(Paragraph(BRAND_NAME, styles['BrandTitle']))
    elements.append(Paragraph("Marché immobilier numérique", styles['Small']))
    elements.append(Spacer(1, 8 * mm))
    elements.append(HRFlowable(width="100%", color=BRAND_COLOR, thickness=1.5))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph(document_title, styles['DocTitle']))
    elements.append(Paragraph(f"Référence : {reference}", styles['Small']))
    elements.append(Spacer(1, 6 * mm))


def _footer_note(elements, styles):
    elements.append(Spacer(1, 10 * mm))
    elements.append(HRFlowable(width="100%", color=colors.lightgrey, thickness=0.5))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        f"Document généré automatiquement par {BRAND_NAME}. "
        f"En cas de litige, référez-vous au numéro de référence ci-dessus.",
        styles['Small']
    ))


def _kv_table(rows):
    table = Table(rows, colWidths=[60 * mm, 100 * mm])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.lightgrey),
    ]))
    return table


def build_pdf(document_title, reference, sections):
    """sections : liste de (titre_section_ou_None, liste_de_paires_cle_valeur).
    Retourne les bytes du PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )
    styles = _styles()
    elements = []
    _header(elements, styles, document_title, reference)

    for section_title, rows in sections:
        if section_title:
            elements.append(Paragraph(section_title, styles['Heading3']))
            elements.append(Spacer(1, 2 * mm))
        elements.append(_kv_table(rows))
        elements.append(Spacer(1, 6 * mm))

    _footer_note(elements, styles)
    doc.build(elements)
    return buffer.getvalue()
