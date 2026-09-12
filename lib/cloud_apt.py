"""Isolate bootstrap APT sources from the unused LLVM image repository."""
from pathlib import Path
import re


def without_llvm(text, deb822=False):
    # Preserve all remaining source options and signature verification settings.
    if deb822:
        return "\n\n".join(block for block in re.split(r"\n\s*\n", text)
                            if not re.search(r"https?://apt[.]llvm[.]org(?:/|\s|$)", block)) + "\n"
    return "\n".join(line for line in text.splitlines()
                       if not re.search(r"https?://apt[.]llvm[.]org(?:/|\s|$)", line)) + "\n"


def prepare_apt_profile(state_root, source_root=Path("/etc/apt")):
    """Return an APT_CONFIG path only when the unused LLVM source exists."""
    files = [source_root / "sources.list"]
    parts = source_root / "sources.list.d"
    files += sorted(parts.glob("*.list")) + sorted(parts.glob("*.sources"))
    originals = {path: path.read_text() for path in files if path.is_file()}
    if not any(re.search(r"https?://apt[.]llvm[.]org(?:/|\s|$)", text) for text in originals.values()):
        return None
    profile = state_root.resolve() / "apt-profile"
    destination_parts = profile / "sources.list.d"
    destination_parts.mkdir(parents=True, exist_ok=True)
    # Only files owned by this generated source profile are refreshed.
    for path in destination_parts.iterdir():
        if path.is_file() and path.suffix in (".list", ".sources"):
            path.unlink()
    main = profile / "sources.list"
    main.write_text("")
    for source, text in originals.items():
        destination = main if source == source_root / "sources.list" else destination_parts / source.name
        destination.write_text(without_llvm(text, source.suffix == ".sources"))
    config = profile / "apt.conf"
    for path in (main, destination_parts):
        if any(character in str(path) for character in ('"', '\n', '\r', '\\')):
            raise ValueError("Unsupported character in cloud APT state path")
    config.write_text(f'Dir::Etc::sourcelist "{main}";\nDir::Etc::sourceparts "{destination_parts}";\n')
    return config
