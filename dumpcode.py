#!/usr/bin/env python3
"""
Codebase File Selector & Code Dumper (clipboard edition)
Usage: python script.py [directory]
"""

import os
import sys
import argparse
from pathlib import Path

# ---------- Config ----------
SKIP_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", "node_modules",
    ".venv", "venv", "env", ".idea", ".vscode", "dist", "build",
    ".next", ".nuxt", "target", "bin", "obj",
}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h",
    ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt",
    ".html", ".css", ".scss", ".sql", ".sh", ".bash", ".zsh",
    ".json", ".yaml", ".yml", ".toml", ".md", ".txt", ".xml",
}

MAX_FILE_SIZE = 1_000_000  # 1 MB


# ---------- Clipboard ----------
def copy_to_clipboard(text: str) -> bool:
    """Try several backends. Returns True on success."""
    # 1) pyperclip (if installed)
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass

    # 2) tkinter (built-in on most Python installs)
    try:
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()  # keep clipboard after window closes
        r.destroy()
        return True
    except Exception:
        pass

    # 3) OS-specific fallbacks
    import subprocess, shutil
    try:
        if sys.platform == "darwin" and shutil.which("pbcopy"):
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
            return True
        if sys.platform.startswith("linux"):
            for cmd in (["xclip", "-selection", "clipboard"],
                        ["xsel", "--clipboard", "--input"],
                        ["wl-copy"]):
                if shutil.which(cmd[0]):
                    subprocess.run(cmd, input=text.encode("utf-8"), check=True)
                    return True
        if sys.platform.startswith("win"):
            subprocess.run(["clip"], input=text.encode("utf-16le"), check=True)
            return True
    except Exception:
        pass

    return False


# ---------- File discovery ----------
def find_files(root: Path):
    found = []
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            try:
                if fpath.stat().st_size > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            if CODE_EXTENSIONS and fpath.suffix.lower() not in CODE_EXTENSIONS:
                continue
            try:
                rel = fpath.relative_to(root)
            except ValueError:
                rel = fpath
            found.append(rel)
    return sorted(found)


# ---------- Selection parsing ----------
def parse_selection(choice: str, total: int):
    selected = set()
    parts = [p.strip() for p in choice.split(",") if p.strip()]
    for part in parts:
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            if a > b:
                a, b = b, a
            for i in range(a, b + 1):
                if 1 <= i <= total:
                    selected.add(i - 1)
        else:
            i = int(part)
            if 1 <= i <= total:
                selected.add(i - 1)
    return sorted(selected)


# ---------- Output builder ----------
def build_output(root: Path, files: list) -> str:
    root = root.resolve()
    chunks = []
    for rel in files:
        fpath = root / rel
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            content = f"<could not read file: {e}>"
        chunks.append(f"{rel}:\n{'-' * 60}\n{content}\n{'=' * 60}\n")
    return "\n".join(chunks)


# ---------- Interactive selection ----------
def interactive_select(files: list):
    print(f"\nFound {len(files)} files:\n")
    for i, f in enumerate(files, 1):
        print(f"  {i:>3}. {f}")

    print(
        "\nEnter numbers to select files.\n"
        "  Examples: '1,3,5'  |  '2-8'  |  '1,4-6,10'\n"
        "  'all' = every file, 'q' = quit"
    )

    while True:
        choice = input("\n> ").strip().lower()
        if choice in ("q", "quit", "exit"):
            return []
        if choice == "all":
            return files
        try:
            indices = parse_selection(choice, len(files))
        except ValueError:
            print("Invalid input. Try again.")
            continue
        if not indices:
            print("No valid files selected. Try again.")
            continue
        return [files[i] for i in indices]


# ---------- Main ----------
def main():
    parser = argparse.ArgumentParser(description="Select codebase files and copy them to clipboard.")
    parser.add_argument("directory", nargs="?", default=".",
                        help="Directory to scan (default: current)")
    parser.add_argument("-o", "--output",
                        help="Also write output to this file")
    parser.add_argument("--print", dest="do_print", action="store_true",
                        help="Also print to stdout")
    args = parser.parse_args()

    root = Path(args.directory)
    if not root.exists() or not root.is_dir():
        print(f"Error: '{root}' is not a valid directory.")
        sys.exit(1)

    files = find_files(root)
    if not files:
        print("No matching files found.")
        sys.exit(0)

    selected = interactive_select(files)
    if not selected:
        print("Nothing selected. Exiting.")
        sys.exit(0)

    text = build_output(root, selected)

    if args.do_print:
        print("\n" + text)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"\nAlso wrote to {args.output}")

    if copy_to_clipboard(text):
        size_kb = len(text.encode("utf-8")) / 1024
        print(f"\n✅ Copied {len(selected)} file(s) to clipboard ({size_kb:.1f} KB). Just paste!")
    else:
        # Fallback: save to file and tell user
        fallback = "clipboard_dump.txt"
        Path(fallback).write_text(text, encoding="utf-8")
        print(
            "\n⚠️  Could not access the clipboard on this system.\n"
            f"   Saved to '{fallback}' instead.\n"
            "   To enable clipboard support, install one of:\n"
            "     pip install pyperclip\n"
            "     (Linux) sudo apt install xclip   # or xsel / wl-clipboard"
        )


if __name__ == "__main__":
    main()