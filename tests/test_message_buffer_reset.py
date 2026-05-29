"""Tests for MessageBuffer.reset(). PROP-RESET-01 through PROP-RESET-05."""
import pytest


class TestMessageBufferReset:
    def test_fresh_buffer_reset_is_noop(self):
        """reset() on a fresh buffer leaves all fields at defaults without error."""
        from cli.main import MessageBuffer
        buf = MessageBuffer()
        buf.reset()
        assert len(buf.messages) == 0
        assert len(buf.tool_calls) == 0
        assert len(buf._processed_message_ids) == 0
        assert buf.agent_status == {}
        assert buf.current_report is None
        assert buf.final_report is None
        assert buf.report_sections == {}
        assert buf.selected_analysts == []

    def test_reset_clears_state_set_by_init_for_analysis(self):
        """After init_for_analysis(), reset() returns buffer to empty state."""
        from cli.main import MessageBuffer
        buf = MessageBuffer()
        buf.init_for_analysis(["market"])
        assert len(buf.agent_status) > 0
        assert len(buf.report_sections) > 0

        buf.reset()
        assert buf.agent_status == {}
        assert buf.report_sections == {}
        assert buf.selected_analysts == []
        assert len(buf._processed_message_ids) == 0

    def test_reset_removes_monkey_patched_methods(self):
        """After monkey-patching and reset(), add_message must not be in __dict__."""
        from cli.main import MessageBuffer
        buf = MessageBuffer()

        # Simulate the monkey-patching done by run_analysis()
        buf.add_message = lambda *a, **kw: None
        buf.add_tool_call = lambda *a, **kw: None
        buf.update_report_section = lambda *a, **kw: None

        assert "add_message" in buf.__dict__
        assert "add_tool_call" in buf.__dict__
        assert "update_report_section" in buf.__dict__

        buf.reset()

        assert "add_message" not in buf.__dict__
        assert "add_tool_call" not in buf.__dict__
        assert "update_report_section" not in buf.__dict__
        # Class-level method is accessible after reset
        assert callable(buf.add_message)
