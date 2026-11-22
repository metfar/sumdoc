from io import StringIO;
from unittest.mock import patch;
import pytest;
from sumdoc.common import GlobalOptions;
from sumdoc.registry import resolve_tool;
from sumdoc.tools import lessans;
from sumdoc.tools.ansiview import parse_ansi, plain_text, render_line;


def test_registered_tool_and_aliases():
    assert resolve_tool('lessans').name == 'lessans';
    assert resolve_tool('lessrich').name == 'md2rich';


def test_truecolor_bg_preserves_final_spaces():
    lines = parse_ansi('\x1b[48;2;1;2;3mA    \x1b[0m\n');
    assert len(lines[0]) == 5;
    assert all(c.style.bg == (1, 2, 3) for c in lines[0]);
    assert '48;2;1;2;3m' in render_line(lines[0], 0, 8);


def test_plain_output_and_stream_output(tmp_path):
    source = tmp_path / 'screenshot.ans';
    raw = '\x1b[38;5;196mRed\x1b[0m\n';
    source.write_text(raw);
    output = StringIO();
    with patch.object(lessans.sys, 'stdout', output):
        assert lessans.main([str(source), '--plain'], GlobalOptions()) == 0;
    assert output.getvalue() == 'Red\n';
    output = StringIO();
    with patch.object(lessans.sys, 'stdout', output):
        assert lessans.main([str(source)], GlobalOptions()) == 0;
    assert output.getvalue() == raw;


def test_pager_and_output_validation(tmp_path):
    source = tmp_path / 'file.ans';
    source.write_text('text');
    with pytest.raises(ValueError, match='cannot be combined'):
        lessans.main([str(source), '--pager', '--no-pager'], GlobalOptions());
    with pytest.raises(ValueError, match='terminal'):
        lessans.main([str(source), '--pager'], GlobalOptions());
