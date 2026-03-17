import pandas as pd
from typing import Dict, Optional


class RatioCalculator:
    """
    Calculate comprehensive financial ratios from raw financial data
    All ratios are properly categorized for display in analysis views
    """

    def __init__(self):
        """Initialize with ratio category mappings"""
        self.ratio_categories = {
            # Liquidity Ratios (Short-term financial health)
            'liquidity': [
                'Current Ratio',
                'Quick Ratio',
                'Cash Ratio',
                'Working Capital',
                'Working Capital Ratio',
                'Cash Flow Coverage',
                'Defensive Interval'
            ],

            # Profitability Ratios (Earning capacity)
            'profitability': [
                'Net Profit Margin (%)',
                'Gross Profit Margin (%)',
                'Operating Profit Margin (%)',
                'ROA',
                'ROE',
                'ROIC'
            ],

            # Solvency/Leverage Ratios (Long-term financial stability)
            'solvency': [
                'Debt to Equity',
                'Debt Ratio',
                'Equity Ratio',
                'Interest Coverage',
                'Equity Multiplier'
            ],

            # Efficiency/Activity Ratios (Asset utilization)
            'efficiency': [
                'Asset Turnover',
                'Inventory Turnover',
                'Receivables Turnover',
                'Payables Turnover',
                'Days Inventory Outstanding',
                'Days Sales Outstanding'
            ]
        }

    def calculate_ratios(self, data: Dict) -> Dict[str, Optional[float]]:
        """
        Calculate ALL financial ratios from raw data
        Every ratio is calculated and will appear in analysis

        Args:
            data: Dictionary containing raw financial statement data

        Returns:
            Dictionary of calculated ratios (None for unavailable calculations)
        """
        # Extract values
        current_assets = data.get('current assets')
        current_liabilities = data.get('current liabilities')
        inventory = data.get('inventory')
        cash = data.get('cash')
        accounts_receivable = data.get('accounts receivable')
        accounts_payable = data.get('accounts payable')
        total_liabilities = data.get('total liabilities')
        total_equity = data.get('total equity')
        total_assets = data.get('total assets')
        net_income = data.get('net income')
        revenue = data.get('revenue')
        total_cogs = data.get('total cogs')
        ebit = data.get('ebit')
        interest_expense = data.get('interest expense', 0)

        ratios = {}

        # ========== LIQUIDITY RATIOS ==========
        ratios["Current Ratio"] = self._safe_divide(current_assets, current_liabilities)

        ratios["Quick Ratio"] = self._safe_divide(
            self._safe_subtract(current_assets, inventory),
            current_liabilities
        )

        ratios["Cash Ratio"] = self._safe_divide(cash, current_liabilities)

        ratios["Working Capital"] = self._safe_subtract(current_assets, current_liabilities)

        ratios["Working Capital Ratio"] = self._safe_divide(
            self._safe_subtract(current_assets, current_liabilities),
            total_assets,
            multiply_by=100
        )

        ratios["Cash Flow Coverage"] = self._estimate_cash_flow_coverage(data, ratios)

        ratios["Defensive Interval"] = self._calculate_defensive_interval(data)

        # ========== PROFITABILITY RATIOS ==========
        ratios["Net Profit Margin (%)"] = self._safe_divide(net_income, revenue, multiply_by=100)

        ratios["Gross Profit Margin (%)"] = self._safe_divide(
            self._safe_subtract(revenue, total_cogs),
            revenue,
            multiply_by=100
        )

        ratios["Operating Profit Margin (%)"] = self._safe_divide(ebit, revenue, multiply_by=100)

        ratios["ROA"] = self._safe_divide(net_income, total_assets, multiply_by=100)

        ratios["ROE"] = self._safe_divide(net_income, total_equity, multiply_by=100)

        ratios["ROIC"] = self._calculate_roic(net_income, total_equity, total_liabilities, interest_expense)

        # ========== SOLVENCY/LEVERAGE RATIOS ==========
        ratios["Debt to Equity"] = self._safe_divide(total_liabilities, total_equity)

        ratios["Debt Ratio"] = self._safe_divide(total_liabilities, total_assets)

        ratios["Equity Ratio"] = self._safe_divide(total_equity, total_assets)

        ratios["Interest Coverage"] = self._safe_divide(ebit,
                                                        interest_expense) if interest_expense and interest_expense > 0 else None

        ratios["Equity Multiplier"] = self._safe_divide(total_assets, total_equity)

        # ========== EFFICIENCY/ACTIVITY RATIOS ==========
        ratios["Asset Turnover"] = self._safe_divide(revenue, total_assets)

        # Inventory Turnover = COGS / Average Inventory
        ratios["Inventory Turnover"] = self._safe_divide(total_cogs, inventory)

        # Receivables Turnover = Revenue / Average Receivables
        ratios["Receivables Turnover"] = self._safe_divide(revenue, accounts_receivable)

        # Payables Turnover = COGS / Average Payables
        ratios["Payables Turnover"] = self._safe_divide(total_cogs, accounts_payable)

        # Days ratios (365 / Turnover)
        if ratios["Inventory Turnover"]:
            ratios["Days Inventory Outstanding"] = 365 / ratios["Inventory Turnover"]
        else:
            ratios["Days Inventory Outstanding"] = None

        if ratios["Receivables Turnover"]:
            ratios["Days Sales Outstanding"] = 365 / ratios["Receivables Turnover"]
        else:
            ratios["Days Sales Outstanding"] = None

        return ratios

    def get_ratio_category(self, ratio_name: str) -> str:
        """
        Get the category for a given ratio name

        Args:
            ratio_name: Name of the financial ratio

        Returns:
            Category name ('liquidity', 'profitability', 'solvency', or 'efficiency')
        """
        for category, ratios in self.ratio_categories.items():
            if ratio_name in ratios:
                return category
        return 'other'  # Fallback category

    def get_ratios_by_category(self, ratios: Dict) -> Dict[str, Dict]:
        """
        Organize calculated ratios by their categories

        Args:
            ratios: Dictionary of calculated ratios

        Returns:
            Dictionary organized by category
        """
        categorized = {
            'liquidity': {},
            'profitability': {},
            'solvency': {},
            'efficiency': {}
        }

        for ratio_name, ratio_value in ratios.items():
            category = self.get_ratio_category(ratio_name)
            if category in categorized and ratio_value is not None:
                categorized[category][ratio_name] = ratio_value

        return categorized

    # ========== HELPER METHODS ==========

    def _safe_divide(self, numerator, denominator, multiply_by=1):
        """Safely divide two numbers, returning None if invalid"""
        if numerator is None or denominator is None:
            return None
        if pd.isna(numerator) or pd.isna(denominator):
            return None
        if denominator == 0:
            return None
        return (numerator / denominator) * multiply_by

    def _safe_subtract(self, a, b):
        """Safely subtract two numbers"""
        if a is None or b is None:
            return None
        if pd.isna(a) or pd.isna(b):
            return None
        return a - b

    def _calculate_roic(self, net_income, equity, liabilities, interest_expense):
        """Calculate Return on Invested Capital"""
        if any(x is None or pd.isna(x) for x in [net_income, equity, liabilities]):
            return None

        invested_capital = equity + liabilities
        if invested_capital == 0:
            return None

        # NOPAT approximation
        nopat = net_income + (interest_expense if interest_expense else 0)
        return (nopat / invested_capital) * 100

    def _estimate_cash_flow_coverage(self, data, ratios):
        """Estimate cash flow coverage ratio"""
        net_income = data.get('net income')
        current_liabilities = data.get('current liabilities')

        if net_income and current_liabilities and current_liabilities != 0:
            return (net_income / current_liabilities) * 100
        return None

    def _calculate_defensive_interval(self, data):
        """Calculate defensive interval (days company can operate with liquid assets)"""
        cash = data.get('cash', 0) or 0
        accounts_receivable = data.get('accounts receivable', 0) or 0
        revenue = data.get('revenue', 0) or 0
        total_cogs = data.get('total cogs', 0) or 0

        # Liquid assets
        liquid_assets = cash + accounts_receivable

        # Daily operating expenses (simplified)
        if revenue and total_cogs:
            operating_expenses = revenue - total_cogs
            if operating_expenses > 0:
                daily_expenses = operating_expenses / 365
                if daily_expenses > 0:
                    return liquid_assets / daily_expenses

        return None

    def calculate_trend_ratios(self, historical_data: list) -> Dict:
        """
        Calculate trend analysis from multiple periods

        Args:
            historical_data: List of data dictionaries for different periods

        Returns:
            Dictionary containing trend information
        """
        if len(historical_data) < 2:
            return {"error": "Need at least 2 periods for trend analysis"}

        trends = {}

        # Calculate ratios for each period
        period_ratios = []
        for period_data in historical_data:
            ratios = self.calculate_ratios(period_data)
            period_ratios.append(ratios)

        # Calculate trends for each ratio
        for ratio_name in period_ratios[0].keys():
            values = [pr.get(ratio_name) for pr in period_ratios if pr.get(ratio_name) is not None]

            if len(values) >= 2:
                change = values[-1] - values[0]
                pct_change = (change / values[0] * 100) if values[0] != 0 else None

                trends[ratio_name] = {
                    "values": values,
                    "change": change,
                    "percentage_change": pct_change,
                    "direction": "improving" if change > 0 else "declining" if change < 0 else "stable",
                    "volatility": self._calculate_volatility(values),
                    "category": self.get_ratio_category(ratio_name)
                }

        return trends

    def _calculate_volatility(self, values):
        """Calculate coefficient of variation as volatility measure"""
        if len(values) < 2:
            return None

        import statistics
        mean = statistics.mean(values)
        if mean == 0:
            return None

        std_dev = statistics.stdev(values)
        return (std_dev / mean) * 100