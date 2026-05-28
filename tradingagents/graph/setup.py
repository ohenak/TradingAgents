# TradingAgents/graph/setup.py

import warnings
from typing import Any, Dict
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from tradingagents.agents import *
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.dataflows.config import get_config

from .analyst_execution import build_analyst_execution_plan
from .conditional_logic import ConditionalLogic


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm: Any,
        deep_thinking_llm: Any,
        tool_nodes: Dict[str, ToolNode],
        conditional_logic: ConditionalLogic,
        analyst_concurrency_limit: int = 1,
    ):
        """Initialize with required components."""
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.tool_nodes = tool_nodes
        self.conditional_logic = conditional_logic
        self.analyst_concurrency_limit = analyst_concurrency_limit

    def setup_graph(
        self, selected_analysts=["market", "social", "news", "fundamentals"]
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": Social media analyst
                - "news": News analyst
                - "fundamentals": Fundamentals analyst
        """
        # "wheel" is handled separately after Trader; strip it before building the pipeline plan
        pipeline_analysts = [a for a in selected_analysts if a != "wheel"]
        plan = build_analyst_execution_plan(
            pipeline_analysts,
            concurrency_limit=self.analyst_concurrency_limit,
        )

        analyst_factories = {
            "market": lambda: create_market_analyst(self.quick_thinking_llm),
            "social": lambda: create_sentiment_analyst(self.quick_thinking_llm),
            "news": lambda: create_news_analyst(self.quick_thinking_llm),
            "fundamentals": lambda: create_fundamentals_analyst(self.quick_thinking_llm),
        }

        # Create researcher and manager nodes
        bull_researcher_node = create_bull_researcher(self.quick_thinking_llm)
        bear_researcher_node = create_bear_researcher(self.quick_thinking_llm)
        research_manager_node = create_research_manager(self.deep_thinking_llm)
        trader_node = create_trader(self.quick_thinking_llm)

        # Create risk analysis nodes
        aggressive_analyst = create_aggressive_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        conservative_analyst = create_conservative_debator(self.quick_thinking_llm)
        portfolio_manager_node = create_portfolio_manager(self.deep_thinking_llm)

        # Create workflow
        workflow = StateGraph(AgentState)

        # Add analyst nodes to the graph
        first_analyst_node = plan.specs[0].agent_node
        for spec in plan.specs:
            workflow.add_node(spec.agent_node, analyst_factories[spec.key]())
            workflow.add_node(spec.clear_node, create_msg_delete())
            workflow.add_node(spec.tool_node, self.tool_nodes[spec.key])

        # Add other nodes
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Aggressive Analyst", aggressive_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Conservative Analyst", conservative_analyst)
        workflow.add_node("Portfolio Manager", portfolio_manager_node)

        # --- Wheel options nodes (ADR-WHEEL-03) ---
        # Config validation warning for options_lookforward_days
        try:
            cfg = get_config()
            wheel_cfg = cfg.get("wheel", {})
            options_lookforward = wheel_cfg.get("options_lookforward_days", 45)
            dte_high = wheel_cfg.get("recommended_dte_high", 45)
            if options_lookforward < dte_high:
                warnings.warn(
                    f"options_lookforward_days ({options_lookforward}) is less than "
                    f"recommended_dte_high ({dte_high}). "
                    f"The effective lookforward window will be extended automatically.",
                    UserWarning,
                    stacklevel=2,
                )
        except Exception:
            pass

        wheel_selected = "wheel" in [a.lower() for a in selected_analysts]

        if wheel_selected:
            # Register WheelAnalyst node
            wheel_analyst_node = create_wheel_analyst(self.deep_thinking_llm)
            workflow.add_node("wheel_analyst", wheel_analyst_node)

            # Register per-agent options ToolNodes so each routes back to its own caller
            _tn_wa = self.tool_nodes.get("options_wheel_analyst")
            _tn_csp = self.tool_nodes.get("options_csp")
            _tn_cc = self.tool_nodes.get("options_cc")
            if _tn_wa is not None:
                workflow.add_node("tools_options_wheel_analyst", _tn_wa)
            if _tn_csp is not None:
                workflow.add_node("tools_options_csp", _tn_csp)
            if _tn_cc is not None:
                workflow.add_node("tools_options_cc", _tn_cc)

            # Register options execution nodes
            csp_agent_node = create_csp_agent(self.deep_thinking_llm)
            cc_agent_node = create_cc_agent(self.deep_thinking_llm)
            roll_check_agent_node = create_roll_check_agent(self.quick_thinking_llm)
            workflow.add_node("csp_agent", csp_agent_node)
            workflow.add_node("cc_agent", cc_agent_node)
            workflow.add_node("roll_check_agent", roll_check_agent_node)

            # Register wheel_cycle_summary node
            from tradingagents.graph.wheel_nodes import wheel_cycle_summary
            workflow.add_node("wheel_cycle_summary", wheel_cycle_summary)
            workflow.add_edge("wheel_cycle_summary", END)

        # --- Conditional START edge (ADR-WHEEL-03) ---
        # Build the full routing mapping for route_wheel_phase
        # Update first_analyst_node on ConditionalLogic to match the plan
        self.conditional_logic.first_analyst_node = first_analyst_node

        # Build route mapping
        wheel_route_mapping: dict = {
            first_analyst_node: first_analyst_node,
        }
        if wheel_selected:
            wheel_route_mapping.update({
                "roll_check_agent": "roll_check_agent",
                "cc_agent": "cc_agent",
                "wheel_cycle_summary": "wheel_cycle_summary",
            })

        workflow.add_conditional_edges(
            START,
            self.conditional_logic.route_wheel_phase,
            wheel_route_mapping,
        )

        # Connect analysts in sequence
        for i, spec in enumerate(plan.specs):
            current_analyst = spec.agent_node
            current_tools = spec.tool_node
            current_clear = spec.clear_node

            # Add conditional edges for current analyst
            workflow.add_conditional_edges(
                current_analyst,
                getattr(self.conditional_logic, f"should_continue_{spec.key}"),
                [current_tools, current_clear],
            )
            workflow.add_edge(current_tools, current_analyst)

            # Connect to next analyst or to Bull Researcher if this is the last analyst
            if i < len(plan.specs) - 1:
                workflow.add_edge(current_clear, plan.specs[i + 1].agent_node)
            else:
                workflow.add_edge(current_clear, "Bull Researcher")

        # Add remaining edges
        workflow.add_conditional_edges(
            "Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Bear Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_conditional_edges(
            "Bear Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bull Researcher": "Bull Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_edge("Research Manager", "Trader")
        if wheel_selected:
            # Route through wheel_analyst before risk debate (ADR-WHEEL-03)
            workflow.add_edge("Trader", "wheel_analyst")
            # Conditional edge: wheel_analyst → tools_options_wheel_analyst (if tool calls) → back
            # Otherwise → Aggressive Analyst
            if self.tool_nodes.get("options_wheel_analyst") is not None:
                workflow.add_conditional_edges(
                    "wheel_analyst",
                    self.conditional_logic.should_continue_wheel_analyst,
                    {
                        "tools_options_wheel_analyst": "tools_options_wheel_analyst",
                        "Aggressive Analyst": "Aggressive Analyst",
                    },
                )
                workflow.add_edge("tools_options_wheel_analyst", "wheel_analyst")
            else:
                workflow.add_edge("wheel_analyst", "Aggressive Analyst")
        else:
            workflow.add_edge("Trader", "Aggressive Analyst")
        workflow.add_conditional_edges(
            "Aggressive Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Conservative Analyst": "Conservative Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )
        workflow.add_conditional_edges(
            "Conservative Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Neutral Analyst": "Neutral Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )
        workflow.add_conditional_edges(
            "Neutral Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Aggressive Analyst": "Aggressive Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )

        if wheel_selected:
            # In screening mode, Portfolio Manager routes to csp_agent so CspAgent
            # can generate the CSP recommendation (REQ-LIFE-01 AC2, REQ-TRADE-01 AC1).
            # In all other wheel phases and equity-only mode, Portfolio Manager routes to END.
            workflow.add_conditional_edges(
                "Portfolio Manager",
                self.conditional_logic.route_after_portfolio_manager,
                {
                    "csp_agent": "csp_agent",
                    "__end__": END,
                },
            )
            # csp_agent: tool calls → tools_options_csp → back; otherwise → END
            if self.tool_nodes.get("options_csp") is not None:
                workflow.add_conditional_edges(
                    "csp_agent",
                    self.conditional_logic.should_continue_csp_agent,
                    {
                        "tools_options_csp": "tools_options_csp",
                        "__end__": END,
                    },
                )
                workflow.add_edge("tools_options_csp", "csp_agent")
            else:
                workflow.add_edge("csp_agent", END)
            # cc_agent: tool calls → tools_options_cc → back; otherwise → END
            if self.tool_nodes.get("options_cc") is not None:
                workflow.add_conditional_edges(
                    "cc_agent",
                    self.conditional_logic.should_continue_cc_agent,
                    {
                        "tools_options_cc": "tools_options_cc",
                        "__end__": END,
                    },
                )
                workflow.add_edge("tools_options_cc", "cc_agent")
            else:
                workflow.add_edge("cc_agent", END)
        else:
            workflow.add_edge("Portfolio Manager", END)

        return workflow
