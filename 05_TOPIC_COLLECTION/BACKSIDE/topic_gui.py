"""Native topic collection GUI over the existing search and copy-only engine."""
from __future__ import annotations
import json
import os
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

STATION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STATION.parent))
from engine.topic_collection import plan_collection, review_html, collect_selection
from gui.drive_harvester import plan_export, slugify

FORMATS = {"Markdown": {".md", ".markdown"}, "HTML": {".html", ".htm"}, "Text": {".txt"},
           "PDF": {".pdf"}, "Word": {".docx"}, "Lean": {".lean"}, "Spreadsheets / CSV": {".xlsx", ".xls", ".csv"}}


def depth(row):
    try:
        return len(Path(row["path"]).relative_to(row["scan_root"]).parts) - 1
    except ValueError:
        return len(Path(row["path"]).parts) - 2


class TopicCollectionGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("05 · Topic Collection — David-OS")
        self.geometry(f"{min(1480, self.winfo_screenwidth() - 80)}x{min(900, self.winfo_screenheight() - 100)}")
        self.minsize(1050, 700)
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.busy = False
        self.closing = False
        self.plan = None
        self.plan_dir = None
        self.selected = set()
        self.preview = None
        self.seed_rules = json.loads((STATION / "BACKSIDE/request.example.json").read_text(encoding="utf-8")).get("seeds", []) if (STATION / "BACKSIDE/request.example.json").is_file() else []
        self.topic = tk.StringVar(value="grace")
        self.synonyms = tk.StringVar(value="charis, unmerited favor, justification, sanctification, external restoration")
        self.recover = tk.BooleanVar(value=True)
        self.limit = tk.IntVar(value=5000)
        self.filter = tk.StringVar()
        self.order = tk.StringVar(value="Best match")
        self.layout = tk.StringVar(value="flat")
        self.minimum = tk.IntVar(value=0)
        self.destination = tk.StringVar(value=str(STATION / "OUTBOX"))
        self.status = tk.StringVar(value="Choose roots and formats, then search. Originals stay where they are.")
        self.summary = tk.StringVar(value="One topic → a clean working collection")
        self.selection_label = tk.StringVar(value="0 selected")
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._poll_id = self.after(100, self.poll)

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#131b27", foreground="#e4e9f1", font=("Segoe UI", 10))
        style.configure("Treeview", background="#172231", fieldbackground="#172231", foreground="#e4e9f1", rowheight=29)
        style.map("Treeview", background=[("selected", "#354962")])
        style.configure("TEntry", fieldbackground="#233147", foreground="#f3f5f9")
        style.configure("TCombobox", fieldbackground="#233147", foreground="#e4e9f1")
        self.configure(bg="#131b27")
        header = ttk.Frame(self, padding=16)
        header.pack(fill="x")
        ttk.Label(header, text="05  TOPIC COLLECTION", font=("Segoe UI", 19, "bold"), foreground="#e2bd76").pack(side="left")
        ttk.Label(header, textvariable=self.summary).pack(side="right")
        split = ttk.Panedwindow(self, orient="horizontal")
        split.pack(fill="both", expand=True, padx=12)
        left_host = ttk.Frame(split)
        left_canvas = tk.Canvas(left_host, width=350, background="#131b27", highlightthickness=0)
        left_scroll = ttk.Scrollbar(left_host, orient="vertical", command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_scroll.set)
        left_scroll.pack(side="right", fill="y")
        left_canvas.pack(side="left", fill="both", expand=True)
        left = ttk.Frame(left_canvas, padding=12)
        left_window = left_canvas.create_window((0, 0), window=left, anchor="nw")
        left.bind("<Configure>", lambda _: left_canvas.configure(scrollregion=left_canvas.bbox("all")))
        left_canvas.bind("<Configure>", lambda event: left_canvas.itemconfigure(left_window, width=event.width))
        right = ttk.Frame(split, padding=8)
        split.add(left_host, weight=0)
        split.add(right, weight=1)
        ttk.Label(left, text="1 · Search criteria", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(left, text="Topic").pack(anchor="w", pady=(10, 0))
        ttk.Entry(left, textvariable=self.topic, width=39).pack(fill="x")
        ttk.Label(left, text="Related terms (comma separated)").pack(anchor="w", pady=(8, 0))
        ttk.Entry(left, textvariable=self.synonyms).pack(fill="x")
        ttk.Label(left, text="Source roots — one folder, drive or file per line").pack(anchor="w", pady=(10, 0))
        self.roots = tk.Text(left, height=6, width=38, bg="#233147", fg="#e4e9f1", insertbackground="white", wrap="none")
        self.roots.pack(fill="x")
        root_buttons = ttk.Frame(left)
        root_buttons.pack(fill="x", pady=4)
        ttk.Button(root_buttons, text="Add folder…", command=self.add_folder).pack(side="left")
        ttk.Button(root_buttons, text="Add file…", command=self.add_file).pack(side="left", padx=4)
        self.format_vars = {}
        formats = ttk.LabelFrame(left, text="Paper formats", padding=8)
        formats.pack(fill="x", pady=8)
        for index, (name, extensions) in enumerate(FORMATS.items()):
            var = tk.BooleanVar(value=name not in {"Lean", "Spreadsheets / CSV"})
            self.format_vars[name] = var
            ttk.Checkbutton(formats, text=name, variable=var).grid(row=index // 2, column=index % 2, sticky="w", padx=4)
        fields = ttk.LabelFrame(left, text="Match in", padding=8)
        fields.pack(fill="x", pady=4)
        self.fields = {}
        for index, (key, label) in enumerate([("filename", "File name"), ("folder", "Folder names"), ("heading", "Title / headings"), ("body", "Document text"), ("tags", "Tags"), ("sidecar", "Metadata")]):
            var = tk.BooleanVar(value=True)
            self.fields[key] = var
            ttk.Checkbutton(fields, text=label, variable=var).grid(row=index // 2, column=index % 2, sticky="w")
        ttk.Checkbutton(left, text="Include .trash recovery (flag separately)", variable=self.recover).pack(anchor="w", pady=5)
        ttk.Label(left, text="Archive matches are retained and flagged.").pack(anchor="w")
        limits = ttk.Frame(left)
        limits.pack(fill="x", pady=8)
        ttk.Label(limits, text="File limit").pack(side="left")
        ttk.Spinbox(limits, from_=1, to=1000000, textvariable=self.limit, width=8).pack(side="left", padx=5)
        self.scan_button = ttk.Button(left, text="SEARCH — create review plan", command=self.search)
        self.scan_button.pack(fill="x", pady=5)
        ttk.Button(left, text="Load existing plan…", command=self.load_dialog).pack(fill="x", pady=3)
        ttk.Button(left, text="Load Grace pilot", command=self.load_pilot).pack(fill="x", pady=3)
        ttk.Button(left, text="Stop current task", command=self.stop_event.set).pack(fill="x", pady=3)
        ttk.Label(left, text="400,000 text characters / file; 25 MB ceiling.\nPDF text needs an extractable text layer.\nSearch scores are heuristics, not probabilities.", wraplength=330, foreground="#a9b6ca").pack(anchor="w", pady=10)

        tools = ttk.Frame(right)
        tools.pack(fill="x")
        ttk.Button(tools, text="Stop", command=self.stop_event.set).pack(side="right", padx=4)
        ttk.Entry(tools, textvariable=self.filter, width=23).pack(side="left")
        ttk.Label(tools, text="  Sort:").pack(side="left")
        ttk.Combobox(tools, textvariable=self.order, values=["Best match", "File name", "File type", "Least nesting", "Recovery tier", "Source folder"], state="readonly", width=16).pack(side="left")
        ttk.Label(tools, text="  Min score").pack(side="left")
        ttk.Spinbox(tools, from_=0, to=100, textvariable=self.minimum, width=5).pack(side="left")
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True, pady=8)
        results = ttk.Frame(self.notebook)
        folders = ttk.Frame(self.notebook)
        detail = ttk.Frame(self.notebook)
        self.notebook.add(results, text="Papers — flat view")
        self.notebook.add(folders, text="Original folder structure")
        self.notebook.add(detail, text="Preview / activity")
        columns = ("take", "name", "type", "score", "tier", "depth", "folder")
        self.table = ttk.Treeview(results, columns=columns, show="headings", selectmode="browse")
        for col, title, width in zip(columns, ["Collect", "Paper", "Type", "Match", "Source tier", "Nesting", "Original folder"], [60, 260, 70, 65, 160, 70, 350]):
            self.table.heading(col, text=title)
            self.table.column(col, width=width, minwidth=50, stretch=col in {"name", "folder"})
        scroll = ttk.Scrollbar(results, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        horizontal = ttk.Scrollbar(results, orient="horizontal", command=self.table.xview)
        horizontal.pack(side="bottom", fill="x")
        self.table.configure(xscrollcommand=horizontal.set)
        self.table.pack(fill="both", expand=True)
        self.table.bind("<ButtonRelease-1>", self.clicked)
        self.table.bind("<<TreeviewSelect>>", self.show_detail)
        self.tree = ttk.Treeview(folders, columns=("count",), show="tree headings")
        self.tree.heading("#0", text="Source hierarchy (matched papers only)")
        self.tree.heading("count", text="Papers beneath")
        self.tree.column("count", width=110, stretch=False)
        tree_scroll = ttk.Scrollbar(folders, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.details = tk.Text(detail, bg="#172231", fg="#dbe5f2", wrap="word", state="disabled")
        self.details.pack(fill="both", expand=True)
        select = ttk.Frame(right)
        select.pack(fill="x")
        ttk.Button(select, text="Select visible", command=self.select_visible).pack(side="left")
        ttk.Button(select, text="Clear selection", command=self.clear_selection).pack(side="left", padx=5)
        ttk.Label(select, textvariable=self.selection_label).pack(side="left", padx=10)
        output = ttk.LabelFrame(right, text="2 · Simplify the working collection", padding=10)
        output.pack(fill="x", pady=8)
        ttk.Radiobutton(output, text="One flat folder of papers", variable=self.layout, value="flat").pack(anchor="w")
        ttk.Radiobutton(output, text="One folder per file type", variable=self.layout, value="extension").pack(anchor="w")
        ttk.Label(output, text="Destination parent (a new topic folder is created inside it)").pack(anchor="w", pady=(5, 0))
        row = ttk.Frame(output)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.destination).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse…", command=self.choose_destination).pack(side="left", padx=5)
        row = ttk.Frame(output)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text="Preview new layout", command=self.preview_export).pack(side="left")
        self.copy_button = ttk.Button(row, text="Copy selected papers", command=self.copy, state="disabled")
        self.copy_button.pack(side="left", padx=5)
        ttk.Button(row, text="Open OUTBOX", command=lambda: os.startfile(STATION / "OUTBOX")).pack(side="left")
        ttk.Label(output, text="Original folders stay intact. Their structure is recorded in provenance; it is not recreated in flat mode.", wraplength=800).pack(anchor="w", pady=(6, 0))
        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", padx=12)
        ttk.Label(self, textvariable=self.status, padding=10).pack(fill="x")
        for var in (self.filter, self.order, self.minimum):
            var.trace_add("write", lambda *_: self.refresh())
        for var in (self.layout, self.destination):
            var.trace_add("write", lambda *_: self.invalidate())

    def add_folder(self):
        path = filedialog.askdirectory(parent=self, title="Add source folder or drive")
        if path:
            self.roots.insert("end", path + "\n")

    def add_file(self):
        for path in filedialog.askopenfilenames(parent=self, title="Add known source files"):
            self.roots.insert("end", path + "\n")

    def choose_destination(self):
        path = filedialog.askdirectory(parent=self, title="Destination parent")
        if path:
            self.destination.set(path)

    def log(self, value):
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("end", value)
        self.details.configure(state="disabled")

    def invalidate(self):
        self.preview = None
        self.copy_button.configure(state="disabled")

    def set_busy(self, value):
        self.busy = value
        self.scan_button.configure(state="disabled" if value else "normal")
        if value:
            self.invalidate()
            self.progress.start(12)
        else:
            self.progress.stop()

    def worker(self, operation):
        if self.busy:
            return
        self.stop_event.clear()
        self.set_busy(True)
        def run():
            try:
                self.events.put(("done", operation()))
            except Exception as exc:
                self.events.put(("error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=run, daemon=True).start()

    def search(self):
        if self.busy:
            return
        try:
            request = {"topic": self.topic.get().strip(), "synonyms": [s.strip() for s in self.synonyms.get().split(",") if s.strip()],
                       "roots": [s.strip() for s in self.roots.get("1.0", "end").splitlines() if s.strip()],
                       "include_trash": self.recover.get(), "max_files": self.limit.get(),
                       "extensions": sorted({ext for name, exts in FORMATS.items() if self.format_vars[name].get() for ext in exts}),
                       "fields": [key for key, var in self.fields.items() if var.get()],
                       "seeds": self.seed_rules if self.topic.get().strip().casefold() == "grace" else []}
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            out = STATION / "OUTBOX" / (slugify(request["topic"]) + "-plan-" + stamp)
        except Exception as exc:
            messagebox.showerror("Criteria", str(exc), parent=self)
            return
        def operation():
            plan = plan_collection(request, exclude=[STATION], stop=self.stop_event.is_set, progress=lambda m: self.events.put(("progress", m)))
            out.mkdir(parents=True)
            (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            (out / "REVIEW.html").write_text(review_html(plan), encoding="utf-8")
            return ("plan", plan, out)
        self.status.set("Searching selected roots…")
        self.worker(operation)
        self.summary.set("Searching… displayed papers are from the previous plan")

    def load_dialog(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self, title="Load collection plan", filetypes=[("Plan JSON", "*.json")])
        if path:
            try:
                self.load_plan(json.loads(Path(path).read_text(encoding="utf-8-sig")), Path(path).parent)
            except Exception as exc:
                messagebox.showerror("Plan", str(exc), parent=self)

    def load_pilot(self):
        if self.busy:
            return
        paths = sorted((STATION / "OUTBOX").glob("grace-pilot-*/plan.json"))
        if paths:
            self.load_plan(json.loads(paths[-1].read_text(encoding="utf-8")), paths[-1].parent)
        else:
            messagebox.showinfo("Grace pilot", "No saved Grace pilot is present here.", parent=self)

    def load_plan(self, plan, directory):
        if plan.get("schema") != "topic-collection/1":
            raise ValueError("Choose a topic-collection plan")
        self.plan, self.plan_dir = plan, directory
        self.seed_rules = plan.get("seed_rules", self.seed_rules if plan["topic"].casefold() == "grace" else [])
        self.selected.clear()
        self.topic.set(plan["topic"])
        self.synonyms.set(", ".join(plan["profile"]["synonyms"]))
        self.roots.delete("1.0", "end")
        self.roots.insert("1.0", "\n".join(plan["roots"]) + "\n")
        self.recover.set(plan["include_trash"])
        for key, var in self.fields.items():
            var.set(key in plan["profile"]["fields"])
        included_types = set(plan.get("extensions", [row["ext"] for row in plan["files"]]))
        for name, var in self.format_vars.items():
            var.set(bool(FORMATS[name] & included_types))
        self.filter.set("")
        self.minimum.set(0)
        self.build_tree()
        self.refresh()
        self.status.set(f"Loaded {len(plan['files'])} candidates · {'PARTIAL' if plan['partial'] else 'selected scope completed'} · {directory}")

    def visible(self):
        if not self.plan:
            return []
        query = self.filter.get().casefold()
        try:
            minimum = self.minimum.get()
        except tk.TclError:
            minimum = 0
        rows = [r for r in self.plan["files"] if query in (r["path"] + " " + r["source_tier"]).casefold() and r["confidence"] >= minimum]
        keys = {"Best match": lambda r: (-r["confidence"], r["name"].casefold()), "File name": lambda r: r["name"].casefold(),
                "File type": lambda r: (r["ext"], r["name"]), "Least nesting": lambda r: (depth(r), r["name"]),
                "Recovery tier": lambda r: (r["source_tier"], r["name"]), "Source folder": lambda r: str(Path(r["path"]).parent)}
        return sorted(rows, key=keys.get(self.order.get(), keys["Best match"]))

    def refresh(self):
        if not hasattr(self, "table"):
            return
        self.invalidate()
        self.table.delete(*self.table.get_children())
        self.display_rows = self.visible()
        for i, row in enumerate(self.display_rows):
            self.table.insert("", "end", iid=str(i), values=("☑" if row["path"] in self.selected else "☐", row["name"], row["ext"], row["confidence"], row["source_tier"], depth(row), str(Path(row["path"]).parent)))
        hidden = len(self.selected - {r["path"] for r in self.display_rows})
        self.selection_label.set(f"{len(self.selected)} selected" + (f" ({hidden} hidden by filter)" if hidden else ""))
        if self.plan:
            deepest = max((depth(r) for r in self.plan["files"]), default=0)
            self.summary.set(f"{len(self.plan['files'])} candidates · {len(self.display_rows)} visible · deepest nesting {deepest}")

    def clicked(self, event):
        item = self.table.identify_row(event.y)
        if item and self.table.identify_column(event.x) == "#1" and not self.busy:
            path = self.display_rows[int(item)]["path"]
            if path in self.selected:
                self.selected.remove(path)
            else:
                self.selected.add(path)
            self.refresh()

    def show_detail(self, *_):
        selection = self.table.selection()
        if selection:
            row = self.display_rows[int(selection[0])]
            self.log(json.dumps(row, ensure_ascii=False, indent=2))

    def select_visible(self):
        if not self.busy:
            self.selected.update(r["path"] for r in self.visible())
            self.refresh()

    def clear_selection(self):
        if not self.busy:
            self.selected.clear()
            self.refresh()

    def build_tree(self):
        self.tree.delete(*self.tree.get_children())
        nodes, counts = {}, {}
        for row in self.plan["files"]:
            root = row["scan_root"]
            parts = Path(row["path"]).relative_to(root).parts[:-1]
            parent, key = "", root
            for label in [root, *parts]:
                if parent:
                    key += "/" + label
                if key not in nodes:
                    nodes[key] = self.tree.insert(parent, "end", text=label, open=not parent)
                parent = nodes[key]
                counts[key] = counts.get(key, 0) + 1
        for key, item in nodes.items():
            self.tree.set(item, "count", counts[key])

    def preview_export(self):
        if self.busy or not self.plan or not self.selected:
            return
        try:
            chosen = [r for r in self.plan["files"] if r["path"] in self.selected]
            base = Path(self.destination.get()).expanduser().resolve()
            if not base.is_dir():
                raise ValueError("Choose an existing destination parent")
            out = base / (slugify(self.plan["topic"]) + "-collection-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
            rows = plan_export(chosen, self.plan["profile"], out / "FILES", self.layout.get())
            self.preview = (out, self.layout.get(), {"plan_sha256": self.plan["plan_sha256"], "selected_paths": sorted(self.selected)})
            self.log(f"COPY {len(chosen)} files · layout {self.layout.get()}\nOriginal sources unchanged. Source metadata will be preserved beside copies.\n\n" + "\n\n".join(f"{r['path']}\n  → {target}" for r, target in rows))
            self.notebook.select(2)
            self.copy_button.configure(state="normal")
        except Exception as exc:
            self.invalidate()
            messagebox.showerror("Layout preview", str(exc), parent=self)

    def copy(self):
        if not self.preview or self.busy:
            return
        out, layout, selection = self.preview
        plan = self.plan
        def operation():
            result = collect_selection(plan, selection, out, layout=layout, stop=self.stop_event.is_set,
                                       progress=lambda n, path: self.events.put(("progress", f"Copy {n}/{len(selection['selected_paths'])} · {path}")))
            return ("collection", result, out)
        self.worker(operation)

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    self.status.set(value)
                else:
                    self.set_busy(False)
                    if kind == "error":
                        self.status.set(value)
                        self.log(value)
                    elif value[0] == "plan":
                        self.load_plan(value[1], value[2])
                    else:
                        self.status.set(f"{value[1]['status']} · {value[2]}")
                        self.log(json.dumps(value[1], ensure_ascii=False, indent=2))
        except queue.Empty:
            pass
        if self.closing and not self.busy:
            self.destroy()
        else:
            self._poll_id = self.after(100, self.poll)

    def destroy(self):
        try:
            self.after_cancel(self._poll_id)
        except (tk.TclError, AttributeError):
            pass
        super().destroy()

    def close(self):
        if self.busy:
            self.stop_event.set()
            self.closing = True
            self.status.set("Stopping safely before closing…")
        else:
            self.destroy()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, help="Open an existing plan without starting a scan")
    args = parser.parse_args()
    (STATION / "INBOX").mkdir(exist_ok=True)
    (STATION / "OUTBOX").mkdir(exist_ok=True)
    app = TopicCollectionGUI()
    if args.plan:
        app.load_plan(json.loads(args.plan.read_text(encoding="utf-8-sig")), args.plan.parent)
    app.mainloop()
