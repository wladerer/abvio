import abvio.outputs as outputs

import unittest
import os
from pathlib import Path

from pymatgen.io.vasp import Kpoints, Vasprun
from pymatgen.core import Structure


base_path = Path(__file__).parent
files_dir = os.path.join(base_path, "files")

test_vasprun_file = os.path.join(files_dir, "vasprun.xml")


class TestOutputs(unittest.TestCase):
    def test_parse_vasprun(self):
        output = outputs.parse_vasprun(test_vasprun_file)

        self.assertIsInstance(output, dict)
        self.assertIn("structure", output)
        self.assertIn("energy", output)
        self.assertIn("kpoints", output)
        self.assertIn("incar", output)


if __name__ == "__main__":
    unittest.main()
