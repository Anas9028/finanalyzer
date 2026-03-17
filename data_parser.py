import pandas as pd
import warnings
from typing import Dict, Any
from datetime import datetime

warnings.filterwarnings("ignore", category=UserWarning, module='openpyxl')


class DataParser:
    """
    Parse financial data from Excel files (Balance Sheet and Income Statement)
    """

    def read_company_files(self, balance_file: str, income_file: str) -> Dict[str, Any]:
        """
        Read and parse both balance sheet and income statement files

        Args:
            balance_file: Path to balance sheet Excel file
            income_file: Path to income statement Excel file

        Returns:
            Dictionary containing all parsed financial data
        """
        data = {}

        try:
            print("📖 Reading Balance Sheet...")
            # Read Balance Sheet
            balance_data = self._parse_balance_sheet(balance_file)
            data.update(balance_data)
            print(f"   ✅ Found {len(balance_data)} balance sheet items")

            print("📖 Reading Income Statement...")
            # Read Income Statement
            income_data = self._parse_income_statement(income_file)
            data.update(income_data)
            print(f"   ✅ Found {len(income_data)} income statement items")

            # Validate data consistency
            print("🔍 Validating data...")
            self._validate_data(data)
            print("   ✅ Data validation passed")

            # Print summary
            print("\n📊 Data Summary:")
            print(f"   Period: {data.get('from date')} to {data.get('to date')}")
            print(f"   Total Assets: ${data.get('total assets', 0):,.2f}")
            print(f"   Total Equity: ${data.get('total equity', 0):,.2f}")
            print(f"   Revenue: ${data.get('revenue', 0):,.2f}")
            print(f"   Net Income: ${data.get('net income', 0):,.2f}")

        except Exception as e:
            print(f"❌ Error in read_company_files: {str(e)}")
            raise RuntimeError(f"Error reading files: {str(e)}")

        return data

    def _parse_balance_sheet(self, filepath: str) -> Dict:
        """Parse balance sheet Excel file"""
        data = {}

        try:
            xls = pd.ExcelFile(filepath)
            print(f"   📄 Sheets found: {xls.sheet_names}")

            # Find the balance sheet
            for sheet_name in xls.sheet_names:
                if "balance" in sheet_name.lower():
                    print(f"   📑 Processing sheet: {sheet_name}")
                    df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

                    # Extract key values
                    for i, row in df.iterrows():
                        row_label = str(row[0]).strip().lower() if pd.notna(row[0]) else ""

                        # Assets
                        if 'total assets' in row_label or 'total asset' in row_label:
                            data['total assets'] = pd.to_numeric(row[6], errors='coerce')
                            print(f"      ✓ Total Assets: {data.get('total assets')}")

                        if 'total current asset' in row_label:
                            data['current assets'] = pd.to_numeric(row[6], errors='coerce')
                            print(f"      ✓ Current Assets: {data.get('current assets')}")

                        if row_label == 'cash' or 'cash and cash' in row_label:
                            data['cash'] = pd.to_numeric(row[6], errors='coerce')
                            if pd.isna(data['cash']) and i + 1 < len(df):
                                data['cash'] = pd.to_numeric(df.iloc[i + 1][5], errors='coerce')
                            print(f"      ✓ Cash: {data.get('cash')}")

                        if row_label == 'inventory' or 'inventories' in row_label:
                            data['inventory'] = pd.to_numeric(row[6], errors='coerce')
                            if pd.isna(data['inventory']) and i + 1 < len(df):
                                data['inventory'] = pd.to_numeric(df.iloc[i + 1][5], errors='coerce')
                            print(f"      ✓ Inventory: {data.get('inventory')}")

                        if 'accounts receivable' in row_label or 'receivables' in row_label:
                            data['accounts receivable'] = pd.to_numeric(row[6], errors='coerce')
                            print(f"      ✓ Accounts Receivable: {data.get('accounts receivable')}")

                        # Liabilities
                        if 'total liabilities' in row_label or 'total liabilit' in row_label:
                            data['total liabilities'] = pd.to_numeric(row[6], errors='coerce')
                            print(f"      ✓ Total Liabilities: {data.get('total liabilities')}")

                        if 'total current liabilit' in row_label:
                            data['current liabilities'] = pd.to_numeric(row[6], errors='coerce')
                            print(f"      ✓ Current Liabilities: {data.get('current liabilities')}")

                        if 'long-term debt' in row_label or 'long term debt' in row_label:
                            data['long term debt'] = pd.to_numeric(row[6], errors='coerce')

                        if 'accounts payable' in row_label or 'payables' in row_label:
                            data['accounts payable'] = pd.to_numeric(row[6], errors='coerce')

                        # Equity
                        if 'total equity' in row_label or "total stockholder" in row_label or "shareholder" in row_label:
                            data['total equity'] = pd.to_numeric(row[6], errors='coerce')
                            print(f"      ✓ Total Equity: {data.get('total equity')}")

                        if 'retained earnings' in row_label:
                            data['retained earnings'] = pd.to_numeric(row[6], errors='coerce')

                    break

            # Calculate derived values if missing
            if 'current assets' not in data and 'total assets' in data:
                data['current assets'] = data.get('cash', 0) + data.get('accounts receivable', 0) + data.get(
                    'inventory', 0)
                print(f"      ℹ️  Calculated Current Assets: {data['current assets']}")

            # If still missing critical values, set defaults
            if 'cash' not in data or pd.isna(data.get('cash')):
                data['cash'] = 0
                print(f"      ⚠️  Cash not found, using 0")

            if 'inventory' not in data or pd.isna(data.get('inventory')):
                data['inventory'] = 0
                print(f"      ⚠️  Inventory not found, using 0")

        except Exception as e:
            print(f"❌ Error parsing balance sheet: {str(e)}")
            raise RuntimeError(f"Error parsing balance sheet: {str(e)}")

        return data

    def _parse_income_statement(self, filepath: str) -> Dict:
        """Parse income statement Excel file"""
        data = {}

        try:
            xls = pd.ExcelFile(filepath)
            print(f"   📄 Sheets found: {xls.sheet_names}")

            # Find income statement sheet
            for sheet_name in xls.sheet_names:
                if "income" in sheet_name.lower() or "profit" in sheet_name.lower():
                    print(f"   📑 Processing sheet: {sheet_name}")
                    df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

                    # Extract key values
                    for i, row in df.iterrows():
                        row_label = str(row[0]).strip().lower() if pd.notna(row[0]) else ""
                        row_label2 = str(row[2]).strip().lower() if len(row) > 2 and pd.notna(row[2]) else ""

                        # Revenue
                        if 'net sales' in row_label or 'revenue' in row_label or 'total revenue' in row_label:
                            data['revenue'] = pd.to_numeric(row[6], errors='coerce')
                            print(f"      ✓ Revenue: {data.get('revenue')}")

                        if 'sales revenue' in row_label and 'revenue' not in data:
                            data['revenue'] = pd.to_numeric(row[6], errors='coerce')

                        # Cost of Goods Sold
                        if 'total cost of goods sold' in row_label or 'total cogs' in row_label:
                            data['total cogs'] = pd.to_numeric(row[6], errors='coerce')
                            print(f"      ✓ COGS: {data.get('total cogs')}")

                        if 'cost of sales' in row_label and 'total cogs' not in data:
                            data['total cogs'] = pd.to_numeric(row[6], errors='coerce')

                        # Operating Income
                        if 'income from operations' in row_label or 'operating income' in row_label:
                            data['ebit'] = pd.to_numeric(row[6], errors='coerce')
                            print(f"      ✓ EBIT: {data.get('ebit')}")

                        if 'ebit' in row_label.replace(' ', ''):
                            data['ebit'] = pd.to_numeric(row[6], errors='coerce')

                        # Net Income
                        if 'net income' in row_label and 'before' not in row_label:
                            data['net income'] = pd.to_numeric(row[6], errors='coerce')
                            print(f"      ✓ Net Income: {data.get('net income')}")

                        # Interest Expense
                        if 'interest expense' in row_label or 'interest expense' in row_label2:
                            data['interest expense'] = pd.to_numeric(row[4], errors='coerce')
                            if pd.isna(data['interest expense']):
                                data['interest expense'] = pd.to_numeric(row[6], errors='coerce')
                            print(f"      ✓ Interest Expense: {data.get('interest expense')}")

                        # Operating Expenses
                        if 'operating expenses' in row_label or 'total operating' in row_label:
                            data['operating expenses'] = pd.to_numeric(row[6], errors='coerce')

                        # Depreciation
                        if 'depreciation' in row_label:
                            data['depreciation'] = pd.to_numeric(row[6], errors='coerce')

                    break

            # Find dates in inputs sheet
            for sheet_name in xls.sheet_names:
                if "input" in sheet_name.lower():
                    print(f"   📑 Reading dates from: {sheet_name}")
                    df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

                    # Read dates from B2 and B3
                    if len(df) >= 3:
                        from_date_raw = df.iloc[1, 1] if len(df.columns) > 1 else None
                        to_date_raw = df.iloc[2, 1] if len(df.columns) > 1 else None

                        # Convert to datetime
                        if isinstance(from_date_raw, pd.Timestamp):
                            data['from date'] = from_date_raw
                        elif from_date_raw:
                            try:
                                data['from date'] = pd.to_datetime(from_date_raw)
                            except:
                                data['from date'] = None

                        if isinstance(to_date_raw, pd.Timestamp):
                            data['to date'] = to_date_raw
                        elif to_date_raw:
                            try:
                                data['to date'] = pd.to_datetime(to_date_raw)
                            except:
                                data['to date'] = None

                        print(f"      ✓ From Date: {data.get('from date')}")
                        print(f"      ✓ To Date: {data.get('to date')}")

                    break

            # If dates not found, use default period (current year)
            if 'from date' not in data or 'to date' not in data:
                from datetime import date
                current_year = date.today().year
                data['from date'] = pd.Timestamp(f'{current_year}-01-01')
                data['to date'] = pd.Timestamp(f'{current_year}-12-31')
                print(f"      ⚠️  Dates not found, using default: {data['from date']} to {data['to date']}")

            # Set default for interest expense if missing
            if 'interest expense' not in data or pd.isna(data.get('interest expense')):
                data['interest expense'] = 0
                print(f"      ⚠️  Interest Expense not found, using 0")

        except Exception as e:
            print(f"❌ Error parsing income statement: {str(e)}")
            raise RuntimeError(f"Error parsing income statement: {str(e)}")

        return data

    def _validate_data(self, data: Dict):
        """Validate parsed data for consistency and completeness"""

        # Check required fields
        required_fields = ['total assets', 'total equity', 'revenue', 'net income']
        missing_fields = [field for field in required_fields if
                          field not in data or data[field] is None or pd.isna(data[field])]

        if missing_fields:
            raise ValueError(f"Missing required financial data: {', '.join(missing_fields)}")

        # Check date validity
        if 'from date' not in data or 'to date' not in data:
            raise ValueError("Period dates are missing")

        if data['from date'] is None or data['to date'] is None:
            raise ValueError("Invalid period dates")

        if data['from date'] >= data['to date']:
            raise ValueError("Start date must be before end date")

        # Validate accounting equation: Assets = Liabilities + Equity
        if all(k in data and data[k] is not None for k in ['total assets', 'total liabilities', 'total equity']):
            assets = data['total assets']
            liabilities = data['total liabilities']
            equity = data['total equity']

            balance = assets - (liabilities + equity)
            tolerance = assets * 0.01  # 1% tolerance

            if abs(balance) > tolerance:
                print(f"      ⚠️  Warning: Balance sheet doesn't balance. Difference: ${balance:,.2f}")

        # Ensure non-negative values for key metrics
        for key in ['total assets', 'revenue']:
            if key in data and data[key] is not None and data[key] < 0:
                raise ValueError(f"{key} cannot be negative")

        return True