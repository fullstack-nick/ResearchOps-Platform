from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / "grafana" / "dashboards"


def main() -> None:
    parser = argparse.ArgumentParser(description="Import ResearchOps dashboards into Azure Managed Grafana.")
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--grafana-name", required=True)
    parser.add_argument("--workspace-resource-id", required=True)
    args = parser.parse_args()

    dashboard_files = sorted(DASHBOARD_DIR.glob("*.json"))
    if not dashboard_files:
        raise SystemExit(f"No dashboard JSON files found in {DASHBOARD_DIR}")

    with tempfile.TemporaryDirectory(prefix="researchops-grafana-") as tmp:
        tmpdir = Path(tmp)
        for dashboard_file in dashboard_files:
            rendered = _render_dashboard(dashboard_file, args.workspace_resource_id)
            rendered_path = tmpdir / dashboard_file.name
            rendered_path.write_text(json.dumps(rendered, indent=2), encoding="utf-8")
            _run(
                [
                    _az_cli(),
                    "grafana",
                    "dashboard",
                    "import",
                    "--resource-group",
                    args.resource_group,
                    "--name",
                    args.grafana_name,
                    "--definition",
                    str(rendered_path),
                    "--overwrite",
                    "true",
                ]
            )
            print(f"Imported {dashboard_file.name}")


def _render_dashboard(dashboard_file: Path, workspace_resource_id: str) -> dict[str, object]:
    text = dashboard_file.read_text(encoding="utf-8").replace(
        "__WORKSPACE_RESOURCE_ID__",
        workspace_resource_id,
    )
    return json.loads(text)


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _az_cli() -> str:
    executable = shutil.which("az") or shutil.which("az.cmd")
    if executable is None:
        raise RuntimeError("Azure CLI executable was not found on PATH.")
    return executable


if __name__ == "__main__":
    main()
