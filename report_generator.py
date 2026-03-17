import os
import tempfile
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Table, TableStyle, PageBreak, KeepTogether, Image)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import io


class ReportGenerator:
    """Generate professional PDF reports for financial analysis — with embedded charts"""

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="finanalyzer_")
        self.styles = getSampleStyleSheet()

        self.colors = {
            'primary':        colors.HexColor('#1565C0'),
            'primary_dark':   colors.HexColor('#0D47A1'),
            'primary_light':  colors.HexColor('#E3F2FD'),
            'primary_medium': colors.HexColor('#42A5F5'),
            'success':        colors.HexColor('#4CAF50'),
            'success_light':  colors.HexColor('#E8F5E9'),
            'success_medium': colors.HexColor('#81C784'),
            'warning':        colors.HexColor('#FF9800'),
            'warning_light':  colors.HexColor('#FFF3E0'),
            'warning_dark':   colors.HexColor('#F57C00'),
            'danger':         colors.HexColor('#F44336'),
            'danger_light':   colors.HexColor('#FFEBEE'),
            'danger_medium':  colors.HexColor('#E57373'),
            'gray_dark':      colors.HexColor('#424242'),
            'gray_medium':    colors.HexColor('#757575'),
            'gray_light':     colors.HexColor('#FAFAFA'),
            'gray_border':    colors.HexColor('#E0E0E0'),
            'bg_white':       colors.white,
            'bg_light':       colors.HexColor('#F5F7FA'),
            'bg_section':     colors.HexColor('#F8F9FA'),
        }

        # Matplotlib color palette (matches web UI)
        self._mpl_colors = ['#1976D2','#2E7D32','#F57C00','#C62828','#7B1FA2',
                            '#00838F','#F9A825','#37474F','#AD1457','#558B2F']

        self._setup_custom_styles()

    # ------------------------------------------------------------------
    # STYLES
    # ------------------------------------------------------------------
    def _setup_custom_styles(self):
        defs = [
            ("CoverTitle",     dict(parent='Title',   fontSize=36, textColor=self.colors['primary_dark'], spaceAfter=16, alignment=TA_CENTER, fontName='Helvetica-Bold', leading=42)),
            ("CoverSubtitle",  dict(parent='Normal',  fontSize=14, textColor=self.colors['gray_medium'],  spaceAfter=8,  alignment=TA_CENTER, fontName='Helvetica',      leading=18)),
            ("SectionHeader",  dict(parent='Heading1',fontSize=16, textColor=colors.white, spaceBefore=20, spaceAfter=12, fontName='Helvetica-Bold', leading=20, borderPadding=10, backColor=self.colors['primary'], leftIndent=10, rightIndent=10)),
            ("SubSectionHeader",dict(parent='Heading2',fontSize=12, textColor=self.colors['primary'], spaceBefore=14, spaceAfter=8, fontName='Helvetica-Bold', leading=15, leftIndent=6, borderPadding=6, backColor=self.colors['primary_light'])),
            ("BodyText",       dict(parent='Normal',  fontSize=10, leading=14, textColor=self.colors['gray_dark'], fontName='Helvetica', alignment=TA_JUSTIFY, spaceAfter=6, spaceBefore=2)),
            ("HighlightBox",   dict(parent='Normal',  fontSize=9,  leading=13, textColor=self.colors['primary_dark'], leftIndent=10, rightIndent=10, borderWidth=1, borderColor=self.colors['primary'],  borderPadding=10, backColor=self.colors['primary_light'], fontName='Helvetica', spaceBefore=8, spaceAfter=8)),
            ("SuccessBox",     dict(parent='Normal',  fontSize=9,  leading=13, textColor=self.colors['success'],      leftIndent=10, rightIndent=10, borderWidth=1, borderColor=self.colors['success'],  borderPadding=10, backColor=self.colors['success_light'], fontName='Helvetica', spaceBefore=8, spaceAfter=8)),
            ("WarningBox",     dict(parent='Normal',  fontSize=9,  leading=13, textColor=self.colors['warning_dark'], leftIndent=10, rightIndent=10, borderWidth=1, borderColor=self.colors['warning'],  borderPadding=10, backColor=self.colors['warning_light'], fontName='Helvetica', spaceBefore=8, spaceAfter=8)),
            ("DangerBox",      dict(parent='Normal',  fontSize=9,  leading=13, textColor=self.colors['danger'],       leftIndent=10, rightIndent=10, borderWidth=1, borderColor=self.colors['danger'],   borderPadding=10, backColor=self.colors['danger_light'],  fontName='Helvetica', spaceBefore=8, spaceAfter=8)),
        ]
        for name, kwargs in defs:
            if name not in self.styles:
                parent_name = kwargs.pop('parent', 'Normal')
                self.styles.add(ParagraphStyle(name=name, parent=self.styles[parent_name], **kwargs))

    # ------------------------------------------------------------------
    # PUBLIC: ANALYSIS REPORT
    # ------------------------------------------------------------------
    def generate_analysis_report(self, analysis, company) -> str:
        pdf_path = os.path.join(self.temp_dir, f"analysis_report_{analysis.id}.pdf")
        doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2.5*cm, bottomMargin=2.5*cm,
                                title=f"Financial Analysis - {company.name}",
                                author="FinAnalyzer Pro")
        story = []
        story.extend(self._create_cover_page(company, analysis));           story.append(PageBreak())
        story.extend(self._create_health_score_section(analysis, company)); story.append(PageBreak())
        story.extend(self._create_chart_page(analysis, company));           story.append(PageBreak())
        story.extend(self._create_executive_summary(analysis, company));    story.append(PageBreak())

        alerts = analysis.ai_analysis.get('alerts', [])
        if alerts:
            story.extend(self._create_alerts_section(analysis)); story.append(PageBreak())

        story.extend(self._create_financial_overview(analysis));                                           story.append(PageBreak())
        story.extend(self._create_ratio_analysis_by_category(analysis,'liquidity','Liquidity Analysis')); story.append(PageBreak())
        story.extend(self._create_ratio_analysis_by_category(analysis,'profitability','Profitability Analysis')); story.append(PageBreak())
        story.extend(self._create_ratio_analysis_by_category(analysis,'solvency','Solvency Analysis'));   story.append(PageBreak())
        story.extend(self._create_ratio_analysis_by_category(analysis,'efficiency','Efficiency Analysis')); story.append(PageBreak())
        story.extend(self._create_recommendations_section(analysis));                                     story.append(PageBreak())
        story.extend(self._create_appendix(analysis))

        doc.build(story, onFirstPage=self._add_header_footer, onLaterPages=self._add_header_footer)
        return pdf_path

    # ------------------------------------------------------------------
    # CHARTS PAGE — NEW
    # ------------------------------------------------------------------
    def _create_chart_page(self, analysis, company):
        """Embed matplotlib charts: Radar + Bar + Waterfall into the PDF"""
        elements = []
        elements.append(Paragraph("<b>📊 VISUAL FINANCIAL OVERVIEW</b>", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.4*cm))

        health_data    = analysis.ai_analysis.get('health_score', {})
        category_scores = health_data.get('category_scores', {})
        financial_data  = analysis.financial_data
        raw             = financial_data.raw_data

        # ---- ROW 1: Radar + Category Bar (side by side) ----
        try:
            radar_img = self._make_radar_chart(category_scores, company.name)
            bar_img   = self._make_category_bar(category_scores)
            row = [[radar_img, bar_img]]
            t = Table(row, colWidths=[9*cm, 9*cm])
            t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'), ('LEFTPADDING',(0,0),(-1,-1),4), ('RIGHTPADDING',(0,0),(-1,-1),4)]))
            elements.append(t)
            elements.append(Spacer(1, 0.6*cm))
        except Exception as e:
            elements.append(Paragraph(f"[Chart generation error: {e}]", self.styles['BodyText']))

        # ---- ROW 2: Waterfall (Revenue → Net Income) ----
        try:
            wf_img = self._make_waterfall_chart(raw, company.name)
            elements.append(Paragraph("<b>📉 Revenue to Net Income Waterfall</b>", self.styles['SubSectionHeader']))
            elements.append(Spacer(1, 0.3*cm))
            elements.append(wf_img)
        except Exception as e:
            elements.append(Paragraph(f"[Waterfall chart error: {e}]", self.styles['BodyText']))

        return elements

    def _make_radar_chart(self, category_scores, company_name):
        cats   = ['Liquidity', 'Profitability', 'Solvency', 'Efficiency']
        keys   = ['liquidity', 'profitability', 'solvency', 'efficiency']
        vals   = [category_scores.get(k, 0) for k in keys]
        N      = len(cats)
        angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
        vals   += vals[:1]; angles += angles[:1]

        fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
        ax.set_facecolor('#F8F9FA')
        fig.patch.set_facecolor('white')
        ax.plot(angles, vals, 'o-', linewidth=2.5, color='#1976D2')
        ax.fill(angles, vals, alpha=0.25, color='#1976D2')
        ax.set_thetagrids(np.degrees(angles[:-1]), cats, fontsize=10)
        ax.set_ylim(0, 100)
        ax.set_yticks([25, 50, 75, 100])
        ax.set_yticklabels(['25','50','75','100'], fontsize=7, color='#757575')
        ax.grid(color='#e0e0e0', linewidth=0.8)
        ax.set_title(f'Financial Radar\n{company_name}', fontsize=10, fontweight='bold', color='#0D47A1', pad=12)
        plt.tight_layout()

        buf = io.BytesIO(); fig.savefig(buf, format='PNG', dpi=150, bbox_inches='tight'); plt.close(fig); buf.seek(0)
        return Image(buf, width=8.5*cm, height=8*cm)

    def _make_category_bar(self, category_scores):
        cats   = ['Liquidity', 'Profitability', 'Solvency', 'Efficiency']
        keys   = ['liquidity', 'profitability', 'solvency', 'efficiency']
        vals   = [category_scores.get(k, 0) for k in keys]
        bar_colors = ['#4CAF50' if v>=70 else '#2196F3' if v>=55 else '#FF9800' if v>=40 else '#F44336' for v in vals]

        fig, ax = plt.subplots(figsize=(4, 3.5))
        fig.patch.set_facecolor('white'); ax.set_facecolor('#F8F9FA')
        bars = ax.barh(cats, vals, color=bar_colors, height=0.55, edgecolor='white', linewidth=1.5)
        for bar, val in zip(bars, vals):
            ax.text(min(val+2, 95), bar.get_y()+bar.get_height()/2, f'{val:.0f}', va='center', ha='left', fontsize=9, fontweight='bold', color='#424242')
        ax.set_xlim(0, 105); ax.set_xlabel('Score (/100)', fontsize=9); ax.set_title('Category Scores', fontsize=10, fontweight='bold', color='#0D47A1')
        ax.axvline(70, color='#4CAF50', linestyle='--', linewidth=1, alpha=0.7, label='Target (70)')
        ax.legend(fontsize=8); ax.grid(axis='x', color='#e0e0e0', linewidth=0.7); ax.set_axisbelow(True)
        plt.tight_layout()

        buf = io.BytesIO(); fig.savefig(buf, format='PNG', dpi=150, bbox_inches='tight'); plt.close(fig); buf.seek(0)
        return Image(buf, width=8.5*cm, height=7.5*cm)

    def _make_waterfall_chart(self, raw, company_name):
        revenue   = raw.get('revenue', 0) or 0
        cogs      = raw.get('total cogs', 0) or 0
        gross     = revenue - cogs
        op_exp    = raw.get('operating expenses', 0) or max(0, gross - (raw.get('ebit', gross) or gross))
        ebit      = raw.get('ebit', gross - op_exp) or 0
        interest  = raw.get('interest expense', 0) or 0
        net_inc   = raw.get('net income', 0) or 0

        labels = ['Revenue', '– COGS', 'Gross Profit', '– Op. Expenses', 'EBIT', '– Interest', 'Net Income']
        values = [revenue, -cogs, gross, -op_exp, ebit, -interest, net_inc]
        bar_clrs = ['#1976D2','#F44336','#4CAF50','#F44336','#2196F3','#F44336','#4CAF50' if net_inc>=0 else '#F44336']

        # Running totals for waterfall
        bottoms = [0, revenue, 0, gross, 0, ebit, 0]

        fig, ax = plt.subplots(figsize=(9, 4))
        fig.patch.set_facecolor('white'); ax.set_facecolor('#F8F9FA')

        for i, (lbl, val, bot, clr) in enumerate(zip(labels, values, bottoms, bar_clrs)):
            ax.bar(i, abs(val), bottom=bot if val>0 else bot+val, color=clr, width=0.6, edgecolor='white', linewidth=1.5, alpha=0.88)
            ypos = (bot + abs(val)/2) if val > 0 else (bot + val + abs(val)/2)
            ax.text(i, ypos, f'${abs(val)/1e6:.1f}M' if abs(val)>=1e6 else f'${abs(val):,.0f}',
                    ha='center', va='center', fontsize=8, fontweight='bold', color='white')

        ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, fontsize=9, rotation=20, ha='right')
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x,_: f'${x/1e6:.1f}M' if abs(x)>=1e6 else f'${x:,.0f}'))
        ax.set_title(f'Revenue Waterfall — {company_name}', fontsize=11, fontweight='bold', color='#0D47A1', pad=10)
        ax.grid(axis='y', color='#e0e0e0', linewidth=0.7); ax.set_axisbelow(True)
        legend_patches = [mpatches.Patch(color='#1976D2',label='Total'), mpatches.Patch(color='#4CAF50',label='Profit'), mpatches.Patch(color='#F44336',label='Deduction')]
        ax.legend(handles=legend_patches, fontsize=8, loc='upper right')
        plt.tight_layout()

        buf = io.BytesIO(); fig.savefig(buf, format='PNG', dpi=150, bbox_inches='tight'); plt.close(fig); buf.seek(0)
        return Image(buf, width=17*cm, height=7.5*cm)

    # ------------------------------------------------------------------
    # HEALTH SCORE SECTION
    # ------------------------------------------------------------------
    def _create_health_score_section(self, analysis, company):
        elements = []
        elements.append(Paragraph("<b>📊 FINANCIAL HEALTH SCORE DASHBOARD</b>", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.6*cm))

        health_data     = analysis.ai_analysis.get('health_score', {})
        overall_score   = health_data.get('overall_score', analysis.ai_analysis.get('overall', {}).get('health_score', 0))
        grade           = health_data.get('grade', 'N/A')
        grade_desc      = health_data.get('grade_description', '')
        category_scores = health_data.get('category_scores', {})
        interpretation  = health_data.get('interpretation', '')

        score_color = '#4CAF50' if overall_score >= 70 else '#FF9800' if overall_score >= 50 else '#F44336'
        score_card_data = [[
            Paragraph(f"<para align='center'><font size='42' color='{score_color}'><b>{overall_score}</b></font>"
                      f"<font size='18' color='{score_color}'>/100</font><br/>"
                      f"<font size='14' color='#0D47A1'><b>Grade: {grade}</b></font><br/>"
                      f"<font size='10' color='#757575'>{grade_desc}</font></para>", self.styles['BodyText']),
            Paragraph(f"<b>Financial Health Assessment</b><br/><br/>{interpretation}", self.styles['BodyText'])
        ]]
        score_table = Table(score_card_data, colWidths=[5*cm, 12*cm])
        score_table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(0,0),self.colors['primary_light']),
            ('BACKGROUND',(1,0),(1,0),colors.white),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('ALIGN',(0,0),(0,0),'CENTER'),
            ('GRID',(0,0),(-1,-1),1,self.colors['gray_border']),
            ('BOTTOMPADDING',(0,0),(-1,-1),15),
            ('TOPPADDING',(0,0),(-1,-1),15),
            ('LEFTPADDING',(0,0),(-1,-1),10),
        ]))
        elements.append(score_table)
        elements.append(Spacer(1, 0.8*cm))

        if category_scores:
            elements.append(Paragraph("<b>📈 Category Score Breakdown</b>", self.styles['SubSectionHeader']))
            elements.append(Spacer(1, 0.4*cm))
            cat_data = [[Paragraph("<b>Category</b>",self.styles['BodyText']),
                         Paragraph("<b>Score</b>",self.styles['BodyText']),
                         Paragraph("<b>Bar</b>",self.styles['BodyText']),
                         Paragraph("<b>Status</b>",self.styles['BodyText'])]]
            cat_labels = {'liquidity':'💧 Liquidity','profitability':'📈 Profitability','solvency':'🏦 Solvency','efficiency':'⚙️ Efficiency'}
            for cat_key, cat_label in cat_labels.items():
                score = category_scores.get(cat_key, 0)
                bar = '█'*int(score/5) + '░'*(20-int(score/5))
                if score>=70: status_text,status_color='Strong','#4CAF50'
                elif score>=55: status_text,status_color='Good','#2196F3'
                elif score>=40: status_text,status_color='Fair','#FF9800'
                else: status_text,status_color='Weak','#F44336'
                cat_data.append([
                    Paragraph(cat_label, self.styles['BodyText']),
                    Paragraph(f"<b><font color='{status_color}'>{score:.0f}/100</font></b>", self.styles['BodyText']),
                    Paragraph(f"<font face='Courier' size='9' color='{status_color}'>{bar}</font>", self.styles['BodyText']),
                    Paragraph(f"<font color='{status_color}'><b>{status_text}</b></font>", self.styles['BodyText'])
                ])
            cat_table = Table(cat_data, colWidths=[4.5*cm,3*cm,6*cm,3.5*cm])
            cat_table.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),self.colors['primary']),
                ('TEXTCOLOR',(0,0),(-1,0),colors.white),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),('ALIGN',(0,1),(0,-1),'LEFT'),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10),
                ('BOTTOMPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),12),
                ('GRID',(0,0),(-1,-1),1,self.colors['gray_border']),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,self.colors['bg_section']])
            ]))
            elements.append(cat_table)
            elements.append(Spacer(1, 0.8*cm))

        strengths  = health_data.get('strengths', [])
        weaknesses = health_data.get('weaknesses', [])
        alerts_summary = analysis.ai_analysis.get('alert_summary', {})

        if strengths:
            elements.append(Paragraph("<b>💪 Key Strengths</b>", self.styles['BodyText']))
            elements.append(Paragraph("<br/>".join([f"✅ {s}" for s in strengths]), self.styles['SuccessBox']))
            elements.append(Spacer(1, 0.4*cm))
        if weaknesses:
            elements.append(Paragraph("<b>🎯 Improvement Areas</b>", self.styles['BodyText']))
            elements.append(Paragraph("<br/>".join([f"⚠️ {w}" for w in weaknesses]), self.styles['WarningBox']))
            elements.append(Spacer(1, 0.4*cm))

        if alerts_summary.get('total', 0) > 0:
            critical_count = alerts_summary.get('critical', 0)
            high_count     = alerts_summary.get('high', 0)
            total_alerts   = alerts_summary.get('total', 0)
            alert_text = (f"<b>🚨 Alert Summary:</b> {total_alerts} total alerts — "
                          f"<font color='#F44336'>{critical_count} Critical</font> | "
                          f"<font color='#FF9800'>{high_count} High Priority</font>. "
                          "See the Alerts section for details.")
            elements.append(Paragraph(alert_text, self.styles['DangerBox'] if critical_count>0 else self.styles['WarningBox']))

        return elements

    # ------------------------------------------------------------------
    # ALERTS SECTION
    # ------------------------------------------------------------------
    def _create_alerts_section(self, analysis):
        elements = []
        elements.append(Paragraph("<b>🚨 AUTOMATED FINANCIAL ALERTS</b>", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.4*cm))

        alerts = analysis.ai_analysis.get('alerts', [])
        alert_summary = analysis.ai_analysis.get('alert_summary', {})
        if not alerts:
            elements.append(Paragraph("✅ No threshold breaches detected.", self.styles['SuccessBox']))
            return elements

        summary_text = (f"<b>Alert Summary:</b> {alert_summary.get('total',len(alerts))} alerts | "
                        f"Critical: {alert_summary.get('critical',0)} | High: {alert_summary.get('high',0)} | "
                        f"Medium: {alert_summary.get('medium',0)}")
        elements.append(Paragraph(summary_text, self.styles['DangerBox'] if alert_summary.get('critical',0)>0 else self.styles['WarningBox']))
        elements.append(Spacer(1, 0.6*cm))

        severity_order  = ['critical','high','medium','low']
        severity_config = {
            'critical': ('🔴 CRITICAL ALERTS', self.colors['danger'],       self.colors['danger_light']),
            'high':     ('🟠 HIGH PRIORITY',   self.colors['warning_dark'], self.colors['warning_light']),
            'medium':   ('🟡 MEDIUM PRIORITY', colors.HexColor('#F57C00'),  colors.HexColor('#FFF8E1')),
            'low':      ('🔵 LOW PRIORITY',    self.colors['primary'],      self.colors['primary_light']),
        }

        for severity in severity_order:
            sev_alerts = [a for a in alerts if a.get('severity')==severity]
            if not sev_alerts: continue
            label, txt_clr, bg_clr = severity_config[severity]
            elements.append(Paragraph(f"<b>{label}</b>", self.styles['SubSectionHeader']))
            elements.append(Spacer(1, 0.3*cm))
            tbl_data = [[Paragraph("<b>Ratio</b>",self.styles['BodyText']),Paragraph("<b>Value</b>",self.styles['BodyText']),Paragraph("<b>Issue</b>",self.styles['BodyText']),Paragraph("<b>Benchmark</b>",self.styles['BodyText'])]]
            for alert in sev_alerts:
                tbl_data.append([
                    Paragraph(f"<b>{alert.get('ratio','N/A')}</b>", self.styles['BodyText']),
                    Paragraph(f"{alert.get('value',0):.2f}", self.styles['BodyText']),
                    Paragraph(alert.get('gap','See message'), self.styles['BodyText']),
                    Paragraph(alert.get('industry_benchmark','N/A'), self.styles['BodyText'])
                ])
            tbl = Table(tbl_data, colWidths=[4*cm,3*cm,5*cm,5*cm])
            tbl.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),txt_clr),('TEXTCOLOR',(0,0),(-1,0),colors.white),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),('ALIGN',(0,1),(0,-1),'LEFT'),
                ('FONTSIZE',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),
                ('GRID',(0,0),(-1,-1),0.5,self.colors['gray_border']),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,bg_clr])
            ]))
            elements.append(tbl); elements.append(Spacer(1,0.4*cm))
            if severity in ('critical','high'):
                for alert in sev_alerts:
                    action = alert.get('action','')
                    if action:
                        elements.append(Paragraph(f"<b>→ {alert.get('ratio')}:</b> {action}", self.styles['DangerBox'] if severity=='critical' else self.styles['WarningBox']))
                        elements.append(Spacer(1,0.2*cm))
            elements.append(Spacer(1,0.4*cm))
        return elements

    # ------------------------------------------------------------------
    # COVER PAGE
    # ------------------------------------------------------------------
    def _create_cover_page(self, company, analysis):
        elements = []
        elements.append(Spacer(1, 3*cm))
        elements.append(Paragraph("<b>FINANCIAL ANALYSIS REPORT</b>", self.styles['CoverTitle']))
        elements.append(Spacer(1, 1.5*cm))
        elements.append(Paragraph(f"<para align='center' fontSize='18' textColor='#0D47A1'><b>{company.name}</b></para>", self.styles['BodyText']))
        elements.append(Spacer(1, 0.5*cm))
        if company.industry:
            elements.append(Paragraph(f"<para align='center' fontSize='12' textColor='#757575'>Industry: {company.industry}</para>", self.styles['BodyText']))
            elements.append(Spacer(1, 1.5*cm))
        fd = analysis.financial_data
        elements.append(Paragraph(f"<para align='center' fontSize='11' textColor='#424242'><b>Analysis Period</b><br/><br/>{fd.period_start.strftime('%B %d, %Y')} — {fd.period_end.strftime('%B %d, %Y')}</para>", self.styles['BodyText']))
        elements.append(Spacer(1, 3*cm))
        elements.append(Paragraph(f"<para align='center' fontSize='9' color='#757575'><b>Report Generated:</b> {date.today().strftime('%B %d, %Y')}<br/><b>Analysis ID:</b> #{analysis.id}<br/><b>Prepared by:</b> FinAnalyzer Pro AI Platform<br/><b>Developer:</b> Anas Ata Meawi</para>", self.styles['BodyText']))
        return elements

    # ------------------------------------------------------------------
    # EXECUTIVE SUMMARY
    # ------------------------------------------------------------------
    def _create_executive_summary(self, analysis, company):
        elements = []
        elements.append(Paragraph("<b>EXECUTIVE SUMMARY</b>", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.6*cm))
        overall      = analysis.ai_analysis.get('overall', {})
        health_score = overall.get('health_score', 50)

        summary_data = [
            [Paragraph("<b>Metric</b>",self.styles['BodyText']), Paragraph("<b>Value</b>",self.styles['BodyText']), Paragraph("<b>Status</b>",self.styles['BodyText'])],
            ["Financial Health Score", Paragraph(f"<b><font size='14' color='#1565C0'>{health_score}/100</font></b>",self.styles['BodyText']), self._get_status_indicator(health_score)],
            ["Risk Level", Paragraph(f"<b>{overall.get('risk_level','Medium')}</b>",self.styles['BodyText']), self._get_risk_indicator(overall.get('risk_level','Medium'))],
            ["Investment Rating", Paragraph(f"<b>{self._extract_rating_str(overall.get('investment_rating','Hold'))}</b>",self.styles['BodyText']), "⭐"*self._get_star_rating(overall.get('investment_rating','Hold'))],
        ]
        summary_table = Table(summary_data, colWidths=[6.5*cm,5*cm,5.5*cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),self.colors['primary']),('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('ALIGN',(0,0),(-1,0),'CENTER'),('ALIGN',(0,1),(0,-1),'LEFT'),('ALIGN',(1,1),(-1,-1),'CENTER'),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10),
            ('BOTTOMPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),12),
            ('BACKGROUND',(0,1),(-1,-1),colors.white),('GRID',(0,0),(-1,-1),1,self.colors['gray_border']),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,self.colors['bg_section']])
        ]))
        elements.append(summary_table); elements.append(Spacer(1,0.8*cm))

        elements.append(Paragraph("<b>💪 Key Strengths</b>", self.styles['SubSectionHeader']))
        elements.append(Spacer(1, 0.3*cm))
        strengths = overall.get('strengths', [])[:3]
        if strengths:
            elements.append(Paragraph("<br/>".join([f"✓ {s}" for s in strengths]), self.styles['SuccessBox']))
        else:
            elements.append(Paragraph("No specific strengths identified.", self.styles['BodyText']))

        elements.append(Spacer(1, 0.6*cm))
        elements.append(Paragraph("<b>⚠️ Areas for Improvement</b>", self.styles['SubSectionHeader']))
        elements.append(Spacer(1, 0.3*cm))
        weaknesses = overall.get('weaknesses', [])[:3]
        if weaknesses:
            elements.append(Paragraph("<br/>".join([f"• {w}" for w in weaknesses]), self.styles['WarningBox']))
        else:
            elements.append(Paragraph("No critical weaknesses identified.", self.styles['BodyText']))
        return elements

    # ------------------------------------------------------------------
    # FINANCIAL OVERVIEW
    # ------------------------------------------------------------------
    def _create_financial_overview(self, analysis):
        elements = []
        elements.append(Paragraph("<b>FINANCIAL OVERVIEW</b>", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.6*cm))
        raw = analysis.financial_data.raw_data
        total_assets = raw.get('total assets', 1) or 1
        overview_data = [[Paragraph("<b>Financial Item</b>",self.styles['BodyText']), Paragraph("<b>Amount (USD)</b>",self.styles['BodyText']), Paragraph("<b>% of Assets</b>",self.styles['BodyText'])]]
        items = [
            ('Total Assets',        raw.get('total assets',0),        True),
            ('Total Liabilities',   raw.get('total liabilities',0),   True),
            ('Total Equity',        raw.get('total equity',0),        True),
            ('Revenue',             raw.get('revenue',0),             False),
            ('Net Income',          raw.get('net income',0),          False),
            ('Current Assets',      raw.get('current assets',0),      True),
            ('Current Liabilities', raw.get('current liabilities',0), True),
        ]
        for item_name, value, show_pct in items:
            pct = (value/total_assets*100) if show_pct and total_assets>0 else 0
            overview_data.append([Paragraph(item_name,self.styles['BodyText']), Paragraph(self._format_currency(value),self.styles['BodyText']), Paragraph(f"{pct:.1f}%" if show_pct else "—",self.styles['BodyText'])])
        tbl = Table(overview_data, colWidths=[7*cm,5.5*cm,4.5*cm])
        tbl.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),self.colors['primary']),('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('ALIGN',(0,0),(0,-1),'LEFT'),('ALIGN',(1,0),(-1,-1),'RIGHT'),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10),
            ('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,self.colors['bg_section']]),
            ('GRID',(0,0),(-1,-1),1,self.colors['gray_border']),
        ]))
        elements.append(tbl)
        return elements

    # ------------------------------------------------------------------
    # RATIO ANALYSIS
    # ------------------------------------------------------------------
    def _create_ratio_analysis_by_category(self, analysis, category_key, english_title):
        elements = []
        icons = {'liquidity':'💧','profitability':'📈','solvency':'🏦'}
        icon = icons.get(category_key,'📊')
        elements.append(Paragraph(f"<b>{icon} {english_title.upper()}</b>", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.6*cm))
        category_summary = analysis.ai_analysis.get(category_key, {})
        if category_summary.get('summary'):
            elements.append(Paragraph(f"<b>Category Overview:</b><br/>{category_summary.get('summary')}", self.styles['HighlightBox']))
            elements.append(Spacer(1, 0.6*cm))
        individual_ratios = analysis.ai_analysis.get('individual_ratios', {})
        category_ratios = {k:v for k,v in individual_ratios.items() if v.get('category')==category_key}
        for ratio_name, ratio_data in category_ratios.items():
            elements.extend(self._create_ratio_section(ratio_name, ratio_data))
            elements.append(Spacer(1, 0.8*cm))
        return elements

    def _create_ratio_section(self, ratio_name, ratio_data):
        elements = []
        status       = ratio_data.get('status','good')
        status_color = self._get_status_color_hex(status)
        elements.append(Paragraph(f"<para fontSize='12' textColor='{status_color}'><b>{ratio_name}</b></para>", self.styles['BodyText']))
        elements.append(Spacer(1, 0.4*cm))
        metrics_data = [
            [Paragraph("<b>Current Value</b>",self.styles['BodyText']),Paragraph("<b>Status</b>",self.styles['BodyText']),Paragraph("<b>Optimal Range</b>",self.styles['BodyText'])],
            [Paragraph(f"<font size='13'><b>{ratio_data.get('value',0):.2f}</b></font>",self.styles['BodyText']),
             Paragraph(f"<font color='{status_color}'><b>{ratio_data.get('status_text','N/A')}</b></font>",self.styles['BodyText']),
             Paragraph(f"{ratio_data.get('optimal_range',(0,0))[0]:.2f} – {ratio_data.get('optimal_range',(0,0))[1]:.2f}",self.styles['BodyText'])]
        ]
        tbl = Table(metrics_data, colWidths=[5.7*cm,5.7*cm,5.6*cm])
        tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),self.colors['bg_section']),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10),('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),('GRID',(0,0),(-1,-1),1,self.colors['gray_border']),('BACKGROUND',(0,1),(-1,1),colors.white)]))
        elements.append(tbl); elements.append(Spacer(1,0.4*cm))
        elements.append(Paragraph(f"<b>What This Measures:</b> {ratio_data.get('description','N/A')}<br/><br/><b>Interpretation:</b> {ratio_data.get('interpretation','N/A')}", self.styles['BodyText']))
        elements.append(Spacer(1,0.4*cm))
        if ratio_data.get('ai_insight'):
            elements.append(Paragraph(f"<b>🤖 AI Analysis:</b><br/>{ratio_data.get('ai_insight')}", self.styles['HighlightBox']))
            elements.append(Spacer(1,0.4*cm))
        recs = ratio_data.get('recommendations',[])
        if recs:
            rec_text = "<b>✅ Recommended Actions:</b><br/>" + "".join([f"{i}. {r}<br/>" for i,r in enumerate(recs[:3],1)])
            elements.append(Paragraph(rec_text, self.styles['SuccessBox']))
        return elements

    # ------------------------------------------------------------------
    # RECOMMENDATIONS
    # ------------------------------------------------------------------
    def _create_recommendations_section(self, analysis):
        elements = []
        elements.append(Paragraph("<b>STRATEGIC RECOMMENDATIONS</b>", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.6*cm))
        recs = analysis.ai_analysis.get('recommendations', {})
        for title, key, style in [
            ("⚡ Immediate Actions (Next 30 Days)", 'immediate_actions', 'DangerBox'),
            ("📅 Short-Term Strategies (3-6 Months)", 'short_term',       'WarningBox'),
            ("🎯 Long-Term Initiatives (1+ Years)",  'long_term',        'SuccessBox'),
        ]:
            elements.append(Paragraph(f"<b>{title}</b>", self.styles['SubSectionHeader']))
            elements.append(Spacer(1, 0.3*cm))
            items = recs.get(key, [])[:5]
            if items:
                elements.append(Paragraph("".join([f"<b>{i}.</b> {a}<br/>" for i,a in enumerate(items,1)]), self.styles[style]))
            else:
                elements.append(Paragraph("No items identified.", self.styles['BodyText']))
            elements.append(Spacer(1, 0.6*cm))
        return elements

    # ------------------------------------------------------------------
    # APPENDIX
    # ------------------------------------------------------------------
    def _create_appendix(self, analysis):
        elements = []
        elements.append(Paragraph("<b>APPENDIX: COMPLETE RATIO SUMMARY</b>", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.6*cm))
        ratios = analysis.ratios
        categories = {
            'Liquidity Ratios':     ['Current Ratio','Quick Ratio','Cash Ratio','Working Capital'],
            'Profitability Ratios': ['Net Profit Margin (%)','Gross Profit Margin (%)','Operating Profit Margin (%)','ROA','ROE','ROIC'],
            'Solvency Ratios':      ['Debt to Equity','Debt Ratio','Equity Ratio','Interest Coverage'],
            'Efficiency Ratios':    ['Asset Turnover','Equity Multiplier','Inventory Turnover','Days Inventory Outstanding'],
        }
        for cat_name, ratio_names in categories.items():
            elements.append(Paragraph(f"<b>{cat_name}</b>", self.styles['SubSectionHeader']))
            elements.append(Spacer(1, 0.4*cm))
            cat_data = [[Paragraph("<b>Ratio Name</b>",self.styles['BodyText']),Paragraph("<b>Value</b>",self.styles['BodyText']),Paragraph("<b>Unit</b>",self.styles['BodyText'])]]
            for rn in ratio_names:
                if rn in ratios and ratios[rn] is not None:
                    unit = '%' if '%' in rn or rn in ('ROA','ROE','ROIC') else 'x'
                    cat_data.append([Paragraph(rn,self.styles['BodyText']),Paragraph(f"{ratios[rn]:.2f}",self.styles['BodyText']),Paragraph(unit,self.styles['BodyText'])])
            if len(cat_data)>1:
                tbl = Table(cat_data, colWidths=[9*cm,4.5*cm,3.5*cm])
                tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),self.colors['primary']),('TEXTCOLOR',(0,0),(-1,0),colors.white),('ALIGN',(0,0),(0,-1),'LEFT'),('ALIGN',(1,0),(-1,-1),'CENTER'),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,self.colors['bg_section']]),('GRID',(0,0),(-1,-1),1,self.colors['gray_border'])]))
                elements.append(tbl); elements.append(Spacer(1,0.6*cm))
        elements.append(Spacer(1, 1*cm))
        elements.append(Paragraph("<para alignment='justify' fontSize='8' color='#757575'><b>DISCLAIMER:</b> This financial analysis report has been generated using FinAnalyzer Pro's AI-powered analytical tools. This report should not be considered as professional financial, investment, or legal advice. Users should consult with qualified professionals before making any decisions.<br/><br/><b>© 2025 FinAnalyzer Pro. All rights reserved. | Developed by Anas Ata Meawi</b></para>", self.styles['BodyText']))
        return elements

    # ------------------------------------------------------------------
    # COMPARISON REPORT
    # ------------------------------------------------------------------
    def generate_comparison_report(self, analysis1, analysis2, comparison, compare_type='periods'):
        pdf_path = os.path.join(self.temp_dir, f"comparison_{analysis1.id}_vs_{analysis2.id}.pdf")
        doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2.5*cm, bottomMargin=2.5*cm,
                                title="Financial Comparison Report", author="FinAnalyzer Pro")
        story = []
        story.extend(self._create_comparison_cover(analysis1, analysis2, compare_type));     story.append(PageBreak())
        story.extend(self._create_comparison_charts(analysis1, analysis2, compare_type));    story.append(PageBreak())
        story.extend(self._create_comparison_summary(analysis1, analysis2, comparison, compare_type)); story.append(PageBreak())
        story.extend(self._create_comparison_details(analysis1, analysis2, comparison, compare_type)); story.append(PageBreak())
        story.extend(self._create_comparison_conclusions(comparison, compare_type))
        doc.build(story, onFirstPage=self._add_header_footer, onLaterPages=self._add_header_footer)
        return pdf_path

    def _create_comparison_charts(self, analysis1, analysis2, compare_type):
        """Radar overlay + grouped bar for comparison"""
        elements = []
        elements.append(Paragraph("<b>📊 VISUAL COMPARISON OVERVIEW</b>", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.5*cm))

        try:
            def get_scores(analysis):
                hd = analysis.ai_analysis.get('health_score', {})
                cs = hd.get('category_scores', {})
                return {
                    'liquidity':     cs.get('liquidity', 0),
                    'profitability': cs.get('profitability', 0),
                    'solvency':      cs.get('solvency', 0),
                    'efficiency':    cs.get('efficiency', 0),
                    'overall':       hd.get('overall_score', analysis.ai_analysis.get('overall', {}).get('health_score', 0))
                }

            s1 = get_scores(analysis1)
            s2 = get_scores(analysis2)

            if compare_type == 'companies':
                lbl1 = analysis1.company.name[:18]
                lbl2 = analysis2.company.name[:18]
            else:
                lbl1 = f"Period 1 ({analysis1.financial_data.period_end.strftime('%Y-%m')})"
                lbl2 = f"Period 2 ({analysis2.financial_data.period_end.strftime('%Y-%m')})"

            radar_img  = self._make_comparison_radar(s1, s2, lbl1, lbl2)
            grouped_img = self._make_comparison_grouped_bar(s1, s2, lbl1, lbl2)

            row = [[radar_img, grouped_img]]
            t = Table(row, colWidths=[9*cm, 9*cm])
            t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]))
            elements.append(t)
        except Exception as e:
            elements.append(Paragraph(f"[Chart error: {e}]", self.styles['BodyText']))

        return elements

    def _make_comparison_radar(self, s1, s2, lbl1, lbl2):
        cats   = ['Liquidity','Profitability','Solvency','Efficiency','Overall']
        keys   = ['liquidity','profitability','solvency','efficiency','overall']
        v1 = [s1[k] for k in keys]; v2 = [s2[k] for k in keys]
        N = len(cats); angles = np.linspace(0,2*np.pi,N,endpoint=False).tolist()
        v1 += v1[:1]; v2 += v2[:1]; angles += angles[:1]

        fig, ax = plt.subplots(figsize=(4.2,4.2), subplot_kw=dict(polar=True))
        ax.set_facecolor('#F8F9FA'); fig.patch.set_facecolor('white')
        ax.plot(angles, v1, 'o-', lw=2.5, color='#1976D2', label=lbl1)
        ax.fill(angles, v1, alpha=0.2, color='#1976D2')
        ax.plot(angles, v2, 's-', lw=2.5, color='#F57C00', label=lbl2)
        ax.fill(angles, v2, alpha=0.2, color='#F57C00')
        ax.set_thetagrids(np.degrees(angles[:-1]), cats, fontsize=9)
        ax.set_ylim(0,100); ax.set_yticks([25,50,75,100]); ax.set_yticklabels(['25','50','75','100'],fontsize=7,color='#757575')
        ax.grid(color='#e0e0e0',linewidth=0.8)
        ax.legend(loc='upper right', bbox_to_anchor=(1.35,1.1), fontsize=8)
        ax.set_title('Radar Comparison', fontsize=10, fontweight='bold', color='#0D47A1', pad=14)
        plt.tight_layout()
        buf = io.BytesIO(); fig.savefig(buf,format='PNG',dpi=150,bbox_inches='tight'); plt.close(fig); buf.seek(0)
        return Image(buf, width=8.5*cm, height=8*cm)

    def _make_comparison_grouped_bar(self, s1, s2, lbl1, lbl2):
        cats = ['Liquidity','Profitability','Solvency','Efficiency','Overall']
        keys = ['liquidity','profitability','solvency','efficiency','overall']
        v1 = [s1[k] for k in keys]; v2 = [s2[k] for k in keys]
        x = np.arange(len(cats)); w = 0.35

        fig, ax = plt.subplots(figsize=(4.2,3.8))
        fig.patch.set_facecolor('white'); ax.set_facecolor('#F8F9FA')
        bars1 = ax.bar(x-w/2, v1, w, label=lbl1, color='#1976D2', edgecolor='white', linewidth=1.5, alpha=0.88)
        bars2 = ax.bar(x+w/2, v2, w, label=lbl2, color='#F57C00', edgecolor='white', linewidth=1.5, alpha=0.88)
        for bar in list(bars1)+list(bars2):
            h = bar.get_height()
            ax.text(bar.get_x()+bar.get_width()/2, h+1, f'{h:.0f}', ha='center', va='bottom', fontsize=7, fontweight='bold')
        ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=8, rotation=18, ha='right')
        ax.set_ylim(0,115); ax.set_ylabel('Score (/100)',fontsize=8)
        ax.axhline(70, color='#4CAF50', linestyle='--', linewidth=1, alpha=0.7)
        ax.legend(fontsize=8, loc='upper right')
        ax.grid(axis='y', color='#e0e0e0', linewidth=0.7); ax.set_axisbelow(True)
        ax.set_title('Score Comparison', fontsize=10, fontweight='bold', color='#0D47A1')
        plt.tight_layout()
        buf = io.BytesIO(); fig.savefig(buf,format='PNG',dpi=150,bbox_inches='tight'); plt.close(fig); buf.seek(0)
        return Image(buf, width=8.5*cm, height=7.5*cm)

    def _create_comparison_cover(self, analysis1, analysis2, compare_type):
        elements = []
        elements.append(Spacer(1, 2*cm))
        elements.append(Paragraph("<b>FINANCIAL COMPARISON REPORT</b>", self.styles['CoverTitle']))
        elements.append(Spacer(1, 1.2*cm))
        if compare_type == 'companies':
            elements.append(Paragraph(f"<para align='center' fontSize='16' textColor='#0D47A1'><b>{analysis1.company.name}</b></para>", self.styles['BodyText']))
            elements.append(Spacer(1, 0.4*cm))
            elements.append(Paragraph("<para align='center' fontSize='28' textColor='#1565C0'><b>VS</b></para>", self.styles['BodyText']))
            elements.append(Spacer(1, 0.4*cm))
            elements.append(Paragraph(f"<para align='center' fontSize='16' textColor='#0D47A1'><b>{analysis2.company.name}</b></para>", self.styles['BodyText']))
        else:
            elements.append(Paragraph(f"<para align='center' fontSize='16' textColor='#0D47A1'><b>{analysis1.company.name}</b><br/><br/><font size='13' color='#1565C0'>Period-over-Period Analysis</font><br/><font size='11' color='#757575'>{analysis1.financial_data.period_end.strftime('%Y-%m-%d')} vs {analysis2.financial_data.period_end.strftime('%Y-%m-%d')}</font></para>", self.styles['BodyText']))
        elements.append(Spacer(1, 2*cm))
        elements.append(Paragraph(f"<para align='center' fontSize='9' color='#757575'><b>Report Generated:</b> {date.today().strftime('%B %d, %Y')}<br/><b>Comparison Type:</b> {'Company Comparison' if compare_type=='companies' else 'Period Analysis'}<br/><b>Prepared by:</b> FinAnalyzer Pro<br/><b>Developer:</b> Anas Ata Meawi</para>", self.styles['BodyText']))
        return elements

    def _create_comparison_summary(self, analysis1, analysis2, comparison, compare_type):
        elements = []
        elements.append(Paragraph("<b>EXECUTIVE SUMMARY</b>", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.6*cm))
        if compare_type == 'companies':
            h1 = [Paragraph("<b>Metric</b>",self.styles['BodyText']),Paragraph(f"<b>{analysis1.company.name}</b>",self.styles['BodyText']),Paragraph(f"<b>{analysis2.company.name}</b>",self.styles['BodyText'])]
        else:
            h1 = [Paragraph("<b>Metric</b>",self.styles['BodyText']),Paragraph("<b>Period 1</b>",self.styles['BodyText']),Paragraph("<b>Period 2</b>",self.styles['BodyText'])]
        summary_data = [h1,
            ["Health Score", str(analysis1.ai_analysis.get('overall',{}).get('health_score','N/A')), str(analysis2.ai_analysis.get('overall',{}).get('health_score','N/A'))],
            ["Risk Level",   analysis1.ai_analysis.get('overall',{}).get('risk_level','N/A'), analysis2.ai_analysis.get('overall',{}).get('risk_level','N/A')],
        ]
        tbl = Table(summary_data, colWidths=[6*cm,5.5*cm,5.5*cm])
        tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),self.colors['primary']),('TEXTCOLOR',(0,0),(-1,0),colors.white),('ALIGN',(0,0),(-1,-1),'CENTER'),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),('GRID',(0,0),(-1,-1),1,self.colors['gray_border']),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,self.colors['bg_section']])]))
        elements.append(tbl); elements.append(Spacer(1,0.8*cm))
        return elements

    def _create_comparison_details(self, analysis1, analysis2, comparison, compare_type):
        elements = []
        elements.append(Paragraph("<b>DETAILED RATIO COMPARISON</b>", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.6*cm))
        diffs = comparison.get('differences' if compare_type=='companies' else 'changes', {})
        for ratio_name, diff_data in diffs.items():
            elements.extend(self._create_ratio_comparison_box(ratio_name, diff_data, analysis1, analysis2, compare_type))
            elements.append(Spacer(1, 0.6*cm))
        return elements

    def _create_ratio_comparison_box(self, ratio_name, diff_data, analysis1, analysis2, compare_type):
        elements = []
        elements.append(Paragraph(f"<b><font color='#1565C0' size='12'>{ratio_name}</font></b>", self.styles['BodyText']))
        elements.append(Spacer(1, 0.4*cm))
        if compare_type == 'companies':
            values_data = [
                [Paragraph(f"<b>{analysis1.company.name}</b>",self.styles['BodyText']),"→",Paragraph(f"<b>{analysis2.company.name}</b>",self.styles['BodyText']),"Change"],
                [f"{diff_data.get('value1',0):.2f}","→",f"{diff_data.get('value2',0):.2f}",f"{diff_data.get('percentage_change',0):+.1f}%"]
            ]
        else:
            values_data = [
                [Paragraph("<b>Old Value</b>",self.styles['BodyText']),"→",Paragraph("<b>New Value</b>",self.styles['BodyText']),"Change"],
                [f"{diff_data.get('old_value',0):.2f}","→",f"{diff_data.get('new_value',0):.2f}",f"{diff_data.get('percentage_change',0):+.1f}%"]
            ]
        tbl = Table(values_data, colWidths=[4.2*cm,1.5*cm,4.2*cm,3*cm])
        tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),self.colors['bg_section']),('ALIGN',(0,0),(-1,-1),'CENTER'),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),('GRID',(0,0),(-1,-1),1,self.colors['gray_border']),('BACKGROUND',(0,1),(-1,1),colors.white)]))
        elements.append(tbl); elements.append(Spacer(1,0.4*cm))
        if diff_data.get('ai_insight'):
            elements.append(Paragraph(f"<b>🤖 AI Analysis:</b><br/>{diff_data.get('ai_insight')}", self.styles['HighlightBox']))
        return elements

    def _create_comparison_conclusions(self, comparison, compare_type):
        elements = []
        elements.append(Paragraph("<b>CONCLUSIONS & RECOMMENDATIONS</b>", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.6*cm))
        ai_insights = comparison.get('ai_insights', {})
        if compare_type == 'companies':
            winner = ai_insights.get('stronger_company', 'N/A')
            elements.append(Paragraph(f"<b>Overall Assessment:</b> Based on comprehensive financial analysis, <b>{winner}</b> demonstrates stronger overall financial performance.", self.styles['HighlightBox']))
        else:
            trend = ai_insights.get('overall_trend', 'stable')
            elements.append(Paragraph(f"<b>Overall Trend:</b> The financial performance between the two periods shows a <b>{trend}</b> trend.", self.styles['HighlightBox']))
        elements.append(Spacer(1, 1*cm))
        elements.append(Paragraph("<para alignment='justify' fontSize='8' color='#757575'><b>DISCLAIMER:</b> This comparison report has been generated using FinAnalyzer Pro's AI-powered analytical tools. This report should not be considered professional financial, investment, or legal advice.<br/><br/><b>© 2025 FinAnalyzer Pro. All rights reserved. | Developed by Anas Ata Meawi</b></para>", self.styles['BodyText']))
        return elements

    # ------------------------------------------------------------------
    # HEADER / FOOTER
    # ------------------------------------------------------------------
    def _add_header_footer(self, canvas, doc):
        canvas.saveState()
        width, height = A4
        if doc.page > 1:
            canvas.setStrokeColor(self.colors['primary']); canvas.setLineWidth(2)
            canvas.line(2*cm, height-1.8*cm, width-2*cm, height-1.8*cm)
            canvas.setFont('Helvetica-Bold',10); canvas.setFillColor(self.colors['primary'])
            canvas.drawString(2*cm, height-1.5*cm, "FinAnalyzer Pro")
            canvas.setFont('Helvetica',9); canvas.setFillColor(self.colors['gray_medium'])
            canvas.drawRightString(width-2*cm, height-1.5*cm, "Financial Analysis Report")
        canvas.setStrokeColor(self.colors['primary']); canvas.setLineWidth(2)
        canvas.line(2*cm, 2.2*cm, width-2*cm, 2.2*cm)
        canvas.setFont('Helvetica',8); canvas.setFillColor(self.colors['gray_medium'])
        canvas.drawString(2*cm, 1.8*cm, "FinAnalyzer Pro")
        canvas.setFont('Helvetica-Bold',8); canvas.setFillColor(self.colors['primary'])
        canvas.drawString(2*cm, 1.5*cm, "Developed by: Anas Ata Meawi")
        canvas.setFont('Helvetica',7); canvas.setFillColor(self.colors['gray_medium'])
        canvas.drawString(2*cm, 1.2*cm, f"Generated: {date.today().strftime('%B %d, %Y')}")
        canvas.setFont('Helvetica-Bold',10); canvas.setFillColor(self.colors['primary'])
        canvas.drawRightString(width-2*cm, 1.8*cm, f"Page {doc.page}")
        canvas.setFont('Helvetica-Bold',8); canvas.setFillColor(self.colors['danger'])
        canvas.drawRightString(width-2*cm, 1.5*cm, "CONFIDENTIAL")
        canvas.restoreState()

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _format_currency(self, value):
        if value is None: return "N/A"
        return f"${value:,.2f}"

    def _get_status_color_hex(self, status):
        return {'excellent':'#4CAF50','good':'#2196F3','warning':'#FF9800','critical':'#F44336'}.get(status,'#2196F3')

    def _get_status_bg_color_hex(self, status):
        return {'excellent':'#E8F5E9','good':'#E3F2FD','warning':'#FFF3E0','critical':'#FFEBEE'}.get(status,'#E3F2FD')

    def _get_status_indicator(self, score):
        if score>=80: return "🟢 Excellent"
        elif score>=60: return "🔵 Good"
        elif score>=40: return "🟡 Fair"
        else: return "🔴 Critical"

    def _get_risk_indicator(self, risk_level):
        return {'Low':'🟢 Low Risk','Medium':'🟡 Medium Risk','High':'🔴 High Risk'}.get(risk_level,'⚪ Unknown')

    def _extract_rating_str(self, rating):
        """Extract a clean string from investment_rating, whether it's a string or dict."""
        if isinstance(rating, dict):
            return rating.get('rating') or rating.get('value') or rating.get('label') or 'Hold'
        return str(rating) if rating else 'Hold'

    def _get_star_rating(self, rating):
        # rating might be a dict (e.g. {'rating': 'Hold', ...}) or a plain string
        if isinstance(rating, dict):
            rating = rating.get('rating') or rating.get('value') or rating.get('label') or 'Hold'
        if not isinstance(rating, str):
            rating = str(rating) if rating else 'Hold'
        return {'Strong Buy':5,'Buy':4,'Hold':3,'Sell':2,'Strong Sell':1}.get(rating, 3)

    def get_report_metadata(self, analysis) -> dict:
        """Return metadata about what will be in the generated report (for UI preview)."""
        sections = [
            "Cover Page",
            "Health Score Dashboard",
            "Visual Charts (Radar, Bar, Waterfall)",
            "Executive Summary",
        ]
        alerts = analysis.ai_analysis.get('alerts', [])
        if alerts:
            sections.append(f"Alerts ({len(alerts)} issues)")
        sections += [
            "Financial Overview",
            "Liquidity Analysis",
            "Profitability Analysis",
            "Solvency Analysis",
            "Efficiency Analysis",
            "Strategic Recommendations",
            "Complete Ratio Appendix",
        ]
        estimated_pages = 10 + (1 if alerts else 0)
        return {
            "sections": sections,
            "estimated_pages": estimated_pages,
            "includes_charts": True,
            "includes_ai": True,
        }

    def cleanup(self):
        import shutil
        try: shutil.rmtree(self.temp_dir)
        except Exception as e: print(f"Cleanup error: {e}")