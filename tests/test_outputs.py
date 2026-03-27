import pytest
import abvio.outputs as outputs

from pathlib import Path

FILES_DIR = Path(__file__).parent / "files"


def test_parse_vasprun_returns_expected_keys():
    result = outputs.parse_vasprun(str(FILES_DIR / "vasprun.xml"))
    assert isinstance(result, dict)
    assert "structure" in result
    assert "energy"    in result
    assert "kpoints"   in result
    assert "incar"     in result
