"""Basic Tkinter GUI mirroring the original TimeCheck Google Sheet tabs."""

from __future__ import annotations

import argparse
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, simpledialog, ttk

from timecheck import TimeCheck
from timecheck.sheets import SHEET_TAB_MAP, import_workbook


def _fill_tree(tree: ttk.Treeview, rows: list[tuple[str, ...]]) -> None:
    for item in tree.get_children():
        tree.delete(item)
    for row in rows:
        tree.insert("", tk.END, values=row)


def _df_rows(df, columns: list[str], limit: int | None = None) -> list[tuple[str, ...]]:
    if df.empty:
        return []
    subset = df.iloc[::-1] if limit else df
    if limit:
        subset = subset.head(limit)
    return [tuple(str(row.get(column, "")) for column in columns) for _, row in subset.iterrows()]


class TimeCheckGUI:
    """Simple dashboard aligned with Daily / Tasks / Projects / Areas / TimeSheet tabs."""

    def __init__(self, timecheck: TimeCheck) -> None:
        self.tc = timecheck
        self.root = tk.Tk()
        self.root.title("TimeCheck")
        self.root.geometry("780x560")
        self.root.minsize(640, 480)

        self.status = tk.StringVar()
        self._build_menu()
        self._build_layout()
        self._refresh_all()
        self._set_status("Ready")

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Import Google Sheet (.xlsx)...", command=self._import_sheet)
        file_menu.add_separator()
        file_menu.add_command(label="Save", command=self._save)
        file_menu.add_command(label="Refresh", command=self._refresh_all)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

    def _build_layout(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._build_daily_tab()
        self._build_tasks_tab()
        self._build_projects_tab()
        self._build_areas_tab()
        self._build_timesheet_tab()
        self._build_summary_tab()

        ttk.Label(main, textvariable=self.status, relief=tk.SUNKEN, anchor=tk.W).pack(
            fill=tk.X, pady=(8, 0)
        )

    def _build_daily_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Daily")

        ttk.Label(tab, text="Task").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.log_task = ttk.Combobox(tab, width=48, state="readonly")
        self.log_task.grid(row=0, column=1, sticky=tk.EW, pady=4)

        ttk.Label(tab, text="Minutes").grid(row=1, column=0, sticky=tk.W, pady=4)
        default_minutes = int(self.tc.config.get("default_log_duration_minutes", 15))
        self.log_minutes = tk.StringVar(value=str(default_minutes))
        ttk.Entry(tab, textvariable=self.log_minutes, width=10).grid(
            row=1, column=1, sticky=tk.W, pady=4
        )

        ttk.Label(tab, text="Notes").grid(row=2, column=0, sticky=tk.NW, pady=4)
        self.log_notes = tk.Text(tab, width=50, height=4, wrap=tk.WORD)
        self.log_notes.grid(row=2, column=1, sticky=tk.EW, pady=4)

        ttk.Button(tab, text="Log Entry", command=self._log_entry).grid(
            row=3, column=1, sticky=tk.E, pady=(4, 8)
        )

        cols = ("date", "task", "total", "notes")
        self.daily_tree = self._make_tree(tab, cols, ["Date", "Task", "Total", "Notes"], row=4)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(4, weight=1)

    def _build_tasks_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Tasks")

        ttk.Label(tab, text="Task name").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.new_task_name = tk.StringVar()
        ttk.Entry(tab, textvariable=self.new_task_name, width=50).grid(
            row=0, column=1, sticky=tk.EW, pady=4
        )

        ttk.Label(tab, text="Project").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.new_task_project = ttk.Combobox(tab, width=48, state="readonly")
        self.new_task_project.grid(row=1, column=1, sticky=tk.EW, pady=4)

        ttk.Label(tab, text="Status").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.new_task_status = tk.StringVar(value="In Progress")
        ttk.Combobox(
            tab,
            textvariable=self.new_task_status,
            values=["Not Started", "In Progress", "Complete"],
            state="readonly",
            width=20,
        ).grid(row=2, column=1, sticky=tk.W, pady=4)

        ttk.Button(tab, text="Add Task", command=self._add_task).grid(
            row=3, column=1, sticky=tk.E, pady=(4, 8)
        )

        cols = ("task", "project", "time log", "status")
        self.tasks_tree = self._make_tree(
            tab, cols, ["Task", "Project", "Time Log", "Status"], row=4
        )
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(4, weight=1)

    def _build_projects_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Projects")

        ttk.Label(tab, text="Project").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.new_project_name = tk.StringVar()
        ttk.Entry(tab, textvariable=self.new_project_name, width=50).grid(
            row=0, column=1, sticky=tk.EW, pady=4
        )

        ttk.Label(tab, text="Area").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.new_project_area = ttk.Combobox(tab, width=48, state="readonly")
        self.new_project_area.grid(row=1, column=1, sticky=tk.EW, pady=4)

        ttk.Label(tab, text="Max weekly hours").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.new_project_hours = tk.StringVar(value="")
        ttk.Entry(tab, textvariable=self.new_project_hours, width=10).grid(
            row=2, column=1, sticky=tk.W, pady=4
        )

        ttk.Button(tab, text="Add Project", command=self._add_project).grid(
            row=3, column=1, sticky=tk.E, pady=(4, 8)
        )

        cols = ("project", "area", "time log", "max weekly hours", "status")
        self.projects_tree = self._make_tree(
            tab,
            cols,
            ["Project", "Area", "Time Log", "Max Weekly Hrs", "Status"],
            row=4,
        )
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(4, weight=1)

    def _build_areas_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Areas")

        ttk.Label(tab, text="Area").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.new_area_name = tk.StringVar()
        ttk.Entry(tab, textvariable=self.new_area_name, width=50).grid(
            row=0, column=1, sticky=tk.EW, pady=4
        )

        ttk.Label(tab, text="Max weekly hours").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.new_area_hours = tk.StringVar(value="")
        ttk.Entry(tab, textvariable=self.new_area_hours, width=10).grid(
            row=1, column=1, sticky=tk.W, pady=4
        )

        self.new_area_alert = tk.BooleanVar(value=False)
        ttk.Checkbutton(tab, text="Enable weekly hour alerts", variable=self.new_area_alert).grid(
            row=2, column=1, sticky=tk.W, pady=4
        )

        ttk.Button(tab, text="Add Area", command=self._add_area).grid(
            row=3, column=1, sticky=tk.E, pady=(4, 8)
        )

        cols = ("area", "time log", "Max Weekly Hours", "Alert")
        self.areas_tree = self._make_tree(
            tab, cols, ["Area", "Time Log", "Max Weekly Hrs", "Alert"], row=4
        )
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(4, weight=1)

    def _build_timesheet_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="TimeSheet")

        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(bar, text="Configure Timesheet Areas...", command=self._configure_timesheet).pack(
            side=tk.LEFT
        )

        self.timesheet_tree = ttk.Treeview(tab, show="headings", height=14)
        scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.timesheet_tree.yview)
        self.timesheet_tree.configure(yscrollcommand=scroll.set)
        self.timesheet_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_summary_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Summary")

        ttk.Label(tab, text="Weekly hours by area").pack(anchor=tk.W)
        self.summary_areas = ttk.Treeview(
            tab, columns=("name", "hours", "time_log"), show="headings", height=4
        )
        for col, label, width in [("name", "Area", 160), ("hours", "Hours", 80), ("time_log", "Total", 90)]:
            self.summary_areas.heading(col, text=label)
            self.summary_areas.column(col, width=width, stretch=False)
        self.summary_areas.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(tab, text="Active alerts (rolling 7-day window)").pack(anchor=tk.W)
        self.summary_alerts = ttk.Treeview(
            tab, columns=("level", "entity", "message"), show="headings", height=6
        )
        for col, label in [("level", "Level"), ("entity", "Entity"), ("message", "Message")]:
            self.summary_alerts.heading(col, text=label)
            self.summary_alerts.column(col, width=100 if col == "level" else 200)
        self.summary_alerts.column("message", width=360)
        self.summary_alerts.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

    def _make_tree(
        self,
        parent: ttk.Frame,
        columns: tuple[str, ...],
        headings: list[str],
        row: int,
    ) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, columnspan=2, sticky=tk.NSEW, pady=(4, 0))
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=10)
        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
            tree.column(column, width=120, stretch=True)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    def _column_values(self, df, name: str) -> list[str]:
        if df.empty or name not in df.columns:
            return []
        return [str(value).strip() for value in df[name].tolist() if str(value).strip()]

    def _refresh_lists(self) -> None:
        tasks = self._column_values(self.tc.tasks.df, "task")
        projects = self._column_values(self.tc.projects.df, "project")
        areas = self._column_values(self.tc.areas.df, "area")

        self.log_task["values"] = tasks
        self.new_task_project["values"] = projects
        self.new_project_area["values"] = areas

    def _refresh_daily(self) -> None:
        _fill_tree(
            self.daily_tree,
            _df_rows(self.tc.log.df, ["date", "task", "total", "notes"], limit=50),
        )

    def _refresh_tasks(self) -> None:
        _fill_tree(
            self.tasks_tree,
            _df_rows(self.tc.tasks.df, ["task", "project", "time log", "status"]),
        )

    def _refresh_projects(self) -> None:
        _fill_tree(
            self.projects_tree,
            _df_rows(
                self.tc.projects.df,
                ["project", "area", "time log", "max weekly hours", "status"],
            ),
        )

    def _refresh_areas(self) -> None:
        _fill_tree(
            self.areas_tree,
            _df_rows(self.tc.areas.df, ["area", "time log", "Max Weekly Hours", "Alert"]),
        )

    def _refresh_timesheet(self) -> None:
        df = self.tc.timesheet.df
        columns = list(self.tc.timesheet.columns)
        self.timesheet_tree.configure(columns=columns)
        for column in columns:
            self.timesheet_tree.heading(column, text=column)
            self.timesheet_tree.column(column, width=100, stretch=True)
        _fill_tree(self.timesheet_tree, _df_rows(df, columns, limit=60))

    def _refresh_summary(self) -> None:
        weekly = self.tc.metrics.weekly()
        _fill_tree(
            self.summary_areas,
            [(m.name, str(m.hours), m.time_log) for m in weekly["areas"]],
        )
        alerts = self.tc.check_alerts()
        _fill_tree(
            self.summary_alerts,
            [(a.level, a.entity, a.message) for a in alerts],
        )

    def _refresh_all(self) -> None:
        self.tc.load()
        self._refresh_lists()
        self._refresh_daily()
        self._refresh_tasks()
        self._refresh_projects()
        self._refresh_areas()
        self._refresh_timesheet()
        self._refresh_summary()
        self._set_status("Refreshed.")

    def _set_status(self, message: str) -> None:
        profile = self.tc.config.get("name") or "default"
        self.status.set(f"{message} | Profile: {profile} | {self.tc.data_root}")

    def _format_today(self) -> str:
        today = datetime.now()
        return f"{today.month}/{today.day}/{today.year}"

    def _log_entry(self) -> None:
        task = self.log_task.get().strip()
        if not task:
            messagebox.showwarning("Daily", "Select a task.")
            return
        try:
            minutes = int(self.log_minutes.get().strip())
            if minutes <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Daily", "Enter a positive number of minutes.")
            return

        notes = self.log_notes.get("1.0", tk.END).strip()
        stop = datetime.now()
        start = stop - timedelta(minutes=minutes)
        try:
            self.tc.log_entry(task, start=start, stop=stop, notes=notes)
            self.tc.save()
        except Exception as exc:
            messagebox.showerror("Daily", f"Could not log entry:\n{exc}")
            return

        self.log_notes.delete("1.0", tk.END)
        self._refresh_daily()
        self._refresh_tasks()
        self._refresh_projects()
        self._refresh_areas()
        self._refresh_timesheet()
        self._refresh_summary()
        self._set_status(f"Logged {minutes} min for '{task}'.")

    def _add_task(self) -> None:
        task_name = self.new_task_name.get().strip()
        project = self.new_task_project.get().strip()
        if not task_name:
            messagebox.showwarning("Tasks", "Enter a task name.")
            return
        if not project:
            messagebox.showwarning("Tasks", "Select a project.")
            return

        today = self._format_today()
        try:
            self.tc.add(
                "tasks",
                {
                    "task": task_name,
                    "project": project,
                    "details": "",
                    "priority": "1",
                    "time log": "0:00:00",
                    "status": self.new_task_status.get(),
                    "Anticipated Time": "",
                    "start date": today,
                    "due date": "",
                    "point of contact": "",
                    "last update": today,
                    "completed on": "",
                },
            )
            self.tc.save("tasks")
        except Exception as exc:
            messagebox.showerror("Tasks", f"Could not add task:\n{exc}")
            return

        self.new_task_name.set("")
        self._refresh_lists()
        self.log_task.set(task_name)
        self._refresh_tasks()
        self._set_status(f"Added task '{task_name}'.")

    def _add_project(self) -> None:
        name = self.new_project_name.get().strip()
        area = self.new_project_area.get().strip()
        if not name:
            messagebox.showwarning("Projects", "Enter a project name.")
            return
        if not area:
            messagebox.showwarning("Projects", "Select an area.")
            return

        try:
            self.tc.add(
                "projects",
                {
                    "project": name,
                    "time log": "0:00:00",
                    "max weekly hours": self.new_project_hours.get().strip(),
                    "due date": "",
                    "#tasks": "0",
                    "area": area,
                    "status": "Not Started",
                },
            )
            self.tc.save("projects")
        except Exception as exc:
            messagebox.showerror("Projects", f"Could not add project:\n{exc}")
            return

        self.new_project_name.set("")
        self._refresh_lists()
        self._refresh_projects()
        self._set_status(f"Added project '{name}'.")

    def _add_area(self) -> None:
        name = self.new_area_name.get().strip()
        if not name:
            messagebox.showwarning("Areas", "Enter an area name.")
            return

        try:
            self.tc.add(
                "areas",
                {
                    "area": name,
                    "time log": "0:00:00",
                    "Max Weekly Hours": self.new_area_hours.get().strip(),
                    "Alert": "TRUE" if self.new_area_alert.get() else "FALSE",
                },
            )
            self.tc.save("areas")
        except Exception as exc:
            messagebox.showerror("Areas", f"Could not add area:\n{exc}")
            return

        self.new_area_name.set("")
        self._refresh_lists()
        self._refresh_areas()
        self._set_status(f"Added area '{name}'.")

    def _configure_timesheet(self) -> None:
        areas = self._column_values(self.tc.areas.df, "area")
        if not areas:
            messagebox.showinfo("TimeSheet", "Add areas first.")
            return
        current = list(self.tc.config.get("timesheet_areas") or [])
        dialog = _AreaSelectDialog(self.root, areas, current)
        if dialog.result is None:
            return
        self.tc.set_timesheet_areas(dialog.result)
        self.tc.save()
        self._refresh_timesheet()
        self._set_status("Updated timesheet areas.")

    def _import_sheet(self) -> None:
        path = filedialog.askopenfilename(
            title="Import Google Sheet export",
            filetypes=[("Excel workbook", "*.xlsx"), ("All files", "*.*")],
        )
        if not path:
            return
        if not messagebox.askyesno(
            "Import",
            "Replace local tables with data from the selected workbook?\n\n"
            f"Expected tabs: {', '.join(SHEET_TAB_MAP)}",
        ):
            return
        try:
            imported = import_workbook(self.tc, path, replace=True)
        except ImportError as exc:
            messagebox.showerror("Import", str(exc))
            return
        except Exception as exc:
            messagebox.showerror("Import", f"Import failed:\n{exc}")
            return

        summary = ", ".join(f"{name}: {count} rows" for name, count in imported.items())
        self._refresh_all()
        messagebox.showinfo("Import", f"Imported {summary}")
        self._set_status("Imported Google Sheet export.")

    def _save(self) -> None:
        try:
            self.tc.save()
        except Exception as exc:
            messagebox.showerror("Save", f"Could not save data:\n{exc}")
            return
        self._set_status("Saved all tables.")

    def run(self) -> None:
        self.root.mainloop()


class _AreaSelectDialog:
    """Simple multi-select dialog for timesheet area columns."""

    def __init__(self, parent: tk.Misc, areas: list[str], selected: list[str]) -> None:
        self.result: list[str] | None = None
        self.top = tk.Toplevel(parent)
        self.top.title("Timesheet Areas")
        self.top.transient(parent)
        self.top.grab_set()

        ttk.Label(
            self.top,
            text="Select areas to include on the timesheet (like the original sheet):",
            wraplength=360,
        ).pack(anchor=tk.W, padx=12, pady=(12, 8))

        self.vars: dict[str, tk.BooleanVar] = {}
        frame = ttk.Frame(self.top, padding=(12, 0))
        frame.pack(fill=tk.BOTH, expand=True)
        for area in areas:
            var = tk.BooleanVar(value=area in selected)
            self.vars[area] = var
            ttk.Checkbutton(frame, text=area, variable=var).pack(anchor=tk.W)

        buttons = ttk.Frame(self.top, padding=12)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(buttons, text="Apply", command=self._apply).pack(side=tk.RIGHT)
        self.top.wait_window()

    def _apply(self) -> None:
        self.result = [area for area, var in self.vars.items() if var.get()]
        self.top.destroy()

    def _cancel(self) -> None:
        self.top.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="TimeCheck GUI")
    parser.add_argument("--name", help="Registered profile name")
    args = parser.parse_args()
    tc = TimeCheck(name=args.name) if args.name else TimeCheck()
    TimeCheckGUI(tc).run()


if __name__ == "__main__":
    main()
