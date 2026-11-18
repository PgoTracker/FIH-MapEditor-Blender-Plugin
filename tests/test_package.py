import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fih_package", ROOT / "blender_fih_exporter" / "package.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackageTests(unittest.TestCase):
    def test_blender_instance_names(self):
        self.assertEqual(package.asset_name("Spinner.001"), "Spinner")
        self.assertEqual(package.asset_name("Spinner.1000"), "Spinner")
        with self.assertRaises(package.ExportError):
            package.asset_name("My Spinner")

    def test_writes_reader_compatible_entry_names(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "test.fihmap.zip")
            object_data = {"Source": "package://Spinner", "SourceName": "Spinner", "Pos": [0, 0, 0], "Rot": [0, 0, 0], "Scale": [1, 1, 1]}
            package.write_package(path, "Test", [object_data], {"Spinner": {"obj": b"v 0 0 0\n", "cs": b"class Spinner {}", "png": None}})
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(set(archive.namelist()), {"map.fihmap.json", "geometry/Spinner.obj", "scripts/Spinner.cs"})
                self.assertEqual(json.loads(archive.read("map.fihmap.json"))["FormatVersion"], 15)

    def test_matching_impact_sound(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "impact.fihmap.zip")
            object_data = {"Source": "package://Suzanne", "SourceName": "Suzanne", "Pos": [0, 0, 0], "Rot": [0, 0, 0], "Scale": [1, 1, 1]}
            audio = b"RIFF----WAVEfmt "
            package.write_package(path, "Impact", [object_data], {
                "Suzanne": {"obj": b"v 0 0 0\n", "sound": audio, "sound_ext": ".wav"}
            })
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.read("sounds/Suzanne.wav"), audio)
            with self.assertRaises(package.ExportError):
                package.write_package(path, "Impact", [object_data], {
                    "Suzanne": {"obj": b"v 0 0 0\n", "sound": b"invalid audio", "sound_ext": ".wav"}
                })


if __name__ == "__main__":
    unittest.main()
