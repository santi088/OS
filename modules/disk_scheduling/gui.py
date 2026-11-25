"""
Disk Scheduling GUI Module for Mini OS Simulator.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from gui.theme import COLORS, FONTS
from modules.disk_scheduling.algorithms import (
    DiskScheduler, DiskConfig, DiskAlgorithm, DiskResult,
    generate_sample_disk_config
)


class DiskSchedulingWindow:
    """Disk Scheduling simulation window."""
    
    def __init__(self, parent_window, content_frame):
        self.parent = parent_window
        self.content_frame = content_frame
        self.current_result: Optional[DiskResult] = None
        self.config = None
        
        self._setup_ui()
        self._load_sample_data()
        for variable in (self.head_var, self.min_cyl_var, self.max_cyl_var,
                         self.direction_var, self.requests_var):
            variable.trace_add("write", self._configuration_changed)
        self.algo_var.trace_add("write", self._algorithm_changed)
    
    def _setup_ui(self):
        """Setup the UI components."""
        main_paned = ttk.PanedWindow(self.content_frame, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Use the same scrollable, adjustable split as Memory Manager.
        left = ttk.Frame(main_paned)
        right = ttk.Frame(main_paned)
        main_paned.add(left, weight=1)
        main_paned.add(right, weight=1)
        scroll_canvas = tk.Canvas(left, width=1, height=1, highlightthickness=0,
                                  background=ttk.Style().lookup("TFrame", "background") or "#eeeeee")
        vertical = ttk.Scrollbar(left, orient=tk.VERTICAL, command=scroll_canvas.yview)
        horizontal = ttk.Scrollbar(left, orient=tk.HORIZONTAL, command=scroll_canvas.xview)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        scroll_canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        scroll_canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        controls = ttk.Frame(scroll_canvas)
        item = scroll_canvas.create_window((0, 0), window=controls, anchor="nw")
        def sync_controls(event=None):
            width = max(scroll_canvas.winfo_width(), controls.winfo_reqwidth())
            height = max(scroll_canvas.winfo_height(), controls.winfo_reqheight())
            scroll_canvas.itemconfigure(item, width=width, height=height)
            scroll_canvas.configure(scrollregion=(0, 0, width, height))
        controls.bind("<Configure>", sync_controls)
        scroll_canvas.bind("<Configure>", sync_controls)
        self._create_config_panel(controls)
        self._create_algorithm_panel(controls)
        self._create_results_panel(controls)
        self._create_visualization_panel(right)

        # Set the divider only when real geometry is available. Keep its
        # relative position through later window resizes, including maximize.
        ratio = [0.5]
        last_width = [0]
        def resize_panes(event):
            if event.width <= 2 or event.width == last_width[0]:
                return
            last_width[0] = event.width
            main_paned.sashpos(0, round(event.width * ratio[0]))
        def remember_sash(event):
            width = main_paned.winfo_width()
            if width > 2:
                ratio[0] = main_paned.sashpos(0) / width
        main_paned.bind("<Configure>", resize_panes, add="+")
        main_paned.bind("<ButtonRelease-1>", remember_sash, add="+")

    def _create_config_panel(self, parent):
        """Create disk configuration panel."""
        frame = ttk.LabelFrame(parent, text="Disk Configuration", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))
        
        frame.columnconfigure(1, weight=1)
        # Initial head
        ttk.Label(frame, text="Initial Head Position:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.head_var = tk.StringVar(value="50")
        ttk.Spinbox(frame, from_=0, to=1000, textvariable=self.head_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        # Cylinder range
        ttk.Label(frame, text="Min Cylinder:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.min_cyl_var = tk.StringVar(value="0")
        ttk.Spinbox(frame, from_=0, to=1000, textvariable=self.min_cyl_var, width=10).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(frame, text="Max Cylinder:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.max_cyl_var = tk.StringVar(value="199")
        ttk.Spinbox(frame, from_=0, to=10000, textvariable=self.max_cyl_var, width=10).grid(row=2, column=1, padx=5, pady=5)
        
        # Initial direction
        ttk.Label(frame, text="Initial Direction:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        self.direction_var = tk.StringVar(value="up")
        ttk.Combobox(frame, textvariable=self.direction_var, values=["up", "down"], width=8, state="readonly").grid(row=3, column=1, padx=5, pady=5)
        
        # Requests
        ttk.Label(frame, text="Request Queue (comma-separated):").grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        self.requests_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.requests_var, width=40).grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        
        ttk.Button(frame, text="Apply Configuration", command=self._apply_config).grid(row=6, column=0, columnspan=2, pady=10)
    
    def _create_algorithm_panel(self, parent):
        """Create algorithm selection panel."""
        frame = ttk.LabelFrame(parent, text="Algorithm Selection", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))
        
        self.algo_var = tk.StringVar(value=DiskAlgorithm.FCFS.value)
        
        choices = ttk.Frame(frame)
        choices.pack(fill=tk.X)
        for col in range(3):
            choices.columnconfigure(col, weight=1)
        for i, algo in enumerate(DiskAlgorithm):
            label = {DiskAlgorithm.CSCAN: "C-SCAN", DiskAlgorithm.CLOOK: "C-LOOK"}.get(algo, algo.value.upper())
            ttk.Radiobutton(choices, text=label, variable=self.algo_var,
                            value=algo.value).grid(row=i//3, column=i%3, sticky=tk.W, pady=3)
        ttk.Button(frame, text="Run Simulation", command=self._run_simulation).pack(fill=tk.X, pady=(8, 4))
        ttk.Button(frame, text="Compare All", command=self._compare_all).pack(fill=tk.X)

    def _create_results_panel(self, parent):
        """Create results panel."""
        frame = ttk.LabelFrame(parent, text="Results", padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Metrics
        metrics_frame = ttk.Frame(frame)
        metrics_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.metrics = {}
        for i, (label, key) in enumerate([
            ("Total movement (cylinders)", "total"), ("Avg seek (cylinders/request)", "avg")
        ]):
            row, col = i, 0
            f = ttk.Frame(metrics_frame)
            f.grid(row=row, column=col, padx=10, pady=5, sticky=tk.W)
            ttk.Label(f, text=f"{label}:", font=FONTS.get("body", ("Segoe UI", 10))).pack(side=tk.LEFT)
            self.metrics[key] = ttk.Label(f, text="--", font=FONTS.get("body", ("Segoe UI", 10)))
            self.metrics[key].pack(side=tk.LEFT, padx=5)
        
        # Service order table
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("Step", "From", "To", "Distance", "Request Served")
        self.result_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        for col in columns:
            self.result_tree.heading(col, text=col)
            self.result_tree.column(col, width=110 if col == "Request Served" else 60, minwidth=45, anchor=tk.CENTER)
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.result_tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_tree.configure(yscrollcommand=scroll.set)
    
    def _create_visualization_panel(self, parent):
        """Create visualization panel."""
        self.visual_parent = parent
        self.comparison_frame = None
        frame = self.movement_frame = ttk.LabelFrame(parent, text="Disk Head Movement", padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        self.fig = Figure(figsize=(8, 5), dpi=100, facecolor=COLORS['bg_panel'])
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(COLORS['bg_panel'])
        self.ax.tick_params(colors=COLORS['text_secondary'])
        for spine in self.ax.spines.values():
            spine.set_color(COLORS['border'])
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def _clear_results(self):
        self._hide_comparison()
        self.current_result = None
        for metric in self.metrics.values():
            metric.config(text="--")
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        self._draw_visualization()

    def _configuration_changed(self, *_):
        # Never run a previously applied configuration after editing the inputs.
        self.config = None
        self._clear_results()

    def _algorithm_changed(self, *_):
        self._clear_results()

    def _apply_config(self):
        """Read the visible form and validate before running any algorithm."""
        self.config = None
        self._clear_results()
        try:
            head = int(self.head_var.get().strip())
            min_cyl = int(self.min_cyl_var.get().strip())
            max_cyl = int(self.max_cyl_var.get().strip())
            raw = self.requests_var.get().strip()
            if not raw:
                raise ValueError("No requests in queue")
            requests = [int(x.strip()) for x in raw.split(",")]
            self.config = DiskConfig(head, (min_cyl, max_cyl), requests, self.direction_var.get())
            return True
        except (ValueError, tk.TclError) as e:
            messagebox.showerror("Invalid configuration", str(e), parent=self.parent)
            return False

    def _run_simulation(self):
        """Run using the current form; Apply remains an explicit validation action."""
        if not self._apply_config():
            return
        try:
            self.current_result = DiskScheduler.run_algorithm(DiskAlgorithm(self.algo_var.get()), self.config)
            self._display_results()
            self._draw_visualization()
        except Exception as e:
            self._clear_results()
            messagebox.showerror("Error", str(e), parent=self.parent)

    def _hide_comparison(self):
        """Restore the movement graph without changing the selected result."""
        if self.comparison_frame is not None:
            self.comparison_frame.pack_forget()
        if self.movement_frame.winfo_manager() != "pack":
            self.movement_frame.pack(fill=tk.BOTH, expand=True)

    def _compare_all(self):
        if self.config is None and not self._apply_config():
            return
        results = DiskScheduler.compare_all(self.config)

        # Embed comparison in the existing right panel. A separate Toplevel
        # can take focus away from the simulator's internal desktop window.
        if self.comparison_frame is None:
            frame = self.comparison_frame = ttk.LabelFrame(
                self.visual_parent, text="Algorithm Comparison", padding=10)
            ttk.Button(frame, text="Back to Head Movement",
                       command=self._hide_comparison).pack(anchor=tk.W, pady=(0, 8))
            columns = ("Algorithm", "Total Movement (cyl)", "Avg Seek (cyl/request)")
            self.comparison_tree = ttk.Treeview(frame, columns=columns,
                                                show="headings", height=6)
            for col in columns:
                self.comparison_tree.heading(col, text=col)
                self.comparison_tree.column(col, width=150, minwidth=70, anchor=tk.CENTER)
            self.comparison_tree.pack(fill=tk.X, pady=(0, 8))
            self.comparison_fig = Figure(figsize=(6, 3), dpi=100,
                                         facecolor=COLORS['bg_panel'])
            self.comparison_ax = self.comparison_fig.add_subplot(111)
            self.comparison_canvas = FigureCanvasTkAgg(self.comparison_fig, master=frame)
            self.comparison_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        for item in self.comparison_tree.get_children():
            self.comparison_tree.delete(item)
        for algo, result in results.items():
            self.comparison_tree.insert("", tk.END, values=(
                algo.value.upper(), result.total_head_movement,
                f"{result.avg_seek_distance:.2f}"))

        ax = self.comparison_ax
        ax.clear()
        ax.set_facecolor(COLORS['bg_panel'])
        ax.tick_params(colors=COLORS['text_secondary'])
        for spine in ax.spines.values():
            spine.set_color(COLORS['border'])
        algos = [r.algorithm.value.upper() for r in results.values()]
        totals = [r.total_head_movement for r in results.values()]
        bars = ax.bar(algos, totals, color=['#6c8cff', '#f87171', '#4ade80',
                                            '#fbbf24', '#a78bfa', '#60a5fa'])
        ax.set_ylabel('Total Head Movement (cylinders)', color=COLORS['text_primary'])
        ax.set_title('Algorithm Comparison', color=COLORS['text_primary'])
        ax.set_ylim(0, max(1, max(totals) * 1.18))
        for bar, val in zip(bars, totals):
            ax.annotate(str(val), (bar.get_x() + bar.get_width()/2, val),
                        xytext=(0, 3), textcoords='offset points',
                        ha='center', va='bottom', color=COLORS['text_primary'], fontsize=9)
        self.comparison_fig.tight_layout()
        self.movement_frame.pack_forget()
        self.comparison_frame.pack(fill=tk.BOTH, expand=True)
        self.comparison_canvas.draw_idle()

    def _display_results(self):
        """Display simulation results."""
        if not self.current_result:
            return
        
        r = self.current_result
        self.metrics["total"].config(text=str(r.total_head_movement))
        self.metrics["avg"].config(text=f"{r.avg_seek_distance:.2f}")
        
        # Update table
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        
        for i, ((from_cyl, to_cyl, dist), kind) in enumerate(zip(r.execution_path, r.step_kinds)):
            served = str(to_cyl) if kind in ("request", "wrap_request") else "—"
            self.result_tree.insert("", tk.END, values=(i+1, from_cyl, to_cyl, dist, served))

    def _draw_visualization(self):
        """Draw disk head movement visualization."""
        self.ax.clear()
        self.ax.set_facecolor(COLORS['bg_panel'])
        self.ax.tick_params(colors=COLORS['text_secondary'])
        for spine in self.ax.spines.values():
            spine.set_color(COLORS['border'])
        
        if not self.current_result or not self.config:
            self.ax.set_xticks([])
            self.ax.set_yticks([])
            self.ax.text(0.5, 0.5, "Run Simulation to view head movement",
                         transform=self.ax.transAxes, ha="center", va="center", color=COLORS["text_secondary"])
            self.canvas.draw()
            return
        
        r = self.current_result
        config = r.config
        
        # Build sequence of (sequence_index, cylinder) points
        # X-axis = movement sequence, Y-axis = cylinder number
        sequence_points = [(0, config.initial_head)]  # Start with initial head
        for i, (from_cyl, to_cyl, dist) in enumerate(r.execution_path):
            sequence_points.append((i + 1, to_cyl))
        
        seq_indices = [p[0] for p in sequence_points]
        cylinders = [p[1] for p in sequence_points]
        
        min_cyl, max_cyl = config.cylinder_range
        
        # Solid travel for normal moves; dashed travel for circular returns.
        used_labels = set()
        def label_once(label):
            if label in used_labels:
                return "_nolegend_"
            used_labels.add(label)
            return label

        self.ax.plot(0, config.initial_head, 's', markersize=10,
                     markerfacecolor=COLORS['success'], markeredgecolor='white',
                     label='Initial head')
        self.ax.annotate(str(config.initial_head), (0, config.initial_head),
                         xytext=(0, 10), textcoords='offset points', ha='center',
                         color=COLORS['success'], fontsize=9)
        for i, ((source, destination, distance), kind) in enumerate(zip(r.execution_path, r.step_kinds), 1):
            wrap = kind in ("wrap", "wrap_request")
            served = kind in ("request", "wrap_request")
            self.ax.plot([i-1, i], [source, destination],
                         color=COLORS['warning'] if wrap else COLORS['accent'],
                         linestyle='--' if wrap else '-', linewidth=2,
                         label=label_once('Circular return' if wrap else 'Head movement'))
            color = COLORS['danger'] if served else COLORS['warning']
            self.ax.plot(i, destination, marker='o' if served else 's', linestyle='None',
                         markersize=7, markerfacecolor=color, markeredgecolor='white',
                         label=label_once('Request served' if served else 'Non-service boundary'))
            self.ax.annotate(str(destination), (i, destination), xytext=(0, 10),
                             textcoords='offset points', ha='center', color='white', fontsize=9,
                             bbox=dict(boxstyle='round,pad=0.2', facecolor=color, alpha=0.8))

        # Mark all request positions as reference on Y-axis
        for req in sorted(set(config.requests)):
            self.ax.axhline(y=req, color=COLORS['border'], linewidth=0.5, alpha=0.3, zorder=0)
        
        # Configure axes
        self.ax.set_xlim(-0.5, len(sequence_points) - 0.5)
        y_margin = (max_cyl - min_cyl) * 0.1
        self.ax.set_ylim(min_cyl - y_margin, max_cyl + y_margin)
        
        # X-axis: sequence steps
        x_labels = ['Start'] + [str(i) for i in range(1, len(sequence_points))]
        self.ax.set_xticks(seq_indices)
        self.ax.set_xticklabels(x_labels, rotation=45, ha='right')
        
        self.ax.set_xlabel('Movement Step', color='white', fontsize=11)
        self.ax.set_ylabel('Cylinder Number', color='white', fontsize=11)
        self.ax.set_title(f'Disk Head Movement - {r.algorithm.value.upper()}',
                         color='white', fontsize=12, fontweight='bold', pad=15)
        
        # Grid for readability
        self.ax.grid(True, alpha=0.3, linestyle='--', axis='y')
        
        # Legend
        self.ax.legend(loc='upper left', facecolor=COLORS['bg_card'],
                      edgecolor=COLORS['border'], labelcolor=COLORS['text_primary'],
                      fontsize=9)
        
        self.fig.tight_layout()
        self.canvas.draw()
    
    def _load_sample_data(self):
        """Load sample data."""
        config = generate_sample_disk_config()
        
        self.head_var.set(config.initial_head)
        self.min_cyl_var.set(config.cylinder_range[0])
        self.max_cyl_var.set(config.cylinder_range[1])
        self.direction_var.set(config.initial_direction)
        self.requests_var.set(",".join(map(str, config.requests)))
        
        self._apply_config()


def create_disk_scheduling_module(parent_window, content_frame):
    """Factory function to create disk scheduling module."""
    return DiskSchedulingWindow(parent_window, content_frame)