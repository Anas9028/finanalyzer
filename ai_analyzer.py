import os
from typing import Dict, Any, List, Optional
import json
import statistics
from groq import Groq


class AIAnalyzer:
    """
    Enhanced AI-powered financial analysis module using Groq with LLaMA 3 70B
    New Features:
    - Smart automatic interpretations with context-aware explanations
    - Financial forecasting using linear regression
    - Automated alert system for threshold breaches
    - Comprehensive Financial Health Score (0-100)
    - Industry benchmarking with intelligent gap analysis
    """

    def __init__(self, api_key=None):
        """Initialize AI Analyzer with Groq and LLaMA 3 70B"""
        self.api_key = api_key or os.getenv('GROQ_API_KEY')
        if self.api_key:
            self.client = Groq(api_key=self.api_key)
        else:
            self.client = None

        self.model = "llama-3.3-70b-versatile"

        print(f"\n{'=' * 60}")
        print(f"🤖 AI ANALYZER INITIALIZED (ENHANCED v2.0)")
        print(f"{'=' * 60}")
        print(f"✅ Model: {self.model}")
        print(f"✅ Smart Auto-Interpretations: Enabled")
        print(f"✅ Financial Forecasting: Enabled")
        print(f"✅ Alert System: Enabled")
        print(f"✅ Financial Health Score: Enabled")
        print(f"{'=' * 60}\n")

        self.industry_ranges = self._initialize_industry_ranges()

        self.ratio_configs = {
            'Current Ratio': {
                'category': 'liquidity',
                'optimal_range': (1.5, 3.0),
                'description': 'Measures ability to pay short-term obligations with current assets',
                'higher_is_better': True,
                'alert_threshold_low': 1.0,
                'alert_threshold_high': 5.0,
                'weight': 8  # Weight for health score calculation
            },
            'Quick Ratio': {
                'category': 'liquidity',
                'optimal_range': (1.0, 2.0),
                'description': 'Measures immediate liquidity without relying on inventory',
                'higher_is_better': True,
                'alert_threshold_low': 0.5,
                'alert_threshold_high': 4.0,
                'weight': 7
            },
            'Cash Ratio': {
                'category': 'liquidity',
                'optimal_range': (0.5, 1.0),
                'description': 'Most conservative liquidity measure using only cash',
                'higher_is_better': True,
                'alert_threshold_low': 0.2,
                'alert_threshold_high': 3.0,
                'weight': 5
            },
            'Working Capital': {
                'category': 'liquidity',
                'optimal_range': (0, 1000000),
                'description': 'Net current assets available for operations',
                'higher_is_better': True,
                'alert_threshold_low': -100000,
                'alert_threshold_high': None,
                'weight': 6
            },
            'Working Capital Ratio': {
                'category': 'liquidity',
                'optimal_range': (10, 30),
                'description': 'Working capital as percentage of total assets',
                'higher_is_better': True,
                'alert_threshold_low': 5,
                'alert_threshold_high': None,
                'weight': 5
            },
            'Cash Flow Coverage': {
                'category': 'liquidity',
                'optimal_range': (20, 50),
                'description': 'Ability to cover current liabilities with operating cash flow',
                'higher_is_better': True,
                'alert_threshold_low': 10,
                'alert_threshold_high': None,
                'weight': 4
            },
            'Defensive Interval': {
                'category': 'liquidity',
                'optimal_range': (60, 120),
                'description': 'Number of days company can operate with liquid assets',
                'higher_is_better': True,
                'alert_threshold_low': 30,
                'alert_threshold_high': None,
                'weight': 4
            },
            'Net Profit Margin (%)': {
                'category': 'profitability',
                'optimal_range': (10.0, 25.0),
                'description': 'Percentage of revenue that becomes net profit',
                'higher_is_better': True,
                'alert_threshold_low': 0,
                'alert_threshold_high': None,
                'weight': 10
            },
            'Gross Profit Margin (%)': {
                'category': 'profitability',
                'optimal_range': (30.0, 50.0),
                'description': 'Profit after deducting cost of goods sold',
                'higher_is_better': True,
                'alert_threshold_low': 10,
                'alert_threshold_high': None,
                'weight': 8
            },
            'Operating Profit Margin (%)': {
                'category': 'profitability',
                'optimal_range': (15.0, 30.0),
                'description': 'Profitability from core operations before interest and taxes',
                'higher_is_better': True,
                'alert_threshold_low': 5,
                'alert_threshold_high': None,
                'weight': 8
            },
            'ROA': {
                'category': 'profitability',
                'optimal_range': (5.0, 15.0),
                'description': 'Return on assets - efficiency of asset utilization',
                'higher_is_better': True,
                'alert_threshold_low': 2,
                'alert_threshold_high': None,
                'weight': 9
            },
            'ROE': {
                'category': 'profitability',
                'optimal_range': (15.0, 25.0),
                'description': 'Return on equity - return generated for shareholders',
                'higher_is_better': True,
                'alert_threshold_low': 8,
                'alert_threshold_high': None,
                'weight': 10
            },
            'ROIC': {
                'category': 'profitability',
                'optimal_range': (10.0, 20.0),
                'description': 'Return on invested capital - efficiency of capital deployment',
                'higher_is_better': True,
                'alert_threshold_low': 5,
                'alert_threshold_high': None,
                'weight': 7
            },
            'Debt to Equity': {
                'category': 'solvency',
                'optimal_range': (0.3, 1.5),
                'description': 'Financial leverage - debt relative to shareholder equity',
                'inverse_logic': True,
                'alert_threshold_low': None,
                'alert_threshold_high': 3.0,
                'weight': 9
            },
            'Debt Ratio': {
                'category': 'solvency',
                'optimal_range': (0.3, 0.6),
                'description': 'Proportion of assets financed by debt',
                'inverse_logic': True,
                'alert_threshold_low': None,
                'alert_threshold_high': 0.8,
                'weight': 8
            },
            'Equity Ratio': {
                'category': 'solvency',
                'optimal_range': (0.4, 0.7),
                'description': 'Proportion of assets financed by equity',
                'higher_is_better': True,
                'alert_threshold_low': 0.2,
                'alert_threshold_high': None,
                'weight': 7
            },
            'Interest Coverage': {
                'category': 'solvency',
                'optimal_range': (3.0, 8.0),
                'description': 'Ability to pay interest expenses from operating income',
                'higher_is_better': True,
                'alert_threshold_low': 1.5,
                'alert_threshold_high': None,
                'weight': 8
            },
            'Equity Multiplier': {
                'category': 'solvency',
                'optimal_range': (1.5, 2.5),
                'description': 'Total assets per dollar of equity - measures leverage',
                'higher_is_better': False,
                'alert_threshold_low': None,
                'alert_threshold_high': 5.0,
                'weight': 5
            },
            'Asset Turnover': {
                'category': 'efficiency',
                'optimal_range': (1.0, 2.5),
                'description': 'Efficiency in using assets to generate revenue',
                'higher_is_better': True,
                'alert_threshold_low': 0.3,
                'alert_threshold_high': None,
                'weight': 8
            },
            'Inventory Turnover': {
                'category': 'efficiency',
                'optimal_range': (5.0, 12.0),
                'description': 'How quickly inventory is sold and replaced',
                'higher_is_better': True,
                'alert_threshold_low': 2.0,
                'alert_threshold_high': None,
                'weight': 7
            },
            'Receivables Turnover': {
                'category': 'efficiency',
                'optimal_range': (8.0, 15.0),
                'description': 'Efficiency in collecting accounts receivable',
                'higher_is_better': True,
                'alert_threshold_low': 4.0,
                'alert_threshold_high': None,
                'weight': 7
            },
            'Payables Turnover': {
                'category': 'efficiency',
                'optimal_range': (6.0, 12.0),
                'description': 'How quickly company pays its suppliers',
                'higher_is_better': False,
                'alert_threshold_low': None,
                'alert_threshold_high': None,
                'weight': 5
            },
            'Days Inventory Outstanding': {
                'category': 'efficiency',
                'optimal_range': (30, 60),
                'description': 'Average days to sell inventory',
                'inverse_logic': True,
                'alert_threshold_low': None,
                'alert_threshold_high': 120,
                'weight': 6
            },
            'Days Sales Outstanding': {
                'category': 'efficiency',
                'optimal_range': (30, 45),
                'description': 'Average days to collect receivables',
                'inverse_logic': True,
                'alert_threshold_low': None,
                'alert_threshold_high': 90,
                'weight': 6
            }
        }

    # ==================== FINANCIAL HEALTH SCORE ====================

    def calculate_financial_health_score(self, ratios: Dict, industry: str = 'Services') -> Dict:
        """
        Calculate a comprehensive Financial Health Score (0-100)
        Weighted scoring across all 4 ratio categories
        Returns score, grade, breakdown, and detailed interpretation
        """
        print("\n📊 Calculating Financial Health Score...")

        category_scores = {
            'liquidity': {'score': 0, 'max': 0, 'weight': 25},
            'profitability': {'score': 0, 'max': 0, 'weight': 35},
            'solvency': {'score': 0, 'max': 0, 'weight': 25},
            'efficiency': {'score': 0, 'max': 0, 'weight': 15}
        }

        ratio_scores = {}

        for ratio_name, ratio_value in ratios.items():
            if ratio_value is None or ratio_name not in self.ratio_configs:
                continue

            config = self.ratio_configs[ratio_name].copy()
            industry_range = self._get_optimal_range(ratio_name, industry)
            config['optimal_range'] = industry_range

            weight = config.get('weight', 5)
            category = config.get('category', 'other')

            # Score this ratio 0-100
            ratio_score = self._score_single_ratio(ratio_value, config)
            weighted_score = ratio_score * weight

            ratio_scores[ratio_name] = {
                'raw_score': ratio_score,
                'weight': weight,
                'weighted_score': weighted_score,
                'status': self._determine_ratio_status(ratio_value, config)
            }

            if category in category_scores:
                category_scores[category]['score'] += weighted_score
                category_scores[category]['max'] += 100 * weight

        # Normalize category scores to 0-100
        normalized_categories = {}
        for cat, data in category_scores.items():
            if data['max'] > 0:
                normalized = (data['score'] / data['max']) * 100
            else:
                normalized = 50  # neutral if no data
            normalized_categories[cat] = round(normalized, 1)

        # Calculate overall weighted score
        overall = 0
        total_weight = sum(d['weight'] for d in category_scores.values())
        for cat, data in category_scores.items():
            cat_norm = normalized_categories[cat]
            overall += cat_norm * (data['weight'] / total_weight)

        overall = round(overall, 1)

        # Determine grade
        grade, grade_desc = self._get_grade(overall)

        # Generate interpretation
        interpretation = self._generate_health_score_interpretation(overall, normalized_categories, industry)

        # Generate alerts based on score
        alerts = self._generate_score_alerts(ratios, normalized_categories, industry)

        print(f"   ✅ Health Score: {overall}/100 ({grade})")

        return {
            'overall_score': overall,
            'grade': grade,
            'grade_description': grade_desc,
            'category_scores': normalized_categories,
            'ratio_scores': ratio_scores,
            'interpretation': interpretation,
            'alerts': alerts,
            'strengths': self._identify_strengths(normalized_categories),
            'weaknesses': self._identify_weaknesses(normalized_categories),
            'risk_level': 'Low' if overall > 75 else 'Medium' if overall > 50 else 'High',
            'investment_rating': self._get_investment_rating(overall)
        }

    def _score_single_ratio(self, value: float, config: Dict) -> float:
        """Score a single ratio from 0-100"""
        optimal_min, optimal_max = config.get('optimal_range', (0, 100))
        inverse = config.get('inverse_logic', False)

        if inverse:
            if value <= optimal_min:
                return 100.0
            elif value <= optimal_max:
                ratio = (optimal_max - value) / (optimal_max - optimal_min)
                return 60 + (ratio * 40)
            elif value <= optimal_max * 1.5:
                return 30.0
            else:
                return 10.0
        else:
            if value >= optimal_max:
                # Check if too high (excessive)
                if value > optimal_max * 2.5:
                    return 70.0  # penalize excessively high values
                return 100.0
            elif value >= optimal_min:
                ratio = (value - optimal_min) / (optimal_max - optimal_min)
                return 60 + (ratio * 40)
            elif value >= optimal_min * 0.7:
                return 30.0
            else:
                return 10.0

    def _get_grade(self, score: float) -> tuple:
        if score >= 90:
            return 'A+', 'Outstanding Financial Health'
        elif score >= 80:
            return 'A', 'Excellent Financial Health'
        elif score >= 70:
            return 'B+', 'Good Financial Health'
        elif score >= 60:
            return 'B', 'Satisfactory Financial Health'
        elif score >= 50:
            return 'C', 'Fair Financial Health'
        elif score >= 40:
            return 'D', 'Below Average Financial Health'
        else:
            return 'F', 'Critical Financial Health'

    def _get_investment_rating(self, score: float) -> str:
        if score >= 80:
            return 'Strong Buy'
        elif score >= 65:
            return 'Buy'
        elif score >= 50:
            return 'Hold'
        elif score >= 35:
            return 'Sell'
        else:
            return 'Strong Sell'

    def _identify_strengths(self, category_scores: Dict) -> List[str]:
        strengths = []
        for cat, score in category_scores.items():
            if score >= 70:
                msgs = {
                    'liquidity': 'Strong liquidity position – company can meet short-term obligations',
                    'profitability': 'Healthy profitability – generating solid returns for stakeholders',
                    'solvency': 'Sound capital structure – well-balanced debt and equity',
                    'efficiency': 'High operational efficiency – assets working effectively'
                }
                strengths.append(msgs.get(cat, f'{cat.capitalize()} metrics are strong'))
        return strengths if strengths else ['Stable overall financial position']

    def _identify_weaknesses(self, category_scores: Dict) -> List[str]:
        weaknesses = []
        for cat, score in category_scores.items():
            if score < 50:
                msgs = {
                    'liquidity': 'Liquidity concerns – risk of difficulty meeting short-term obligations',
                    'profitability': 'Profitability below benchmark – revenue efficiency needs improvement',
                    'solvency': 'High leverage risk – debt levels require attention',
                    'efficiency': 'Low asset efficiency – operational improvements needed'
                }
                weaknesses.append(msgs.get(cat, f'{cat.capitalize()} metrics need improvement'))
        return weaknesses if weaknesses else ['Minor optimization opportunities identified']

    def _generate_health_score_interpretation(self, score: float, categories: Dict, industry: str) -> str:
        grade, desc = self._get_grade(score)
        strongest = max(categories, key=categories.get)
        weakest = min(categories, key=categories.get)

        return (
            f"With an overall Financial Health Score of {score}/100 (Grade: {grade} – {desc}), "
            f"the company demonstrates {'strong' if score >= 65 else 'moderate' if score >= 50 else 'challenged'} "
            f"financial standing within the {industry} industry. "
            f"The strongest dimension is {strongest} (score: {categories[strongest]:.0f}/100), "
            f"while {weakest} (score: {categories[weakest]:.0f}/100) presents the greatest opportunity for improvement. "
            f"{'The company is well-positioned for growth and investment.' if score >= 65 else 'Focused improvement in key areas is recommended before major strategic decisions.'}"
        )

    # ==================== ALERT SYSTEM ====================

    def generate_alerts(self, ratios: Dict, industry: str = 'Services') -> List[Dict]:
        """
        Automated alert system that detects threshold breaches and generates
        prioritized warnings with actionable recommendations
        """
        print("\n🚨 Running Alert System...")
        alerts = []

        for ratio_name, ratio_value in ratios.items():
            if ratio_value is None or ratio_name not in self.ratio_configs:
                continue

            config = self.ratio_configs[ratio_name]
            industry_range = self._get_optimal_range(ratio_name, industry)

            alert = self._check_ratio_alert(ratio_name, ratio_value, config, industry_range, industry)
            if alert:
                alerts.append(alert)

        # Sort by severity
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        alerts.sort(key=lambda x: severity_order.get(x['severity'], 4))

        print(f"   ✅ Generated {len(alerts)} alerts ({sum(1 for a in alerts if a['severity'] in ['critical', 'high'])} high-priority)")
        return alerts

    def _check_ratio_alert(self, name: str, value: float, config: Dict, industry_range: tuple, industry: str) -> Optional[Dict]:
        """Check if a ratio triggers an alert"""
        low_threshold = config.get('alert_threshold_low')
        high_threshold = config.get('alert_threshold_high')
        inverse = config.get('inverse_logic', False)
        opt_min, opt_max = industry_range

        alert = None

        if not inverse:
            if low_threshold is not None and value < low_threshold:
                severity = 'critical' if value < low_threshold * 0.7 else 'high'
                alert = {
                    'ratio': name,
                    'value': value,
                    'severity': severity,
                    'type': 'below_threshold',
                    'message': f"{name} is critically low at {value:.2f} (threshold: {low_threshold})",
                    'industry_benchmark': f"{opt_min:.2f} – {opt_max:.2f}",
                    'gap': f"{((opt_min - value) / opt_min * 100):.1f}% below industry minimum" if opt_min != 0 else f"{abs(value - opt_min):.2f} below industry minimum",
                    'action': self._get_alert_action(name, 'low', value, industry),
                    'category': config.get('category', 'other')
                }
            elif high_threshold is not None and value > high_threshold:
                severity = 'medium'
                alert = {
                    'ratio': name,
                    'value': value,
                    'severity': severity,
                    'type': 'above_threshold',
                    'message': f"{name} is unusually high at {value:.2f} – may indicate inefficiency",
                    'industry_benchmark': f"{opt_min:.2f} – {opt_max:.2f}",
                    'gap': f"{((value - opt_max) / opt_max * 100):.1f}% above industry maximum" if opt_max != 0 else f"{abs(value - opt_max):.2f} above industry maximum",
                    'action': self._get_alert_action(name, 'high', value, industry),
                    'category': config.get('category', 'other')
                }
        else:
            if high_threshold is not None and value > high_threshold:
                severity = 'critical' if value > high_threshold * 1.5 else 'high'
                alert = {
                    'ratio': name,
                    'value': value,
                    'severity': severity,
                    'type': 'above_threshold',
                    'message': f"{name} is dangerously high at {value:.2f} (threshold: {high_threshold})",
                    'industry_benchmark': f"{opt_min:.2f} – {opt_max:.2f}",
                    'gap': f"{((value - opt_max) / opt_max * 100):.1f}% above safe range" if opt_max != 0 else f"{abs(value - opt_max):.2f} above safe range",
                    'action': self._get_alert_action(name, 'high_inverse', value, industry),
                    'category': config.get('category', 'other')
                }

        return alert

    def _get_alert_action(self, ratio_name: str, direction: str, value: float, industry: str) -> str:
        actions = {
            ('Current Ratio', 'low'): "Accelerate receivables collection, reduce current liabilities, or secure short-term credit lines",
            ('Quick Ratio', 'low'): "Improve cash position, reduce short-term debt, or accelerate accounts receivable",
            ('Cash Ratio', 'low'): "Build cash reserves through better working capital management or drawdown on credit facilities",
            ('Net Profit Margin (%)', 'low'): "Review cost structure, identify overhead inefficiencies, and assess pricing strategy",
            ('ROE', 'low'): "Evaluate capital allocation efficiency, consider share buybacks or improved dividend policy",
            ('ROA', 'low'): "Audit underperforming assets, improve asset utilization, or divest non-core assets",
            ('Debt to Equity', 'high_inverse'): "Prioritize debt reduction, avoid new borrowing, consider equity issuance",
            ('Debt Ratio', 'high_inverse'): "Implement debt restructuring plan, negotiate longer repayment terms",
            ('Interest Coverage', 'low'): "Urgently reduce debt or increase EBIT – risk of debt covenant breach",
            ('Inventory Turnover', 'low'): "Implement lean inventory management, improve demand forecasting, clear slow-moving stock",
            ('Asset Turnover', 'low'): f"Review asset productivity in {industry} context, consider asset disposal or better utilization",
        }
        return actions.get((ratio_name, direction),
                           f"Review {ratio_name} performance and benchmark against {industry} industry peers")

    def _generate_score_alerts(self, ratios: Dict, category_scores: Dict, industry: str) -> List[Dict]:
        """Generate category-level alerts based on health scores"""
        alerts = []
        for cat, score in category_scores.items():
            if score < 40:
                alerts.append({
                    'severity': 'critical',
                    'category': cat,
                    'message': f"{cat.capitalize()} health score is critically low ({score:.0f}/100)",
                    'action': f"Immediate review of all {cat} metrics required"
                })
            elif score < 55:
                alerts.append({
                    'severity': 'medium',
                    'category': cat,
                    'message': f"{cat.capitalize()} health score is below target ({score:.0f}/100)",
                    'action': f"Develop an improvement plan for {cat} metrics within 90 days"
                })
        return alerts

    # ==================== FORECASTING ====================

    def generate_forecasting(self, historical_analyses: List) -> Dict:
        """
        Generate financial forecasts using linear regression on historical data
        Predicts next period values for key ratios with confidence intervals
        """
        print("\n🔮 Generating Financial Forecasts...")

        if len(historical_analyses) < 2:
            return {
                'available': False,
                'message': 'At least 2 historical periods are needed for forecasting',
                'periods_available': len(historical_analyses)
            }

        key_ratios = [
            'Current Ratio', 'Quick Ratio',
            'Net Profit Margin (%)', 'ROA', 'ROE',
            'Debt to Equity', 'Asset Turnover'
        ]

        forecasts = {}
        periods_used = len(historical_analyses)

        for ratio_name in key_ratios:
            values = []
            for analysis in historical_analyses:
                r = analysis.ratios if hasattr(analysis, 'ratios') else analysis.get('ratios', {})
                val = r.get(ratio_name)
                if val is not None:
                    values.append(float(val))

            if len(values) >= 2:
                forecast = self._linear_forecast(values, ratio_name)
                forecasts[ratio_name] = forecast

        # Overall trend assessment
        improving = sum(1 for f in forecasts.values() if f.get('trend') == 'improving')
        declining = sum(1 for f in forecasts.values() if f.get('trend') == 'declining')
        total = len(forecasts)

        if total > 0:
            if improving / total >= 0.6:
                overall_outlook = 'positive'
                outlook_desc = 'Strong positive momentum – most key metrics are trending upward'
            elif declining / total >= 0.6:
                overall_outlook = 'negative'
                outlook_desc = 'Concerning downward trend – proactive measures recommended'
            else:
                overall_outlook = 'mixed'
                outlook_desc = 'Mixed signals – some metrics improving while others need attention'
        else:
            overall_outlook = 'insufficient_data'
            outlook_desc = 'Insufficient historical data for reliable forecasting'

        print(f"   ✅ Forecasted {len(forecasts)} ratios | Outlook: {overall_outlook}")

        return {
            'available': True,
            'periods_used': periods_used,
            'forecasts': forecasts,
            'overall_outlook': overall_outlook,
            'outlook_description': outlook_desc,
            'improving_count': improving,
            'declining_count': declining,
            'stable_count': total - improving - declining,
            'forecast_note': f"Forecast based on {periods_used} historical periods using linear regression"
        }

    def _linear_forecast(self, values: List[float], ratio_name: str) -> Dict:
        """Apply linear regression to forecast next period value"""
        n = len(values)
        x = list(range(n))

        # Linear regression
        x_mean = sum(x) / n
        y_mean = sum(values) / n

        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator

        intercept = y_mean - slope * x_mean

        # Forecast next period
        next_x = n
        forecasted_value = slope * next_x + intercept

        # Calculate R-squared for confidence
        ss_res = sum((values[i] - (slope * x[i] + intercept)) ** 2 for i in range(n))
        ss_tot = sum((v - y_mean) ** 2 for v in values)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        # Determine confidence level
        if r_squared >= 0.8:
            confidence = 'high'
        elif r_squared >= 0.5:
            confidence = 'medium'
        else:
            confidence = 'low'

        # Trend direction
        pct_change = ((forecasted_value - values[-1]) / abs(values[-1]) * 100) if values[-1] != 0 else 0

        config = self.ratio_configs.get(ratio_name, {})
        inverse = config.get('inverse_logic', False)

        if abs(pct_change) < 3:
            trend = 'stable'
        elif pct_change > 0:
            trend = 'declining' if inverse else 'improving'
        else:
            trend = 'improving' if inverse else 'declining'

        # Simple confidence interval (±1 std dev)
        std = statistics.stdev(values) if len(values) > 1 else abs(forecasted_value * 0.1)
        ci_lower = forecasted_value - std
        ci_upper = forecasted_value + std

        return {
            'current_value': round(values[-1], 3),
            'forecasted_value': round(forecasted_value, 3),
            'trend': trend,
            'percentage_change': round(pct_change, 2),
            'confidence': confidence,
            'r_squared': round(r_squared, 3),
            'confidence_interval': {
                'lower': round(ci_lower, 3),
                'upper': round(ci_upper, 3)
            },
            'historical_values': [round(v, 3) for v in values],
            'slope': round(slope, 4),
            'interpretation': self._interpret_forecast(ratio_name, values[-1], forecasted_value, trend, pct_change)
        }

    def _interpret_forecast(self, name: str, current: float, forecasted: float, trend: str, pct_change: float) -> str:
        direction = "increase" if forecasted > current else "decrease"
        return (
            f"{name} is projected to {direction} from {current:.2f} to {forecasted:.2f} "
            f"({pct_change:+.1f}%) in the next period. "
            f"This {'positive' if trend == 'improving' else 'concerning' if trend == 'declining' else 'stable'} "
            f"trend {'suggests continued momentum' if trend == 'improving' else 'warrants attention' if trend == 'declining' else 'indicates stability'}."
        )

    # ==================== SMART AUTO-INTERPRETATIONS ====================

    def generate_smart_interpretations(self, ratios: Dict, raw_data: Dict, industry: str) -> Dict:
        """
        Generate intelligent, context-aware interpretations for all ratios
        Goes beyond simple "good/bad" to explain the WHY and WHAT IT MEANS for the business
        """
        print("\n💡 Generating Smart Interpretations...")
        interpretations = {}

        # Industry context factors
        industry_context = self._get_industry_context(industry)

        for ratio_name, ratio_value in ratios.items():
            if ratio_value is None:
                continue

            config = self.ratio_configs.get(ratio_name, {})
            industry_range = self._get_optimal_range(ratio_name, industry)

            interpretation = self._build_smart_interpretation(
                ratio_name, ratio_value, config, industry_range, raw_data, industry, industry_context
            )
            interpretations[ratio_name] = interpretation

        print(f"   ✅ Generated interpretations for {len(interpretations)} ratios")
        return interpretations

    def _get_industry_context(self, industry: str) -> Dict:
        """Get industry-specific context for smarter interpretations"""
        contexts = {
            'Manufacturing': {
                'key_driver': 'operational efficiency and inventory management',
                'risk_focus': 'supply chain disruptions and raw material costs',
                'growth_metric': 'capacity utilization and production scaling'
            },
            'Technology': {
                'key_driver': 'R&D investment and intellectual property monetization',
                'risk_focus': 'rapid market changes and talent acquisition costs',
                'growth_metric': 'recurring revenue growth and user acquisition'
            },
            'Retail': {
                'key_driver': 'inventory velocity and customer traffic',
                'risk_focus': 'consumer spending patterns and seasonal volatility',
                'growth_metric': 'same-store sales growth and market expansion'
            },
            'Finance': {
                'key_driver': 'net interest margin and credit quality',
                'risk_focus': 'interest rate changes and credit default exposure',
                'growth_metric': 'loan portfolio growth and fee income diversification'
            },
            'Healthcare': {
                'key_driver': 'patient volume and reimbursement rates',
                'risk_focus': 'regulatory changes and liability exposure',
                'growth_metric': 'service line expansion and payer mix optimization'
            }
        }
        return contexts.get(industry, {
            'key_driver': 'revenue generation and cost efficiency',
            'risk_focus': 'market competition and operational costs',
            'growth_metric': 'revenue growth and market share expansion'
        })

    def _build_smart_interpretation(self, name: str, value: float, config: Dict,
                                     industry_range: tuple, raw_data: Dict, industry: str, context: Dict) -> Dict:
        """Build a rich, multi-layered interpretation for a single ratio"""
        status = self._determine_ratio_status(value, {**config, 'optimal_range': industry_range})
        opt_min, opt_max = industry_range

        # Gap analysis
        if config.get('inverse_logic'):
            gap_pct = ((opt_max - value) / opt_max * 100) if opt_max > 0 else 0
        else:
            midpoint = (opt_min + opt_max) / 2
            gap_pct = ((value - midpoint) / midpoint * 100) if midpoint != 0 else 0

        # Build interpretation layers
        what_it_means = self._what_it_means(name, value, raw_data)
        business_impact = self._business_impact(name, value, status, industry, context)
        benchmark_context = (
            f"Industry benchmark ({industry}): {opt_min:.2f}–{opt_max:.2f}. "
            f"Current value is {abs(gap_pct):.1f}% {'above' if gap_pct > 0 else 'below'} the midpoint."
        )
        action_signal = self._action_signal(name, status, value, industry)

        return {
            'value': value,
            'status': status,
            'what_it_means': what_it_means,
            'business_impact': business_impact,
            'benchmark_context': benchmark_context,
            'action_signal': action_signal,
            'gap_percentage': round(gap_pct, 1),
            'industry_range': industry_range
        }

    def _what_it_means(self, name: str, value: float, raw_data: Dict) -> str:
        """Plain-language explanation of what the ratio value means"""
        revenue = raw_data.get('revenue', 0) or 0
        assets = raw_data.get('total assets', 0) or 0

        explanations = {
            'Current Ratio': f"For every $1 of short-term debt, the company has ${value:.2f} in short-term assets to cover it.",
            'Quick Ratio': f"Excluding inventory, the company has ${value:.2f} in liquid assets for every $1 of current liabilities.",
            'Cash Ratio': f"The company can cover ${value:.2f} of every $1 in current liabilities with cash alone.",
            'Net Profit Margin (%)': f"Out of every $100 in sales, ${value:.2f} becomes net profit after all expenses.",
            'Gross Profit Margin (%)': f"After covering direct costs, ${value:.2f} of every $100 in revenue remains for operations and profit.",
            'Operating Profit Margin (%)': f"Core business operations generate ${value:.2f} profit per $100 of revenue before interest and taxes.",
            'ROA': f"The company generates ${value:.2f} in profit for every $100 of assets it holds.",
            'ROE': f"Shareholders earn ${value:.2f} for every $100 they have invested in the company.",
            'Debt to Equity': f"For every $1 of equity, the company carries ${value:.2f} in debt.",
            'Debt Ratio': f"{value * 100:.1f}% of the company's assets are financed by debt.",
            'Equity Ratio': f"{value * 100:.1f}% of assets are funded by shareholders – the rest is debt-financed.",
            'Interest Coverage': f"Operating income covers interest payments {value:.1f} times over – {'comfortably' if value > 3 else 'barely' if value < 1.5 else 'adequately'}.",
            'Asset Turnover': f"Each dollar of assets generates ${value:.2f} in revenue, indicating {'high' if value > 1.5 else 'moderate' if value > 0.8 else 'low'} asset productivity.",
            'Inventory Turnover': f"Inventory is sold and restocked {value:.1f} times per period – {'very fast' if value > 10 else 'normal pace' if value > 5 else 'slow-moving stock concern'}.",
            'Days Inventory Outstanding': f"Products sit in inventory for an average of {value:.0f} days before being sold.",
            'Days Sales Outstanding': f"It takes an average of {value:.0f} days to collect payment after a sale is made.",
        }
        return explanations.get(name, f"The {name} stands at {value:.2f}, reflecting the company's performance on this metric.")

    def _business_impact(self, name: str, value: float, status: str, industry: str, context: Dict) -> str:
        """Explain the real-world business impact of the ratio value"""
        key_driver = context.get('key_driver', 'operations')
        risk_focus = context.get('risk_focus', 'market conditions')

        if status in ['excellent', 'good']:
            impacts = {
                'Current Ratio': f"Strong short-term financial cushion supports smooth {key_driver} without liquidity stress.",
                'Net Profit Margin (%)': f"Solid profitability funds reinvestment in {key_driver} and provides return to shareholders.",
                'ROE': f"High equity returns attract investor confidence and may lower cost of capital for future expansion.",
                'Debt to Equity': f"Conservative leverage provides financial flexibility and resilience against {risk_focus}.",
                'Asset Turnover': f"Efficient asset deployment directly supports competitive advantage in {industry}.",
            }
        else:
            impacts = {
                'Current Ratio': f"Liquidity pressure may force reliance on expensive short-term financing, impacting {key_driver}.",
                'Net Profit Margin (%)': f"Low margins limit self-funding capacity and create vulnerability to {risk_focus}.",
                'ROE': f"Below-benchmark equity returns may signal capital misallocation or excessive cost base.",
                'Debt to Equity': f"High leverage increases financial risk, especially during periods of {risk_focus}.",
                'Asset Turnover': f"Low asset efficiency suggests underutilized resources that could be redeployed or divested.",
            }

        return impacts.get(name,
                           f"This ratio level {'supports' if status in ['excellent', 'good'] else 'may hinder'} "
                           f"the company's focus on {key_driver} within the {industry} sector.")

    def _action_signal(self, name: str, status: str, value: float, industry: str) -> str:
        """What action should management take based on this ratio"""
        if status == 'excellent':
            return f"✅ Maintain current strategy. Consider whether excess resources in this area can be redeployed for growth."
        elif status == 'good':
            return f"✅ On track. Continue current approach and monitor for any deterioration."
        elif status == 'warning':
            return f"⚠️ Monitor closely. Identify the root cause and prepare a corrective plan within 60-90 days."
        else:
            return f"🔴 Immediate action required. Escalate to senior management and develop a remediation plan urgently."

    # ==================== MAIN ANALYSIS METHOD ====================

    def analyze_ratios(self, ratios: Dict[str, float], raw_data: Dict[str, Any], lang: str = 'en') -> Dict[str, Any]:
        """
        Full enhanced analysis pipeline:
        1. Individual ratio analysis with AI insights
        2. Category summaries
        3. Financial Health Score (NEW)
        4. Alert System (NEW)
        5. Smart Auto-Interpretations (NEW)
        6. Overall assessment, predictions, recommendations
        """
        print("\n" + "=" * 60)
        print("🤖 AI ANALYSIS ENGINE v2.0 STARTED")
        print("=" * 60)

        industry = raw_data.get('industry', 'Services')
        print(f"🏭 Industry: {industry} | Ratios: {len(ratios)}")

        analysis = {}

        # Individual ratio analysis
        print("\n🔍 Analyzing individual ratios...")
        analysis['individual_ratios'] = self._analyze_all_individual_ratios(ratios, raw_data, industry)

        # Category summaries
        print("\n📋 Generating category summaries...")
        for cat in ['liquidity', 'profitability', 'solvency', 'efficiency']:
            analysis[cat] = self._analyze_category_summary(ratios, raw_data, cat, industry)

        # === NEW FEATURE 1: Financial Health Score ===
        print("\n💯 Calculating Financial Health Score...")
        health_score_data = self.calculate_financial_health_score(ratios, industry)
        analysis['health_score'] = health_score_data

        # Use health score for overall (backward compatible)
        analysis['overall'] = {
            'health_score': health_score_data['overall_score'],
            'grade': health_score_data['grade'],
            'grade_description': health_score_data['grade_description'],
            'strengths': health_score_data['strengths'],
            'weaknesses': health_score_data['weaknesses'],
            'risk_level': health_score_data['risk_level'],
            'investment_rating': health_score_data['investment_rating'],
            'category_breakdown': health_score_data['category_scores'],
            'interpretation': health_score_data['interpretation']
        }

        # === NEW FEATURE 2: Alert System ===
        print("\n🚨 Running Alert System...")
        analysis['alerts'] = self.generate_alerts(ratios, industry)
        analysis['alert_summary'] = {
            'total': len(analysis['alerts']),
            'critical': sum(1 for a in analysis['alerts'] if a.get('severity') == 'critical'),
            'high': sum(1 for a in analysis['alerts'] if a.get('severity') == 'high'),
            'medium': sum(1 for a in analysis['alerts'] if a.get('severity') == 'medium'),
        }

        # === NEW FEATURE 3: Smart Auto-Interpretations ===
        print("\n💡 Generating Smart Interpretations...")
        analysis['smart_interpretations'] = self.generate_smart_interpretations(ratios, raw_data, industry)

        # Predictions and recommendations
        analysis['predictions'] = self._generate_predictions(ratios, raw_data)
        analysis['recommendations'] = self._generate_recommendations_enhanced(ratios, raw_data, health_score_data, industry)

        print("\n" + "=" * 60)
        print(f"✅ ANALYSIS COMPLETE | Score: {health_score_data['overall_score']}/100 ({health_score_data['grade']})")
        print(f"   Alerts: {analysis['alert_summary']['critical']} critical, {analysis['alert_summary']['high']} high")
        print("=" * 60 + "\n")

        return analysis

    def _generate_recommendations_enhanced(self, ratios: Dict, raw_data: Dict,
                                            health_data: Dict, industry: str) -> Dict:
        """Generate prioritized recommendations based on health score and alerts"""
        score = health_data['overall_score']
        weaknesses = health_data['weaknesses']
        category_scores = health_data['category_scores']

        # Sort categories by score (worst first)
        sorted_cats = sorted(category_scores.items(), key=lambda x: x[1])

        immediate = []
        short_term = []
        long_term = []

        for cat, cat_score in sorted_cats:
            if cat_score < 45:
                immediate.append(f"🔴 PRIORITY: Immediately address {cat} deficiencies (score: {cat_score:.0f}/100)")
            elif cat_score < 60:
                short_term.append(f"Develop a 90-day improvement plan for {cat} metrics (current score: {cat_score:.0f}/100)")
            else:
                long_term.append(f"Sustain strong {cat} performance while exploring further optimization opportunities")

        # Add specific ratio recommendations
        if ratios.get('Net Profit Margin (%)', 100) < 5:
            immediate.append("Conduct comprehensive cost structure review and pricing analysis")
        if ratios.get('Current Ratio', 2) < 1.0:
            immediate.append("Urgently improve working capital position to avoid liquidity crisis")
        if ratios.get('Debt to Equity', 0) > 3.0:
            immediate.append("Implement debt reduction strategy and avoid new debt obligations")

        if score > 70:
            long_term.extend(["Explore growth initiatives and market expansion",
                               "Consider increasing R&D or capital investment for competitive advantage"])

        return {
            'immediate_actions': immediate[:5] if immediate else ["Continue monitoring current performance metrics"],
            'short_term': short_term[:5] if short_term else ["Optimize resource allocation across business units"],
            'long_term': long_term[:5] if long_term else ["Pursue strategic growth and innovation initiatives"]
        }

    # ==================== EXISTING METHODS (preserved) ====================

    def _initialize_industry_ranges(self) -> Dict:
        return {
            'Manufacturing': {
                'Current Ratio': (1.5, 2.5), 'Quick Ratio': (1.0, 1.8), 'Cash Ratio': (0.3, 0.8),
                'Net Profit Margin (%)': (5.0, 15.0), 'Gross Profit Margin (%)': (20.0, 35.0),
                'ROA': (5.0, 12.0), 'ROE': (12.0, 20.0), 'Debt to Equity': (0.5, 1.5),
                'Asset Turnover': (1.0, 2.0), 'Inventory Turnover': (4.0, 8.0), 'Days Inventory Outstanding': (45, 90)
            },
            'Technology': {
                'Current Ratio': (2.0, 4.0), 'Quick Ratio': (1.5, 3.0), 'Cash Ratio': (0.8, 2.0),
                'Net Profit Margin (%)': (15.0, 30.0), 'Gross Profit Margin (%)': (50.0, 80.0),
                'ROA': (10.0, 25.0), 'ROE': (20.0, 40.0), 'Debt to Equity': (0.1, 0.5),
                'Asset Turnover': (0.5, 1.5), 'Inventory Turnover': (8.0, 15.0), 'Days Inventory Outstanding': (24, 45)
            },
            'Retail': {
                'Current Ratio': (1.2, 2.0), 'Quick Ratio': (0.5, 1.2), 'Cash Ratio': (0.2, 0.6),
                'Net Profit Margin (%)': (2.0, 8.0), 'Gross Profit Margin (%)': (20.0, 40.0),
                'ROA': (4.0, 10.0), 'ROE': (10.0, 18.0), 'Debt to Equity': (0.8, 2.0),
                'Asset Turnover': (2.0, 4.0), 'Inventory Turnover': (6.0, 12.0), 'Days Inventory Outstanding': (30, 60)
            },
            'Finance': {
                'Current Ratio': (0.8, 1.5), 'Quick Ratio': (0.5, 1.0), 'Cash Ratio': (0.1, 0.5),
                'Net Profit Margin (%)': (15.0, 30.0), 'Gross Profit Margin (%)': (60.0, 85.0),
                'ROA': (0.8, 1.5), 'ROE': (10.0, 20.0), 'Debt to Equity': (5.0, 15.0),
                'Asset Turnover': (0.05, 0.15), 'Inventory Turnover': (0, 0), 'Days Inventory Outstanding': (0, 0)
            },
            'Healthcare': {
                'Current Ratio': (1.5, 3.0), 'Quick Ratio': (1.2, 2.5), 'Cash Ratio': (0.5, 1.5),
                'Net Profit Margin (%)': (8.0, 18.0), 'Gross Profit Margin (%)': (35.0, 60.0),
                'ROA': (6.0, 15.0), 'ROE': (12.0, 25.0), 'Debt to Equity': (0.4, 1.2),
                'Asset Turnover': (0.8, 1.8), 'Inventory Turnover': (3.0, 8.0), 'Days Inventory Outstanding': (45, 120)
            },
            'Energy': {
                'Current Ratio': (1.0, 1.8), 'Quick Ratio': (0.7, 1.3), 'Cash Ratio': (0.3, 0.8),
                'Net Profit Margin (%)': (5.0, 15.0), 'Gross Profit Margin (%)': (25.0, 45.0),
                'ROA': (4.0, 12.0), 'ROE': (10.0, 20.0), 'Debt to Equity': (0.8, 2.5),
                'Asset Turnover': (0.4, 1.2), 'Inventory Turnover': (10.0, 20.0), 'Days Inventory Outstanding': (18, 36)
            },
            'Services': {
                'Current Ratio': (1.3, 2.5), 'Quick Ratio': (1.0, 2.0), 'Cash Ratio': (0.4, 1.2),
                'Net Profit Margin (%)': (8.0, 20.0), 'Gross Profit Margin (%)': (40.0, 70.0),
                'ROA': (8.0, 18.0), 'ROE': (15.0, 30.0), 'Debt to Equity': (0.3, 1.0),
                'Asset Turnover': (1.5, 3.0), 'Inventory Turnover': (5.0, 15.0), 'Days Inventory Outstanding': (24, 73)
            },
            'Real Estate': {
                'Current Ratio': (1.5, 3.0), 'Quick Ratio': (1.0, 2.0), 'Cash Ratio': (0.4, 1.0),
                'Net Profit Margin (%)': (10.0, 25.0), 'Gross Profit Margin (%)': (40.0, 70.0),
                'ROA': (3.0, 8.0), 'ROE': (8.0, 18.0), 'Debt to Equity': (1.5, 4.0),
                'Asset Turnover': (0.1, 0.5), 'Inventory Turnover': (0.5, 2.0), 'Days Inventory Outstanding': (180, 730)
            },
            'Construction': {
                'Current Ratio': (1.2, 2.2), 'Quick Ratio': (0.7, 1.4), 'Cash Ratio': (0.3, 0.9),
                'Net Profit Margin (%)': (3.0, 10.0), 'Gross Profit Margin (%)': (15.0, 30.0),
                'ROA': (4.0, 12.0), 'ROE': (10.0, 20.0), 'Debt to Equity': (0.8, 2.0),
                'Asset Turnover': (1.5, 3.0), 'Inventory Turnover': (3.0, 8.0), 'Days Inventory Outstanding': (45, 120)
            },
            'Transportation': {
                'Current Ratio': (1.0, 1.8), 'Quick Ratio': (0.6, 1.2), 'Cash Ratio': (0.2, 0.6),
                'Net Profit Margin (%)': (3.0, 10.0), 'Gross Profit Margin (%)': (15.0, 30.0),
                'ROA': (3.0, 8.0), 'ROE': (10.0, 18.0), 'Debt to Equity': (1.0, 3.0),
                'Asset Turnover': (0.8, 1.5), 'Inventory Turnover': (15.0, 30.0), 'Days Inventory Outstanding': (12, 24)
            },
        }

    def _get_optimal_range(self, ratio_name: str, industry: str) -> tuple:
        if industry in self.industry_ranges:
            industry_data = self.industry_ranges[industry]
            if ratio_name in industry_data:
                return industry_data[ratio_name]
        if ratio_name in self.ratio_configs:
            return self.ratio_configs[ratio_name].get('optimal_range', (0, 100))
        return (0, 100)

    def _detect_high_value_risk(self, name: str, value: float, config: Dict, industry: str) -> Dict:
        risk_assessment = {'has_risk': False, 'risk_level': 'none', 'risk_description': '', 'warnings': []}
        optimal_min, optimal_max = config.get('optimal_range', (0, 100))
        if value > optimal_max * 2:
            risk_assessment['has_risk'] = True
            risk_assessment['risk_level'] = 'high' if value > optimal_max * 3 else 'moderate'
            risk_assessment['risk_description'] = f'{name} is significantly above optimal range'
            risk_assessment['warnings'] = ['Extreme values may indicate anomalies', 'Monitor for sustainability']
        return risk_assessment

    def _analyze_all_individual_ratios(self, ratios: Dict, raw_data: Dict, industry: str) -> Dict:
        individual_analysis = {}
        for ratio_name, ratio_value in ratios.items():
            if ratio_value is None:
                continue
            if ratio_name in self.ratio_configs:
                config = self.ratio_configs[ratio_name].copy()
                config['optimal_range'] = self._get_optimal_range(ratio_name, industry)
                config['industry'] = industry
            else:
                config = {'category': 'other', 'optimal_range': (0, 100), 'description': f'Financial metric: {ratio_name}', 'higher_is_better': True, 'industry': industry}
            risk = self._detect_high_value_risk(ratio_name, ratio_value, config, industry)
            ai_insight = self._get_enhanced_ratio_ai_insight(ratio_name, ratio_value,
                                                              self._determine_ratio_status(ratio_value, config),
                                                              config, raw_data, risk)
            individual_analysis[ratio_name] = {
                'value': ratio_value,
                'category': config.get('category', 'other'),
                'description': config.get('description', ''),
                'optimal_range': config.get('optimal_range', (0, 100)),
                'industry': industry,
                'status': self._determine_ratio_status(ratio_value, config),
                'status_text': self._get_status_text(self._determine_ratio_status(ratio_value, config)),
                'interpretation': self._interpret_ratio(ratio_name, ratio_value, config),
                'ai_insight': ai_insight,
                'recommendations': self._get_ratio_recommendations(ratio_name, ratio_value,
                                                                    self._determine_ratio_status(ratio_value, config),
                                                                    config, risk),
                'risk_assessment': risk
            }
        return individual_analysis

    def _analyze_category_summary(self, ratios: Dict, raw_data: Dict, category: str, industry: str) -> Dict:
        category_ratios = {k: v for k, v in ratios.items()
                           if k in self.ratio_configs and v is not None
                           and self.ratio_configs[k].get('category') == category}
        if not category_ratios:
            return {'summary': f'No {category} ratios available.', 'overall_status': 'unknown', 'ratios_count': 0}

        counts = {'excellent': 0, 'good': 0, 'warning': 0, 'critical': 0}
        for rn, rv in category_ratios.items():
            config = self.ratio_configs.get(rn, {}).copy()
            config['optimal_range'] = self._get_optimal_range(rn, industry)
            s = self._determine_ratio_status(rv, config)
            counts[s] = counts.get(s, 0) + 1

        total = len(category_ratios)
        if counts['excellent'] >= total * 0.6:
            overall_status, summary = 'excellent', f"Strong {category} position with {counts['excellent']}/{total} ratios excellent."
        elif (counts['excellent'] + counts['good']) >= total * 0.6:
            overall_status, summary = 'good', f"Solid {category} performance with {counts['excellent'] + counts['good']}/{total} ratios performing well."
        elif counts['warning'] > total * 0.4:
            overall_status, summary = 'warning', f"{category.capitalize()} shows areas needing attention."
        else:
            overall_status, summary = 'critical', f"{category.capitalize()} requires immediate action."

        return {'summary': summary, 'overall_status': overall_status, 'ratios_count': total, **counts, 'industry': industry}

    def _determine_ratio_status(self, value: float, config: Dict) -> str:
        optimal_min, optimal_max = config.get('optimal_range', (0, 100))
        inverse = config.get('inverse_logic', False)
        if inverse:
            if value <= optimal_min: return 'excellent'
            elif value <= optimal_max: return 'good'
            elif value <= optimal_max * 1.5: return 'warning'
            else: return 'critical'
        else:
            if value >= optimal_max: return 'excellent'
            elif value >= optimal_min: return 'good'
            elif value >= optimal_min * 0.7: return 'warning'
            else: return 'critical'

    def _get_status_text(self, status: str) -> str:
        return {'excellent': 'Excellent - Above Target', 'good': 'Good - Within Optimal Range',
                'warning': 'Warning - Below Target', 'critical': 'Critical - Needs Attention'}.get(status, 'Unknown')

    def _interpret_ratio(self, name: str, value: float, config: Dict) -> str:
        interpretations = {
            'Current Ratio': f"The company has ${value:.2f} in current assets for every $1 of current liabilities.",
            'Quick Ratio': f"The company can cover ${value:.2f} of every $1 in current liabilities with liquid assets.",
            'Net Profit Margin (%)': f"The company generates {value:.2f}% profit from each dollar of revenue.",
            'ROA': f"The company generates {value:.2f}% return on its total assets.",
            'ROE': f"Shareholders earn {value:.2f}% return on their equity investment.",
            'Debt to Equity': f"The company has ${value:.2f} of debt for every $1 of equity.",
        }
        return interpretations.get(name, f"The {name} value is {value:.2f}. {config.get('description', '')}")

    def _get_enhanced_ratio_ai_insight(self, name: str, value: float, status: str, config: Dict,
                                       raw_data: Dict, risk_assessment: Dict = None) -> str:
        if not self.client:
            return f"The {name} of {value:.2f} indicates {status} performance based on industry standards."
        try:
            industry = config.get('industry', 'General')
            optimal_range = config.get('optimal_range', (0, 0))
            risk_context = ""
            if risk_assessment and risk_assessment.get('has_risk'):
                risk_context = f"\n⚠️ HIGH VALUE RISK: {risk_assessment.get('risk_description', '')}"

            prompt = f"""As a senior financial analyst in {industry}, analyze: {name} = {value:.2f} (Status: {status})
Industry range: {optimal_range[0]:.2f}–{optimal_range[1]:.2f}
Revenue: ${raw_data.get('revenue', 0):,.0f} | Assets: ${raw_data.get('total assets', 0):,.0f}
{risk_context}

Provide a concise 2-3 sentence analysis covering: (1) what this means for the business, (2) key risks or opportunities, (3) strategic implication."""

            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": f"You are a senior financial analyst specializing in {industry}. Be concise and actionable."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model, temperature=0.6, max_tokens=200
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"The {name} of {value:.2f} indicates {status} performance for {industry} industry."

    def _get_ratio_recommendations(self, name: str, value: float, status: str, config: Dict, risk_assessment: Dict = None) -> list:
        if status in ['excellent', 'good']:
            recs = [f"Maintain current {name} performance", "Continue monitoring regularly", "Use as benchmark for future periods"]
        elif status == 'warning':
            recs = [f"Monitor {name} closely", "Identify root causes", "Implement improvement plan within 3 months"]
        else:
            recs = [f"🔴 Urgent action required for {name}", "Develop immediate corrective measures", "Review operational strategies"]
        return recs

    def _generate_predictions(self, ratios: Dict, raw_data: Dict) -> Dict:
        return {
            "trends": ["Performance trajectory depends on operational improvements", "Market conditions will influence outcomes"],
            "risks": ["Market volatility", "Competition pressure", "Regulatory changes"],
            "opportunities": ["Operational efficiency gains", "Market expansion", "Cost optimization"],
            "key_metrics": ["Net Profit Margin", "Current Ratio", "Debt to Equity", "ROE"]
        }

    def compare_companies(self, analysis1, analysis2):
        ratios1, ratios2 = analysis1.ratios, analysis2.ratios
        differences = {}
        for ratio_name in ratios1.keys():
            if ratio_name in ratios2:
                v1, v2 = ratios1[ratio_name], ratios2[ratio_name]
                if v1 is not None and v2 is not None:
                    diff = v2 - v1
                    pct = (diff / v1 * 100) if v1 != 0 else 0
                    is_imp = self._is_ratio_improvement(ratio_name, diff)
                    differences[ratio_name] = {
                        'value1': v1, 'value2': v2, 'difference': diff,
                        'percentage_change': pct, 'trend': 'stable' if abs(pct) < 5 else ('increase' if pct > 0 else 'decrease'),
                        'is_improvement': is_imp,
                        'ai_insight': f"Company 2 shows {abs(pct):.1f}% {'improvement' if is_imp else 'decline'} in {ratio_name}."
                    }
        imp2 = sum(1 for d in differences.values() if d['is_improvement'] and d['difference'] > 0)
        imp1 = sum(1 for d in differences.values() if not d['is_improvement'] and d['difference'] < 0)
        stronger = analysis2.company.name if imp2 > imp1 else analysis1.company.name
        return {'differences': differences, 'ai_insights': {'stronger_company': stronger, 'total_metrics_compared': len(differences), 'improvement_areas': imp2, 'decline_areas': len(differences) - imp2}}

    def compare_periods(self, analysis1, analysis2):
        ratios_old, ratios_new = analysis1.ratios, analysis2.ratios
        changes = {}
        for ratio_name in ratios_old.keys():
            if ratio_name in ratios_new:
                old_val, new_val = ratios_old[ratio_name], ratios_new[ratio_name]
                if old_val is not None and new_val is not None:
                    change = new_val - old_val
                    pct = (change / old_val * 100) if old_val != 0 else 0
                    is_imp = self._is_ratio_improvement(ratio_name, change)
                    changes[ratio_name] = {
                        'old_value': old_val, 'new_value': new_val, 'change': change,
                        'percentage_change': pct,
                        'change_direction': 'stable' if abs(pct) < 3 else ('increased' if change > 0 else 'decreased'),
                        'is_improvement': is_imp,
                        'ai_insight': f"The {ratio_name} {'increased' if change > 0 else 'decreased'} by {abs(pct):.1f}%. This is {'positive' if is_imp else 'concerning'}."
                    }
        improvements = sum(1 for c in changes.values() if c['is_improvement'])
        total = len(changes)
        overall_trend = 'improving' if improvements >= total * 0.6 else ('declining' if improvements <= total * 0.4 else 'stable')
        return {'changes': changes, 'ai_insights': {'overall_trend': overall_trend, 'total_metrics': total, 'improved_metrics': improvements, 'declined_metrics': total - improvements}}

    def _is_ratio_improvement(self, ratio_name: str, change: float) -> bool:
        negative_ratios = ['Debt to Equity', 'Debt Ratio', 'Days Inventory Outstanding', 'Days Sales Outstanding']
        return change < 0 if ratio_name in negative_ratios else change > 0