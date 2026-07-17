#!/usr/bin/env python3
"""
SEO Feedback Handoff PDF generator.

Reads a JSON spec describing an article and its anchored open comments, and
writes the locked Kulin handoff PDF (summary block + article with margin
comments, color-coded by type).

Usage:
    python3 seo_handoff_generator.py spec.json "/path/to/output.pdf"

JSON spec shape:
{
  "meta": {
    "title":   "How to Choose the Best Carpet for Stairs: A Complete Guide",
    "client":  "Home Carpet One (HC1)",
    "status":  "Revisions in progress",
    "round":   1,
    "keywords":"best carpet for stairs, stair carpet, carpet for staircases",
    "source":  "HC1 SEO Articles (Notion)",
    "generated":"June 14, 2026",
    "footer":  "HC1 SEO content review - client feedback handoff - prepared by Kulin Agency"
  },
  "blocks": [
    {"type": "h2", "text": "Why Stair Carpet Is Different"},
    {"type": "p",  "text": "Plain paragraph, no comment."},
    {"type": "p",
     "text": "A good stair carpet cuts noise by up to 70%{{1}} and softens footsteps.",
     "comments": [
        {"n": 1, "ctype": "REVISION REQUEST",
         "text": "Where does the 70% figure come from? ...",
         "who": "HC1 review", "when": "Jun 12"}
     ]}
  ]
}

Notes:
- ctype must be one of: "REVISION REQUEST", "QUESTION", "APPROVAL".
- Put a {{n}} token in the paragraph text where comment n's marker should sit.
- Summary counts are computed automatically from the comments.
"""
import sys, json, re
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

INK      = colors.HexColor("#1F2933")
SUBINK   = colors.HexColor("#5B6770")
HAIRLINE = colors.HexColor("#D8DEE3")
NAVY     = colors.HexColor("#10243E")
ACCENT   = colors.HexColor("#B4490B")

TYPE_COLOR = {
    "REVISION REQUEST": (colors.HexColor("#B4490B"), colors.HexColor("#FDF1E7")),
    "QUESTION":         (colors.HexColor("#1D4ED8"), colors.HexColor("#EAF1FE")),
    "APPROVAL":         (colors.HexColor("#15803D"), colors.HexColor("#EAF7EF")),
}
LABELS = [("REVISION REQUEST","REVISION REQUESTS"),
          ("QUESTION","QUESTIONS"),
          ("APPROVAL","APPROVALS")]

styles = getSampleStyleSheet()
def S(name, **kw):
    base = kw.pop("parent", styles["Normal"]); return ParagraphStyle(name, parent=base, **kw)

title_st  = S("t", fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=NAVY, spaceAfter=2)
sub_st    = S("s", fontName="Helvetica", fontSize=9.5, leading=14, textColor=SUBINK)
h2_st     = S("h2", fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=NAVY, spaceBefore=12, spaceAfter=5)
body_st   = S("b", fontName="Helvetica", fontSize=10, leading=15.5, textColor=INK, spaceAfter=8, alignment=TA_LEFT)
small_st  = S("sm", fontName="Helvetica", fontSize=8, leading=11, textColor=SUBINK)
clabel_st = S("cl", fontName="Helvetica-Bold", fontSize=7.5, leading=10)
cbody_st  = S("cb", fontName="Helvetica", fontSize=8.5, leading=12, textColor=INK, spaceBefore=2)
cmeta_st  = S("cm", fontName="Helvetica-Oblique", fontSize=7.5, leading=10, textColor=SUBINK, spaceBefore=3)

def hx(c): return c.hexval()[2:]

def apply_markers(text, comments):
    for c in comments or []:
        ctype = c["ctype"]; col = hx(TYPE_COLOR[ctype][0])
        token = "{{%d}}" % c["n"]
        repl = f'<super><font size=7 color="#{col}"><b>[{c["n"]}]</b></font></super>'
        text = text.replace(token, repl)
    return text

def comment_box(c):
    tc, bg = TYPE_COLOR[c["ctype"]]
    label = Paragraph(f'<font color="#{hx(tc)}">[{c["n"]}]&nbsp;&nbsp;{c["ctype"]}</font>', clabel_st)
    body  = Paragraph(c["text"], cbody_st)
    meta  = Paragraph(f'{c.get("who","")} &nbsp;&middot;&nbsp; {c.get("when","")}', cmeta_st)
    inner = Table([[label],[body],[meta]], colWidths=[150])
    inner.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),bg),
        ("LINEBEFORE",(0,0),(-1,-1),2.2,tc),
        ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
        ("TOPPADDING",(0,0),(0,0),6),("BOTTOMPADDING",(0,-1),(-1,-1),6),
        ("TOPPADDING",(0,1),(-1,-1),0)]))
    return inner

def two_col(left, comment_flows):
    stacked = []
    for i, cf in enumerate(comment_flows):
        if i: stacked.append(Spacer(1,5))
        stacked.append(cf)
    t = Table([[left, stacked]], colWidths=[322, 182])
    t.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(0,0),0),("RIGHTPADDING",(0,0),(0,0),10),
        ("LEFTPADDING",(1,0),(1,0),0),("RIGHTPADDING",(1,0),(1,0),0),
        ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    return t

def chip(num, label, key):
    tc,bg = TYPE_COLOR[key]
    c = Table([[Paragraph(str(num), S("n", fontName="Helvetica-Bold", fontSize=15, leading=16, textColor=tc, alignment=1))],
               [Paragraph(label, S("l", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=tc, alignment=1))]],
              colWidths=[150])
    c.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),("BOX",(0,0),(-1,-1),0.6,tc),
        ("TOPPADDING",(0,0),(0,0),7),("BOTTOMPADDING",(0,1),(-1,-1),7),("TOPPADDING",(0,1),(-1,-1),0)]))
    return c

def build(spec, out):
    m = spec["meta"]; blocks = spec["blocks"]
    counts = {k:0 for k,_ in LABELS}
    for b in blocks:
        for c in b.get("comments", []) or []:
            counts[c["ctype"]] = counts.get(c["ctype"],0)+1
    total = sum(counts.values())

    story = []
    story.append(Paragraph("Client Feedback Handoff",
        S("k", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=ACCENT, spaceAfter=4)))
    story.append(Paragraph(m["title"], title_st))
    meta_line = (f'Client: {m.get("client","")}&nbsp;&nbsp;|&nbsp;&nbsp;Status: {m.get("status","")}'
                 f'&nbsp;&nbsp;|&nbsp;&nbsp;Review round: {m.get("round","")}'
                 f'&nbsp;&nbsp;|&nbsp;&nbsp;Generated: {m.get("generated","")}')
    story.append(Paragraph(meta_line, sub_st))
    if m.get("keywords") or m.get("source"):
        story.append(Paragraph(f'Keyword targets: {m.get("keywords","")}'
                               f'&nbsp;&nbsp;|&nbsp;&nbsp;Source: {m.get("source","")}', sub_st))
    story.append(Spacer(1,8)); story.append(HRFlowable(width="100%", thickness=1, color=HAIRLINE)); story.append(Spacer(1,10))

    total_chip = Table([[Paragraph(str(total), S("bn", fontName="Helvetica-Bold", fontSize=22, leading=24, textColor=colors.white, alignment=1))],
                        [Paragraph("OPEN COMMENTS", S("bl", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.white, alignment=1))]],
                       colWidths=[120])
    total_chip.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),NAVY),
        ("TOPPADDING",(0,0),(0,0),9),("BOTTOMPADDING",(0,1),(-1,-1),9),("TOPPADDING",(0,1),(-1,-1),0)]))
    summary = Table([[total_chip,
                      chip(counts["REVISION REQUEST"],"REVISION REQUESTS","REVISION REQUEST"),
                      chip(counts["QUESTION"],"QUESTIONS","QUESTION"),
                      chip(counts["APPROVAL"],"APPROVALS","APPROVAL")]],
                    colWidths=[126,128,128,122])
    summary.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-2,-1),6),("RIGHTPADDING",(-1,0),(-1,-1),0),
        ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    story.append(summary); story.append(Spacer(1,6))
    story.append(Paragraph("Open (unresolved) client comments only. Resolved threads excluded. "
        "Each comment is numbered and anchored to its passage below.", small_st))
    story.append(Spacer(1,12)); story.append(HRFlowable(width="100%", thickness=1, color=HAIRLINE)); story.append(Spacer(1,10))

    for b in blocks:
        if b["type"] == "h2":
            story.append(Paragraph(b["text"], h2_st)); continue
        comments = b.get("comments", []) or []
        para = Paragraph(apply_markers(b["text"], comments), body_st)
        if comments:
            story.append(two_col(para, [comment_box(c) for c in comments]))
            story.append(Spacer(1,8))
        else:
            story.append(para)

    footer_text = m.get("footer","SEO content review - client feedback handoff")
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(HAIRLINE); canvas.setLineWidth(0.5)
        canvas.line(54, 42, letter[0]-54, 42)
        canvas.setFont("Helvetica", 7.5); canvas.setFillColor(SUBINK)
        canvas.drawString(54, 30, footer_text)
        canvas.drawRightString(letter[0]-54, 30, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(out, pagesize=letter, leftMargin=54, rightMargin=54,
                            topMargin=50, bottomMargin=54, title=m["title"])
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out

if __name__ == "__main__":
    spec_path, out_path = sys.argv[1], sys.argv[2]
    with open(spec_path) as f:
        spec = json.load(f)
    print("wrote:", build(spec, out_path))
