from io import StringIO;
from unittest.mock import patch;

from sumdoc.common import GlobalOptions;
from sumdoc.tools import lessrich;
from sumdoc.tools.ansiview import parse_ansi, plain_text;


def test_rendered_markdown_is_scrollable_and_searchable(tmp_path):
    src = tmp_path / 'demo.md';
    src.write_text('# Encabezado\n\n' + ('Línea de texto\n\n' * 60) + '| A | B |\n|---|---|\n| hola | mundo |\n');
    captured = {};
    def fake_viewer(lines, name, no_color=False):
        captured['lines'] = lines;
        captured['text'] = plain_text(lines);
        captured['name'] = name;
    with patch.object(lessrich.sys.stdin, 'isatty', return_value=True), patch.object(lessrich.sys.stdout, 'isatty', return_value=True), patch('sumdoc.tools.ansiview.run_viewer', side_effect=fake_viewer):
        result = lessrich.main([str(src)], GlobalOptions(quiet=True));
    assert result == 0;
    assert len(captured['lines']) > 50;
    assert 'Encabezado' in '\n'.join(captured['text']);
    assert 'mundo' in '\n'.join(captured['text']);


def test_no_pager_stdout_is_preserved(tmp_path):
    src = tmp_path / 'demo.md';
    src.write_text('# Salida\n');
    output = StringIO();
    with patch.object(lessrich.sys, 'stdout', output):
        assert lessrich.main([str(src), '--no-pager', '--no-color'], GlobalOptions(quiet=True)) == 0;
    assert 'Salida' in output.getvalue();


def test_ansi_parser_preserves_colored_trailing_spaces():
    lines = parse_ansi('X\x1b[48;2;1;2;3m    \x1b[0m\n');
    assert len(lines[0]) == 5;
    assert all(c.style.bg == (1, 2, 3) for c in lines[0][1:]);
