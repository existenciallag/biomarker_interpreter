# report_generator.py
# Genera el informe PDF a partir de un PanelResult (scoring) o dict LLM

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os

# ─── Paleta de colores ───────────────────────────────────────────────────
class P:
    teal800   = colors.HexColor("#085041")
    teal600   = colors.HexColor("#0F6E56")
    teal200   = colors.HexColor("#5DCAA5")
    teal50    = colors.HexColor("#E1F5EE")
    purple800 = colors.HexColor("#3C3489")
    purple600 = colors.HexColor("#534AB7")
    purple50  = colors.HexColor("#EEEDFE")
    amber600  = colors.HexColor("#854F0B")
    amber50   = colors.HexColor("#FAEEDA")
    amber100  = colors.HexColor("#FAC775")
    blue800   = colors.HexColor("#0C447C")
    blue50    = colors.HexColor("#E6F1FB")
    green800  = colors.HexColor("#27500A")
    green600  = colors.HexColor("#3B6D11")
    green50   = colors.HexColor("#EAF3DE")
    red600    = colors.HexColor("#A32D2D")
    red50     = colors.HexColor("#FCEBEB")
    coral600  = colors.HexColor("#993C1D")
    coral50   = colors.HexColor("#FAECE7")
    gray100   = colors.HexColor("#D3D1C7")
    gray50    = colors.HexColor("#F1EFE8")
    white     = colors.white
    black     = colors.HexColor("#1A1A1A")

NIVEL_COLORES = {
    "Óptimo":    (P.green50,   P.green800),
    "Bueno":     (P.teal50,    P.teal800),
    "Atención":  (P.amber50,   P.amber600),
    "Riesgo":    (P.coral50,   P.coral600),
    "Crítico":   (P.red50,     P.red600),
}

CAT_DISPLAY = {
    "inflamacion":          "Inflamación sistémica",
    "metabolismo_glucemico":"Metabolismo glucémico",
    "lipidos":              "Perfil lipídico",
    "hierro":               "Metabolismo del hierro",
    "metilacion":           "Vía de metilación",
    "hepatico":             "Función hepática",
    "tiroideo":             "Función tiroidea",
    "hormonas":             "Hormonas y ejes",
}

# ─── Estilos de párrafo ───────────────────────────────────────────────────
def build_styles():
    return {
        "title": ParagraphStyle("title",
            fontName="Helvetica-Bold", fontSize=22,
            textColor=P.white, alignment=TA_LEFT, leading=26),
        "subtitle": ParagraphStyle("subtitle",
            fontName="Helvetica", fontSize=11,
            textColor=P.teal200, alignment=TA_LEFT, leading=16),
        "section_title": ParagraphStyle("section_title",
            fontName="Helvetica-Bold", fontSize=13,
            textColor=P.teal800, spaceBefore=14, spaceAfter=6, leading=18),
        "cat_title": ParagraphStyle("cat_title",
            fontName="Helvetica-Bold", fontSize=11,
            textColor=P.white, alignment=TA_LEFT, leading=14),
        "body": ParagraphStyle("body",
            fontName="Helvetica", fontSize=9.5,
            textColor=P.black, leading=14, spaceAfter=4, alignment=TA_JUSTIFY),
        "body_small": ParagraphStyle("body_small",
            fontName="Helvetica", fontSize=8.5,
            textColor=P.black, leading=12),
        "body_bold": ParagraphStyle("body_bold",
            fontName="Helvetica-Bold", fontSize=9.5,
            textColor=P.black, leading=14),
        "label": ParagraphStyle("label",
            fontName="Helvetica-Bold", fontSize=8,
            textColor=P.gray100, leading=11, spaceAfter=1),
        "value": ParagraphStyle("value",
            fontName="Helvetica-Bold", fontSize=16,
            textColor=P.teal800, leading=20),
        "meta": ParagraphStyle("meta",
            fontName="Helvetica", fontSize=8.5,
            textColor=P.gray100, leading=12),
        "alerta": ParagraphStyle("alerta",
            fontName="Helvetica-Bold", fontSize=9,
            textColor=P.red600, leading=13),
        "patron_title": ParagraphStyle("patron_title",
            fontName="Helvetica-Bold", fontSize=9.5,
            textColor=P.purple800, leading=13),
        "narrativa": ParagraphStyle("narrativa",
            fontName="Helvetica", fontSize=9.5,
            textColor=P.black, leading=15, spaceAfter=6, alignment=TA_JUSTIFY,
            firstLineIndent=12),
        "footer": ParagraphStyle("footer",
            fontName="Helvetica", fontSize=7.5,
            textColor=P.gray100, alignment=TA_CENTER),
    }

# ─── Header / Footer en canvas ──────────────────────────────────────────
def _header_footer(canvas, doc, paciente_id, fecha_str, modo):
    W, H = A4
    # Header bar
    canvas.saveState()
    canvas.setFillColor(P.teal800)
    canvas.rect(0, H - 1.4*cm, W, 1.4*cm, fill=1, stroke=0)
    canvas.setFillColor(P.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(1.5*cm, H - 0.9*cm, "INFORME DE LONGEVIDAD — MEDICINA 3.0")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(W - 1.5*cm, H - 0.9*cm, f"Paciente: {paciente_id}  |  {fecha_str}  |  Modo: {modo.upper()}")
    # Footer
    canvas.setFillColor(P.gray50)
    canvas.rect(0, 0, W, 1.0*cm, fill=1, stroke=0)
    canvas.setFillColor(P.gray100)
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(W/2, 0.38*cm,
        "Informe generado automáticamente. Requiere revisión y firma de profesional habilitado antes de su entrega al paciente.")
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawRightString(W - 1.5*cm, 0.38*cm, f"Página {doc.page}")
    canvas.restoreState()

# ─── Portada ─────────────────────────────────────────────────────────────
def build_cover(story, styles, panel_result, modo):
    W = A4[0] - 3*cm
    pr = panel_result

    # Bloque de header
    bg_color = P.teal800
    cover_data = [[
        Paragraph(f"INFORME DE LONGEVIDAD", styles["title"]),
        ""
    ]]
    cover_table = Table(cover_data, colWidths=[W * 0.7, W * 0.3])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg_color),
        ("TOPPADDING",    (0,0), (-1,-1), 18),
        ("BOTTOMPADDING", (0,0), (-1,-1), 18),
        ("LEFTPADDING",   (0,0), (-1,-1), 18),
        ("RIGHTPADDING",  (0,0), (-1,-1), 12),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [bg_color]),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 0.4*cm))

    # Datos del paciente
    sexo_label = "Masculino" if pr.sexo == "M" else "Femenino"
    meta_data = [
        ["Paciente ID",    pr.paciente_id, "Fecha análisis",  pr.fecha],
        ["Edad",           f"{pr.edad} años", "Sexo",          sexo_label],
        ["Modo interpretación", modo.upper(), "Análisis previo",
         "Sí" if pr.tiene_longitudinal else "No"],
    ]
    meta_table = Table(meta_data, colWidths=[3.5*cm, 5*cm, 3.5*cm, 5*cm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
        ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",  (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,-1), P.teal800),
        ("TEXTCOLOR", (2,0), (2,-1), P.teal800),
        ("BACKGROUND",(0,0), (-1,-1), P.gray50),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [P.gray50, P.white]),
        ("TOPPADDING",    (0,0),(-1,-1), 7),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("GRID", (0,0), (-1,-1), 0.3, P.gray100),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.5*cm))

    # Score global + edad biológica
    sg_bg, sg_text = NIVEL_COLORES.get(pr.score_global, (P.gray50, P.black))
    score_data = [
        [
            Paragraph("SCORE GLOBAL", ParagraphStyle("", fontName="Helvetica-Bold",
                fontSize=8, textColor=P.gray100, leading=11)),
            Paragraph("EDAD BIOLÓGICA ESTIMADA", ParagraphStyle("", fontName="Helvetica-Bold",
                fontSize=8, textColor=P.gray100, leading=11)),
        ],
        [
            Paragraph(pr.score_global, ParagraphStyle("", fontName="Helvetica-Bold",
                fontSize=18, textColor=sg_text, leading=22)),
            Paragraph(pr.edad_biologica_estimada, ParagraphStyle("", fontName="Helvetica",
                fontSize=9, textColor=P.black, leading=13)),
        ]
    ]
    score_table = Table(score_data, colWidths=[4*cm, W - 4*cm])
    score_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (0,-1), sg_bg),
        ("BACKGROUND",    (1,0), (1,-1), P.blue50),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("GRID",          (0,0), (-1,-1), 0.3, P.gray100),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 0.6*cm))

    # Alertas críticas (si las hay)
    if pr.alertas:
        story.append(Paragraph("⚠ ALERTAS CRÍTICAS", styles["section_title"]))
        for a in pr.alertas:
            alert_row = [[
                Paragraph(f"{a.nombre}: {a.valor} — {a.nota_alerta}",
                    ParagraphStyle("", fontName="Helvetica-Bold", fontSize=9,
                        textColor=P.red600, leading=13))
            ]]
            at = Table(alert_row, colWidths=[W])
            at.setStyle(TableStyle([
                ("BACKGROUND", (0,0),(-1,-1), P.red50),
                ("TOPPADDING", (0,0),(-1,-1), 7),
                ("BOTTOMPADDING",(0,0),(-1,-1), 7),
                ("LEFTPADDING",(0,0),(-1,-1), 10),
                ("LINEABOVE",  (0,0),(-1,0), 1.5, P.red600),
            ]))
            story.append(at)
            story.append(Spacer(1, 0.15*cm))

# ─── Tabla de resumen de categorías ──────────────────────────────────────
def build_category_summary(story, styles, panel_result):
    W = A4[0] - 3*cm
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("Resumen por categoría", styles["section_title"]))

    header = [
        Paragraph("Categoría", ParagraphStyle("", fontName="Helvetica-Bold",
            fontSize=8.5, textColor=P.white)),
        Paragraph("Score", ParagraphStyle("", fontName="Helvetica-Bold",
            fontSize=8.5, textColor=P.white, alignment=TA_CENTER)),
        Paragraph("Biomarcadores evaluados", ParagraphStyle("", fontName="Helvetica-Bold",
            fontSize=8.5, textColor=P.white)),
        Paragraph("Hallazgo principal", ParagraphStyle("", fontName="Helvetica-Bold",
            fontSize=8.5, textColor=P.white)),
    ]

    rows = [header]
    for cat in panel_result.categorias:
        bg, fg = NIVEL_COLORES.get(cat.score, (P.gray50, P.black))
        nombres = ", ".join([b.nombre for b in cat.biomarcadores if b.valor is not None])
        # Hallazgo = el peor biomarcador
        peor = max([b for b in cat.biomarcadores if b.valor is not None and b.clasificacion],
                   key=lambda b: NIVEL_COLORES.get(b.clasificacion, (None,None)) and
                       ["Óptimo","Bueno","Atención","Riesgo","Crítico"].index(b.clasificacion) if b.clasificacion else 0,
                   default=None)
        hallazgo = f"{peor.nombre}: {peor.valor} {peor.unidad}" if peor else "—"

        rows.append([
            Paragraph(cat.nombre_display, ParagraphStyle("", fontName="Helvetica", fontSize=9, textColor=P.black)),
            Paragraph(cat.score,  ParagraphStyle("", fontName="Helvetica-Bold", fontSize=9,
                textColor=fg, alignment=TA_CENTER)),
            Paragraph(nombres,    ParagraphStyle("", fontName="Helvetica", fontSize=8.5, textColor=P.black)),
            Paragraph(hallazgo,   ParagraphStyle("", fontName="Helvetica-Bold", fontSize=8.5,
                textColor=P.black)),
        ])

    t = Table(rows, colWidths=[3.8*cm, 2.2*cm, 6*cm, 5.5*cm])
    style_cmds = [
        ("BACKGROUND",    (0,0), (-1,0), P.teal800),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [P.white, P.gray50]),
        ("GRID",          (0,0), (-1,-1), 0.3, P.gray100),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]
    # Colorear fila de score
    for i, cat in enumerate(panel_result.categorias, 1):
        bg, _ = NIVEL_COLORES.get(cat.score, (P.gray50, P.black))
        style_cmds.append(("BACKGROUND", (1,i), (1,i), bg))

    t.setStyle(TableStyle(style_cmds))
    story.append(t)

# ─── Tabla de biomarcadores por categoría ────────────────────────────────
def build_biomarkers_detail(story, styles, panel_result):
    W = A4[0] - 3*cm
    story.append(PageBreak())
    story.append(Paragraph("Detalle de biomarcadores", styles["section_title"]))

    for cat in panel_result.categorias:
        cat_bg, _ = NIVEL_COLORES.get(cat.score, (P.teal800, P.white))

        header_row = [
            Paragraph(f"  {cat.nombre_display}", ParagraphStyle("", fontName="Helvetica-Bold",
                fontSize=10, textColor=P.white)),
            Paragraph(cat.score, ParagraphStyle("", fontName="Helvetica-Bold",
                fontSize=10, textColor=P.white, alignment=TA_CENTER)),
            "", "", "", ""
        ]

        bio_header = [
            Paragraph("Biomarcador", ParagraphStyle("",fontName="Helvetica-Bold",fontSize=8,textColor=P.teal800)),
            Paragraph("Valor", ParagraphStyle("",fontName="Helvetica-Bold",fontSize=8,textColor=P.teal800,alignment=TA_CENTER)),
            Paragraph("Unidad", ParagraphStyle("",fontName="Helvetica-Bold",fontSize=8,textColor=P.teal800)),
            Paragraph("Clasificación", ParagraphStyle("",fontName="Helvetica-Bold",fontSize=8,textColor=P.teal800,alignment=TA_CENTER)),
            Paragraph("Rango longevidad", ParagraphStyle("",fontName="Helvetica-Bold",fontSize=8,textColor=P.teal800)),
            Paragraph("Δ vs anterior", ParagraphStyle("",fontName="Helvetica-Bold",fontSize=8,textColor=P.teal800,alignment=TA_CENTER)),
        ]

        rows = [header_row, bio_header]

        for b in cat.biomarcadores:
            if b.valor is None:
                continue
            bg, fg = NIVEL_COLORES.get(b.clasificacion, (P.white, P.black))

            delta_str = "—"
            if b.delta is not None:
                signo = "+" if b.delta > 0 else ""
                arrow = "↑" if b.delta > 0 else ("↓" if b.delta < 0 else "→")
                delta_str = f"{arrow} {signo}{b.delta:.1f}"
                if b.tendencia:
                    delta_str += f"\n{b.tendencia}"

            rows.append([
                Paragraph(b.nombre, ParagraphStyle("",fontName="Helvetica",fontSize=9,textColor=P.black)),
                Paragraph(str(b.valor), ParagraphStyle("",fontName="Helvetica-Bold",fontSize=10,
                    textColor=fg, alignment=TA_CENTER)),
                Paragraph(b.unidad, ParagraphStyle("",fontName="Helvetica",fontSize=8.5,textColor=P.black)),
                Paragraph(b.clasificacion or "—", ParagraphStyle("",fontName="Helvetica-Bold",fontSize=8.5,
                    textColor=fg, alignment=TA_CENTER)),
                Paragraph(b.rango_longevidad, ParagraphStyle("",fontName="Helvetica",fontSize=7.5,
                    textColor=P.black)),
                Paragraph(delta_str, ParagraphStyle("",fontName="Helvetica",fontSize=8,
                    textColor=P.teal600, alignment=TA_CENTER)),
            ])

        col_w = [4*cm, 1.8*cm, 1.6*cm, 2.4*cm, 5.4*cm, 2.3*cm]
        t = Table(rows, colWidths=col_w)

        style_cmds = [
            # Header de categoría
            ("BACKGROUND",    (0,0), (-1,0), P.teal800),
            ("SPAN",          (0,0), (-1,0)),
            # Sub-header
            ("BACKGROUND",    (0,1), (-1,1), P.teal50),
            ("LINEBELOW",     (0,1), (-1,1), 0.5, P.teal200),
            # Datos
            ("ROWBACKGROUNDS",(0,2), (-1,-1), [P.white, P.gray50]),
            ("GRID",          (0,0), (-1,-1), 0.3, P.gray100),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 7),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ]
        # Colorear fondo de columna clasificación
        for i, b in enumerate([b for b in cat.biomarcadores if b.valor is not None], 2):
            bg, _ = NIVEL_COLORES.get(b.clasificacion, (P.white, P.black))
            style_cmds.append(("BACKGROUND", (3,i), (3,i), bg))
            style_cmds.append(("BACKGROUND", (1,i), (1,i), bg))

        t.setStyle(TableStyle(style_cmds))
        story.append(KeepTogether([t, Spacer(1, 0.4*cm)]))

# ─── Patrones intersistema ────────────────────────────────────────────────
def build_patterns(story, styles, panel_result):
    if not panel_result.patrones:
        return
    W = A4[0] - 3*cm
    story.append(Paragraph("Patrones clínicos intersistema detectados", styles["section_title"]))

    for p in panel_result.patrones:
        rel_bg, rel_fg = (P.red50, P.red600) if p["relevancia"] == "Alta" else (P.amber50, P.amber600)
        rows = [
            [
                Paragraph(p["patron"], ParagraphStyle("",fontName="Helvetica-Bold",
                    fontSize=10, textColor=P.purple800)),
                Paragraph(f"Relevancia: {p['relevancia']}", ParagraphStyle("",fontName="Helvetica-Bold",
                    fontSize=8.5, textColor=rel_fg, alignment=TA_RIGHT)),
            ],
            [
                Paragraph(
                    f"<b>Biomarcadores:</b> {', '.join(p['biomarcadores'])}<br/>{p['descripcion']}",
                    ParagraphStyle("",fontName="Helvetica",fontSize=9,textColor=P.black,leading=13)
                ),
                ""
            ]
        ]
        t = Table(rows, colWidths=[W*0.75, W*0.25])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), P.purple50),
            ("BACKGROUND",    (0,1), (-1,1), P.white),
            ("BACKGROUND",    (1,0), (1,0), rel_bg),
            ("SPAN",          (0,1), (-1,1)),
            ("GRID",          (0,0), (-1,-1), 0.3, P.gray100),
            ("TOPPADDING",    (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("LINEABOVE",     (0,0), (-1,0), 1.5, P.purple600),
        ]))
        story.append(KeepTogether([t, Spacer(1, 0.3*cm)]))

# ─── Sección narrativa LLM ───────────────────────────────────────────────
def build_llm_section(story, styles, llm_result):
    """Recibe el dict JSON que devuelve la API y renderiza secciones clave."""
    story.append(PageBreak())
    story.append(Paragraph("Interpretación clínica integrada (LLM)", styles["section_title"]))

    # Protocolo DIRe
    dire = llm_result.get("protocolo_dire", {})
    if dire.get("diagnostico"):
        story.append(Paragraph("Diagnóstico integrado", styles["body_bold"]))
        story.append(Paragraph(dire["diagnostico"], styles["narrativa"]))
        story.append(Spacer(1, 0.2*cm))

    # Intervenciones
    interv = dire.get("intervencion", {})
    for prio in ["prioridad_1", "prioridad_2", "prioridad_3"]:
        bloque = interv.get(prio)
        if not bloque or not bloque.get("objetivo"):
            continue
        num = prio.split("_")[1]
        story.append(Paragraph(f"Prioridad {num}: {bloque['objetivo']}", styles["body_bold"]))
        for iv in bloque.get("intervenciones", []):
            ev = iv.get("evidencia","")
            nota = f" [{iv['nota_arg']}]" if iv.get("nota_arg") else ""
            text = f"• <b>{iv.get('tipo','')}</b>: {iv.get('descripcion','')} — Evidencia: {ev}{nota}"
            story.append(Paragraph(text, styles["body_small"]))
        story.append(Spacer(1, 0.2*cm))

    # Narrativa
    narrativa = llm_result.get("narrativa_clinica", "")
    if narrativa:
        story.append(HRFlowable(width="100%", thickness=0.5, color=P.teal200, spaceAfter=8))
        story.append(Paragraph("Narrativa clínica", styles["section_title"]))
        for parrafo in narrativa.split("\n"):
            if parrafo.strip():
                story.append(Paragraph(parrafo.strip(), styles["narrativa"]))

    # Reevaluación
    reeval = dire.get("reevaluacion", {})
    if reeval.get("plazo_recomendado"):
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph("Plan de reevaluación (DIRe)", styles["section_title"]))
        r_rows = [
            ["Plazo recomendado", reeval.get("plazo_recomendado","—")],
            ["Biomarcadores prioritarios", ", ".join(reeval.get("biomarcadores_prioritarios",[]))],
            ["Objetivo cuantitativo", reeval.get("objetivo_cuantitativo","—")],
        ]
        rt = Table(r_rows, colWidths=[4.5*cm, 13*cm])
        rt.setStyle(TableStyle([
            ("FONTNAME",  (0,0),(0,-1),"Helvetica-Bold"),
            ("FONTSIZE",  (0,0),(-1,-1), 9),
            ("TEXTCOLOR", (0,0),(0,-1), P.teal800),
            ("ROWBACKGROUNDS",(0,0),(-1,-1),[P.teal50, P.white]),
            ("GRID",      (0,0),(-1,-1), 0.3, P.gray100),
            ("TOPPADDING",(0,0),(-1,-1), 6),
            ("BOTTOMPADDING",(0,0),(-1,-1), 6),
            ("LEFTPADDING",(0,0),(-1,-1), 8),
        ]))
        story.append(rt)

# ─── Función principal de generación ─────────────────────────────────────
def generate_pdf(panel_result, output_path: str, modo: str, llm_result: dict = None):
    """
    panel_result: objeto PanelResult del scoring engine
    output_path:  ruta de salida del PDF
    modo:         "scoring" | "llm"
    llm_result:   dict con la respuesta JSON de la API (solo si modo == "llm")
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.8*cm, bottomMargin=1.4*cm,
        title=f"Informe Longevidad — {panel_result.paciente_id}",
        author="Laboratorio Clínico · Área de Longevidad"
    )

    styles = build_styles()
    story = []
    fecha_str = panel_result.fecha or datetime.today().strftime("%Y-%m-%d")

    # Portada
    build_cover(story, styles, panel_result, modo)
    story.append(Spacer(1, 0.4*cm))

    # Resumen de categorías
    build_category_summary(story, styles, panel_result)

    # Detalle de biomarcadores
    build_biomarkers_detail(story, styles, panel_result)

    # Patrones intersistema
    build_patterns(story, styles, panel_result)

    # Sección LLM (solo si modo == "llm" y hay resultado)
    if modo == "llm" and llm_result:
        build_llm_section(story, styles, llm_result)

    # Disclaimer final
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=P.gray100))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Este informe es un instrumento de apoyo diagnóstico generado a partir de rangos de referencia de Medicina 3.0. "
        "No reemplaza el criterio clínico del médico tratante. Los rangos óptimos utilizados difieren de los valores de "
        "referencia convencionales de laboratorio y están orientados a la optimización de la salud a largo plazo.",
        styles["footer"]
    ))

    def on_page(canvas, doc):
        _header_footer(canvas, doc, panel_result.paciente_id, fecha_str, modo)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return output_path
