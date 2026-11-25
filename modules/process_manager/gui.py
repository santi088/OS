"""
Process Manager GUI Module for Mini OS Simulator.
"""

import tkinter as tk
import math
from tkinter import ttk, messagebox
from typing import List, Optional
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from gui.theme import COLORS, FONTS
from modules.process_manager.algorithms import (
    ProcessManager, SimulatedProcess, ProcessState, TransitionReason,
    MultiprogrammingResult, MultiprocessingResult, CPUScheduleEvent,
    SchedulingAlgorithm, generate_sample_processes
)


class ProcessManagerWindow:
    """Process Manager simulation window."""
    
    def __init__(self, parent_window, content_frame):
        self.parent = parent_window
        self.content_frame = content_frame
        self.mp_result: Optional[MultiprogrammingResult] = None
        
        self._setup_ui()
        self._load_sample_data()
    
    def _setup_ui(self):
        # Equal grid columns avoid the collapsed-sash issue in internal windows.
        main = ttk.Frame(self.content_frame)
        main.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main.columnconfigure(0, weight=1, uniform="panels")
        main.columnconfigure(1, weight=1, uniform="panels")
        main.rowconfigure(0, weight=1)
        holder = ttk.Frame(main)
        holder.grid(row=0,column=0,sticky="nsew",padx=(0,4))
        holder.rowconfigure(0,weight=1); holder.columnconfigure(0,weight=1)
        scroll_canvas = tk.Canvas(holder, highlightthickness=0, width=1, height=1, background="#eeeeee")
        scroll_canvas.grid(row=0,column=0,sticky="nsew")
        sy=ttk.Scrollbar(holder,orient="vertical",command=scroll_canvas.yview)
        sx=ttk.Scrollbar(holder,orient="horizontal",command=scroll_canvas.xview)
        sy.grid(row=0,column=1,sticky="ns"); sx.grid(row=1,column=0,sticky="ew")
        scroll_canvas.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        left=ttk.Frame(scroll_canvas)
        win=scroll_canvas.create_window((0,0),window=left,anchor="nw")
        def resize(event=None):
            scroll_canvas.itemconfigure(win,width=max(scroll_canvas.winfo_width(),left.winfo_reqwidth()))
            scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
        left.bind("<Configure>",resize); scroll_canvas.bind("<Configure>",resize)
        self._create_mp_config(left)
        self._create_mp_controls(left)
        self._create_mp_results(left)
        right=ttk.Frame(main)
        right.grid(row=0,column=1,sticky="nsew")
        self._create_mp_visualization(right)
        self.mp_timeslice_var.trace_add("write",lambda *_: self._mp_reset())

    def _create_mp_config(self, parent):
        """Create multiprogramming configuration."""
        frame = ttk.LabelFrame(parent, text="Process Configuration", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Process list
        columns = ("PID", "Arrival", "Burst", "I/O Freq", "Priority")
        self.mp_tree = ttk.Treeview(frame, columns=columns, show="headings", height=6)
        for col in columns:
            self.mp_tree.heading(col, text=col)
            self.mp_tree.column(col, width=70, anchor=tk.CENTER)
        self.mp_tree.configure(displaycolumns=("PID", "Arrival", "Burst", "I/O Freq"))
        self.mp_tree.pack(fill=tk.BOTH, expand=True)
        
        # Add process form
        form = ttk.Frame(frame)
        form.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(form, text="PID:").grid(row=0, column=0, padx=2)
        self.mp_pid_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.mp_pid_var, width=8).grid(row=0, column=1, padx=2)
        
        ttk.Label(form, text="Arrival:").grid(row=0, column=2, padx=2)
        self.mp_arrival_var = tk.DoubleVar(value=0.0)
        ttk.Entry(form, textvariable=self.mp_arrival_var, width=8).grid(row=0, column=3, padx=2)
        
        ttk.Label(form, text="Burst:").grid(row=1, column=0, padx=2)
        self.mp_burst_var = tk.DoubleVar(value=10.0)
        ttk.Entry(form, textvariable=self.mp_burst_var, width=8).grid(row=1, column=1, padx=2)
        
        ttk.Label(form, text="I/O Freq:").grid(row=1, column=2, padx=2)
        self.mp_io_var = tk.DoubleVar(value=0.0)
        ttk.Entry(form, textvariable=self.mp_io_var, width=8).grid(row=1, column=3, padx=2)
        
        self.mp_priority_var = tk.IntVar(value=0)
        
        btn_frame = ttk.Frame(form)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=5, sticky="w")
        ttk.Button(btn_frame, text="Add", command=self._mp_add_process).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Remove", command=self._mp_remove_process).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Clear", command=self._mp_clear_processes).pack(side=tk.LEFT, padx=2)
        
        self.mp_tree.bind("<<TreeviewSelect>>", self._mp_on_select)
        
        # Simulation params
        param_frame = ttk.LabelFrame(frame, text="Simulation Parameters", padding=5)
        param_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Algorithm selection
        algo_frame = ttk.Frame(param_frame)
        algo_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(algo_frame, text="Algorithm:").pack(side=tk.LEFT, padx=5)
        self.mp_algo_var = tk.StringVar(value=SchedulingAlgorithm.ROUND_ROBIN.value)
        algo_combo = ttk.Combobox(
            algo_frame,
            textvariable=self.mp_algo_var,
            values=[a.value for a in SchedulingAlgorithm],
            state="readonly",
            width=18
        )
        algo_combo.pack(side=tk.LEFT, padx=5)
        algo_combo.bind("<<ComboboxSelected>>", self._on_algo_change)
        
        # Time Slice (only relevant for Round Robin)
        ts_frame = ttk.Frame(param_frame)
        ts_frame.pack(fill=tk.X, pady=(0, 5))
        self.ts_frame = ts_frame
        ttk.Label(ts_frame, text="Time Slice:").pack(side=tk.LEFT, padx=5)
        self.mp_timeslice_var = tk.DoubleVar(value=2.0)
        self.mp_timeslice_spin = ttk.Spinbox(
            ts_frame, from_=0.1, to=10.0, increment=0.1,
            textvariable=self.mp_timeslice_var, width=8
        )
        self.mp_timeslice_spin.pack(side=tk.LEFT, padx=5)
        
        # Priority info label
        info_frame = ttk.Frame(param_frame)
        info_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(
            info_frame,
            text="I/O Freq: CPU time between I/O requests (0 = none).",
            font=("Segoe UI", 8),
            foreground="#444444"
        ).pack(side=tk.LEFT, padx=5)
    
    def _on_algo_change(self, event=None):
        """Handle algorithm selection change."""
        algo = SchedulingAlgorithm(self.mp_algo_var.get())
        if algo == SchedulingAlgorithm.ROUND_ROBIN:
            self.mp_timeslice_spin.configure(state="normal")
        else:
            self.mp_timeslice_spin.configure(state="disabled")
        self._mp_reset()
    
    # ==================== MULTIPROGRAMMING CONTROLS ====================
    
    def _create_mp_controls(self, parent):
        frame = ttk.LabelFrame(parent, text="Simulation Controls", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(frame, text="Run Simulation", command=self._mp_run).pack(side=tk.LEFT,padx=2)
        ttk.Button(frame, text="Reset Results", command=self._mp_reset).pack(side=tk.LEFT,padx=2)
        self.mp_time_label = ttk.Label(frame, text="Time: 0.00")
        self.mp_time_label.pack(side=tk.RIGHT,padx=4)

    def _create_mp_results(self, parent):
        """Create results panel."""
        frame = ttk.LabelFrame(parent, text="Results", padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Metrics
        metrics_frame = ttk.Frame(frame)
        metrics_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.mp_metrics = {}
        for i, (label, key) in enumerate([
            ("CPU Utilization", "cpu_util"), ("Throughput", "throughput"),
            ("Avg Turnaround", "avg_turnaround"), ("Avg Waiting", "avg_waiting"),
            ("Avg Response", "avg_response"), ("Dispatch switches", "ctx_switches"),
            ("Peak resident processes", "max_mp")
        ]):
            row, col = divmod(i, 2)
            f = ttk.Frame(metrics_frame)
            f.grid(row=row, column=col, padx=8, pady=3, sticky=tk.W)
            ttk.Label(f, text=f"{label}:", font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
            self.mp_metrics[key] = ttk.Label(f, text="--", font=("Segoe UI", 8))
            self.mp_metrics[key].pack(side=tk.LEFT, padx=3)
        
        # Schedule log
        log_frame=ttk.Frame(frame)
        log_frame.pack(fill=tk.BOTH,expand=True)
        self.mp_log = tk.Text(log_frame,height=10,width=35,wrap="word",bg=COLORS["bg_panel"],fg=COLORS["text_primary"],font=FONTS["mono_small"],state="disabled")
        log_scroll=ttk.Scrollbar(log_frame,orient="vertical",command=self.mp_log.yview)
        self.mp_log.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side=tk.RIGHT,fill=tk.Y)
        self.mp_log.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        ttk.Label(frame,text="Waiting = ready-queue time only. I/O duration: random 0.5–3 units. Dispatch switches count idle-to-process and PID changes; no switch overhead.",wraplength=340).pack(anchor="w",pady=3)
    
    # ==================== MULTIPROGRAMMING VISUALIZATION ====================
    
    def _create_mp_visualization(self, parent):
        """Create Gantt chart visualization."""
        frame = ttk.LabelFrame(parent, text="CPU Timeline", padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        self.mp_fig = Figure(figsize=(8, 4), dpi=100, facecolor=COLORS['bg_panel'])
        self.mp_ax = self.mp_fig.add_subplot(111)
        self.mp_ax.set_facecolor(COLORS['bg_panel'])
        self.mp_ax.tick_params(colors=COLORS['text_secondary'])
        for spine in self.mp_ax.spines.values():
            spine.set_color(COLORS['border'])
        
        self.mp_canvas = FigureCanvasTkAgg(self.mp_fig, master=frame)
        self.mp_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    # ==================== MULTIPROGRAMMING HANDLERS ====================
    
    def _mp_add_process(self):
        """Add a process from form inputs."""
        try:
            pid = self.mp_pid_var.get().strip()
            arrival = self.mp_arrival_var.get()
            burst = self.mp_burst_var.get()
            io_freq = self.mp_io_var.get()
            priority = self.mp_priority_var.get()
            
            if not pid:
                messagebox.showerror("Error", "Process ID required")
                return
            if not all(math.isfinite(x) for x in (arrival,burst,io_freq)) or arrival < 0 or burst <= 0 or io_freq < 0:
                messagebox.showerror("Error", "Invalid values (arrival >= 0, burst > 0, io_freq >= 0)")
                return
            if any(str(self.mp_tree.item(item)['values'][0]) == pid for item in self.mp_tree.get_children()):
                messagebox.showerror("Error", f"Process {pid} already exists")
                return
            
            self.mp_tree.insert("", tk.END, values=(pid, arrival, burst, io_freq, priority))
            self._mp_reset()
            self.mp_pid_var.set("")
            self.mp_arrival_var.set(0.0)
            self.mp_burst_var.set(10.0)
            self.mp_io_var.set(0.0)
            self.mp_priority_var.set(0)
            
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def _mp_remove_process(self):
        """Remove selected process."""
        selection = self.mp_tree.selection()
        if not selection:
            return
        self.mp_tree.delete(selection[0])
        self._mp_reset()
    
    def _mp_clear_processes(self):
        """Clear all processes."""
        for item in self.mp_tree.get_children():
            self.mp_tree.delete(item)
        self._mp_reset()
    
    def _mp_on_select(self, event):
        """Populate form from selected process."""
        selection = self.mp_tree.selection()
        if not selection:
            return
        values = self.mp_tree.item(selection[0])['values']
        self.mp_pid_var.set(str(values[0]))
        self.mp_arrival_var.set(float(values[1]))
        self.mp_burst_var.set(float(values[2]))
        self.mp_io_var.set(float(values[3]))
        self.mp_priority_var.set(int(values[4]))
    
    def _mp_run(self):
        self._mp_reset()
        try:
            processes=[]
            for item in self.mp_tree.get_children():
                v=self.mp_tree.item(item)["values"]
                processes.append(SimulatedProcess(str(v[0]),float(v[1]),float(v[2]),float(v[3]),int(v[4])))
            if not processes: raise ValueError("No processes defined")
            algo=SchedulingAlgorithm(self.mp_algo_var.get())
            time_slice=self.mp_timeslice_var.get() if algo==SchedulingAlgorithm.ROUND_ROBIN else 2.0
            result=ProcessManager.simulate_multiprogramming(processes,algo,time_slice)
            if any(p.state!=ProcessState.TERMINATED for p in result.processes):
                raise ValueError("Simulation exceeded its 1000-time-unit limit; reduce workload.")
            self.mp_result=result
            self.mp_time_label.configure(text=f"Time: {result.total_time:.2f}")
            self._display_mp_results()
        except (ValueError,tk.TclError,RuntimeError,ArithmeticError) as e:
            messagebox.showerror("Error",str(e))

    def _mp_reset(self):
        self.mp_result=None
        self.mp_time_label.configure(text="Time: 0.00")
        for metric in self.mp_metrics.values(): metric.configure(text="--")
        self.mp_log.configure(state="normal")
        self.mp_log.delete("1.0",tk.END)
        self.mp_log.configure(state="disabled")
        self._draw_mp_gantt()

    def _display_mp_results(self):
        """Display multiprogramming results."""
        if not self.mp_result:
            return
        
        r = self.mp_result
        self.mp_metrics["cpu_util"].config(text=f"{r.cpu_utilization:.1f}%")
        self.mp_metrics["throughput"].config(text=f"{r.throughput:.3f} proc/unit")
        self.mp_metrics["avg_turnaround"].config(text=f"{r.avg_turnaround:.2f}")
        self.mp_metrics["avg_waiting"].config(text=f"{r.avg_waiting:.2f}")
        self.mp_metrics["avg_response"].config(text=f"{r.avg_response:.2f}")
        self.mp_metrics["ctx_switches"].config(text=str(r.context_switches))
        self.mp_metrics["max_mp"].config(text=str(r.degree_of_multiprogramming))
        
        self.mp_log.configure(state="normal")
        self.mp_log.delete(1.0, tk.END)
        for event in r.schedule:
            self.mp_log.insert(tk.END, f"[{event.time:6.2f}] {event.process_id:>4} | {event.event_type:<10} | {event.details}\n")
        
        self.mp_log.configure(state="disabled")
        self._draw_mp_gantt()
    
    def _draw_mp_gantt(self):
        """Draw multiprogramming Gantt chart."""
        self.mp_ax.clear()
        self.mp_ax.set_facecolor(COLORS['bg_panel'])
        self.mp_ax.tick_params(colors=COLORS['text_secondary'])
        for spine in self.mp_ax.spines.values():
            spine.set_color(COLORS['border'])
        
        if not self.mp_result:
            self.mp_canvas.draw()
            return
        
        r = self.mp_result
        events = r.schedule
        if not events:
            self.mp_canvas.draw()
            return
        
        # State history is authoritative, including SRTF preemptions.
        merged=[]
        for proc in r.processes:
            for (start,state,_),(end,_,_) in zip(proc.state_history,proc.state_history[1:]):
                if state==ProcessState.RUNNING and end>start:
                    if merged and merged[-1][0]==proc.pid and merged[-1][2]==start:
                        merged[-1]=(proc.pid,merged[-1][1],end)
                    else: merged.append((proc.pid,start,end))

        # Group intervals by process for color assignment
        procs = sorted(set(pid for pid, _, _ in merged))
        colors = ['#6c8cff', '#f87171', '#4ade80', '#fbbf24', '#a78bfa', '#60a5fa']
        color_map = {p: colors[i % len(colors)] for i, p in enumerate(procs)}
        
        # Draw each interval as a bar, grouped by PID on Y-axis
        # Each process gets exactly one horizontal row
        y_positions = []
        y_labels = []
        y = 0.5
        for pid in procs:
            # Collect all intervals for this process
            proc_intervals = [(s, e) for p, s, e in merged if p == pid]
            for start, end in proc_intervals:
                self.mp_ax.barh(y, end - start, left=start, height=0.6,
                               color=color_map[pid], edgecolor='white', linewidth=0.5)
                if end - start > 0.5:
                    self.mp_ax.text(start + (end - start) / 2, y, pid, ha='center', va='center',
                                   color='white', fontsize=8, fontweight='bold')
            y_positions.append(y)
            y_labels.append(pid)
            y += 1
        
        self.mp_ax.set_ylim(0, len(procs) + 0.5)
        self.mp_ax.set_yticks(y_positions)
        self.mp_ax.set_yticklabels(y_labels, color='white')
        # Set X-axis upper limit to the max interval end time + small padding
        max_end = max((e for _, _, e in merged), default=0)
        self.mp_ax.set_xlim(0, max(r.total_time * 1.05, 1))
        self.mp_ax.set_xlabel('Time units (blank = not running)', color='white')
        self.mp_ax.set_title(f'CPU Timeline - {r.algorithm.replace("_", " ").title()}', color='white')
        
        self.mp_fig.tight_layout()
        self.mp_canvas.draw()
    
    def _load_sample_data(self):
        """Load sample processes."""
        sample = generate_sample_processes()
        
        # Multiprogramming view
        for p in sample:
            self.mp_tree.insert("", tk.END, values=(p.pid, p.arrival_time, p.burst_time, p.io_frequency, p.priority))


def create_process_manager_module(parent_window, content_frame):
    """Factory function to create process manager module."""
    return ProcessManagerWindow(parent_window, content_frame)
