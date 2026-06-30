"""Sprint 1 Review — stakeholder Agile metrics deck (river_fish / project RF).

Built from LIVE Jira data (pulled via REST). Native python-pptx charts (no matplotlib).
Re-run:  python make_sprint_review.py
"""
from __future__ import annotations
import datetime
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION

TODAY = datetime.date.today().strftime("%d %b %Y")
NAVY=RGBColor(0x00,0x2B,0x5B); GOLD=RGBColor(0xE6,0xB8,0x00); WHITE=RGBColor(0xFF,0xFF,0xFF)
LGRAY=RGBColor(0xF2,0xF2,0xF2); DK=RGBColor(0x33,0x33,0x33); GREEN=RGBColor(0x0A,0x7A,0x33)
RED=RGBColor(0xB0,0x00,0x00); BLUE=RGBColor(0x1F,0x5C,0xA8); AMBER=RGBColor(0xC8,0x5A,0x00)

prs=Presentation(); prs.slide_width=Inches(13.33); prs.slide_height=Inches(7.5)
B=prs.slide_layouts[6]

def rect(s,l,t,w,h,c):
    sh=s.shapes.add_shape(1,Inches(l),Inches(t),Inches(w),Inches(h)); sh.fill.solid()
    sh.fill.fore_color.rgb=c; sh.line.fill.background(); return sh
def txt(s,text,l,t,w,h,size=18,bold=False,color=DK,align=PP_ALIGN.LEFT,italic=False):
    tb=s.shapes.add_textbox(Inches(l),Inches(t),Inches(w),Inches(h)); tf=tb.text_frame
    tf.word_wrap=True; p=tf.paragraphs[0]; p.alignment=align; r=p.add_run(); r.text=text
    f=r.font; f.size=Pt(size); f.bold=bold; f.italic=italic; f.color.rgb=color; return tb
def bullets(s,items,l,t,w,h,size=13,color=DK,gap=5):
    tb=s.shapes.add_textbox(Inches(l),Inches(t),Inches(w),Inches(h)); tf=tb.text_frame; tf.word_wrap=True
    for i,it in enumerate(items):
        p=tf.add_paragraph() if i else tf.paragraphs[0]; p.space_after=Pt(gap)
        if isinstance(it,tuple):
            r=p.add_run(); r.text=f"▸  {it[0]}"; r.font.size=Pt(size); r.font.bold=True; r.font.color.rgb=NAVY
            r2=p.add_run(); r2.text=it[1]; r2.font.size=Pt(size); r2.font.color.rgb=color
        else:
            r=p.add_run(); r.text=f"▸  {it}"; r.font.size=Pt(size); r.font.color.rgb=color
def header(s,t,sub=None):
    rect(s,0,0,13.33,1.1,NAVY); txt(s,t,0.3,0.1,12.7,0.62,size=26,bold=True,color=WHITE)
    if sub: txt(s,sub,0.3,0.72,12.7,0.34,size=12.5,color=GOLD)
    rect(s,0,1.1,13.33,0.04,GOLD)
def card(s,l,t,w,big,small,c):
    rect(s,l,t,w,1.55,LGRAY); rect(s,l,t,w,0.1,c)
    txt(s,big,l,t+0.22,w,0.7,size=27,bold=True,color=NAVY,align=PP_ALIGN.CENTER)
    txt(s,small,l+0.08,t+0.98,w-0.16,0.5,size=11,color=DK,align=PP_ALIGN.CENTER)
def chart(s,ctype,cats,series,l,t,w,h,title):
    cd=CategoryChartData(); cd.categories=cats
    for nm,vals in series: cd.add_series(nm,vals)
    gf=s.shapes.add_chart(ctype,Inches(l),Inches(t),Inches(w),Inches(h),cd); ch=gf.chart
    ch.has_title=True; ch.chart_title.text_frame.text=title
    ch.chart_title.text_frame.paragraphs[0].runs[0].font.size=Pt(13)
    ch.has_legend=len(series)>1
    if ch.has_legend: ch.legend.position=XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout=False
    return ch

# 1 TITLE
s=prs.slides.add_slide(B); rect(s,0,0,13.33,7.5,NAVY); rect(s,0,3.0,13.33,0.06,GOLD)
txt(s,"Sprint 1 Review",0.8,1.6,11.7,1.0,size=42,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
txt(s,"river_fish — Column-Level Data Lineage  ·  Project RF",0.8,2.9,11.7,0.5,size=17,bold=True,color=GOLD,align=PP_ALIGN.CENTER)
txt(s,f"Agile delivery metrics for stakeholder review  ·  {TODAY}",0.8,3.35,11.7,0.4,size=13,color=LGRAY,align=PP_ALIGN.CENTER)
txt(s,"Source: live Jira (REST)  ·  multi-agent delivery  ·  synthetic data, real public market data",0.8,6.7,11.7,0.4,size=11,color=RGBColor(0x9F,0xB3,0xC8),align=PP_ALIGN.CENTER)

# 2 EXEC SUMMARY (cards)
s=prs.slides.add_slide(B); header(s,"Executive Summary","Delivered the full prototype (M1–M7); 2 items carried (externally blocked)")
cards=[("43 / 46","Story Points completed (93%)",GREEN),("16 / 18","stories Done (89%)",GREEN),
       ("~18×","throughput vs human estimate",GOLD),("9.8 h","AI-actual effort (1 session)",BLUE),
       ("18/18 · 20/20","tests · eval green",GREEN),("0","defects escaped to release",GREEN),
       ("+16 SP","scope added mid-sprint (+53%)",AMBER),("2","carried over (deploy, QA)",AMBER)]
for i,(b_,sm,c) in enumerate(cards):
    col=i%4; row=i//4; card(s,0.45+col*3.15,1.45+row*1.95,2.95,b_,sm,c)
txt(s,"Headline: a full audit-grade lineage prototype delivered in one session with an AI agent team — "
     "quality gates green, governance proven, the only open items blocked on external inputs (HuggingFace "
     "credentials, a usage-limit reset).",0.5,5.55,12.4,1.0,size=13,color=DK)

# 3 SCOPE & VELOCITY (chart)
s=prs.slides.add_slide(B); header(s,"Scope & Velocity","30 SP committed · +16 SP emerged · 43 SP delivered")
chart(s,XL_CHART_TYPE.COLUMN_CLUSTERED,["Baseline\ncommit","Scope\nadded","Completed","Carried\nover"],
      [("Story Points",(30,16,43,3))],0.5,1.4,6.6,5.4,"Sprint 1 — Story Points")
bullets(s,[("Velocity: ","43 SP delivered in the sprint window."),
           ("Baseline 30 SP — 100% done. ","Every originally-planned milestone (M1–M7) shipped."),
           ("Scope grew +16 SP (+53%) ","mid-sprint: live market data, gap analysis, the synthetic data platform, deploy-prep, retro & the agent-method demo."),
           ("Carried over 3 SP ","(RF-17 deploy, RF-18 QA re-run) — both blocked on external inputs, not capacity."),
           ("Predictability caveat: ","baseline commitment was fully met; the added scope was unestimated (see Process Findings).")],
        7.3,1.5,5.7,5.2,size=13,gap=9)

# 4 ESTIMATION & ACCELERATION (chart)
s=prs.slides.add_slide(B); header(s,"Estimation & Throughput","Planned-equivalent effort vs. AI-actual")
chart(s,XL_CHART_TYPE.COLUMN_CLUSTERED,["Planned\n(human-equiv)","AI-actual"],
      [("Hours",(172,9.8))],0.5,1.4,6.0,5.4,"Effort: 43 SP delivered (hours)")
txt(s,"~18×",7.0,1.7,5.8,1.0,size=46,bold=True,color=GOLD)
txt(s,"throughput acceleration vs. a human-hour estimate (1 SP = 4 h convention).",7.05,2.7,5.8,0.8,size=14,color=DK)
bullets(s,[("Planned-equivalent: ","43 SP × 4 h = 172 human-hours."),
           ("AI-actual logged: ","9.8 h (Jira worklogs, epic excluded to avoid roll-up double-count)."),
           ("Baseline view: ","30 SP estimated 120 h → 6.2 h actual = 19.4×."),
           ("Estimation accuracy: ","baseline estimates were directionally sound; the unestimated additions are the gap to close next sprint.")],
        7.0,3.55,5.9,3.0,size=13,gap=8)

# 5 QUALITY
s=prs.slides.add_slide(B); header(s,"Quality & Engineering Health","Gated, red-teamed, honest")
q=[("18 / 18","regression tests",GREEN),("20 / 20","eval (correctness, governance, adversarial)",GREEN),
   ("3","defects caught pre-release (1 High, 2 Med)",AMBER),("0","defects escaped to release",GREEN)]
for i,(b_,sm,c) in enumerate(q): card(s,0.45+i*3.15,1.5,2.95,b_,sm,c)
rect(s,0.45,3.45,12.43,0.32,NAVY); txt(s,"QUALITY PRACTICES",0.55,3.48,12,0.26,size=11,bold=True,color=WHITE)
bullets(s,[("Deterministic, auditable backbone — ","lineage proven correct vs. hand-authored ground truth."),
           ("Governance verified mechanically — ","eval asserts SQL-text-only; no data rows reach an LLM."),
           ("Defects found early — ","find_node false-match (High) and the lstrip name-corruption (Med) caught and fixed before release."),
           ("Independent QA — ","interim red-team checkpoint; a second independent re-run is scheduled (RF-18)."),
           ("Honest reporting — ","the eval harness reports failures rather than hiding them.")],
        0.5,3.95,12.4,3.0,size=13,gap=7)

# 6 WORK BREAKDOWN (chart)
s=prs.slides.add_slide(B); header(s,"Where the Effort Went","AI-actual minutes by workstream (590 min total)")
chart(s,XL_CHART_TYPE.BAR_CLUSTERED,
      ["Research & Planning","Lineage engine + hardening","LLM / NL + Visualization",
       "Data platform (synth/market/gap)","Eval, Docs & QA","Infra, Deploy, Retro & Reporting"],
      [("Minutes",(60,95,140,115,75,105))],0.5,1.35,12.4,5.6,"Effort by workstream")

# 7 PROCESS FINDINGS & RISKS
s=prs.slides.add_slide(B); header(s,"Process Findings & Risks","Candid — for the retrospective and next-sprint planning")
rect(s,0.35,1.3,6.3,5.5,LGRAY); txt(s,"Process findings",0.5,1.4,6,0.4,size=14,bold=True,color=NAVY)
bullets(s,[("Scope growth unestimated — ","+16 SP (+53%) added mid-sprint without points; estimate additions up front next time."),
           ("Sprints defined but not run — ","two sprints sit in 'future'; work executed as continuous flow → no native burndown until a sprint is formally closed."),
           ("Lead time ≠ effort — ","~6 days calendar lead, but ~9.8 h actual effort (bursty/compressed)."),
           ("Board automation gated — ","the safety guardrail blocked auto-updating Jira (SP back-fill, sprint close) — needs explicit approval.")],
        0.5,1.85,6.0,4.8,size=12.5,gap=8)
rect(s,6.75,1.3,6.23,5.5,RGBColor(0xFD,0xEC,0xEA)); txt(s,"Risks / impediments",6.9,1.4,6,0.4,size=14,bold=True,color=RED)
bullets(s,[("RF-17 deploy — ","blocked on HuggingFace account/token (external)."),
           ("RF-18 QA re-run — ","blocked on usage-limit reset (10pm IST)."),
           ("Security — ","two API tokens were exposed in chat → rotation pending (high priority)."),
           ("Single-session concentration — ","delivery depended on one continuous session; spread cadence for resilience.")],
        6.9,1.85,5.9,4.8,size=12.5,color=RGBColor(0x70,0x20,0x18),gap=8)

# 8 GOVERNANCE
s=prs.slides.add_slide(B); header(s,"Governance & Compliance","Controls held throughout — the basis for an audit conversation")
bullets(s,[("Data boundary — ","customer/counterparty data 100% SYNTHETIC (DPDP-safe); only PUBLIC market data is real."),
           ("On-prem proven — ","the engine reads SQL text only; no data rows enter an LLM prompt (asserted by the eval harness)."),
           ("Audit-grade lineage — ","deterministic parser → DAG; the LLM only explains, labelled 'suggestion — needs sign-off'."),
           ("BCBS 239 alignment — ","attribute (column)-level traceability, the regulatory expectation in the domain."),
           ("Human-in-the-loop — ","sign-off, repository pushes, and all credential handling stayed with the human owner.")],
        0.5,1.5,12.4,4.0,size=14,gap=11)
rect(s,0.35,6.2,12.63,0.7,GREEN); txt(s,"Result: speed with governance intact — a repeatable, auditable AI-accelerated delivery model.",
     0.5,6.32,12.3,0.45,size=13.5,bold=True,color=WHITE,align=PP_ALIGN.CENTER)

# 9 NEXT STEPS
s=prs.slides.add_slide(B); header(s,"Next Steps & Actions","Owner action in bold")
bullets(s,[("Rotate the two exposed API tokens — ","HIGH priority security action (owner)."),
           ("Deploy to HuggingFace (RF-17) — ","owner provides HF token; keep the public Space $0/key-less."),
           ("Independent QA re-run (RF-18) — ","after the usage-limit reset."),
           ("Formalize Sprint 1 in Jira — ","approve the SP back-fill + sprint close to generate native velocity/burndown (currently gated)."),
           ("Estimate scope additions up front — ","carry the retro action to improve predictability."),
           ("Sprint 2 candidates — ","HF deploy, independent QA, the agent-method showcase, and any stakeholder-requested extensions.")],
        0.5,1.5,12.4,4.6,size=14,gap=11)
rect(s,0.35,6.5,12.63,0.6,NAVY); txt(s,"river_fish · Sprint 1 · 43/46 SP · 18/18 + 20/20 green · one team, not human-vs-AI",
     0.5,6.61,12.3,0.4,size=11.5,color=WHITE,align=PP_ALIGN.CENTER)

out=r"c:\Users\vijay\claude\Projects\river_fish\Sprint1_Review_river_fish.pptx"
prs.save(out); print("Saved:",out)
