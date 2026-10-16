"""Optional local desktop GUI. No network server or mutation actions."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import json
import sys

READ_ONLY = frozenset({"workspace", "files", "dashboard", "prepare", "commands", "recipes", "guide"})

# Arguments are data, never commands. No permission/remote switches are exposed.
OPTIONS = {
    "workspace": frozenset({"--checkout", "--repo"}),
    "files": frozenset({"--checkout", "--repo", "--search", "--limit"}),
    "dashboard": frozenset({"--checkout", "--proposal"}),
    "prepare": frozenset({"--checkout", "--repo", "--issue", "--model", "--output", "--allowed-file"}),
    "commands": frozenset({"--group", "--search"}),
    "recipes": frozenset({"--topic"}),
    "guide": frozenset(),
}


def validate_arguments(action: str, args: list[str] | tuple[str, ...]) -> None:
    """Fail closed before invoking the CLI, including for unexpected options."""
    if action not in READ_ONLY or type(args) not in (list, tuple) or any(type(x) is not str for x in args):
        raise ValueError("Only known read-only actions and string arguments are allowed")
    if any(x in {"--allow-source-upload", "--approve", "--approve-local",
                 "--approve-publish", "--remote"} for x in args):
        raise ValueError("GUI cannot grant write, upload or remote permissions")
    allowed = OPTIONS[action]
    if len(args) % 2:
        raise ValueError("GUI arguments must be option/value pairs")
    for i in range(0, len(args), 2):
        option, value = args[i:i + 2]
        if option not in allowed or not value or value.startswith("--") or any(ord(c) < 32 for c in value):
            raise ValueError("Unexpected or invalid GUI option/value")



def inspect(action: str, args: list[str] | tuple[str, ...] = ()) -> dict:
    """Run an explicit local-only CLI command and return its result."""
    validate_arguments(action, args)
    from .cli import main as cli_main
    output, errors = StringIO(), StringIO()
    argv = [action, *args]
    if action != "guide" and "--json" not in args:
        argv.append("--json")
    with redirect_stdout(output), redirect_stderr(errors):
        rc = cli_main(argv)
    if rc:
        return {"ok": False, "error": errors.getvalue().strip() or "Local validation failed"}
    result = output.getvalue()
    try:
        data = json.loads(result)
    except ValueError:
        data = {"text": result.strip()}
    return {"ok": True, "data": data}


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="gh-engineer gui")
    parser.add_argument("--checkout", default=".")
    parser.add_argument("--proposal", default="")
    options = parser.parse_args(argv)
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        print("Tkinter unavailable. Install your OS Tk package, or use 'gh-engineer menu'.", file=sys.stderr)
        return 2
    try:
        root = tk.Tk()
    except tk.TclError:
        print("No graphical display. Use 'gh-engineer menu' in a terminal.", file=sys.stderr)
        return 2
    root.title("GitHub Engineering Agent · Desktop")
    root.geometry("1060x760")
    root.minsize(720, 500)
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    style.configure("Heading.TLabel", font=("TkDefaultFont", 17, "bold"))
    style.configure("Section.TLabel", font=("TkDefaultFont", 11, "bold"))
    style.configure("TButton", padding=(10, 7))
    checkout = tk.StringVar(value=str(Path(options.checkout).resolve()))
    proposal = tk.StringVar(value=options.proposal)
    repo = tk.StringVar()
    issue = tk.StringVar()
    model = tk.StringVar()
    destination = tk.StringVar()
    filter_text = tk.StringVar()
    selected_paths: list[str] = []
    selected_checkout = ""

    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="GitHub Engineering Agent", style="Heading.TLabel").pack(anchor="w")
    ttk.Label(frame, text="Local dashboard · Read-only · No upload, commit or publish").pack(anchor="w", pady=(2, 10))
    for label, variable, kind in (("Checkout", checkout, "directory"), ("Proposal", proposal, "file")):
        line = ttk.Frame(frame)
        line.pack(fill="x", pady=3)
        ttk.Label(line, text=label, width=12).pack(side="left")
        ttk.Entry(line, textvariable=variable).pack(side="left", fill="x", expand=True, padx=6)
        def browse(variable=variable, kind=kind):
            value = (filedialog.askdirectory() if kind == "directory"
                     else filedialog.askopenfilename(filetypes=[("JSON", "*.json")]))
            if value:
                variable.set(value)
        ttk.Button(line, text="Browse", command=browse).pack(side="left")
    tabs = ttk.Notebook(frame)
    tabs.pack(fill="both", expand=True, pady=(8, 12))
    root.bind("<Control-Key-1>", lambda _event: tabs.select(0))
    root.bind("<Control-Key-2>", lambda _event: tabs.select(1))
    root.bind("<Control-Key-3>", lambda _event: tabs.select(2))
    root.bind("<Control-Key-4>", lambda _event: tabs.select(3))
    panels = {}
    for label in ("Overview", "Files", "Plan preview", "Help"):
        page = ttk.Frame(tabs, padding=15)
        tabs.add(page, text=label)
        panels[label] = page
    ttk.Label(frame, text="LOCAL RESULT  ·  Select text or copy the complete result", style="Section.TLabel").pack(anchor="w")
    result_frame = ttk.Frame(frame)
    result_frame.pack(fill="both", expand=True, pady=(4, 0))
    output = tk.Text(result_frame, height=10, state="disabled", wrap="word", font=("TkFixedFont", 10))
    output.pack(side="left", fill="both", expand=True)
    output_scroll = ttk.Scrollbar(result_frame, orient="vertical", command=output.yview)
    output_scroll.pack(side="right", fill="y")
    output.configure(yscrollcommand=output_scroll.set)
    output.configure(takefocus=True)
    status = tk.StringVar(value="Ready · local inspection only")
    footer = ttk.Frame(frame)
    footer.pack(fill="x", pady=(6, 0))
    ttk.Label(footer, textvariable=status).pack(side="left", fill="x", expand=True)
    def copy_result():
        value = output.get("1.0", "end-1c")
        if value:
            root.clipboard_clear()
            root.clipboard_append(value)
            status.set("Result copied to clipboard")
    ttk.Button(footer, text="Copy result", command=copy_result).pack(side="right")
    root.bind("<Control-Shift-C>", lambda _event: copy_result())
    def show(message):
        output.configure(state="normal")
        output.delete("1.0", "end")
        output.insert("1.0", message if isinstance(message, str) else json.dumps(message, indent=2))
        output.configure(state="disabled")
    def call(action, args=()):
        status.set(f"Checking {action} locally…")
        root.update_idletasks()
        try:
            result = inspect(action, list(args))
        except (ValueError, OSError) as exc:
            result = {"ok": False, "error": str(exc)}
        show(result.get("data", result.get("error")))
        status.set(f"{action}: {'complete' if result['ok'] else 'validation failed'} · local only")
        return result

    home = panels["Overview"]
    ttk.Label(home, text="Workspace and proposal status", style="Heading.TLabel").pack(anchor="w", pady=8)
    ttk.Button(home, text="Check local workspace", command=lambda: call("workspace", ["--checkout", checkout.get()])).pack(anchor="w", pady=6)
    ttk.Label(home, text="Select a tab, then run an explicit local check. No checks run automatically.").pack(anchor="w", pady=4)
    ttk.Button(home, text="Inspect proposal progress", command=lambda: call("dashboard", ["--checkout", checkout.get(), "--proposal", proposal.get()])).pack(anchor="w", pady=6)
    ttk.Label(home, text="Local PASS does not confirm a remote PR or target CI.").pack(anchor="w", pady=10)

    files_page = panels["Files"]
    ttk.Label(files_page, text="Eligible tracked files", style="Heading.TLabel").pack(anchor="w")
    top = ttk.Frame(files_page)
    top.pack(fill="x", pady=8)
    ttk.Entry(top, textvariable=filter_text).pack(side="left", fill="x", expand=True)
    list_frame = ttk.Frame(files_page)
    list_frame.pack(fill="both", expand=True)
    items = tk.Listbox(list_frame, selectmode="extended", height=12, exportselection=False)
    items.pack(side="left", fill="both", expand=True)
    file_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=items.yview)
    file_scroll.pack(side="right", fill="y")
    items.configure(yscrollcommand=file_scroll.set)
    counter = ttk.Label(files_page, text="Search local paths to begin")
    counter.pack(anchor="w", pady=5)
    def refresh():
        nonlocal selected_checkout
        selected_paths.clear()
        selected_checkout = ""
        items.delete(0, "end")
        counter.configure(text="Searching…")
        result = call("files", ["--checkout", checkout.get(), "--search", filter_text.get(), "--limit", "50"])
        if result["ok"]:
            data = result["data"]
            for name in data["files"]:
                items.insert("end", name)
            counter.configure(text=f"{data['shown']} shown / {data['matching_count']} matching" +
                              (" · refine search for more" if data["truncated"] else ""))
        else:
            counter.configure(text="Search failed · no files selected")
    ttk.Button(top, text="Search", command=refresh).pack(side="left", padx=7)
    filter_text_entry = top.winfo_children()[0]
    filter_text_entry.bind("<Return>", lambda _event: refresh())
    def select():
        paths = [items.get(i) for i in items.curselection()]
        if not 1 <= len(paths) <= 12:
            messagebox.showwarning("Selection", "Select between 1 and 12 paths.")
            return
        nonlocal selected_checkout
        selected_paths[:] = paths
        selected_checkout = str(Path(checkout.get()).resolve(strict=False))
        status.set(f"{len(paths)} file paths selected · no upload")
        show({"selected_paths": paths, "uploaded": False})
        tabs.select(panels["Plan preview"])
    ttk.Button(files_page, text="Use selected files in plan preview", command=select).pack(anchor="w", pady=6)
    items.bind("<Double-Button-1>", lambda _event: select())

    preview = panels["Plan preview"]
    ttk.Label(preview, text="Preview a plan · Never execute", style="Heading.TLabel").pack(anchor="w", pady=5)
    for label, value in (("Repository OWNER/REPO", repo), ("Issue number", issue),
                         ("Model", model), ("New output JSON path", destination)):
        line = ttk.Frame(preview)
        line.pack(fill="x", pady=4)
        ttk.Label(line, text=label, width=24).pack(side="left")
        ttk.Entry(line, textvariable=value).pack(side="left", fill="x", expand=True)
    def prepare_preview():
        if not selected_paths or selected_checkout != str(Path(checkout.get()).resolve(strict=False)):
            selected_paths.clear()
            show("File selection is missing or checkout changed. Search and select eligible files again.")
            status.set("Selection requires refresh")
            return
        number = issue.get().strip()
        if not number.isdecimal() or not 1 <= len(number) <= 12 or int(number) < 1:
            show("Enter a valid positive issue number (up to 12 digits).")
            return
        args = ["--checkout", checkout.get(), "--repo", repo.get(),
                "--issue", number, "--model", model.get(), "--output", destination.get()]
        for name in selected_paths:
            args.extend(["--allowed-file", name])
        call("prepare", args)
    ttk.Button(preview, text="Validate and preview only", command=prepare_preview).pack(anchor="w", pady=10)
    ttk.Label(preview, text="The output omits upload approval; use the reviewed CLI workflow separately.").pack(anchor="w")

    help_panel = panels["Help"]
    ttk.Label(help_panel, text="Plan → Review → Apply → Verify → Publish", style="Heading.TLabel").pack(anchor="w", pady=8)
    for label, command in (("Show safe workflow", "guide"), ("Browse commands", "commands"),
                           ("Task examples", "recipes")):
        ttk.Button(help_panel, text=label, command=lambda c=command: call(c)).pack(anchor="w", pady=6)
    root.bind("<Escape>", lambda _event: root.focus_set())
    ttk.Label(frame, text="Shortcuts: Ctrl+1–4 switch tabs · Ctrl+Shift+C copies result · Enter searches files").pack(anchor="w", pady=(4, 0))
    show("Welcome. Choose an overview, search eligible files or preview a scoped plan.\nNo action has been started.")
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
