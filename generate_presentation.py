import json
import os
import matplotlib.pyplot as plt
import numpy as np
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# 1. Load data
DATA_PATH = "pipeline/output/dashboard_data.json"
with open(DATA_PATH, "r") as f:
    data = json.load(f)

IMG_DIR = "presentation_assets"
os.makedirs(IMG_DIR, exist_ok=True)

# Styling defaults for clean, professional executive charts
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 10

# -------------------------------------------------------------
# Chart 1: Waterfall / Bridge (Budget -> Allowance -> Actual)
# -------------------------------------------------------------
bridge = data['bridge']
markets = [b['market'].replace("Central Eastern Europe", "CEE").replace("Greater China", "G. China") for b in bridge]
budget_m = [b['budget'] / 1e6 for b in bridge]
allowance_m = [(b['budget'] + b['justified']) / 1e6 for b in bridge]
actual_m = [b['actual'] / 1e6 for b in bridge]

x = np.arange(len(markets))
width = 0.25

fig, ax = plt.subplots(figsize=(8, 4.2), dpi=200)
rects1 = ax.bar(x - width, budget_m, width, label='Budget', color='#94a3b8', edgecolor='#64748b', linewidth=0.8)
rects2 = ax.bar(x, allowance_m, width, label='Fair Allowance', color='#4f46e5', edgecolor='#3730a3', linewidth=0.8)
rects3 = ax.bar(x + width, actual_m, width, label='Actual Spend', color='#0f172a', edgecolor='#020617', linewidth=0.8)

ax.set_ylabel('EUR Millions', fontweight='bold', color='#334155')
ax.set_title('Market Bridge: Budget vs Fair Allowance vs Actual Spend', fontweight='bold', fontsize=12, pad=12, color='#0f172a')
ax.set_xticks(x)
ax.set_xticklabels(markets, fontweight='semibold', color='#334155')
ax.legend(frameon=True, facecolor='#f8fafc', edgecolor='#e2e8f0')
ax.grid(axis='y', linestyle='--', alpha=0.5, color='#cbd5e1')
ax.set_axisbelow(True)
plt.tight_layout()
chart1_path = os.path.join(IMG_DIR, "bridge_chart.png")
plt.savefig(chart1_path)
plt.close()

# -------------------------------------------------------------
# Chart 2: Justification Quadrant Scatter Plot
# -------------------------------------------------------------
pairs = data['pairs']
sales_pct = [p['sales_vs_plan_pct'] for p in pairs]
spend_pct = [p['spend_vs_budget_pct'] for p in pairs]
real_ov = [p['real_overspend'] for p in pairs]

colors = ['#e11d48' if ro > 0 else '#10b981' for ro in real_ov]

fig, ax = plt.subplots(figsize=(8, 4.5), dpi=200)
scatter = ax.scatter(sales_pct, spend_pct, c=colors, s=45, alpha=0.75, edgecolors='none')

ax.axvline(0, color='#64748b', linestyle='--', linewidth=1)
ax.axhline(0, color='#64748b', linestyle='--', linewidth=1)

# Annotate key outliers
for p in pairs:
    if p['product'] == "Patient Monitor" and p['country'] == "Hungary":
        ax.annotate(f"Hungary Patient Monitor\n(+38.8% ov, -1.7% sales)", 
                    (p['sales_vs_plan_pct'], p['spend_vs_budget_pct']),
                    xytext=(p['sales_vs_plan_pct'] + 1, p['spend_vs_budget_pct'] - 4),
                    fontweight='bold', fontsize=8, color='#b91c1c',
                    arrowprops=dict(arrowstyle="->", color='#b91c1c', lw=1.2))
    elif p['product'] == "Hair Dryer" and p['country'] == "Netherlands":
        ax.annotate(f"Netherlands Hair Dryer\n(Benchmark: -16.4%)", 
                    (p['sales_vs_plan_pct'], p['spend_vs_budget_pct']),
                    xytext=(p['sales_vs_plan_pct'] - 5, p['spend_vs_budget_pct'] - 5),
                    fontweight='bold', fontsize=8, color='#047857',
                    arrowprops=dict(arrowstyle="->", color='#047857', lw=1.2))

ax.set_xlabel('Sales vs Plan (%) [Right = Growth]', fontweight='bold', color='#334155')
ax.set_ylabel('Spend vs Budget (%) [Up = Overspend]', fontweight='bold', color='#334155')
ax.set_title('Justification Quadrant: Separating Growth from Waste', fontweight='bold', fontsize=12, pad=12, color='#0f172a')
ax.grid(True, linestyle='--', alpha=0.4, color='#cbd5e1')

# Custom legend
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], marker='o', color='w', label='Real Overspend (> Allowance)', markerfacecolor='#e11d48', markersize=8),
    Line2D([0], [0], marker='o', color='w', label='Justified / Efficient (<= Allowance)', markerfacecolor='#10b981', markersize=8)
]
ax.legend(handles=legend_elements, loc='upper left', frameon=True, facecolor='#f8fafc', edgecolor='#e2e8f0')
plt.tight_layout()
chart2_path = os.path.join(IMG_DIR, "quadrant_chart.png")
plt.savefig(chart2_path)
plt.close()

# -------------------------------------------------------------
# Chart 3: Monthly Corrected Variance (Timing vs Structural)
# -------------------------------------------------------------
monthly = data['monthly']
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
m_raw = [0.0]*12
m_corr = [0.0]*12
for row in monthly:
    m_idx = row['month'] - 1
    m_raw[m_idx] += row['raw_variance'] / 1e6
    m_corr[m_idx] += row['corrected_variance'] / 1e6

fig, ax = plt.subplots(figsize=(8, 4.2), dpi=200)
bar_colors = ['#e11d48' if c > 0 else '#10b981' for c in m_corr]
ax.bar(months, m_corr, color=bar_colors, width=0.55, label='Corrected Variance (Real Overspend)', alpha=0.85)
ax.plot(months, m_raw, color='#0f172a', marker='o', linewidth=2, label='Raw Variance (Naive Actual - Budget)')
ax.axhline(0, color='#64748b', linestyle='--', linewidth=0.8)

ax.set_ylabel('EUR Millions', fontweight='bold', color='#334155')
ax.set_title('Monthly Trajectory: Naive Raw Variance vs Real Overspend', fontweight='bold', fontsize=12, pad=12, color='#0f172a')
ax.legend(frameon=True, facecolor='#f8fafc', edgecolor='#e2e8f0')
ax.grid(axis='y', linestyle='--', alpha=0.5, color='#cbd5e1')
plt.tight_layout()
chart3_path = os.path.join(IMG_DIR, "monthly_chart.png")
plt.savefig(chart3_path)
plt.close()

# -------------------------------------------------------------
# BUILD SLIDE DECK (16:9 Widescreen)
# -------------------------------------------------------------
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank_layout = prs.slide_layouts[6]

# Theme Colors
C_DARK = RGBColor(15, 23, 42)       # Slate 900
C_PRIMARY = RGBColor(79, 70, 229)   # Indigo 600
C_EMERALD = RGBColor(16, 185, 129) # Emerald 500
C_ROSE = RGBColor(225, 29, 72)     # Rose 600
C_BG_LIGHT = RGBColor(248, 250, 252)
C_MUTED = RGBColor(100, 116, 139)  # Slate 500
C_WHITE = RGBColor(255, 255, 255)
C_CARD_BG = RGBColor(241, 245, 249)

def add_header(slide, title, category="SPEND TRUTH ENGINE"):
    tb = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(1.1))
    tf = tb.text_frame
    tf.word_wrap = True
    p1 = tf.paragraphs[0]
    p1.text = category.upper()
    p1.font.size = Pt(10)
    p1.font.bold = True
    p1.font.color.rgb = C_PRIMARY
    
    p2 = tf.add_paragraph()
    p2.text = title
    p2.font.size = Pt(22)
    p2.font.bold = True
    p2.font.color.rgb = C_DARK

# -------------------------------------------------------------
# SLIDE 1: Title Slide
# -------------------------------------------------------------
s1 = prs.slides.add_slide(blank_layout)
# Background box
bg = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
bg.fill.solid()
bg.fill.fore_color.rgb = C_DARK
bg.line.fill.background()

tb = s1.shapes.add_textbox(Inches(1.2), Inches(2.2), Inches(11), Inches(3.2))
tf = tb.text_frame
tf.word_wrap = True

p_sub = tf.paragraphs[0]
p_sub.text = "PHILIPS HACKATHON 2026 • COMMERCIAL FINANCE INNOVATION"
p_sub.font.size = Pt(12)
p_sub.font.bold = True
p_sub.font.color.rgb = RGBColor(129, 140, 248) # Indigo 400

p_main = tf.add_paragraph()
p_main.text = "Spend Truth Engine"
p_main.font.size = Pt(44)
p_main.font.bold = True
p_main.font.color.rgb = C_WHITE

p_desc = tf.add_paragraph()
p_desc.text = "Separating Sales-Justified Investment from Real A&P Overspend Across €650M Portfolio"
p_desc.font.size = Pt(18)
p_desc.font.color.rgb = RGBColor(203, 213, 225)

p_foot = tf.add_paragraph()
p_foot.text = "End-to-End Analytics, Statistical Anomaly Detection & Executive Commentary Cockpit"
p_foot.font.size = Pt(13)
p_foot.font.color.rgb = RGBColor(148, 163, 184)

# -------------------------------------------------------------
# SLIDE 2: Executive Summary & Core Financial Proof
# -------------------------------------------------------------
s2 = prs.slides.add_slide(blank_layout)
add_header(s2, "Executive Problem & The Core Financial Truth")

# 4 KPI cards across the top
kpis = [
    ("Actual A&P Spend", "€642.66M", "vs €647.62M budget", C_DARK),
    ("Fair Allowance", "€645.68M", "Sales-adjusted target", C_PRIMARY),
    ("Justified Spend", "-€1.94M", "Sales-driven shift", C_MUTED),
    ("Real Overspend", "-€3.02M", "True waste / saving (disciplined)", C_EMERALD),
]

card_w = Inches(2.7)
card_h = Inches(1.3)
top_y = Inches(1.6)

for i, (title, val, sub, col) in enumerate(kpis):
    left_x = Inches(0.8 + i * 2.95)
    box = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left_x, top_y, card_w, card_h)
    box.fill.solid()
    box.fill.fore_color.rgb = C_CARD_BG
    box.line.color.rgb = RGBColor(226, 232, 240)
    
    tf = box.text_frame
    tf.word_wrap = True
    p1 = tf.paragraphs[0]
    p1.text = title.upper()
    p1.font.size = Pt(9)
    p1.font.bold = True
    p1.font.color.rgb = C_MUTED
    
    p2 = tf.add_paragraph()
    p2.text = val
    p2.font.size = Pt(20)
    p2.font.bold = True
    p2.font.color.rgb = col
    
    p3 = tf.add_paragraph()
    p3.text = sub
    p3.font.size = Pt(9)
    p3.font.color.rgb = C_MUTED

# 2 content blocks below
left_b = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(3.2), Inches(5.6), Inches(3.7))
left_b.fill.solid()
left_b.fill.fore_color.rgb = C_WHITE
left_b.line.color.rgb = RGBColor(226, 232, 240)
tf_l = left_b.text_frame
tf_l.word_wrap = True
tf_l.paragraphs[0].text = "THE COMMERCIAL DILEMMA"
tf_l.paragraphs[0].font.size = Pt(11)
tf_l.paragraphs[0].font.bold = True
tf_l.paragraphs[0].font.color.rgb = C_ROSE

points_l = [
    "Traditional Finance checks Naive Variance: Actual - Budget.",
    "Flaw: Penalizes marketing teams that overspend to drive huge sales growth, while letting teams that underperform sales slip by unnoticed.",
    "Philips spends €650M annually across 18 product lines in 21 countries. Without sales adjustment, management makes wrong budget cuts."
]
for p in points_l:
    para = tf_l.add_paragraph()
    para.text = "• " + p
    para.font.size = Pt(11)
    para.font.color.rgb = C_DARK

right_b = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(3.2), Inches(5.7), Inches(3.7))
right_b.fill.solid()
right_b.fill.fore_color.rgb = C_WHITE
right_b.line.color.rgb = RGBColor(226, 232, 240)
tf_r = right_b.text_frame
tf_r.word_wrap = True
tf_r.paragraphs[0].text = "OUR RECONCILIATION ENGINE"
tf_r.paragraphs[0].font.size = Pt(11)
tf_r.paragraphs[0].font.bold = True
tf_r.paragraphs[0].font.color.rgb = C_PRIMARY

points_r = [
    "Fair Allowance = Budget × (Actual Sales / Budget Sales) calculated at finest atomic grain (country × product × channel × month).",
    "Mathematical Identity Proven: Raw Variance (-€4.96M) = Justified (-€1.94M) + Real Overspend (-€3.02M).",
    "Net Global Discipline Masks Local Bleeding: While global totals look clean, Greater China (+€412K) and CEE (+€358K) experience serious real overspend."
]
for p in points_r:
    para = tf_r.add_paragraph()
    para.text = "• " + p
    para.font.size = Pt(11)
    para.font.color.rgb = C_DARK

# -------------------------------------------------------------
# SLIDE 3: Spend Truth Bridge Chart
# -------------------------------------------------------------
s3 = prs.slides.add_slide(blank_layout)
add_header(s3, "Market Bridge: Unmasking Hidden Variances")

s3.shapes.add_picture(chart1_path, Inches(0.8), Inches(1.8), Inches(7.5), Inches(4.8))

callout = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.6), Inches(1.8), Inches(4.0), Inches(4.8))
callout.fill.solid()
callout.fill.fore_color.rgb = C_WHITE
callout.line.color.rgb = RGBColor(226, 232, 240)
tf_c = callout.text_frame
tf_c.word_wrap = True
tf_c.paragraphs[0].text = "KEY MARKET TAKEAWAYS"
tf_c.paragraphs[0].font.size = Pt(12)
tf_c.paragraphs[0].font.bold = True
tf_c.paragraphs[0].font.color.rgb = C_PRIMARY

insights = [
    "North America & Western Europe:\nActual spend stayed well below Fair Allowance (-€2.10M and -€2.31M). Genuine operational discipline.",
    "Greater China:\nRaw variance looks flat (-€41K), but Fair Allowance shrank because sales missed plan. Reality: +€412K Real Overspend.",
    "Central Eastern Europe:\nSales dropped, but actual spend exceeded allowance by +€358K (+0.66%).",
    "Corporate Business Units:\n30 Business-reassigned pairs ended with +€382K real overspend, proving corporate allocations require stricter gates."
]
for ins in insights:
    p = tf_c.add_paragraph()
    p.text = "• " + ins
    p.font.size = Pt(10)
    p.font.color.rgb = C_DARK

# -------------------------------------------------------------
# SLIDE 4: Justification Quadrant
# -------------------------------------------------------------
s4 = prs.slides.add_slide(blank_layout)
add_header(s4, "Justification Quadrant: Spotting Real Waste vs Growth")

s4.shapes.add_picture(chart2_path, Inches(0.8), Inches(1.8), Inches(7.5), Inches(4.8))

callout4 = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.6), Inches(1.8), Inches(4.0), Inches(4.8))
callout4.fill.solid()
callout4.fill.fore_color.rgb = C_WHITE
callout4.line.color.rgb = RGBColor(226, 232, 240)
tf_c4 = callout4.text_frame
tf_c4.word_wrap = True
tf_c4.paragraphs[0].text = "DECISION MATRIX"
tf_c4.paragraphs[0].font.size = Pt(12)
tf_c4.paragraphs[0].font.bold = True
tf_c4.paragraphs[0].font.color.rgb = C_PRIMARY

quad_insights = [
    "Top-Left (Red Dots - Danger):\nOverspent on budget while sales declined. Worst offender: Hungary Patient Monitor (+38.8% overspend, -1.7% sales, 11 months flagged).",
    "Top-Right (Green Dots - Growth):\nOverspent on budget, but sales exceeded plan. The extra spend earned revenue and was fully justified.",
    "Bottom-Right (Emerald Benchmarks):\nSales grew while spend was below allowance. Benchmark: Netherlands Hair Dryer (-16.4% spend efficiency).",
    "Interactive UI Click-to-Inspect:\nDashboard breaks down Local vs Central split for every point to identify execution vs allocation blame."
]
for q in quad_insights:
    p = tf_c4.add_paragraph()
    p.text = "• " + q
    p.font.size = Pt(10)
    p.font.color.rgb = C_DARK

# -------------------------------------------------------------
# SLIDE 5: Monthly Trajectory (Timing vs Structural)
# -------------------------------------------------------------
s5 = prs.slides.add_slide(blank_layout)
add_header(s5, "Monthly Seasonality: Corrected Variance Analysis")

s5.shapes.add_picture(chart3_path, Inches(0.8), Inches(1.8), Inches(7.5), Inches(4.8))

callout5 = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.6), Inches(1.8), Inches(4.0), Inches(4.8))
callout5.fill.solid()
callout5.fill.fore_color.rgb = C_WHITE
callout5.line.color.rgb = RGBColor(226, 232, 240)
tf_c5 = callout5.text_frame
tf_c5.word_wrap = True
tf_c5.paragraphs[0].text = "ANOMALY INSIGHTS"
tf_c5.paragraphs[0].font.size = Pt(12)
tf_c5.paragraphs[0].font.bold = True
tf_c5.paragraphs[0].font.color.rgb = C_PRIMARY

month_insights = [
    "Statistical Engine (Median/MAD):\nFlags |z| > 3.5 per market combined with 1.5× IQR fences to catch non-normal outliers.",
    "July Campaign Spikes:\nStatistically verified high-confidence spikes in Greater China (z = +3.84) and Growth Markets (z = +4.02).",
    "December Deception:\nRaw budget line shows a massive plunge (-€1.29M). Naive finance assumes crisis. Corrected variance reveals it was mostly sales-justified (-€542K).",
    "145 Total Flagged Anomalies:\n76 High-Confidence (both detectors agree) + 69 Medium-Confidence."
]
for mi in month_insights:
    p = tf_c5.add_paragraph()
    p.text = "• " + mi
    p.font.size = Pt(10)
    p.font.color.rgb = C_DARK

# -------------------------------------------------------------
# SLIDE 6: Strategy & Top-5 Score-Maximizing Actions
# -------------------------------------------------------------
s6 = prs.slides.add_slide(blank_layout)
add_header(s6, "Actionable Strategy: Capital Reallocation Playbook")

strat_items = data['strategy'][:5]
col_w = Inches(11.7)

tb_strat = s6.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(11.7), Inches(5.2))
tf_s = tb_strat.text_frame
tf_s.word_wrap = True

p_head = tf_s.paragraphs[0]
p_head.text = "TOP-5 GLOBAL SCORE-MAXIMISING ACTIONS (RANKED BY EUR RECOVERY IMPACT)"
p_head.font.size = Pt(12)
p_head.font.bold = True
p_head.font.color.rgb = C_PRIMARY

for i, act in enumerate(strat_items):
    p_num = tf_s.add_paragraph()
    p_num.text = f"Action #{i+1}: {act['market']} — Estimated Recovery: €{act['est_saving_eur']:,.0f}"
    p_num.font.size = Pt(11)
    p_num.font.bold = True
    p_num.font.color.rgb = C_DARK
    
    p_desc = tf_s.add_paragraph()
    p_desc.text = act['action']
    p_desc.font.size = Pt(10)
    p_desc.font.color.rgb = C_MUTED

p_rec = tf_s.add_paragraph()
p_rec.text = "Reallocation Logic: Never blindly cut spend. Cap overspending pairs back to allowance, and reallocate liberated capital directly to efficiency benchmark products."
p_rec.font.size = Pt(10)
p_rec.font.italic = True
p_rec.font.color.rgb = C_PRIMARY

# -------------------------------------------------------------
# SLIDE 7: Technical Architecture & Data Trust
# -------------------------------------------------------------
s7 = prs.slides.add_slide(blank_layout)
add_header(s7, "Technical Rigor & 93.5/100 Data Trust Score")

b1 = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0))
b1.fill.solid()
b1.fill.fore_color.rgb = C_WHITE
b1.line.color.rgb = RGBColor(226, 232, 240)
tf_b1 = b1.text_frame
tf_b1.word_wrap = True
tf_b1.paragraphs[0].text = "DATA ETL & CLEANING AUDIT"
tf_b1.paragraphs[0].font.size = Pt(11)
tf_b1.paragraphs[0].font.bold = True
tf_b1.paragraphs[0].font.color.rgb = C_PRIMARY

audit_pts = [
    "28 Exact Duplicates dropped (8,780 -> 8,752 rows).",
    "Excluded 2,188 Other Selling Expenses rows (6,564 clean active rows).",
    "13 Missing Amounts Imputed via median actual/budget ratio per country+product+metric; 0 dropped.",
    "Fixed 6 A&P Local sign-entry errors (positive actual with negative budget).",
    "Mapped 1,957 short market codes and reassigned 1,672 Business rows (0 overlap).",
    "Divided local currencies by FX rates across 17 currencies; 1:1 country validation.",
    "Applied Unit Scale Multiplier = 1,000 (reconciled within 1.13% of €650M target)."
]
for pt in audit_pts:
    p = tf_b1.add_paragraph()
    p.text = "✓ " + pt
    p.font.size = Pt(10)
    p.font.color.rgb = C_DARK

b2 = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.0))
b2.fill.solid()
b2.fill.fore_color.rgb = C_WHITE
b2.line.color.rgb = RGBColor(226, 232, 240)
tf_b2 = b2.text_frame
tf_b2.word_wrap = True
tf_b2.paragraphs[0].text = "ARCHITECTURE & USER EXPERIENCE"
tf_b2.paragraphs[0].font.size = Pt(11)
tf_b2.paragraphs[0].font.bold = True
tf_b2.paragraphs[0].font.color.rgb = C_DARK

arch_pts = [
    "Zero-Backend UI Architecture: React 18 + Tailwind CSS + Recharts reading frozen dashboard_data.json.",
    "Production Ready: Bundled in 2.66s via Vite with zero runtime errors.",
    "5 Interactive Cockpit Tabs: Overview, Justification Quadrant, Best & Worst, Strategy, and Data Quality.",
    "Rule-Based Commentary: 100% deterministic, audit-compliant template engine generating natural language narratives without external LLM dependencies.",
    "Reconciliation Guarantee: Mathematically verified identity across all 6 markets and global rollup."
]
for pt in arch_pts:
    p = tf_b2.add_paragraph()
    p.text = "✓ " + pt
    p.font.size = Pt(10)
    p.font.color.rgb = C_DARK

# Save presentation
OUTPUT_PPTX = "Spend_Truth_Engine_Presentation.pptx"
prs.save(OUTPUT_PPTX)
print(f"Presentation saved successfully to: {OUTPUT_PPTX}")
