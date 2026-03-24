#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_CSS = ROOT / "devis.css"
DEFAULT_TEMPLATE = ROOT / "devis.template.html"


def find_executable(name: str) -> str | None:
    candidates = [
        shutil.which(name),
        str(Path(sys.executable).parent / name),
        str(ROOT / ".venv" / "bin" / name),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a devis Markdown file to PDF with pandoc."
    )
    parser.add_argument("input", help="Path to the input Markdown file")
    parser.add_argument(
        "-o",
        "--output",
        help="Output PDF path; defaults to the input filename with a .pdf extension",
    )
    parser.add_argument(
        "-c",
        "--css",
        default=str(DEFAULT_CSS),
        help=f"CSS file to apply when rendering with HTML-based engines (default: {DEFAULT_CSS.name})",
    )
    parser.add_argument(
        "--template",
        default=str(DEFAULT_TEMPLATE),
        help=f"Pandoc HTML template to use (default: {DEFAULT_TEMPLATE.name})",
    )
    parser.add_argument(
        "--pdf-engine",
        default="weasyprint",
        help="Pandoc PDF engine to use (default: weasyprint)",
    )
    parser.add_argument(
        "--pandoc",
        default=find_executable("pandoc"),
        help="Path to the pandoc executable",
    )
    return parser


def fail(message: str) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return 1


def build_resource_path(*paths: Path | None) -> str:
    ordered_paths: list[str] = []
    for path in paths:
        if path is None:
            continue
        resolved = str(path.expanduser().resolve())
        if resolved not in ordered_paths:
            ordered_paths.append(resolved)
    return os.pathsep.join(ordered_paths)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.is_file():
        return fail(f"input file not found: {input_path}")

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        output_path = input_path.with_suffix(".pdf")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not args.pandoc:
        return fail(
            "pandoc executable not found. The Python 'pandoc' package does not include the pandoc binary; install pandoc from https://pandoc.org/installing.html or pass --pandoc /path/to/pandoc."
        )

    css_path = Path(args.css).expanduser().resolve() if args.css else None
    if css_path and not css_path.is_file():
        return fail(f"CSS file not found: {css_path}")

    template_path = Path(args.template).expanduser().resolve() if args.template else None
    if template_path and not template_path.is_file():
        return fail(f"template file not found: {template_path}")

    if args.pdf_engine == "weasyprint" and find_executable("weasyprint") is None:
        return fail(
            "weasyprint executable not found. Install it or choose another engine with --pdf-engine."
        )

    engine_executable = find_executable(args.pdf_engine) if args.pdf_engine else None
    resource_path = build_resource_path(
        input_path.parent,
        css_path.parent if css_path else None,
        template_path.parent if template_path else None,
        ROOT,
    )

    command = [
        args.pandoc,
        str(input_path),
        "--standalone",
        "--section-divs",
        f"--resource-path={resource_path}",
        f"--pdf-engine={args.pdf_engine}",
        "-o",
        str(output_path),
    ]

    if css_path:
        command.extend(["-c", str(css_path)])

    if template_path:
        command.extend(["--template", str(template_path)])

    env = os.environ.copy()
    tool_dirs = []
    for path_str in [
        str(Path(sys.executable).parent),
        str(Path(args.pandoc).expanduser().parent),
        str(Path(engine_executable).expanduser().parent) if engine_executable else None,
    ]:
        if path_str and path_str not in tool_dirs:
            tool_dirs.append(path_str)
    existing_path = env.get("PATH", "")
    env["PATH"] = os.pathsep.join(tool_dirs + ([existing_path] if existing_path else []))

    try:
        subprocess.run(command, check=True, env=env)
    except subprocess.CalledProcessError as exc:
        print("Command failed:", file=sys.stderr)
        print(" ".join(command), file=sys.stderr)
        return exc.returncode or 1

    print(f"Created {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
