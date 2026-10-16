"""Optional Tk desktop for the offline, user-scoped installer."""
from __future__ import annotations

from pathlib import Path
import threading
from queue import Empty, Queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from installer import default_target, install, rollback, status as install_status, uninstall, verify


def main() -> None:
    root = tk.Tk()
    root.title("GitHub Engineering Agent · Installation Manager")
    root.geometry("900x500")
    root.minsize(760, 440)
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

    actions = ttk.Frame(frame)
    actions.pack(fill="x", pady=14)
    buttons = []
    results: Queue[tuple[str, str]] = Queue()

    def poll_results():
        try:
            kind, message = results.get_nowait()
        except Empty:
            pass
        else:
            status.set(message)
            set_busy(False)
        root.after(100, poll_results)


    def set_busy(busy):
        for button in buttons:
            button.configure(state="disabled" if busy else "normal")

    def execute(action):
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
                elif action == "rollback":
                    result = rollback(snapshot[0])
                else:
                    result = uninstall(snapshot[0], confirm)
                results.put(("ok", result))
            except Exception as exc:
                msg = f"{type(exc).__name__}: {exc}"
                results.put(("error", msg))

        threading.Thread(target=worker, daemon=True).start()

    for title, action in (("Install", "install"), ("Update", "update"),
                          ("Repair", "repair"), ("Status", "status"),
                          ("Rollback", "rollback"), ("Verify", "verify"),
                          ("Uninstall", "uninstall")):
        button = ttk.Button(actions, text=title, command=lambda action=action: execute(action))
        button.pack(side="left", padx=(0, 8))
        buttons.append(button)

    ttk.Separator(frame).pack(fill="x", pady=(16, 12))
    ttk.Label(frame, text="Status", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
    ttk.Label(frame, textvariable=status, wraplength=820).pack(anchor="w", fill="x", pady=(6, 0))
    ttk.Label(frame, text="No GitHub/OpenAI tokens are requested or stored. Application configuration is not modified.").pack(anchor="w", pady=(20, 0))
    root.after(100, poll_results)
    root.mainloop()


if __name__ == "__main__":
    main()
