from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

SUPPORTED_ENGINES: tuple[str, ...] = (
    "unity",
    "unreal",
    "godot",
    "blender",
    "maya",
    "houdini",
    "substance",
    "photoshop",
)


def _load_template(engine: str) -> str | None:
    """Optionally load an external README template for an engine.

    Looks for templates under `kagami/core/engines/templates/{engine}.md` or a
    user-provided override via env `KAGAMI_ENGINE_TEMPLATES` pointing to a directory.
    Returns None if not found.
    """
    here = Path(__file__).parent
    local_dir = here / "templates"
    candidates: list[Path] = []
    try:
        candidates.append(local_dir / f"{engine.lower()}.md")
    except Exception:
        pass
    try:
        import os as _os

        override_root = _os.environ.get("KAGAMI_ENGINE_TEMPLATES")
        if override_root:
            candidates.insert(0, Path(override_root) / f"{engine.lower()}.md")
    except Exception:
        pass
    for p in candidates:
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8")
        except Exception:
            continue
    return None


def _engine_readme(engine: str) -> str:
    e = engine.lower()
    try:
        tpl = _load_template(e)
        if tpl:
            return tpl
    except Exception:
        pass
    if e == "unity":
        return "# Unity Import Guide\n\n- Install com.unity.formats.usd (Unity USD) via Package Manager.\n- Ensure Project units: meters; Y-up (default).\n- Unzip this package; drag the `.usd` into the Project.\n- Recommended hierarchy: `/World/Environment`, `/World/Characters`, `/World/Props`.\n- Retarget materials to Unity shaders (HDRP/URP) as needed.\n- Rigging hints: check USD layer customLayerData key `kagami:rigging` or the packaged `rigging.json`.\n"
    if e == "unreal":
        return "# Unreal Import Guide\n\n- Enable USD Importer plugin in Project Settings.\n- Unzip this package; in Content Browser use 'Import' and select the `.usd`.\n- Project/world units: meters; Y-up normalized in export.\n- Map materials to your material graph post-import if required.\n- Rigging hints: read USD layer customLayerData `kagami:rigging` or parse the packaged `rigging.json`.\n"
    if e == "godot":
        return "# Godot Import Guide\n\n- Godot has best support for glTF; this package includes USD.\n- Convert USD→glTF using Blender USD importer if needed, or use a USD plugin.\n- Keep PBR textures (albedo/normal/roughness) alongside geometry.\n"
    if e == "blender":
        return "# Blender Import Guide\n\n- Enable the USD Import add-on.\n- File → Import → Universal Scene Description (.usd/.usda).\n- Axis: Y-up; Scale: meters.\n- You may export to FBX/GLTF for engines after material edits.\n- Rigging hints: USD customLayerData `kagami:rigging` or `rigging.json` in this package.\n"
    if e == "maya":
        return "# Maya Import Guide\n\n- Ensure USD plugin (maya-usd) is enabled.\n- Create → USD → Stage From File, select the `.usd`.\n- Units: meters. Axis: Y-up.\n- Use MaterialX or assign compatible shaders post-import.\n- Rigging hints: USD customLayerData `kagami:rigging` or `rigging.json`.\n"
    if e == "houdini":
        return "# Houdini Import Guide\n\n- Use LOPs/USD Stage to load the `.usd`.\n- Axis/units normalized; instantiate under `/World`.\n- You can author variants/LODs as variantSets.\n- Rigging hints: USD customLayerData `kagami:rigging` or `rigging.json`.\n"
    if e == "substance":
        return "# Substance 3D Painter Guide\n\n- Painter prefers meshes like GLB/FBX; use Blender to convert USD if needed.\n- Keep texture packing conventions (ORM or separate R/G/B channels).\n"
    if e == "photoshop":
        return "# Photoshop 3D/Texture Guide\n\n- For texture edits, work directly on packaged textures in `assets/`.\n- Re-export with the same filenames to preserve material hookups.\n"
    return f"# {engine.title()} Import Guide\n\n- Import the `.usd` along with packaged assets.\n- Units: meters. Axis: Y-up.\n- Rigging hints: USD customLayerData `kagami:rigging` or `rigging.json`.\n"


def generate_engine_artifacts(engine_targets: Iterable[str]) -> dict[str, bytes]:
    """Generate per-engine documentation and manifest hints as files.

    Returns a mapping of relative archive paths → file bytes to be added
    into the export ZIP. Safe to call even if `engine_targets` is empty.
    """
    artifacts: dict[str, bytes] = {}
    normalized = []
    for e in engine_targets or []:
        try:
            key = str(e).strip().lower()
            if not key:
                continue
            if key not in SUPPORTED_ENGINES:
                continue
            normalized.append(key)
        except Exception:
            continue
    if normalized:
        summary_lines = [
            "# Engine Integration\n",
            "This package includes guidance for the following targets:\n\n",
        ]
        for e in normalized:
            summary_lines.append(f"- {e.title()}\n")
        artifacts["ENGINES/README.md"] = "".join(summary_lines).encode("utf-8")
    for e in normalized:
        readme = _engine_readme(e).encode("utf-8")
        artifacts[f"ENGINES/{e}/README.md"] = readme
        manifest_json = f'{{\n  "engine": "{e}",\n  "import": {{ "format": "usd" }},\n  "rigging": {{ "usd_customLayerData": "kagami:rigging", "file": "rigging.json" }},\n  "notes": "Units in meters; Y-up; textures packaged; rigging hints included."\n}}\n'.encode()
        artifacts[f"ENGINES/{e}/manifest.json"] = manifest_json
    return artifacts
