from __future__ import annotations

from AnchorWorks.terminal_operator import AnchorWorksOperatorApp


def test_terminal_operator_app_declares_required_panels():
    app = AnchorWorksOperatorApp(data_root=None)

    assert "Chat" in app.PANEL_TITLES
    assert "Evidence Trace" in app.PANEL_TITLES
    assert "Intake Jobs" in app.PANEL_TITLES
    assert "Missing Anchor Review" in app.PANEL_TITLES
    assert "Counts/Binary Status" in app.PANEL_TITLES
    assert "Corpus Library" in app.PANEL_TITLES
    assert "Operator Surface" in app.PANEL_TITLES
