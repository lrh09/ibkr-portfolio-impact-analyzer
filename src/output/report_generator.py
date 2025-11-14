"""
Report generation for portfolio analysis.
"""
import logging
import json
import pandas as pd
from typing import Dict, List
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate portfolio analysis reports."""

    def __init__(self, export_path: str = 'data/reports/'):
        """
        Initialize report generator.

        Args:
            export_path: Path to export reports
        """
        self.export_path = export_path
        os.makedirs(export_path, exist_ok=True)

    def generate_scenario_summary(self, scenario_results: Dict[str, Dict]) -> pd.DataFrame:
        """
        Generate scenario summary report.

        Args:
            scenario_results: Dictionary of scenario results

        Returns:
            DataFrame with scenario summary
        """
        rows = []

        for scenario_name, result in scenario_results.items():
            worst_pos = result.get('worst_position', {})
            best_pos = result.get('best_position', {})

            rows.append({
                'Scenario': scenario_name,
                'Portfolio P&L': f"${result['portfolio_pnl']:,.2f}",
                '% Change': f"{result['portfolio_pnl_percent']:.2f}%",
                'New Value': f"${result['scenario_portfolio_value']:,.2f}",
                'Worst Position': worst_pos.get('symbol', 'N/A') if worst_pos else 'N/A',
                'Worst P&L': f"${worst_pos.get('pnl', 0):,.2f}" if worst_pos else '$0',
                'Best Position': best_pos.get('symbol', 'N/A') if best_pos else 'N/A',
                'Best P&L': f"${best_pos.get('pnl', 0):,.2f}" if best_pos else '$0'
            })

        df = pd.DataFrame(rows)

        # Sort by P&L
        df['_sort_pnl'] = [result['portfolio_pnl'] for result in scenario_results.values()]
        df = df.sort_values('_sort_pnl')
        df = df.drop('_sort_pnl', axis=1)

        return df

    def generate_position_detail(self, scenario_results: Dict[str, Dict]) -> pd.DataFrame:
        """
        Generate position detail report.

        Args:
            scenario_results: Dictionary of scenario results

        Returns:
            DataFrame with position details
        """
        # Collect all positions
        all_positions = set()
        for result in scenario_results.values():
            for pos_result in result['position_results']:
                all_positions.add(pos_result['symbol'])

        rows = []

        for symbol in sorted(all_positions):
            row = {'Position': symbol}

            # Get current value
            for result in scenario_results.values():
                for pos_result in result['position_results']:
                    if pos_result['symbol'] == symbol:
                        row['Current'] = f"${pos_result['current_value']:,.2f}"
                        row['Type'] = pos_result['type']
                        break
                if 'Current' in row:
                    break

            # Get scenario P&Ls
            max_gain = 0
            max_loss = 0
            max_gain_scenario = ''
            max_loss_scenario = ''

            for scenario_name, result in scenario_results.items():
                for pos_result in result['position_results']:
                    if pos_result['symbol'] == symbol:
                        pnl = pos_result['pnl']
                        row[scenario_name] = f"${pnl:,.2f}"

                        if pnl > max_gain:
                            max_gain = pnl
                            max_gain_scenario = scenario_name
                        if pnl < max_loss:
                            max_loss = pnl
                            max_loss_scenario = scenario_name

            row['Max Loss'] = f"${max_loss:,.2f}"
            row['Max Gain'] = f"${max_gain:,.2f}"
            row['Worst Scenario'] = max_loss_scenario
            row['Best Scenario'] = max_gain_scenario

            rows.append(row)

        df = pd.DataFrame(rows)
        return df

    def generate_risk_matrix(self, positions: List, spot_range: List[float],
                            iv_range: List[float]) -> pd.DataFrame:
        """
        Generate risk matrix (heat map data).

        Args:
            positions: List of positions
            spot_range: List of spot price changes
            iv_range: List of IV changes

        Returns:
            DataFrame with risk matrix
        """
        # This would require running scenarios for each combination
        # Simplified version returning placeholder structure
        matrix_data = []

        for spot_change in spot_range:
            row = {'Spot Change': f"{spot_change:+.1%}"}
            for iv_change in iv_range:
                # Placeholder - would calculate actual P&L
                row[f"IV {iv_change:+.1%}"] = 0.0
            matrix_data.append(row)

        df = pd.DataFrame(matrix_data)
        return df

    def generate_greeks_summary(self, portfolio_metrics: Dict) -> pd.DataFrame:
        """
        Generate Greeks summary.

        Args:
            portfolio_metrics: Portfolio metrics dictionary

        Returns:
            DataFrame with Greeks summary
        """
        greeks_data = [
            {'Greek': 'Delta', 'Value': f"{portfolio_metrics.get('delta', 0):,.2f}",
             'Description': 'Portfolio directional exposure'},
            {'Greek': 'Gamma', 'Value': f"{portfolio_metrics.get('gamma', 0):,.4f}",
             'Description': 'Delta change per $1 move'},
            {'Greek': 'Theta', 'Value': f"${portfolio_metrics.get('theta', 0):,.2f}",
             'Description': 'Daily time decay'},
            {'Greek': 'Vega', 'Value': f"${portfolio_metrics.get('vega', 0):,.2f}",
             'Description': 'P&L change per 1% IV move'},
            {'Greek': 'Rho', 'Value': f"${portfolio_metrics.get('rho', 0):,.2f}",
             'Description': 'P&L change per 1% rate move'}
        ]

        df = pd.DataFrame(greeks_data)
        return df

    def export_to_csv(self, df: pd.DataFrame, filename: str):
        """
        Export DataFrame to CSV.

        Args:
            df: DataFrame to export
            filename: Output filename
        """
        try:
            filepath = os.path.join(self.export_path, filename)
            df.to_csv(filepath, index=False)
            logger.info(f"Exported CSV to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")
            return None

    def export_to_json(self, data: Dict, filename: str):
        """
        Export data to JSON.

        Args:
            data: Dictionary to export
            filename: Output filename
        """
        try:
            filepath = os.path.join(self.export_path, filename)
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Exported JSON to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error exporting JSON: {e}")
            return None

    def export_to_excel(self, dataframes: Dict[str, pd.DataFrame], filename: str):
        """
        Export multiple DataFrames to Excel with multiple sheets.

        Args:
            dataframes: Dictionary of sheet_name -> DataFrame
            filename: Output filename
        """
        try:
            filepath = os.path.join(self.export_path, filename)
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                for sheet_name, df in dataframes.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            logger.info(f"Exported Excel to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error exporting Excel: {e}")
            return None

    def generate_full_report(self, positions: List, scenario_results: Dict[str, Dict],
                            portfolio_metrics: Dict, risk_alerts: List = None) -> Dict[str, pd.DataFrame]:
        """
        Generate full analysis report with all sections.

        Args:
            positions: List of positions
            scenario_results: Dictionary of scenario results
            portfolio_metrics: Portfolio metrics
            risk_alerts: List of risk alerts (optional)

        Returns:
            Dictionary of report section name -> DataFrame
        """
        report = {}

        # Portfolio summary
        summary_data = [{
            'Metric': 'Total Portfolio Value',
            'Value': f"${portfolio_metrics.get('total_value', 0):,.2f}"
        }, {
            'Metric': 'Number of Positions',
            'Value': portfolio_metrics.get('num_positions', 0)
        }, {
            'Metric': 'Stock Positions',
            'Value': portfolio_metrics.get('num_stock_positions', 0)
        }, {
            'Metric': 'Option Positions',
            'Value': portfolio_metrics.get('num_option_positions', 0)
        }, {
            'Metric': 'Total P&L',
            'Value': f"${portfolio_metrics.get('total_pnl', 0):,.2f}"
        }]
        report['Portfolio Summary'] = pd.DataFrame(summary_data)

        # Greeks summary
        report['Greeks Summary'] = self.generate_greeks_summary(portfolio_metrics)

        # Scenario summary
        report['Scenario Summary'] = self.generate_scenario_summary(scenario_results)

        # Position details
        report['Position Details'] = self.generate_position_detail(scenario_results)

        # Risk alerts
        if risk_alerts:
            alerts_data = []
            for alert in risk_alerts:
                alerts_data.append({
                    'Severity': alert.severity,
                    'Type': alert.alert_type,
                    'Message': alert.message,
                    'Time': alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                })
            report['Risk Alerts'] = pd.DataFrame(alerts_data)

        return report

    def print_report(self, report: Dict[str, pd.DataFrame]):
        """
        Print report to console.

        Args:
            report: Dictionary of report sections
        """
        print("\n" + "="*80)
        print("PORTFOLIO RISK ANALYSIS REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")

        for section_name, df in report.items():
            print(f"\n{section_name}")
            print("-" * len(section_name))
            print(df.to_string(index=False))
            print()

    def save_full_report(self, report: Dict[str, pd.DataFrame], base_filename: str = None):
        """
        Save full report in multiple formats.

        Args:
            report: Dictionary of report sections
            base_filename: Base filename (timestamp will be added)

        Returns:
            Dictionary with paths to saved files
        """
        if base_filename is None:
            base_filename = f"portfolio_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        saved_files = {}

        # Save as Excel
        excel_file = f"{base_filename}.xlsx"
        excel_path = self.export_to_excel(report, excel_file)
        if excel_path:
            saved_files['excel'] = excel_path

        # Save each section as CSV
        csv_files = []
        for section_name, df in report.items():
            csv_filename = f"{base_filename}_{section_name.replace(' ', '_')}.csv"
            csv_path = self.export_to_csv(df, csv_filename)
            if csv_path:
                csv_files.append(csv_path)

        if csv_files:
            saved_files['csv'] = csv_files

        logger.info(f"Saved full report: {saved_files}")
        return saved_files
