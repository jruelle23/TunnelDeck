import shutil
import sys
from pathlib import Path


def create_archive() -> None:
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} <source_dir> <output_zip_path>", file=sys.stderr)
        sys.exit(1)

    source = Path(sys.argv[1])
    output = Path(sys.argv[2])

    try:
        created = shutil.make_archive(
            base_name=str(output),
            format="zip",
            root_dir=str(source.parent),
            base_dir=source.name,
        )
        print(f"Successfully created archive: {created}")
    except Exception as e:
        print(f"Failed to create archive: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    create_archive()
