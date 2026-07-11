#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301
#  
#  Copyright 2018-2026 William Martinez Bas <metfar@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#
#import warnings;
#warnings.filterwarnings("ignore", category=UserWarning);

import os;
from pathlib import Path;
import subprocess;
import sys;


def test_symbolic_link_invocation(tmp_path):
    launcher = tmp_path / "sumdoc";
    launcher.write_text(
        "#!/usr/bin/env python3\n"
        "from sumdoc.cli import entry_point;\n"
        "raise SystemExit(entry_point());\n",
        encoding="utf-8",
    );
    launcher.chmod(0o755);
    alias = tmp_path / "html2md";
    alias.symlink_to("sumdoc");
    html = tmp_path / "page.html";
    html.write_text("<h1>Multicall</h1>", encoding="utf-8");
    environment = os.environ.copy();
    source_path = str(Path(__file__).parents[1] / "src");
    environment["PYTHONPATH"] = source_path + os.pathsep + environment.get("PYTHONPATH", "");
    completed = subprocess.run(
        [str(alias), str(html)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    );
    assert completed.returncode == 0;
    assert "Multicall" in completed.stdout;
