"""Optional Tk desktop for the offline, user-scoped installer."""
from __future__ import annotations

from pathlib import Path
import threading
from queue import Empty, Queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from setup_check import snapshot as setup_snapshot
from installer import default_target, install, rollback, status as install_status, uninstall, verify


def main() -> None:
    root = tk.Tk()
    root.title("GitHub Engineering Agent · Installation Manager")
    root.geometry("900x640")
    root.minsize(720, 530)
    target = tk.StringVar(value=str(default_target()))
    wheel = tk.StringVar()
    digest = tk.StringVar()
    status = tk.StringVar(value="Select a trusted local wheel and verify its published SHA-256.")
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Installation Manager", font=("TkDefaultFont", 18, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Local-only · Current user · No automatic downloads or elevation").pack(anchor="w", pady=(4, 18))

    def field(label, variable, browse=None):
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=6)
        ttk.Label(row, text=label, width=15).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        if browse:
            ttk.Button(row, text="Browse", command=browse).pack(side="left", padx=(8, 0))

    field("Install location", target, lambda: target.set(filedialog.askdirectory() or target.get()))
    field("Release wheel", wheel, lambda: wheel.set(
        filedialog.askopenfilename(filetypes=[("Python wheel", "*.whl")]) or wheel.get()))
    field("Expected SHA-256", digest)
    ttk.Label(frame, text="Use a trusted wheel and independently obtained checksum. Verified updates keep the prior release for rollback.").pack(anchor="w", pady=(12, 4))

    ttk.Label(frame, text="MAINTENANCE ACTIONS", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(10, 4))
    actions = ttk.Frame(frame)
    actions.pack(fill="x", pady=(0, 8))
    for column in range(4):
        actions.columnconfigure(column, weight=1)
    buttons = []
    results: Queue[tuple[str, str]] = Queue()
    busy = False
    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.pack(fill="x", pady=(6, 4))

    def poll_results():
        try:
            kind, message = results.get_nowait()
        except Empty:
            pass
        else:
            status.set("Completed" if kind == "ok" else "Failed · review the details below")
            show(message)
            set_busy(False)
        root.after(100, poll_results)


    def set_busy(value):
        nonlocal busy
        busy = value
        for button in buttons:
            button.configure(state="disabled" if value else "normal")
        if value:
            progress.start(12)
        else:
            progress.stop()

    def execute(action):
        if busy:
            return
        if action in ("install", "update", "repair") and (not wheel.get().strip() or len(digest.get().strip()) != 64):
            messagebox.showwarning("Missing release input", "Select a trusted wheel and provide its 64-character SHA-256 checksum.")
            return
        if action == "rollback" and not messagebox.askyesno("Rollback", "Restore the previously verified release?"):
            return
        if action == "uninstall":
            if not messagebox.askyesno("Remove installation", "Remove the managed application environment? Unknown files block removal."):
                return
            confirm = "UNINSTALL"
        else:
            confirm = ""
        snapshot = (Path(target.get()), Path(wheel.get()), digest.get().strip())
        set_busy(True)
        status.set(f"{action.capitalize()} running locally…")

        def worker():
            try:
                if action in ("install", "update", "repair"):
                    result = install(*snapshot)
                elif action == "verify":
                    result = verify(snapshot[0])
                elif action == "status":
                    result = install_status(snapshot[0])
                elif action == "setup":
                    import json
                    result = json.dumps(setup_snapshot(), indent=2, sort_keys=True)
                elif action == "rollback":
                    result = rollback(snapshot[0])
                else:
                    result = uninstall(snapshot[0], confirm)
                results.put(("ok", result))
            except Exception as exc:
                msg = f"{type(exc).__name__}: {exc}"
                results.put(("error", msg))

        threading.Thread(target=worker, daemon=True).start()

    for index, (title, action) in enumerate((("1 · Environment", "setup"), ("2 · Install", "install"),
                          ("3 · Update", "update"), ("4 · Repair", "repair"),
                          ("5 · Status", "status"), ("6 · Verify", "verify"),
                          ("7 · Rollback", "rollback"), ("8 · Uninstall", "uninstall"))):
        button = ttk.Button(actions, text=title, command=lambda action=action: execute(action))
        button.grid(row=index // 4, column=index % 4, sticky="ew", padx=(0, 7), pady=4)
        buttons.append(button)

    ttk.Separator(frame).pack(fill="x", pady=(10, 8))
    ttk.Label(frame, text="STATUS & DETAILS", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
    ttk.Label(frame, textvariable=status, wraplength=820).pack(anchor="w", fill="x", pady=(4, 6))
    results_frame = ttk.Frame(frame)
    results_frame.pack(fill="both", expand=True)
    details = tk.Text(results_frame, height=8, wrap="word", state="disabled", font=("TkFixedFont", 10))
    details.pack(side="left", fill="both", expand=True)
    scroll = ttk.Scrollbar(results_frame, orient="vertical", command=details.yview)
    scroll.pack(side="right", fill="y")
    details.configure(yscrollcommand=scroll.set)

    def show(message):
        details.configure(state="normal")
        details.delete("1.0", "end")
        details.insert("1.0", message)
        details.configure(state="disabled")

    footer = ttk.Frame(frame)
    footer.pack(fill="x", pady=(6, 0))
    ttk.Label(footer, text="Local-only · No secrets stored · No automatic downloads").pack(side="left")
    def copy_details():
        value = details.get("1.0", "end-1c")
        if value:
            root.clipboard_clear()
            root.clipboard_append(value)
    ttk.Button(footer, text="Copy details", command=copy_details).pack(side="right")
    root.bind("<Control-Shift-C>", lambda _event: copy_details())

    def close():
        if busy:
            messagebox.showwarning("Operation running", "Finish the current operation before closing the manager.")
            return
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", close)
    show("Choose Environment to inspect local prerequisites or select a wheel to install.")
    root.after(100, poll_results)
    root.mainloop()


if __name__ == "__main__":
    main()
