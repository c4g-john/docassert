"""Dump every subcommand and flag from the live parser as the STABILITY.md
CLI reference section. CI regenerates and diffs, so the promise can't drift."""
import argparse
import contextlib

from docassert import cli

parser = None
_orig = argparse.ArgumentParser.parse_args


def _spy(self, *a, **k):
    global parser
    if parser is None and self.prog == "docassert":
        parser = self
    raise SystemExit(0)


argparse.ArgumentParser.parse_args = _spy
with contextlib.suppress(SystemExit):
    cli.main(["--help"])
argparse.ArgumentParser.parse_args = _orig

subs = next(a for a in parser._actions
            if isinstance(a, argparse._SubParsersAction))
for name, sp in sorted(subs.choices.items()):
    print(f"### `docassert {name}`\n")
    print(sp.description or sp.format_usage().strip())
    print()
    rows = []
    for act in sp._actions:
        if act.dest == "help":
            continue
        flags = ", ".join(f"`{o}`" for o in act.option_strings) or f"`{act.dest}`"
        rows.append(f"| {flags} | {(act.help or '').replace('|', '/')} |")
    if rows:
        print("| Flag / argument | Meaning |")
        print("|---|---|")
        print("\n".join(rows))
    print()
