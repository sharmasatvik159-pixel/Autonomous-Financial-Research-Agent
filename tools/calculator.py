"""Quantitative Financial Calculation Engine Tool for ARA-1.

Implements Pure Deterministic Calculations conforming to Section 4.2:
- Discounted Cash Flow (DCF) intrinsic equity valuation
- Weighted Average Cost of Capital (WACC)
- Compound Annual Growth Rate (CAGR) and YoY growth
- Profitability, efficiency, and solvency ratios
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional

from tools.tool_registry import BaseTool, ToolMetadata
from tools.schemas import CalculationEngineInput

logger = logging.getLogger("ARA1.CalculationEngine")


class CalculationEngineTool(BaseTool):
    """Tool for deterministic quantitative financial modeling, DCF, and ratio analysis."""

    def __init__(self):
        metadata = ToolMetadata(
            name="calculation_engine",
            description=(
                "Performs deterministic quantitative calculations for equity research: "
                "Discounted Cash Flow ('dcf'), Weighted Average Cost of Capital ('wacc'), "
                "Compound Annual Growth Rate ('cagr'), YoY growth percentage ('growth'), "
                "and margin ratios ('margin'). Returns exact mathematical computations."
            ),
            category="analytics",
            rate_limit_rps=100.0,
            fallback_tools=[],
            unlocked=True,
            input_schema=CalculationEngineInput,
        )
        super().__init__(metadata)

    def run(self, calculation_type: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Routes and executes mathematical calculation models."""
        c_type = calculation_type.strip().lower()
        logger.info(f"Executing calculation_engine: type='{c_type}', inputs={inputs}")

        if c_type in ("dcf", "discounted_cash_flow"):
            return self._calculate_dcf(inputs)
        elif c_type == "wacc":
            return self._calculate_wacc(inputs)
        elif c_type == "cagr":
            return self._calculate_cagr(inputs)
        elif c_type in ("growth", "growth_rate"):
            return self._calculate_growth(inputs)
        elif c_type in ("margin", "margins"):
            return self._calculate_margin(inputs)
        elif c_type in ("pe_ratio", "ratio", "ratios"):
            return self._calculate_ratios(inputs)
        else:
            raise ValueError(
                f"Unsupported calculation_type '{calculation_type}'. "
                f"Supported types: 'dcf', 'wacc', 'cagr', 'growth', 'margin', 'ratios'."
            )

    def _calculate_dcf(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates multi-stage Discounted Cash Flow (DCF) enterprise and equity valuation."""
        # Required parameters
        fcfs = inputs.get("free_cash_flows")
        if not fcfs or not isinstance(fcfs, list):
            # If given base_fcf and growth_rate
            base_fcf = float(inputs.get("base_fcf", 1000.0))
            fcf_growth = float(inputs.get("fcf_growth", 0.10))
            forecast_years = int(inputs.get("forecast_years", 5))
            fcfs = [round(base_fcf * ((1.0 + fcf_growth) ** i), 2) for i in range(1, forecast_years + 1)]
        else:
            fcfs = [float(x) for x in fcfs]

        discount_rate = float(inputs.get("discount_rate", inputs.get("wacc", 0.09)))
        terminal_growth = float(inputs.get("terminal_growth_rate", 0.025))
        shares_outstanding = float(inputs.get("shares_outstanding", 1.0))
        net_debt = float(inputs.get("net_debt", 0.0))

        if discount_rate <= terminal_growth:
            raise ValueError("Discount rate (WACC) must be strictly greater than terminal growth rate.")

        # 1. Present value of forecast period FCFs
        pv_fcfs = []
        discount_factors = []
        for year, fcf in enumerate(fcfs, start=1):
            df = 1.0 / ((1.0 + discount_rate) ** year)
            pv = fcf * df
            discount_factors.append(round(df, 4))
            pv_fcfs.append(round(pv, 2))

        pv_forecast_sum = sum(pv_fcfs)

        # 2. Terminal Value (Gordon Growth Model)
        final_fcf = fcfs[-1]
        terminal_fcf = final_fcf * (1.0 + terminal_growth)
        terminal_value = terminal_fcf / (discount_rate - terminal_growth)
        pv_terminal_value = terminal_value / ((1.0 + discount_rate) ** len(fcfs))

        # 3. Enterprise Value & Equity Value
        enterprise_value = pv_forecast_sum + pv_terminal_value
        equity_value = enterprise_value - net_debt
        implied_share_price = equity_value / shares_outstanding if shares_outstanding > 0 else 0.0

        return {
            "model": "Discounted Cash Flow (DCF)",
            "forecast_period_years": len(fcfs),
            "projected_cash_flows": fcfs,
            "discount_rate_wacc": f"{discount_rate * 100:.2f}%",
            "terminal_growth_rate": f"{terminal_growth * 100:.2f}%",
            "pv_of_projected_cash_flows": round(pv_forecast_sum, 2),
            "terminal_value": round(terminal_value, 2),
            "pv_of_terminal_value": round(pv_terminal_value, 2),
            "terminal_value_share_of_ev": f"{(pv_terminal_value / enterprise_value) * 100:.1f}%",
            "enterprise_value": round(enterprise_value, 2),
            "net_debt": round(net_debt, 2),
            "equity_value": round(equity_value, 2),
            "shares_outstanding": shares_outstanding,
            "implied_share_price": round(implied_share_price, 2),
        }

    def _calculate_wacc(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates Weighted Average Cost of Capital (WACC)."""
        equity_value = float(inputs.get("equity_value", inputs.get("market_cap", 100.0)))
        debt_value = float(inputs.get("debt_value", inputs.get("total_debt", 20.0)))
        cost_of_equity = float(inputs.get("cost_of_equity", 0.10))
        cost_of_debt = float(inputs.get("cost_of_debt", 0.05))
        tax_rate = float(inputs.get("tax_rate", 0.21))

        total_val = equity_value + debt_value
        if total_val <= 0:
            raise ValueError("Total firm value (Equity + Debt) must be greater than zero.")

        weight_equity = equity_value / total_val
        weight_debt = debt_value / total_val
        after_tax_cost_of_debt = cost_of_debt * (1.0 - tax_rate)

        wacc = (weight_equity * cost_of_equity) + (weight_debt * after_tax_cost_of_debt)

        return {
            "model": "Weighted Average Cost of Capital (WACC)",
            "weight_of_equity": f"{weight_equity * 100:.2f}%",
            "weight_of_debt": f"{weight_debt * 100:.2f}%",
            "cost_of_equity": f"{cost_of_equity * 100:.2f}%",
            "pre_tax_cost_of_debt": f"{cost_of_debt * 100:.2f}%",
            "effective_tax_rate": f"{tax_rate * 100:.2f}%",
            "after_tax_cost_of_debt": f"{after_tax_cost_of_debt * 100:.2f}%",
            "wacc_percentage": f"{wacc * 100:.2f}%",
            "wacc_decimal": round(wacc, 4),
        }

    def _calculate_cagr(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates Compound Annual Growth Rate (CAGR)."""
        start_val = float(inputs.get("start_val", inputs.get("start_value", 100.0)))
        end_val = float(inputs.get("end_val", inputs.get("end_value", 200.0)))
        periods = float(inputs.get("periods", inputs.get("years", 3)))

        if start_val <= 0 or periods <= 0:
            raise ValueError("Start value and periods must be positive.")

        cagr = ((end_val / start_val) ** (1.0 / periods)) - 1.0

        return {
            "model": "Compound Annual Growth Rate (CAGR)",
            "start_value": start_val,
            "end_value": end_val,
            "periods": periods,
            "total_percentage_growth": f"{((end_val - start_val) / start_val) * 100:.2f}%",
            "cagr_percentage": f"{cagr * 100:.2f}%",
            "cagr_decimal": round(cagr, 4),
        }

    def _calculate_growth(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates percentage growth between current and prior period."""
        current = float(inputs.get("current", inputs.get("current_value", 0.0)))
        prior = float(inputs.get("prior", inputs.get("prior_value", 0.0)))

        if prior == 0:
            raise ValueError("Prior period value cannot be zero for growth calculation.")

        growth = (current - prior) / abs(prior)

        return {
            "current_value": current,
            "prior_value": prior,
            "absolute_change": round(current - prior, 2),
            "percentage_growth": f"{growth * 100:+.2f}%",
            "growth_decimal": round(growth, 4),
        }

    def _calculate_margin(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates margin ratio (e.g. gross margin, operating margin, net margin)."""
        numerator = float(
            inputs.get("numerator",
            inputs.get("metric_value",
            inputs.get("operating_income",
            inputs.get("net_income",
            inputs.get("gross_profit", 0.0)))))
        )
        revenue = float(inputs.get("revenue", inputs.get("total_revenue", 1.0)))

        if revenue == 0:
            raise ValueError("Revenue cannot be zero for margin calculation.")

        margin = (numerator / revenue) * 100.0
        return {
            "numerator_metric": numerator,
            "total_revenue": revenue,
            "margin_percentage": f"{margin:.2f}%",
            "margin_decimal": round(numerator / revenue, 4),
        }

    def _calculate_ratios(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates valuation multiples and liquidity ratios."""
        price = float(inputs.get("price", inputs.get("stock_price", 100.0)))
        eps = float(inputs.get("eps", inputs.get("diluted_eps", 5.0)))
        book_value = float(inputs.get("book_value_per_share", 20.0))

        pe = price / eps if eps != 0 else None
        pb = price / book_value if book_value > 0 else None

        return {
            "stock_price": price,
            "diluted_eps": eps,
            "pe_ratio": f"{pe:.2f}x" if pe else "N/A",
            "price_to_book": f"{pb:.2f}x" if pb else "N/A",
        }
