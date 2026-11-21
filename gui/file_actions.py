"""File Actions Manager — reusable GUI for file movement operations.

A Tkinter GUI that lets any operator:
- Define file action jobs (copy, move, delete folder trees)
- Preview before executing (always dry-run first)
- Save/load job definitions as JSON
- View logs of completed actions

Jobs live in 10_FILE_ACTIONS/jobs/ as JSON files.
Anyone can add, edit, or remove jobs.

Usage:
    python file_actions.py
"""

import hashlib
import json
import os
import shutil
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

DAVIDOS_ROOT = Path(__file__).resolve().parent.parent
FILE_ACTIONS_DIR = DAVIDOS_ROOT / "10_FILE_ACTIONS"
JOBS_DIR = FILE_ACTIONS_DIR / "jobs"
LOG_DIR = FILE_ACTIONS_DIR / "logs"
JOBS_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)


def sha256_file(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return "UNREADABLE"


def load_jobs():
    jobs = []
    for f in sorted(JOBS_DIR.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                data["_file"] = str(f)
                jobs.append(data)
        except (json.JSONDecodeError, OSError):
            pass
    return jobs


def save_job(job):
    name = job.get("name", "untitled").replace(" ", "_").lower()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{ts}.json"
    path = JOBS_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2, default=str)
    return path


def log_execution(job_name, results):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LOG_DIR / f"{job_name}_{ts}.log"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# File Action Log: {job_name}\n")
        f.write(f"# Executed: {datetime.now().isoformat()}\n\n")
        for r in results:
            f.write(f"{r}\n")
    return path


def execute_action(action_type, source, dest, dry_run=True, verify=False):
    """Execute a single file action. Returns (success, message)."""
    source = Path(source)
    if dest:
        dest = Path(dest)

    if action_type == "copy":
        if not source.exists():
            return False, f"SOURCE NOT FOUND: {source}"
        if dry_run:
            if source.is_dir():
                count = sum(1 for _ in source.rglob("*") if _.is_file())
                return True, f"DRY RUN: Would copy {source} ({count} files) -> {dest}"
            return True, f"DRY RUN: Would copy {source} -> {dest}"
        if source.is_dir():
            shutil.copytree(source, dest, dirs_exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        msg = f"COPIED: {source} -> {dest}"
        if verify and dest.exists():
            if source.is_file():
                s_hash = sha256_file(source)
                d_hash = sha256_file(dest)
                if s_hash == d_hash:
                    msg += " [SHA256 VERIFIED]"
                else:
                    msg += " [SHA256 MISMATCH!]"
        return True, msg

    elif action_type == "delete":
        if not source.exists():
            return False, f"NOT FOUND (already gone?): {source}"
        if dry_run:
            if source.is_dir():
                count = sum(1 for _ in source.rglob("*") if _.is_file())
                size_mb = sum(f.stat().st_size for f in source.rglob("*") if f.is_file()) / 1048576
                return True, f"DRY RUN: Would delete {source} ({count} files, {size_mb:.1f} MB)"
            return True, f"DRY RUN: Would delete {source}"
        if source.is_dir():
            shutil.rmtree(source)
        else:
            source.unlink()
        return True, f"DELETED: {source}"

    elif action_type == "move":
        if not source.exists():
            return False, f"SOURCE NOT FOUND: {source}"
        if dry_run:
            return True, f"DRY RUN: Would move {source} -> {dest}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(dest))
        return True, f"MOVED: {source} -> {dest}"

    return False, f"UNKNOWN ACTION: {action_type}"


class FileActionsGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("File Actions Manager")
        self.root.geometry("950x700")
        self.root.configure(bg="#2b2b2b")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background="#2b2b2b", foreground="#e0e0e0",
                         fieldbackground="#3c3c3c")
        style.configure("TLabel", background="#2b2b2b", foreground="#e0e0e0")
        style.configure("TButton", background="#3c3c3c", foreground="#e0e0e0")
        style.configure("TFrame", background="#2b2b2b")
        style.configure("Treeview", background="#3c3c3c", foreground="#e0e0e0",
                         fieldbackground="#3c3c3c", rowheight=25)
        style.configure("Treeview.Heading", background="#444", foreground="#e0e0e0")
        style.map("Treeview", background=[("selected", "#505050")])

        top = ttk.Frame(root)
        top.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(top, text="File Actions Manager", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="New Job", command=self.new_job).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Load Jobs", command=self.refresh_jobs).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Dry Run Selected", command=self.dry_run).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Execute Selected", command=self.execute).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="View Logs", command=self.view_logs).pack(side=tk.LEFT, padx=3)

        tree_frame = ttk.Frame(root)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        cols = ("name", "action", "source", "dest", "status")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12)
        self.tree.heading("name", text="Job Name")
        self.tree.heading("action", text="Action")
        self.tree.heading("source", text="Source")
        self.tree.heading("dest", text="Destination")
        self.tree.heading("status", text="Status")
        self.tree.column("name", width=150)
        self.tree.column("action", width=60)
        self.tree.column("source", width=300)
        self.tree.column("dest", width=250)
        self.tree.column("status", width=100)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        log_label = ttk.Label(root, text="Output Log")
        log_label.pack(padx=10, anchor=tk.W)
        self.log = scrolledtext.ScrolledText(root, height=15, bg="#1e1e1e", fg="#00ff00",
                                              font=("Consolas", 10), insertbackground="#00ff00")
        self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.jobs = []
        self.refresh_jobs()

    def log_msg(self, msg):
        self.log.insert(tk.END, f"{msg}\n")
        self.log.see(tk.END)

    def refresh_jobs(self):
        self.tree.delete(*self.tree.get_children())
        self.jobs = load_jobs()
        for job in self.jobs:
            for step in job.get("steps", []):
                self.tree.insert("", tk.END, values=(
                    job.get("name", "?"),
                    step.get("action", "?"),
                    step.get("source", ""),
                    step.get("dest", ""),
                    "ready",
                ))
        self.log_msg(f"Loaded {len(self.jobs)} jobs from {JOBS_DIR}")

    def new_job(self):
        win = tk.Toplevel(self.root)
        win.title("New File Action Job")
        win.geometry("600x500")
        win.configure(bg="#2b2b2b")

        ttk.Label(win, text="Job Name:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        name_var = tk.StringVar()
        ttk.Entry(win, textvariable=name_var, width=40).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(win, text="Description:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        desc_var = tk.StringVar()
        ttk.Entry(win, textvariable=desc_var, width=40).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(win, text="Action:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        action_var = tk.StringVar(value="copy")
        ttk.Combobox(win, textvariable=action_var, values=["copy", "move", "delete"],
                      state="readonly", width=15).grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(win, text="Source:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        source_var = tk.StringVar()
        src_frame = ttk.Frame(win)
        src_frame.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(src_frame, textvariable=source_var, width=35).pack(side=tk.LEFT)
        ttk.Button(src_frame, text="...", width=3,
                    command=lambda: source_var.set(filedialog.askdirectory() or source_var.get())).pack(side=tk.LEFT, padx=2)

        ttk.Label(win, text="Destination:").grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
        dest_var = tk.StringVar()
        dst_frame = ttk.Frame(win)
        dst_frame.grid(row=4, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(dst_frame, textvariable=dest_var, width=35).pack(side=tk.LEFT)
        ttk.Button(dst_frame, text="...", width=3,
                    command=lambda: dest_var.set(filedialog.askdirectory() or dest_var.get())).pack(side=tk.LEFT, padx=2)

        ttk.Label(win, text="Verify SHA256:").grid(row=5, column=0, padx=5, pady=5, sticky=tk.W)
        verify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(win, variable=verify_var).grid(row=5, column=1, padx=5, pady=5, sticky=tk.W)

        steps_label = ttk.Label(win, text="Steps (add multiple sources):")
        steps_label.grid(row=6, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)

        steps_list = tk.Listbox(win, height=6, bg="#3c3c3c", fg="#e0e0e0", font=("Consolas", 9))
        steps_list.grid(row=7, column=0, columnspan=2, padx=5, pady=5, sticky=tk.EW)
        steps_data = []

        def add_step():
            step = {
                "action": action_var.get(),
                "source": source_var.get(),
                "dest": dest_var.get() if action_var.get() != "delete" else "",
                "verify": verify_var.get(),
            }
            steps_data.append(step)
            steps_list.insert(tk.END, f"{step['action'].upper()}: {step['source']} -> {step['dest']}")

        def save():
            job = {
                "name": name_var.get() or "untitled",
                "description": desc_var.get(),
                "created": datetime.now().isoformat(),
                "created_by": os.environ.get("USERNAME", "unknown"),
                "steps": steps_data if steps_data else [{
                    "action": action_var.get(),
                    "source": source_var.get(),
                    "dest": dest_var.get() if action_var.get() != "delete" else "",
                    "verify": verify_var.get(),
                }],
            }
            path = save_job(job)
            self.log_msg(f"Job saved: {path}")
            self.refresh_jobs()
            win.destroy()

        btn_row = ttk.Frame(win)
        btn_row.grid(row=8, column=0, columnspan=2, padx=5, pady=10)
        ttk.Button(btn_row, text="Add Step", command=add_step).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Save Job", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=5)

    def _get_selected_steps(self):
        selected = self.tree.selection()
        if not selected:
            selected = self.tree.get_children()
        return [self.tree.item(s, "values") for s in selected]

    def dry_run(self):
        self.log_msg("\n=== DRY RUN ===")
        for vals in self._get_selected_steps():
            name, action, source, dest, _ = vals
            ok, msg = execute_action(action, source, dest, dry_run=True)
            self.log_msg(msg)
        self.log_msg("=== DRY RUN COMPLETE ===\n")

    def execute(self):
        steps = self._get_selected_steps()
        if not steps:
            return
        confirm = messagebox.askyesno(
            "Confirm Execution",
            f"Execute {len(steps)} action(s)?\n\nThis will modify files on disk.\nOriginals are NOT backed up unless the action is 'copy'.",
        )
        if not confirm:
            return
        self.log_msg("\n=== EXECUTING ===")
        results = []
        for vals in steps:
            name, action, source, dest, _ = vals
            ok, msg = execute_action(action, source, dest, dry_run=False, verify=True)
            self.log_msg(msg)
            results.append(msg)
        log_path = log_execution("batch", results)
        self.log_msg(f"Log written: {log_path}")
        self.log_msg("=== EXECUTION COMPLETE ===\n")
        self.refresh_jobs()

    def view_logs(self):
        win = tk.Toplevel(self.root)
        win.title("Execution Logs")
        win.geometry("700x500")
        win.configure(bg="#2b2b2b")
        logs = sorted(LOG_DIR.glob("*.log"), reverse=True)
        lb = tk.Listbox(win, bg="#3c3c3c", fg="#e0e0e0", font=("Consolas", 10), height=10)
        lb.pack(fill=tk.X, padx=10, pady=5)
        for log in logs[:20]:
            lb.insert(tk.END, log.name)
        txt = scrolledtext.ScrolledText(win, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 10))
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        def show_log(event):
            sel = lb.curselection()
            if sel:
                path = LOG_DIR / lb.get(sel[0])
                try:
                    txt.delete("1.0", tk.END)
                    txt.insert("1.0", path.read_text(encoding="utf-8"))
                except OSError:
                    pass
        lb.bind("<<ListboxSelect>>", show_log)


if __name__ == "__main__":
    root = tk.Tk()
    app = FileActionsGUI(root)
    root.mainloop()
