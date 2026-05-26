# TradingAgents/graph/conditional_logic.py

import logging

from tradingagents.agents.utils.agent_states import AgentState

logger = logging.getLogger(__name__)


class ConditionalLogic:
    """Handles conditional logic for determining graph flow."""

    def __init__(
        self,
        max_debate_rounds=1,
        max_risk_discuss_rounds=1,
        first_analyst_node: str = "Market Analyst",
        position_store_dir: str = "memory/wheel_positions",
    ):
        """Initialize with configuration parameters.

        Args:
            max_debate_rounds: Number of debate rounds.
            max_risk_discuss_rounds: Number of risk discussion rounds.
            first_analyst_node: Node name for the first analyst (ADR-WHEEL-03).
            position_store_dir: Directory for WheelPosition JSON files (ADR-WHEEL-05).
        """
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds
        self.first_analyst_node = first_analyst_node
        self.position_store_dir = position_store_dir

    def _load_position(self, ticker: str):
        """Load the latest open WheelPosition for a ticker.

        Returns None if no position exists or on any error.
        """
        try:
            from tradingagents.models.wheel_position import load_latest_open_position
            return load_latest_open_position(ticker, self.position_store_dir)
        except Exception as exc:
            logger.warning("_load_position: failed to load position for %s: %s", ticker, exc)
            return None

    def route_wheel_phase(self, state: AgentState) -> str:
        """Route graph execution based on wheel_phase.

        Routing table (DEC-PLAN-02):
        - None → first_analyst_node (equity path; ADR-WHEEL-03)
        - "screening" → first_analyst_node (starts analyst team + WheelAnalyst)
        - "csp_open" → "roll_check_agent" (TE-v2-F-03; DEC-PLAN-02)
        - "stock_owned" → "cc_agent"
        - "cc_open" → "roll_check_agent"
        - "cycle_complete" → "wheel_cycle_summary"
        - unknown → first_analyst_node (with warning; ADR-WHEEL-02)

        Guard failures for "csp_open" and "cc_open" without backing WheelPosition
        raise WheelStateError (ADR-WHEEL-05).
        """
        from tradingagents.graph.wheel_nodes import WheelStateError

        wheel_phase = state.get("wheel_phase")
        ticker = state.get("company_of_interest", "unknown")

        if wheel_phase is None:
            return self.first_analyst_node

        if wheel_phase == "screening":
            return self.first_analyst_node

        if wheel_phase == "csp_open":
            position = self._load_position(ticker)
            if position is None:
                raise WheelStateError(
                    f"wheel_phase='csp_open' but no WheelPosition found for {ticker}. "
                    f"Cannot route to roll_check_agent without a backing position."
                )
            return "roll_check_agent"

        if wheel_phase == "stock_owned":
            return "cc_agent"

        if wheel_phase == "cc_open":
            position = self._load_position(ticker)
            if position is None:
                raise WheelStateError(
                    f"wheel_phase='cc_open' but no WheelPosition found for {ticker}. "
                    f"Cannot route to roll_check_agent without a backing position."
                )
            return "roll_check_agent"

        if wheel_phase == "cycle_complete":
            return "wheel_cycle_summary"

        # Unknown phase → warn and fall back to equity path (ADR-WHEEL-02)
        warning_msg = (
            f"[WARNING] Unknown wheel_phase '{wheel_phase}' for {ticker}. "
            f"Routing to equity path ({self.first_analyst_node}). "
            f"If this is unexpected, check the wheel_phase value in the position file."
        )
        logger.warning(warning_msg)
        # Surface to CLI user per ADR-WHEEL-02 (stored in state for CLI retrieval)
        return self.first_analyst_node

    def route_after_portfolio_manager(self, state: AgentState) -> str:
        """Route after Portfolio Manager.

        When wheel is selected and wheel_phase is "screening", the graph
        routes to csp_agent so CspAgent can generate the CSP recommendation
        (REQ-LIFE-01 AC2, REQ-TRADE-01 AC1).

        All other paths (equity-only, non-screening wheel phases) route to END.
        """
        wheel_phase = state.get("wheel_phase")
        if wheel_phase == "screening":
            return "csp_agent"
        return "__end__"

    def should_continue_market(self, state: AgentState):
        """Determine if market analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_market"
        return "Msg Clear Market"

    def should_continue_social(self, state: AgentState):
        """Determine if sentiment-analyst tool round should continue.

        Method name keeps the legacy ``social`` suffix to match the
        ``AnalystType.SOCIAL = "social"`` wire value (saved-config
        back-compat); the returned ``clear_node`` label uses the v0.2.5
        rename so it matches the node registered by the execution plan.
        """
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_social"
        return "Msg Clear Sentiment"

    def should_continue_news(self, state: AgentState):
        """Determine if news analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_news"
        return "Msg Clear News"

    def should_continue_fundamentals(self, state: AgentState):
        """Determine if fundamentals analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_fundamentals"
        return "Msg Clear Fundamentals"

    def should_continue_debate(self, state: AgentState) -> str:
        """Determine if debate should continue."""

        if (
            state["investment_debate_state"]["count"] >= 2 * self.max_debate_rounds
        ):  # 3 rounds of back-and-forth between 2 agents
            return "Research Manager"
        if state["investment_debate_state"]["current_response"].startswith("Bull"):
            return "Bear Researcher"
        return "Bull Researcher"

    def should_continue_risk_analysis(self, state: AgentState) -> str:
        """Determine if risk analysis should continue."""
        if (
            state["risk_debate_state"]["count"] >= 3 * self.max_risk_discuss_rounds
        ):  # 3 rounds of back-and-forth between 3 agents
            return "Portfolio Manager"
        if state["risk_debate_state"]["latest_speaker"].startswith("Aggressive"):
            return "Conservative Analyst"
        if state["risk_debate_state"]["latest_speaker"].startswith("Conservative"):
            return "Neutral Analyst"
        return "Aggressive Analyst"
