import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)

pdf_filename = "Spend_Truth_Engine_Speaker_Guide.pdf"
doc = SimpleDocTemplate(
    pdf_filename,
    pagesize=letter,
    rightMargin=45,
    leftMargin=45,
    topMargin=40,
    bottomMargin=40
)

styles = getSampleStyleSheet()

# Custom styles
title_style = ParagraphStyle(
    'DocTitle',
    parent=styles['Heading1'],
    fontName='Helvetica-Bold',
    fontSize=22,
    leading=26,
    textColor=colors.HexColor('#0F172A'),
    spaceAfter=4
)

subtitle_style = ParagraphStyle(
    'DocSubTitle',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=11,
    leading=15,
    textColor=colors.HexColor('#4F46E5'),
    spaceAfter=15
)

h1_style = ParagraphStyle(
    'SlideHeading',
    parent=styles['Heading2'],
    fontName='Helvetica-Bold',
    fontSize=14,
    leading=18,
    textColor=colors.HexColor('#1E293B'),
    spaceBefore=12,
    spaceAfter=6
)

body_style = ParagraphStyle(
    'BodyTextCustom',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=9.5,
    leading=14,
    textColor=colors.HexColor('#334155'),
    spaceAfter=6
)

script_style = ParagraphStyle(
    'ScriptText',
    parent=styles['Normal'],
    fontName='Helvetica-Oblique',
    fontSize=9.5,
    leading=14,
    textColor=colors.HexColor('#0F172A'),
    spaceAfter=6
)

bullet_style = ParagraphStyle(
    'BulletCustom',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=9,
    leading=13,
    textColor=colors.HexColor('#334155'),
    leftIndent=15,
    spaceAfter=4
)

badge_style = ParagraphStyle(
    'Badge',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=8.5,
    textColor=colors.HexColor('#4F46E5')
)

story = []

# Document Header
story.append(Paragraph("Spend Truth Engine — Pitch & Speaker Script", title_style))
story.append(Paragraph("PHILIPS HACKATHON 2026 • EXACT SLIDE-BY-SLIDE PRESENTATION GUIDE", subtitle_style))
story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#E2E8F0'), spaceAfter=12))

# Executive Overview box
summary_data = [
    [Paragraph("<b>Core Problem</b>", badge_style), Paragraph("Philips spends ~€650M on A&P across 18 product lines and 21 countries. Static budget comparisons penalize marketing teams that overspend to drive profitable sales growth, while ignoring teams that hit their budget during severe sales declines.", body_style)],
    [Paragraph("<b>Core Solution</b>", badge_style), Paragraph("The Spend Truth Engine establishes <b>Fair Allowance</b> at the atomic channel-by-month grain, mathematically splitting naive raw variance into <b>Sales-Justified Spend</b> vs. <b>Real Overspend</b>.", body_style)],
    [Paragraph("<b>Key Reconciliation</b>", badge_style), Paragraph("<b>Raw Variance (-€4.96M) = Justified (-€1.94M) + Real Overspend (-€3.02M)</b>. Validated to the exact cent across all 6 markets and global rollup.", body_style)]
]
t_sum = Table(summary_data, colWidths=[110, 410])
t_sum.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
    ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
]))
story.append(t_sum)
story.append(Spacer(1, 14))

# Slides Breakdown
slides_info = [
    {
        "slide": "Slide 1: Title & Executive Introduction",
        "focus": "Establish authority, commercial context, and team mandate.",
        "what_to_show": "Title slide on widescreen (Dark Navy Theme with Indigo branding accents).",
        "script": "“Good morning judges. We are presenting the Spend Truth Engine. Philips spends approximately €650 million annually on Advertising & Promotion. Today, we demonstrate how our solution solves a fundamental commercial finance challenge: separating smart, sales-justified investments from true budget waste.”",
        "key_points": [
            "Scale: €650M A&P spend, 18 product units, 21 countries, 6 operating markets.",
            "Audience context: Positioned for the CFO, Commercial VP, and Financial Controllers.",
            "Promise: A boardroom-auditable, zero-latency decision cockpit."
        ]
    },
    {
        "slide": "Slide 2: Problem Statement & Core Financial Truth",
        "focus": "Prove the mathematical breakdown of Raw Variance.",
        "what_to_show": "4 Top KPI Cards (€642.66M Actual, €645.68M Allowance, -€1.94M Justified, -€3.02M Real Overspend) and side-by-side dilemma box.",
        "script": "“Looking at naive budget variance, Philips appears to have underspent by €5M. But that number is incomplete. Because sales came in -0.34% below target, our Fair Allowance shrank to €645.68M. That -€1.94M is Justified Spend. The remaining -€3.02M represents Real Overspend (disciplined underspend). Our formula holds exactly: Raw Variance = Justified + Real Overspend.”",
        "key_points": [
            "Formula: Fair Allowance = Budget × (Actual Sales / Budget Sales).",
            "Proof: Global A&P actual €642.66M is 11.52% of Total Sales (within target 11-12%).",
            "Why it matters: Eliminates finger-pointing between Marketing and Finance."
        ]
    },
    {
        "slide": "Slide 3: Market Waterfall Bridge (Unmasking Variances)",
        "focus": "Show how market-level aggregates hide local overspends.",
        "what_to_show": "Grouped bar chart showing Budget vs Fair Allowance vs Actual Spend across all 6 markets.",
        "script": "“This chart exposes why static budgeting fails. Look at Greater China: its raw budget variance appears flat at -€41,000, so finance would never audit it. But because sales missed plan, China's Fair Allowance dropped significantly—meaning China actually ran a +€412,000 Real Overspend. In CEE, real overspend was +€358,000. Meanwhile, North America and Western Europe delivered genuine efficiency.”",
        "key_points": [
            "Greater China: Raw -€41K vs Real +€412K (the biggest hidden trap).",
            "North America: -€2.10M below allowance (largest absolute EUR savings).",
            "Western Europe: -€2.31M below allowance (-2.04% vs allowance, best efficiency benchmark)."
        ]
    },
    {
        "slide": "Slide 4: Justification Quadrant (Waste vs. Growth)",
        "focus": "Visual decision matrix separating rogue spend from justified investments.",
        "what_to_show": "Scatter plot (Sales Growth % vs Spend Deviation %) with annotated outliers.",
        "script": "“This is our Justification Quadrant. In the top-left danger zone, products overspent budget while sales declined. Our worst company offender is Hungary Patient Monitor—overspending by +38.8% above allowance with sales down -1.7%, triggering flags in 11 of 12 months. Conversely, in the bottom-right, Netherlands Hair Dryer is our benchmark, achieving sales targets while operating -16.4% below allowance.”",
        "key_points": [
            "Top-Left (Danger): Overspent budget + missed sales (Hungary Patient Monitor, z = +15.39).",
            "Top-Right (Justified Growth): Overspent budget, but sales grew even faster.",
            "Local vs Central Split: Interactive dashboard shows whether overspend is local marketing execution or central allocation."
        ]
    },
    {
        "slide": "Slide 5: Monthly Trajectory & Seasonality Analysis",
        "focus": "Statistical rigor: Median/MAD outlier detection across 12 months.",
        "what_to_show": "12-month composed chart: Black raw variance line vs Red/Green corrected variance bars.",
        "script": "“Because promotional spend is heavy-tailed (-0.9 to 3.1 ratio), standard deviation is distorted. We applied Robust Z-Scores via Median and MAD combined with 1.5× IQR fences. In July, our engine caught high-confidence promotional spikes in Greater China (z = +3.84) and Growth Markets (z = +4.02). In December, the raw line plunges to -€1.29M, but corrected variance proves it was mostly sales-justified (-€542K).”",
        "key_points": [
            "Methodology: z = 0.6745 × (x - median) / MAD with IQR fallback.",
            "145 total flagged deviations: 76 High-Confidence + 69 Medium-Confidence.",
            "July spike: Confirms the brief's suspicion with verified statistical confidence."
        ]
    },
    {
        "slide": "Slide 6: Actionable Strategy (Capital Reallocation)",
        "focus": "Prescriptive EUR cash recovery and capital reallocation.",
        "what_to_show": "Top-5 Score-Maximizing Actions ranked by EUR recovery impact.",
        "script": "“Analytics without action is just trivia. Slide 6 provides a concrete Capital Reallocation Playbook. Rather than across-the-board budget cuts, our engine prescribes specific caps on our top 5 worst overspenders, recovering €1.4M in direct cash leakage and reallocating headroom toward proven efficiency benchmarks like Taiwan Hospital Software and Canada Sonic Toothbrush.”",
        "key_points": [
            "Action 1: China Electric Razor — recover €503.7K.",
            "Action 2: Hungary Patient Monitor — recover €237.2K via approval gate.",
            "Action 3: US Hair Straightener — recover €229.6K.",
            "Action 4 & 5: Brazil and Australia Sonic Toothbrush — recover €438K."
        ]
    },
    {
        "slide": "Slide 7: Technical Rigor & 93.5/100 Data Trust Score",
        "focus": "Data integrity, zero-backend architecture, and auditability.",
        "what_to_show": "ETL audit checklist and frontend software architecture.",
        "script": "“Finally, technical excellence. We achieved a 93.5/100 Data Trust Score. 28 duplicates dropped, 13 missing values imputed via median ratios, 6 sign entry errors corrected, and 17 currencies cleanly converted. The frontend is a zero-backend React 18 dashboard built with Vite in 2.66s, powered by a deterministic template engine that eliminates LLM hallucinations.”",
        "key_points": [
            "Clean Data: 8,780 raw rows -> 8,752 deduped -> 6,564 active rows.",
            "Performance: Instant UI switching, zero runtime errors, zero database cost.",
            "Audit Trail: Fully detailed in the live Data Quality tab and transformed Excel workbook."
        ]
    }
]

for s in slides_info:
    card_content = []
    card_content.append(Paragraph(f"<b>{s['slide']}</b>", h1_style))
    card_content.append(Paragraph(f"<b>Objective:</b> {s['focus']}", body_style))
    card_content.append(Paragraph(f"<b>What to Display:</b> {s['what_to_show']}", body_style))
    card_content.append(Spacer(1, 4))
    card_content.append(Paragraph("<b>Exact Pitch Script (What to Say):</b>", badge_style))
    card_content.append(Paragraph(s['script'], script_style))
    card_content.append(Spacer(1, 4))
    card_content.append(Paragraph("<b>Key Facts & Numbers to Highlight:</b>", badge_style))
    for kp in s['key_points']:
        card_content.append(Paragraph(f"• {kp}", bullet_style))
    card_content.append(Spacer(1, 8))
    card_content.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor('#E2E8F0'), spaceAfter=8))
    story.append(KeepTogether(card_content))

# Live Demo Transition Guidance
demo_guide = [
    Paragraph("<b>PRO DEMO STRATEGY & TRANSITION</b>", h1_style),
    Paragraph("1. Walk through Slides 1 to 4 in PowerPoint to establish the commercial problem and reveal the charts.", body_style),
    Paragraph("2. <b>Live Switch:</b> Alt-Tab into the browser at <code>http://localhost:3000/</code>.", body_style),
    Paragraph("3. Click on <b>Hungary Patient Monitor</b> (extreme top-left dot) in the <b>Justification Quadrant</b> to show the interactive Local vs Central split bar and rule-based commentary.", body_style),
    Paragraph("4. Click the <b>Strategy</b> and <b>Data Quality</b> tabs to show the 93.5/100 Trust Score and the 12-check audit log.", body_style),
    Paragraph("5. Switch back to Slide 6 & 7 to deliver the final conclusion.", body_style)
]
story.append(KeepTogether(demo_guide))

doc.build(story)
print(f"Speaker Guide PDF generated successfully: {pdf_filename}")
