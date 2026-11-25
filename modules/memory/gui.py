"""
Memory Manager GUI Module for Mini OS Simulator.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from gui.theme import COLORS, FONTS
from modules.memory.algorithms import (
    PagingConfig, PageTableEntry, PagingSimulator,
    PageReplacementAlgorithm, PageReplacementSimulator, ReplacementResult,
    Segment, SegmentationSimulator,
    AllocationAlgorithm, MemoryBlock, FragmentationSimulator, FragmentationResult,
    generate_sample_paging_config, generate_sample_page_references,
    generate_sample_segments, generate_sample_memory_blocks, generate_sample_process_requests
)


class MemoryWindow:
    """Memory Manager simulation window with tabs for different modules."""

    def __init__(self, parent_window, content_frame):
        self.parent = parent_window
        self.content_frame = content_frame

        self._setup_ui()
        self.frag_algo_var.trace_add('write', self._on_fragmentation_algorithm_change)
        self._load_sample_data()

    def _setup_ui(self):
        """Setup the UI components."""
        # Notebook for different memory modules
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Paging
        self.paging_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.paging_frame, text="Paging")
        self._create_paging_tab()

        # Tab 2: Page Replacement
        self.replacement_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.replacement_frame, text="Page Replacement")
        self._create_replacement_tab()

        # Tab 3: Segmentation
        self.segmentation_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.segmentation_frame, text="Segmentation")
        self._create_segmentation_tab()

        # Tab 4: Fragmentation
        self.fragmentation_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.fragmentation_frame, text="Fragmentation")
        self._create_fragmentation_tab()

    # ==================== PAGING TAB ====================

    def _make_panels(self, parent):
        """Use the same split and scrollable controls in every tab."""
        pane = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        holder = ttk.Frame(pane)
        right = ttk.Frame(pane)
        pane.add(holder, weight=1)
        pane.add(right, weight=1)
        canvas = tk.Canvas(holder, bg=COLORS['bg_panel'], highlightthickness=0,
                           width=1, height=1)
        vertical = ttk.Scrollbar(holder, orient=tk.VERTICAL, command=canvas.yview)
        horizontal = ttk.Scrollbar(holder, orient=tk.HORIZONTAL, command=canvas.xview)
        canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        canvas.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        left = ttk.Frame(canvas)
        window = canvas.create_window(0, 0, window=left, anchor='nw')
        def sync(event=None):
            width = max(canvas.winfo_width(), left.winfo_reqwidth())
            height = max(canvas.winfo_height(), left.winfo_reqheight())
            canvas.itemconfigure(window, width=width, height=height)
            canvas.configure(scrollregion=(0, 0, width, height))
        canvas.bind('<Configure>', sync)
        left.bind('<Configure>', sync)
        # Match the initial divider on every tab. Preserve manual sash changes.
        previous = [0, 0.5]
        def resize(event):
            if event.width <= 2:
                return
            previous[0] = event.width
            pane.sashpos(0, round(event.width * previous[1]))
        def remember(event):
            if pane.winfo_width() > 2:
                previous[1] = pane.sashpos(0) / pane.winfo_width()
        pane.bind('<Configure>', resize)
        pane.bind('<ButtonRelease-1>', remember, add='+')
        return left, right

    def _table(self, parent, columns, widths, height=5):
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        tree = ttk.Treeview(wrapper, columns=columns, show='headings', height=height)
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, minwidth=42, anchor=tk.CENTER)
        vertical = ttk.Scrollbar(wrapper, orient=tk.VERTICAL, command=tree.yview)
        horizontal = ttk.Scrollbar(wrapper, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)
        return tree

    def _text_output(self, parent, height=5):
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill=tk.BOTH, expand=True)
        text = tk.Text(wrapper, height=height, width=32, wrap=tk.WORD,
                       bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
                       font=FONTS['mono'], highlightthickness=0)
        scroll = ttk.Scrollbar(wrapper, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        return text

    def _chart(self, parent, title, prefix, scrollable=False):
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.pack(fill=tk.BOTH, expand=True)
        figure = Figure(figsize=(3, 3), dpi=100, facecolor=COLORS['bg_panel'])
        ax = figure.add_subplot(111)
        ax.set_facecolor(COLORS['bg_panel'])
        if scrollable:
            viewport = tk.Canvas(frame, bg=COLORS['bg_panel'], highlightthickness=0,
                                 width=1, height=1)
            vbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=viewport.yview)
            hbar = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=viewport.xview)
            viewport.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
            frame.rowconfigure(0, weight=1)
            frame.columnconfigure(0, weight=1)
            viewport.grid(row=0, column=0, sticky='nsew')
            vbar.grid(row=0, column=1, sticky='ns')
            hbar.grid(row=1, column=0, sticky='ew')
            canvas = FigureCanvasTkAgg(figure, master=viewport)
            window = viewport.create_window(0, 0, window=canvas.get_tk_widget(), anchor='nw')
            def fit(event=None):
                minimum = getattr(self, prefix + '_chart_min', (320, 260))
                width = max(viewport.winfo_width(), minimum[0])
                height = max(viewport.winfo_height(), minimum[1])
                viewport.itemconfigure(window, width=width, height=height)
                viewport.configure(scrollregion=(0, 0, width, height))
            viewport.bind('<Configure>', fit)
            setattr(self, prefix + '_chart_fit', fit)
        else:
            canvas = FigureCanvasTkAgg(figure, master=frame)
            widget = canvas.get_tk_widget()
            widget.configure(width=1, height=1)
            widget.pack(fill=tk.BOTH, expand=True)
        setattr(self, prefix + '_fig', figure)
        setattr(self, prefix + '_ax', ax)
        setattr(self, prefix + '_canvas', canvas)
        ax.set_axis_off()
        ax.text(.5, .5, 'No simulation results yet.', transform=ax.transAxes,
                ha='center', va='center', color=COLORS['text_secondary'])
        canvas.draw_idle()

    def _create_paging_tab(self):
        left, right = self._make_panels(self.paging_frame)
        self._create_paging_config(left)
        self._create_paging_page_table(left)
        self._create_paging_translation(left)
        self._create_paging_visualization(right)

    def _create_paging_config(self, parent):
        frame = ttk.LabelFrame(parent, text='Memory Configuration', padding=8)
        frame.pack(fill=tk.X, pady=(0, 8))
        self.logical_mem_var = tk.IntVar(value=64)
        self.physical_mem_var = tk.IntVar(value=32)
        self.page_size_var = tk.IntVar(value=4)
        for i, (label, var, lo, hi) in enumerate([
            ('Logical Memory (KB):', self.logical_mem_var, 4, 1024),
            ('Physical Memory (KB):', self.physical_mem_var, 4, 1024),
            ('Page Size (KB):', self.page_size_var, 1, 64)]):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky='w', padx=2, pady=2)
            ttk.Spinbox(frame, from_=lo, to=hi, textvariable=var, width=8).grid(row=i, column=1, sticky='ew', padx=2, pady=2)
        frame.columnconfigure(1, weight=1)
        ttk.Button(frame, text='Apply', command=self._apply_paging_config).grid(row=3, column=0, sticky='w', pady=4)
        derived = ttk.Frame(frame)
        derived.grid(row=3, column=1, sticky='ew')
        self.pages_label = ttk.Label(derived, text='Pages: --')
        self.frames_label = ttk.Label(derived, text='Frames: --')
        self.pages_label.pack(side=tk.LEFT, padx=3)
        self.frames_label.pack(side=tk.LEFT, padx=3)

    def _create_paging_page_table(self, parent):
        frame = ttk.LabelFrame(parent, text='Page Table', padding=8)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.page_table_tree = self._table(frame, ('Page','Frame','Valid'), (70,70,65), 5)
        edit = ttk.Frame(frame)
        edit.pack(fill=tk.X, pady=3)
        self.pt_page_var = tk.IntVar()
        self.pt_frame_var = tk.IntVar(value=-1)
        self.pt_valid_var = tk.BooleanVar()
        ttk.Label(edit, text='Page:').grid(row=0, column=0, padx=2)
        self.pt_page_spin = ttk.Spinbox(edit, from_=0, to=15, textvariable=self.pt_page_var, width=5)
        self.pt_page_spin.grid(row=0, column=1, padx=2)
        ttk.Label(edit, text='Frame:').grid(row=0, column=2, padx=2)
        self.pt_frame_spin = ttk.Spinbox(edit, from_=-1, to=15, textvariable=self.pt_frame_var, width=5)
        self.pt_frame_spin.grid(row=0, column=3, padx=2)
        ttk.Checkbutton(edit, text='Valid', variable=self.pt_valid_var).grid(row=0, column=4, padx=2)
        actions = ttk.Frame(frame)
        actions.pack(fill=tk.X, pady=3)
        ttk.Button(actions, text='Update', command=self._update_page_table_entry).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions, text='Auto-Assign', command=self._auto_assign_frames).pack(side=tk.LEFT, padx=2)
        self.pt_status_var = tk.StringVar(value='')
        self.pt_status_label = ttk.Label(frame, textvariable=self.pt_status_var, foreground=COLORS['warning'], font=FONTS['small'], wraplength=260)
        self.pt_status_label.pack(fill=tk.X, pady=2)
        frame.bind('<Configure>', lambda event: self.pt_status_label.configure(wraplength=max(80, event.width-20)))

    def _create_paging_translation(self, parent):
        frame = ttk.LabelFrame(parent, text='Address Translation', padding=8)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text='Logical Address (bytes):').pack(anchor=tk.W)
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=4)
        self.logical_addr_var = tk.IntVar(value=0)
        self.logical_addr_entry = ttk.Entry(row, textvariable=self.logical_addr_var, width=12)
        self.logical_addr_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,4))
        ttk.Button(row, text='Translate', command=self._translate_address).pack(side=tk.LEFT)
        self.translation_result = self._text_output(frame, 6)
        self.logical_addr_var.trace_add('write', self._clear_paging_translation)

    def _clear_paging_translation(self, *args):
        self.translation_result.delete('1.0', tk.END)

    def _create_paging_visualization(self, parent):
        self._chart(parent, 'Memory Map', 'paging', scrollable=True)

    def _apply_paging_config(self):
        """Apply paging configuration."""
        try:
            logical = self.logical_mem_var.get() * 1024
            physical = self.physical_mem_var.get() * 1024
            page = self.page_size_var.get() * 1024

            if min(logical, physical, page) <= 0:
                messagebox.showerror("Error", "Memory and page sizes must be positive")
                return
            if logical % page != 0 or physical % page != 0:
                messagebox.showerror("Error", "Memory sizes must be multiples of page size")
                return

            self.paging_config = PagingConfig(logical, physical, page)
            self.page_table = [PageTableEntry() for _ in range(self.paging_config.num_pages)]

            self.pages_label.config(text=f"Pages: {self.paging_config.num_pages}")
            self.frames_label.config(text=f"Frames: {self.paging_config.num_frames}")

            self._refresh_page_table()
            self._draw_paging_visualization()
            self._refresh_translation()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _refresh_page_table(self):
        """Refresh page table display."""
        for item in self.page_table_tree.get_children():
            self.page_table_tree.delete(item)

        for i, entry in enumerate(self.page_table):
            self.page_table_tree.insert("", tk.END, values=(
                i, entry.frame_number if entry.valid else "-", "Yes" if entry.valid else "No"
            ))

        # Update spinbox ranges
        self.pt_page_spin.configure(to=max(0, self.paging_config.num_pages-1))
        self.pt_frame_spin.configure(to=max(-1, self.paging_config.num_frames-1))
        self.pt_status_var.set("")
        self.pt_page_var.set(0)
        self.pt_frame_var.set(-1)
        self.pt_valid_var.set(False)

    def _update_page_table_entry(self):
        """Update a page table entry."""
        if not hasattr(self, 'paging_config'):
            return

        try:
            page = self.pt_page_var.get()
            frame = self.pt_frame_var.get()
            valid = self.pt_valid_var.get()
        except (tk.TclError, ValueError):
            messagebox.showerror("Error", "Enter integer page and frame numbers")
            return
        if not 0 <= page < self.paging_config.num_pages:
            messagebox.showerror("Error", f"Page number must be 0-{self.paging_config.num_pages-1}")
            return

        if valid and (frame < 0 or frame >= self.paging_config.num_frames):
            messagebox.showerror("Error", f"Frame number must be 0-{self.paging_config.num_frames-1}")
            return

        # Handle frame reassignment: find any other page mapped to this frame
        reassigned_from = None
        if valid:
            for i, entry in enumerate(self.page_table):
                if i != page and entry.valid and entry.frame_number == frame:
                    # Unmap the previous page from this frame (just like IRL)
                    self.page_table[i] = PageTableEntry(frame_number=-1, valid=False)
                    reassigned_from = i
                    break

        self.page_table[page] = PageTableEntry(frame_number=frame if valid else -1, valid=valid)
        self._refresh_page_table()
        self._draw_paging_visualization()
        self._refresh_translation()

        # Show inline status message
        if reassigned_from is not None:
            self.pt_status_var.set(
                f"Frame {frame} reassigned from Page {reassigned_from} to Page {page}; "
                f"Page {reassigned_from} is now invalid"
            )
            self.pt_status_label.config(foreground=ttk.Style().lookup("TLabel", "foreground") or COLORS["text_primary"])
        elif valid:
            self.pt_status_var.set(
                f"Page {page} assigned to Frame {frame}"
            )
            self.pt_status_label.config(foreground=ttk.Style().lookup("TLabel", "foreground") or COLORS["text_primary"])
        else:
            self.pt_status_var.set(
                f"Page {page} invalidated"
            )
            self.pt_status_label.config(foreground=ttk.Style().lookup("TLabel", "foreground") or COLORS["text_primary"])

    def _auto_assign_frames(self):
        """Auto-assign frames to pages."""
        if not hasattr(self, 'paging_config'):
            return

        # Reset every entry, including previously mapped high-numbered pages.
        self.page_table = [
            PageTableEntry(frame_number=i, valid=True)
            if i < self.paging_config.num_frames else PageTableEntry()
            for i in range(self.paging_config.num_pages)
        ]

        self._refresh_page_table()
        self._draw_paging_visualization()
        self._refresh_translation()

    def _translate_address(self):
        """Translate logical address using live page table state."""
        if not hasattr(self, 'paging_config'):
            messagebox.showerror("Error", "Apply configuration first")
            return

        try:
            addr = self.logical_addr_var.get()
        except (tk.TclError, ValueError):
            self.translation_result.delete('1.0', tk.END)
            self.translation_result.insert(tk.END, 'Enter an integer logical address.')
            return
        config = self.paging_config

        # Validate address bounds
        if addr < 0 or addr >= config.logical_memory_size:
            self.translation_result.delete(1.0, tk.END)
            self.translation_result.insert(tk.END,
                f"Logical Address: {addr}\n"
                f"Error: Address out of bounds.\n"
                f"Valid range: 0 - {config.logical_memory_size - 1}\n"
                f"(Logical Memory: {config.logical_memory_size // 1024} KB)"
            )
            self.translation_result.tag_add("error", "1.0", "end")
            self.translation_result.tag_config("error", foreground=COLORS["danger"])
            return

        page_size = config.page_size
        page_num = addr // page_size
        offset = addr % page_size

        # Read live page table entry
        if page_num >= len(self.page_table):
            self.translation_result.delete(1.0, tk.END)
            self.translation_result.insert(tk.END,
                f"Logical Address: {addr}\n"
                f"Error: Page number {page_num} exceeds page table size ({len(self.page_table)})\n"
            )
            self.translation_result.tag_add("error", "1.0", "end")
            self.translation_result.tag_config("error", foreground=COLORS["danger"])
            return

        entry = self.page_table[page_num]

        # Check valid bit and frame assignment
        if not entry.valid:
            self.translation_result.delete(1.0, tk.END)
            self.translation_result.insert(tk.END,
                f"Logical Address: {addr}\n"
                f"  Page Number: {addr} // {page_size} = {page_num}\n"
                f"  Offset: {addr} % {page_size} = {offset}\n"
                f"  Page Table[{page_num}]: Frame = -, Valid = No\n"
                f"  Result: Page Fault / Invalid Page\n"
            )
            self.translation_result.tag_add("error", "1.0", "end")
            self.translation_result.tag_config("error", foreground=COLORS["danger"])
            return

        if entry.frame_number < 0 or entry.frame_number >= config.num_frames:
            self.translation_result.delete(1.0, tk.END)
            self.translation_result.insert(tk.END,
                f"Logical Address: {addr}\n"
                f"  Page Number: {addr} // {page_size} = {page_num}\n"
                f"  Offset: {addr} % {page_size} = {offset}\n"
                f"  Page Table[{page_num}]: Frame = {entry.frame_number}, Valid = Yes\n"
                f"  Error: Invalid frame number\n"
                f"  Result: Page Fault / Invalid Page\n"
            )
            self.translation_result.tag_add("error", "1.0", "end")
            self.translation_result.tag_config("error", foreground=COLORS["danger"])
            return

        # Valid translation
        physical_address = entry.frame_number * page_size + offset
        self.translation_result.delete(1.0, tk.END)
        self.translation_result.insert(tk.END,
            f"Logical Address: {addr}\n"
            f"  Page Number: {addr} // {page_size} = {page_num}\n"
            f"  Offset: {addr} % {page_size} = {offset}\n"
            f"  Page Table[{page_num}]: Frame = {entry.frame_number}, Valid = Yes\n"
            f"  Physical Address: {entry.frame_number} * {page_size} + {offset} = {physical_address}\n"
        )
        self.translation_result.tag_add("success", "1.0", "end")
        self.translation_result.tag_config("success", foreground=COLORS["success"])

    def _refresh_translation(self):
        """Refresh address translation when page table changes.

        Re-runs translation for the current Logical Address input,
        or clears the output box if the input is empty.
        """
        addr_text = self.logical_addr_entry.get().strip()
        if not addr_text:
            self.translation_result.delete(1.0, tk.END)
            return
        self._translate_address()

    def _draw_paging_visualization(self):
        ax=self.paging_ax
        ax.clear()
        ax.set_facecolor(COLORS['bg_panel'])
        ax.set_axis_off()
        if not hasattr(self,'paging_config'):
            self.paging_canvas.draw_idle()
            return
        config=self.paging_config
        n=max(config.num_pages,config.num_frames)
        # Show all pages AND frames, including when physical memory is larger.
        self.paging_chart_min=(340,max(280,n*24+80))
        self.paging_chart_fit()
        occupied={entry.frame_number:i for i,entry in enumerate(self.page_table) if entry.valid}
        for i,entry in enumerate(self.page_table):
            label=f'P{i} -> F{entry.frame_number}' if entry.valid else f'P{i} (invalid)'
            ax.barh(i,.95,left=0,height=.78,color=COLORS['accent'] if entry.valid else COLORS['bg_input'],edgecolor=COLORS['border_light'])
            ax.text(.475,i,label,ha='center',va='center',color=COLORS['text_primary'],fontsize=8)
        for i in range(config.num_frames):
            used=occupied.get(i)
            label=f'F{i} <- P{used}' if used is not None else f'F{i} (free)'
            ax.barh(i,.95,left=1.15,height=.78,color=COLORS['accent_dim'] if used is not None else COLORS['bg_input'],edgecolor=COLORS['border_light'])
            ax.text(1.625,i,label,ha='center',va='center',color=COLORS['text_primary'],fontsize=8)
        ax.set_xlim(-.04,2.14)
        ax.set_ylim(n-.5,-.5)
        ax.set_title('Logical Pages                 Physical Frames',color=COLORS['text_primary'],fontsize=10,pad=12)
        self.paging_fig.subplots_adjust(left=.04,right=.96,top=1-min(.12,36/(self.paging_chart_min[1])),bottom=.025)
        self.paging_canvas.draw_idle()

    # ==================== PAGE REPLACEMENT TAB ====================

    def _create_replacement_tab(self):
        left, right = self._make_panels(self.replacement_frame)
        self._create_replacement_config(left)
        self._create_replacement_results(left)
        self._create_replacement_visualization(right)

    def _create_replacement_config(self, parent):
        frame = ttk.LabelFrame(parent, text='Configuration', padding=8)
        frame.pack(fill=tk.X, pady=(0,8))
        ttk.Label(frame, text='Reference String:').pack(anchor=tk.W)
        self.ref_string_var = tk.StringVar(value='7,0,1,2,0,3,0,4,2,3,0,3,2,1,2,0,1,7,0,1')
        ttk.Entry(frame, textvariable=self.ref_string_var, width=25).pack(fill=tk.X, pady=4)
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text='Number of Frames:').pack(side=tk.LEFT, padx=(0,6))
        self.num_frames_var = tk.IntVar(value=3)
        ttk.Spinbox(row, from_=1, to=10, textvariable=self.num_frames_var, width=5).pack(side=tk.LEFT)
        self.replace_algo_var = tk.StringVar(value=PageReplacementAlgorithm.FIFO.value)
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=4)
        for algo in PageReplacementAlgorithm:
            ttk.Radiobutton(row, text=algo.value.upper(), variable=self.replace_algo_var, value=algo.value).pack(side=tk.LEFT, padx=2)
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=4)
        ttk.Button(row, text='Run Simulation', command=self._run_replacement).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text='Compare All', command=self._compare_all_replacement).pack(side=tk.LEFT, padx=2)

    def _create_replacement_results(self, parent):
        frame = ttk.LabelFrame(parent, text='Results', padding=8)
        frame.pack(fill=tk.BOTH, expand=True)
        metrics = ttk.Frame(frame)
        metrics.pack(fill=tk.X, pady=(0,6))
        self.replace_metrics = {}
        for i,(label,key) in enumerate([('Page Faults','faults'),('Page Hits','hits'),('Fault Rate','fault_rate'),('Hit Rate','hit_rate')]):
            row,col=divmod(i,2)
            f=ttk.Frame(metrics)
            f.grid(row=row,column=col,sticky='w',padx=4,pady=2)
            ttk.Label(f,text=label+':',font=FONTS['small']).pack(side=tk.LEFT)
            self.replace_metrics[key]=ttk.Label(f,text='--',font=FONTS['small'])
            self.replace_metrics[key].pack(side=tk.LEFT,padx=4)
        self.replace_tree=self._table(frame, ('Step','Reference','Frames','Fault/Hit','Replaced'), (45,65,130,65,65), 8)

    def _create_replacement_visualization(self, parent):
        self._chart(parent, 'Frame State Timeline', 'replace', scrollable=True)

    def _run_replacement(self):
        """Run page replacement simulation."""
        try:
            ref_str = [int(x.strip()) for x in self.ref_string_var.get().split(",") if x.strip()]
            num_frames = self.num_frames_var.get()
            algo = PageReplacementAlgorithm(self.replace_algo_var.get())

            result = PageReplacementSimulator.run_algorithm(algo, ref_str, num_frames)
            self._display_replacement_result(result)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _compare_all_replacement(self):
        """Compare all algorithms."""
        try:
            ref_str = [int(x.strip()) for x in self.ref_string_var.get().split(",") if x.strip()]
            num_frames = self.num_frames_var.get()

            results = PageReplacementSimulator.compare_all(ref_str, num_frames)

            # Show comparison dialog
            self._show_comparison_dialog(results)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _show_comparison_dialog(self, results: dict):
        """Show algorithm comparison dialog."""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Algorithm Comparison")
        dialog.geometry("500x300")
        dialog.configure(bg=COLORS["bg_panel"])

        text = tk.Text(dialog, bg=COLORS["bg_panel"], fg=COLORS["text_primary"], font=FONTS["mono"])
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text.insert(tk.END, f"{'Algorithm':<12} {'Faults':>8} {'Hits':>8} {'Fault Rate':>12} {'Hit Rate':>10}\n")
        text.insert(tk.END, "-" * 55 + "\n")

        for algo, result in results.items():
            text.insert(tk.END, 
                f"{algo.value.upper():<12} {result.total_faults:>8} {result.total_hits:>8} "
                f"{result.fault_rate:>11.2%} {result.hit_rate:>9.2%}\n"
            )

        text.config(state=tk.DISABLED)

    def _display_replacement_result(self, result: ReplacementResult):
        """Display replacement result."""
        self.replace_metrics["faults"].config(text=str(result.total_faults))
        self.replace_metrics["hits"].config(text=str(result.total_hits))
        self.replace_metrics["fault_rate"].config(text=f"{result.fault_rate:.2%}")
        self.replace_metrics["hit_rate"].config(text=f"{result.hit_rate:.2%}")

        # Update table
        for item in self.replace_tree.get_children():
            self.replace_tree.delete(item)

        for step, (ref, frames, fault, replaced) in enumerate(zip(
            result.reference_string, result.frame_states, result.page_faults, result.replaced_pages
        )):
            frame_str = " | ".join(str(f) if f is not None else "-" for f in frames)
            self.replace_tree.insert("", tk.END, values=(
                step, ref, frame_str, "Fault" if fault else "Hit",
                str(replaced) if replaced is not None else "-"
            ))

        # Draw visualization
        self._draw_replacement_visualization(result)

    def _draw_replacement_visualization(self,result):
        ax=self.replace_ax
        ax.clear()
        ax.set_facecolor(COLORS['bg_panel'])
        ax.set_axis_on()
        ax.tick_params(colors=COLORS['text_secondary'])
        for spine in ax.spines.values():
            spine.set_color(COLORS['border_light'])
        if not result.frame_states:
            self.replace_canvas.draw_idle()
            return
        n=len(result.frame_states)
        k=result.num_frames
        self.replace_chart_min=(max(360,36*n+90),max(260,36*k+125))
        self.replace_chart_fit()
        palette=['#6c8cff','#f87171','#4ade80','#fbbf24','#a78bfa','#60a5fa','#34d399','#fb923c']
        colors={p:palette[i%len(palette)] for i,p in enumerate(sorted(set(result.reference_string)))}
        for step,state in enumerate(result.frame_states):
            for i,page in enumerate(state):
                ax.barh(i,1,left=step,height=.86,color=colors.get(page,COLORS['bg_input']),edgecolor=COLORS['border'],linewidth=.6)
                ax.text(step+.5,i,str(page) if page is not None else '-',ha='center',va='center',fontsize=8,color='#10131a' if page is not None else COLORS['text_secondary'])
            ax.text(step+.5,k,'F' if result.page_faults[step] else 'H',ha='center',va='center',fontsize=8,color=COLORS['danger'] if result.page_faults[step] else COLORS['success'])
        ax.set_xlim(0,n)
        ax.set_ylim(k+.55,-.55)
        ax.set_xticks([i+.5 for i in range(n)])
        ax.set_xticklabels([str(p) for p in result.reference_string],fontsize=8)
        ax.xaxis.tick_top()
        ax.xaxis.set_label_position('top')
        ax.set_xlabel('Reference string (left to right)',color=COLORS['text_primary'],fontsize=9)
        ax.set_yticks(range(k+1))
        ax.set_yticklabels([f'F{i}' for i in range(k)]+['Result'])
        ax.set_title(result.algorithm.value.upper()+'  |  F = Fault, H = Hit',color=COLORS['text_primary'],fontsize=10,pad=12)
        self.replace_fig.subplots_adjust(left=min(.20,65/self.replace_chart_min[0]),right=.98,top=.76,bottom=.10)
        self.replace_canvas.draw_idle()

    # ==================== SEGMENTATION TAB ====================

    def _create_segmentation_tab(self):
        left, right = self._make_panels(self.segmentation_frame)
        self._create_segmentation_segments(left)
        self._create_segmentation_translation(left)
        self._create_segmentation_visualization(right)

    def _create_segmentation_segments(self, parent):
        frame=ttk.LabelFrame(parent,text='Segments',padding=8)
        frame.pack(fill=tk.BOTH,expand=True,pady=(0,8))
        self.segment_tree=self._table(frame,('ID','Name','Base','Limit'),(45,100,75,75),5)
        form=ttk.Frame(frame)
        form.pack(fill=tk.X,pady=4)
        self.seg_id_var=tk.IntVar()
        self.seg_name_var=tk.StringVar()
        self.seg_base_var=tk.IntVar()
        self.seg_limit_var=tk.IntVar()
        for i,(label,var) in enumerate([('ID:',self.seg_id_var),('Name:',self.seg_name_var),('Base:',self.seg_base_var),('Limit:',self.seg_limit_var)]):
            r,c=divmod(i,2)
            ttk.Label(form,text=label).grid(row=r,column=2*c,sticky='w',padx=2,pady=2)
            w=ttk.Spinbox(form,from_=0,to=15,textvariable=var,width=6) if i==0 else ttk.Entry(form,textvariable=var,width=9)
            w.grid(row=r,column=2*c+1,sticky='ew',padx=2,pady=2)
        form.columnconfigure(1,weight=1)
        form.columnconfigure(3,weight=1)
        actions=ttk.Frame(frame)
        actions.pack(fill=tk.X,pady=3)
        for i,(label,cmd) in enumerate([('Add',self._add_segment),('Update',self._update_segment),('Remove',self._remove_segment),('Load Sample',self._load_sample_segments)]):
            r,c=divmod(i,2)
            ttk.Button(actions,text=label,command=cmd).grid(row=r,column=c,sticky='ew',padx=2,pady=2)
            actions.columnconfigure(c,weight=1)
        self.segment_tree.bind('<<TreeviewSelect>>',self._on_segment_select)

    def _create_segmentation_translation(self,parent):
        frame=ttk.LabelFrame(parent,text='Address Translation',padding=8)
        frame.pack(fill=tk.BOTH,expand=True)
        row=ttk.Frame(frame)
        row.pack(fill=tk.X,pady=4)
        self.seg_trans_seg_var=tk.IntVar(value=0)
        self.seg_trans_off_var=tk.IntVar(value=0)
        ttk.Label(row,text='Segment:').grid(row=0,column=0,padx=2,pady=2)
        ttk.Spinbox(row,from_=0,to=15,textvariable=self.seg_trans_seg_var,width=5).grid(row=0,column=1,padx=2)
        ttk.Label(row,text='Offset:').grid(row=0,column=2,padx=2)
        ttk.Entry(row,textvariable=self.seg_trans_off_var,width=9).grid(row=0,column=3,sticky='ew',padx=2)
        row.columnconfigure(3,weight=1)
        ttk.Button(row,text='Translate',command=self._translate_segmented).grid(row=1,column=0,columnspan=4,sticky='w',pady=3)
        self.seg_translation_result=self._text_output(frame,6)
        self.seg_translation_result.configure(state=tk.DISABLED)
        self.seg_trans_seg_var.trace_add('write', self._clear_segment_translation)
        self.seg_trans_off_var.trace_add('write', self._clear_segment_translation)
        self._clear_segment_translation()

    def _clear_segment_translation(self, *args):
        """Do not display a translation for inputs that have changed."""
        self.seg_translation_result.configure(state=tk.NORMAL)
        self.seg_translation_result.delete('1.0', tk.END)
        self.seg_translation_result.insert(tk.END, 'Enter a segment and offset, then click Translate.')
        self.seg_translation_result.configure(state=tk.DISABLED)

    def _clear_segment_editor(self):
        """Clear fields that otherwise describe a deleted segment."""
        self.seg_id_var.set(0)
        self.seg_name_var.set('')
        self.seg_base_var.set(0)
        self.seg_limit_var.set(0)

    def _create_segmentation_visualization(self, parent):
        self._chart(parent, 'Memory Map', 'seg', scrollable=False)
        widget = self.seg_canvas.get_tk_widget()
        self.seg_map_details = tk.StringVar(value='Click a segment or free block to view its size.')
        details = tk.Label(widget.master, textvariable=self.seg_map_details,
                           bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
                           font=FONTS['body'], anchor='w', justify=tk.LEFT,
                           padx=8, pady=8, wraplength=300)
        details.pack(side=tk.BOTTOM, fill=tk.X, before=widget)
        details.bind('<Configure>', lambda event: details.configure(wraplength=max(80, event.width - 16)))
        self.seg_canvas.mpl_connect('button_press_event', self._on_seg_map_click)

    def _on_seg_map_click(self, event):
        """Show the byte count and inclusive address range of the clicked block."""
        if event.button != 1 or event.inaxes is not self.seg_ax:
            return
        if event.xdata is None or event.ydata is None or not -0.18 <= event.ydata <= 0.18:
            return
        for start, size, label in self.seg_map_blocks:
            if start <= event.xdata < start + size:
                self.seg_map_details.set(
                    f'{label} | Size: {size:,} bytes\n'
                    f'Address range: {start:,} - {start + size - 1:,}')
                return

    def _add_segment(self):
        """Add a segment."""
        try:
            sid = self.seg_id_var.get()
            name = self.seg_name_var.get().strip()
            base = self.seg_base_var.get()
            limit = self.seg_limit_var.get()

            if sid < 0 or base < 0:
                messagebox.showerror("Error", "Segment ID and base must be non-negative")
                return
            if not name:
                messagebox.showerror("Error", "Segment name required")
                return
            if limit <= 0:
                messagebox.showerror("Error", "Limit must be positive")
                return
            if any(s.segment_id == sid for s in self.segments):
                messagebox.showerror("Error", f"Segment ID {sid} already exists")
                return

            # Check overlap
            new_start = base
            new_end = base + limit - 1
            for s in self.segments:
                if not (new_end < s.base or new_start > s.end):
                    messagebox.showerror("Error", f"Overlaps with segment {s.segment_id} ({s.name})")
                    return

            self.segments.append(Segment(sid, name, base, limit))
            self.segments.sort(key=lambda s: s.base)
            self._refresh_segments()
            self._draw_segmentation_visualization()

        except (tk.TclError, ValueError):
            messagebox.showerror("Error", "Invalid values")

    def _update_segment(self):
        """Update selected segment."""
        selection = self.segment_tree.selection()
        if not selection:
            return

        try:
            old_id = self.segment_tree.item(selection[0])['values'][0]
            sid = self.seg_id_var.get()
            name = self.seg_name_var.get().strip()
            base = self.seg_base_var.get()
            limit = self.seg_limit_var.get()

            if not name or limit <= 0 or sid < 0 or base < 0:
                messagebox.showerror("Error", "Enter a name, positive limit, and non-negative ID and base")
                return
            if sid != old_id and any(s.segment_id == sid for s in self.segments):
                messagebox.showerror("Error", f"Segment ID {sid} already exists")
                return

            # Find and update
            for i, s in enumerate(self.segments):
                if s.segment_id == old_id:
                    # Check overlap with others
                    new_start = base
                    new_end = base + limit - 1
                    for j, other in enumerate(self.segments):
                        if j != i and not (new_end < other.base or new_start > other.end):
                            messagebox.showerror("Error", f"Overlaps with segment {other.segment_id}")
                            return

                    self.segments[i] = Segment(sid, name, base, limit)
                    break

            self.segments.sort(key=lambda s: s.base)
            self._refresh_segments()
            self._draw_segmentation_visualization()

        except (tk.TclError, ValueError):
            messagebox.showerror("Error", "Invalid values")

    def _remove_segment(self):
        """Remove selected segment."""
        selection = self.segment_tree.selection()
        if not selection:
            return

        sid = self.segment_tree.item(selection[0])['values'][0]
        self.segments = [s for s in self.segments if s.segment_id != sid]
        self._refresh_segments()
        self._clear_segment_editor()
        self._draw_segmentation_visualization()

    def _load_sample_segments(self):
        """Load sample segments."""
        self.segments = generate_sample_segments()
        self._refresh_segments()
        self._clear_segment_editor()
        self._draw_segmentation_visualization()

    def _on_segment_select(self, event):
        """Handle segment selection."""
        selection = self.segment_tree.selection()
        if not selection:
            return

        values = self.segment_tree.item(selection[0])['values']
        self.seg_id_var.set(values[0])
        self.seg_name_var.set(values[1])
        self.seg_base_var.set(values[2])
        self.seg_limit_var.set(values[3])

    def _refresh_segments(self):
        """Refresh segment display and invalidate the old translation."""
        self._clear_segment_translation()
        for item in self.segment_tree.get_children():
            self.segment_tree.delete(item)

        for s in self.segments:
            self.segment_tree.insert("", tk.END, values=(s.segment_id, s.name, s.base, s.limit))

    def _translate_segmented(self):
        """Translate segmented address."""
        try:
            seg_id = self.seg_trans_seg_var.get()
            offset = self.seg_trans_off_var.get()
        except (tk.TclError, ValueError):
            messagebox.showerror('Error', 'Enter a valid integer segment ID and offset')
            return

        result = SegmentationSimulator.translate_address(self.segments, (seg_id, offset))
        explanation = SegmentationSimulator.explain_translation(self.segments, (seg_id, offset))

        self.seg_translation_result.configure(state=tk.NORMAL)
        self.seg_translation_result.tag_remove("error", "1.0", "end")
        self.seg_translation_result.delete(1.0, tk.END)
        self.seg_translation_result.insert(tk.END, explanation.replace("âœ“", "OK").replace("âœ—", "Invalid"))

        if not result.valid:
            self.seg_translation_result.tag_add("error", "1.0", "end")
            self.seg_translation_result.tag_config("error", foreground=COLORS["danger"])
        self.seg_translation_result.configure(state=tk.DISABLED)

    def _draw_address_map(self, prefix, parts, title):
        ax=getattr(self,prefix+'_ax')
        fig=getattr(self,prefix+'_fig')
        canvas=getattr(self,prefix+'_canvas')
        ax.clear()
        ax.set_facecolor(COLORS['bg_panel'])
        ax.set_axis_on()
        ax.tick_params(colors=COLORS['text_secondary'])
        for spine in ax.spines.values():
            spine.set_color(COLORS['border_light'])
        if not parts:
            ax.set_axis_off()
            ax.text(.5,.5,'No memory blocks configured.',transform=ax.transAxes,ha='center',va='center',color=COLORS['text_secondary'])
            canvas.draw_idle()
            return
        end=max(start+size for start,size,label,color,free in parts)
        labels=[]
        for start,size,label,color,free in parts:
            patch=ax.barh(0,size,left=start,height=.36,color=color,edgecolor=COLORS['text_secondary'],linewidth=.7,hatch='///' if free else None)[0]
            text=ax.text(start+size/2,0,label,ha='center',va='center',fontsize=8,color=COLORS['text_primary'] if free else '#10131a',clip_on=True)
            text.set_clip_path(patch)
            labels.append((text,size))
        ax.set_xlim(0,max(1,end))
        ax.set_ylim(-.6,.6)
        ax.set_yticks([])
        ax.set_xlabel('Memory Address (bytes)',color=COLORS['text_primary'])
        ax.set_title(title,color=COLORS['text_primary'],fontsize=11)
        from matplotlib.ticker import MaxNLocator
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5,integer=True))
        fig.subplots_adjust(left=.11,right=.95,bottom=.23,top=.85)
        # A short label stays inside its block even when the window shrinks.
        def fit_labels(event=None):
            width=ax.bbox.width
            for text,size in labels:
                available=width*size/max(1,end)
                text.set_visible(available >= max(30,len(text.get_text())*7+8))
            canvas.draw_idle()
        old=getattr(self,prefix+'_resize_cid',None)
        if old is not None:
            canvas.mpl_disconnect(old)
        setattr(self,prefix+'_resize_cid',canvas.mpl_connect('resize_event',fit_labels))
        fit_labels()

    def _draw_segmentation_visualization(self):
        colors=['#6c8cff','#f87171','#4ade80','#fbbf24','#a78bfa','#60a5fa','#34d399','#fb923c']
        parts=[]
        self.seg_map_blocks=[]
        self.seg_map_details.set('Click a segment or free block to view its size.')
        at=0
        for seg in sorted(self.segments,key=lambda s:s.base):
            if seg.base>at:
                parts.append((at,seg.base-at,'Free',COLORS['bg_input'],True))
                self.seg_map_blocks.append((at,seg.base-at,'Free memory'))
            # Use the segment ID, not its position in the sorted table.
            parts.append((seg.base,seg.limit, f'S{seg.segment_id}', colors[seg.segment_id%len(colors)],False))
            self.seg_map_blocks.append((seg.base,seg.limit,f'S{seg.segment_id} ({seg.name})'))
            at=seg.base+seg.limit
        self._draw_address_map('seg',parts,'Segmentation Memory Layout')

    # ==================== FRAGMENTATION TAB ====================

    def _create_fragmentation_tab(self):
        left, right = self._make_panels(self.fragmentation_frame)
        self._create_fragmentation_config(left)
        self._create_fragmentation_results(left)
        self._create_fragmentation_visualization(right)

    def _create_fragmentation_config(self,parent):
        blocks=ttk.LabelFrame(parent,text='Initial Memory Blocks (bytes)',padding=8)
        blocks.pack(fill=tk.BOTH,expand=True,pady=(0,8))
        self.block_tree=self._table(blocks,('Start','Size','Status'),(85,85,85),4)
        form=ttk.Frame(blocks)
        form.pack(fill=tk.X,pady=3)
        self.block_start_var=tk.IntVar()
        self.block_size_var=tk.IntVar()
        ttk.Label(form,text='Start:').grid(row=0,column=0,padx=2)
        ttk.Entry(form,textvariable=self.block_start_var,width=8).grid(row=0,column=1,sticky='ew',padx=2)
        ttk.Label(form,text='Size:').grid(row=0,column=2,padx=2)
        ttk.Entry(form,textvariable=self.block_size_var,width=8).grid(row=0,column=3,sticky='ew',padx=2)
        form.columnconfigure(1,weight=1)
        form.columnconfigure(3,weight=1)
        ttk.Button(form,text='Add Block',command=self._add_block).grid(row=1,column=0,columnspan=2,sticky='ew',padx=2,pady=3)
        ttk.Button(form,text='Load Sample',command=self._load_sample_fragmentation).grid(row=1,column=2,columnspan=2,sticky='ew',padx=2,pady=3)
        req=ttk.LabelFrame(parent,text='Process Requests (bytes)',padding=8)
        req.pack(fill=tk.BOTH,expand=True,pady=(0,8))
        self.req_tree=self._table(req,('PID','Size'),(100,100),3)
        form=ttk.Frame(req)
        form.pack(fill=tk.X,pady=3)
        self.req_pid_var=tk.StringVar()
        self.req_size_var=tk.IntVar()
        ttk.Label(form,text='PID:').grid(row=0,column=0,padx=2)
        ttk.Entry(form,textvariable=self.req_pid_var,width=8).grid(row=0,column=1,sticky='ew',padx=2)
        ttk.Label(form,text='Size:').grid(row=0,column=2,padx=2)
        ttk.Entry(form,textvariable=self.req_size_var,width=8).grid(row=0,column=3,sticky='ew',padx=2)
        form.columnconfigure(1,weight=1)
        form.columnconfigure(3,weight=1)
        actions=ttk.Frame(req)
        actions.pack(fill=tk.X,pady=3)
        for label,cmd in [('Add Request',self._add_request),('Update',self._update_request),('Clear',self._clear_request_form)]:
            ttk.Button(actions,text=label,command=cmd).pack(side=tk.LEFT,padx=2)
        self.req_tree.bind('<<TreeviewSelect>>',self._on_request_select)
        algo_frame=ttk.LabelFrame(parent,text='Algorithm',padding=8)
        algo_frame.pack(fill=tk.X,pady=(0,8))
        self.frag_algo_var=tk.StringVar(value=AllocationAlgorithm.FIRST_FIT.value)
        row=ttk.Frame(algo_frame)
        row.pack(fill=tk.X,pady=3)
        for algo in AllocationAlgorithm:
            ttk.Radiobutton(row,text=algo.value.replace('_',' ').title(),variable=self.frag_algo_var,value=algo.value).pack(side=tk.LEFT,padx=2)
        row=ttk.Frame(algo_frame)
        row.pack(fill=tk.X,pady=3)
        ttk.Button(row,text='Run Allocation',command=self._run_fragmentation).pack(side=tk.LEFT,padx=2)
        ttk.Button(row,text='Compare All',command=self._compare_all_fragmentation).pack(side=tk.LEFT,padx=2)

    def _create_fragmentation_results(self,parent):
        frame=ttk.LabelFrame(parent,text='Results',padding=8)
        frame.pack(fill=tk.BOTH,expand=True)
        metrics=ttk.Frame(frame)
        metrics.pack(fill=tk.X,pady=(0,4))
        self.frag_metrics={}
        for i,(label,key) in enumerate([('Allocated','allocated'),('Free','free'),('Internal Frag','internal'),('External Frag','external')]):
            r,c=divmod(i,2)
            f=ttk.Frame(metrics)
            f.grid(row=r,column=c,padx=4,pady=2,sticky='w')
            ttk.Label(f,text=label+':',font=FONTS['small']).pack(side=tk.LEFT)
            self.frag_metrics[key]=ttk.Label(f,text='--',font=FONTS['small'])
            self.frag_metrics[key].pack(side=tk.LEFT,padx=4)
        self.frag_log=self._text_output(frame,7)
        self.frag_log.configure(state=tk.DISABLED)

    def _create_fragmentation_visualization(self, parent):
        self._chart(parent, 'Memory Layout', 'frag', scrollable=False)
        self.frag_map_blocks = []
        self.frag_process_colors = {}
        self.frag_map_details = tk.StringVar(value='Click an allocated or free block to view its size.')
        widget = self.frag_canvas.get_tk_widget()
        details = tk.Label(widget.master, textvariable=self.frag_map_details,
                           bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
                           font=FONTS['body'], anchor='w', justify=tk.LEFT,
                           padx=8, pady=8, wraplength=300)
        details.pack(side=tk.BOTTOM, fill=tk.X, before=widget)
        details.bind('<Configure>', lambda event: details.configure(wraplength=max(80, event.width - 16)))
        self.frag_canvas.mpl_connect('button_press_event', self._on_frag_map_click)

    def _on_frag_map_click(self, event):
        if event.button != 1 or event.inaxes is not self.frag_ax:
            return
        if event.xdata is None or event.ydata is None or not -0.18 <= event.ydata <= 0.18:
            return
        for start, size, label in self.frag_map_blocks:
            if start <= event.xdata < start + size:
                self.frag_map_details.set(
                    f'{label} | Size: {size:,} bytes\n'
                    f'Address range: {start:,} - {start + size - 1:,}')
                return
        self.frag_map_details.set('No configured memory block at this address.')

    def _on_fragmentation_algorithm_change(self, *args):
        if hasattr(self, 'memory_blocks'):
            self._clear_fragmentation_results()

    def _add_block(self):
        """Add memory block."""
        try:
            start = self.block_start_var.get()
            size = self.block_size_var.get()
            if start < 0:
                messagebox.showerror("Error", "Start address must be non-negative")
                return
            if size <= 0:
                messagebox.showerror("Error", "Size must be positive")
                return

            # Check overlap
            new_end = start + size - 1
            for b in self.memory_blocks:
                if not (new_end < b.start or start > b.end):
                    messagebox.showerror("Error", f"Overlaps with existing block at {b.start}")
                    return

            self.memory_blocks.append(MemoryBlock(start, size))
            self.memory_blocks.sort(key=lambda b: b.start)
            self._refresh_blocks()
            self._clear_fragmentation_results()

        except (tk.TclError, ValueError):
            messagebox.showerror("Error", "Invalid values")

    def _add_request(self):
        """Add process request."""
        pid = self.req_pid_var.get().strip()
        try:
            size = self.req_size_var.get()

            if not pid:
                messagebox.showerror("Error", "Process ID required")
                return
            if size <= 0:
                messagebox.showerror("Error", "Size must be positive")
                return

            if any(old_pid == pid for old_pid, _ in self.process_requests):
                messagebox.showerror("Error", f"Process ID {pid} already exists")
                return
            self.process_requests.append((pid, size))
            self.req_tree.insert("", tk.END, values=(pid, size))
            self.req_pid_var.set("")
            self.req_size_var.set(0)
            self._clear_fragmentation_results()

        except (tk.TclError, ValueError):
            messagebox.showerror("Error", "Invalid values")

    def _on_request_select(self, event):
        """Populate form from selected request."""
        selection = self.req_tree.selection()
        if not selection:
            return
        values = self.req_tree.item(selection[0])['values']
        self.req_pid_var.set(str(values[0]))
        self.req_size_var.set(int(values[1]))

    def _clear_request_form(self):
        """Clear request input fields and selection."""
        self.req_pid_var.set("")
        self.req_size_var.set(0)
        self.req_tree.selection_remove(self.req_tree.selection())

    def _update_request(self):
        """Update selected request or add new one with validation."""
        pid = self.req_pid_var.get().strip()
        try:
            size = self.req_size_var.get()

            if not pid:
                messagebox.showerror("Error", "Process ID required")
                return
            if size <= 0:
                messagebox.showerror("Error", "Size must be positive")
                return

            selection = self.req_tree.selection()
            selected_index = self.req_tree.index(selection[0]) if selection else -1
            if any(old_pid == pid and i != selected_index
                   for i, (old_pid, _) in enumerate(self.process_requests)):
                messagebox.showerror("Error", f"Process ID {pid} already exists")
                return
            if selection:
                # Update existing request
                idx = self.req_tree.index(selection[0])
                self.process_requests[idx] = (pid, size)
                self.req_tree.item(selection[0], values=(pid, size))
                self.req_tree.selection_remove(selection)
            else:
                # Add new request (same as Add Request)
                self.process_requests.append((pid, size))
                self.req_tree.insert("", tk.END, values=(pid, size))

            self.req_pid_var.set("")
            self.req_size_var.set(0)
            self._clear_fragmentation_results()

        except (tk.TclError, ValueError):
            messagebox.showerror("Error", "Invalid values")

    def _load_sample_fragmentation(self):
        """Load sample fragmentation data."""
        self.memory_blocks = generate_sample_memory_blocks()
        self.process_requests = generate_sample_process_requests()
        self._refresh_blocks()
        self._refresh_requests()
        self._clear_fragmentation_results()

    def _clear_fragmentation_results(self):
        """Discard results that no longer describe the current inputs."""
        for label in self.frag_metrics.values():
            label.config(text="--")
        self.frag_log.configure(state=tk.NORMAL)
        self.frag_log.delete("1.0", tk.END)
        self.frag_log.insert(tk.END, "Run allocation to view results.")
        self.frag_log.configure(state=tk.DISABLED)
        self._draw_fragmentation_visualization()

    def _refresh_blocks(self):
        """Refresh block display."""
        for item in self.block_tree.get_children():
            self.block_tree.delete(item)

        for b in self.memory_blocks:
            self.block_tree.insert("", tk.END, values=(b.start, b.size, "Free" if not b.allocated else f"P{b.process_id}"))

    def _refresh_requests(self):
        """Refresh request display."""
        for item in self.req_tree.get_children():
            self.req_tree.delete(item)

        for pid, size in self.process_requests:
            self.req_tree.insert("", tk.END, values=(pid, size))

    def _run_fragmentation(self):
        """Run fragmentation simulation."""
        if not self.memory_blocks or not self.process_requests:
            messagebox.showerror("Error", "Define memory blocks and process requests first")
            return

        algo = AllocationAlgorithm(self.frag_algo_var.get())
        try:
            result = FragmentationSimulator.allocate(algo, self.memory_blocks, self.process_requests)
        except ValueError as error:
            messagebox.showerror("Error", str(error))
            return
        self._display_fragmentation_result(result)

    def _compare_all_fragmentation(self):
        """Compare all fragmentation algorithms."""
        if not self.memory_blocks or not self.process_requests:
            messagebox.showerror("Error", "Define memory blocks and process requests first")
            return

        try:
            results = FragmentationSimulator.compare_all(self.memory_blocks, self.process_requests)
        except ValueError as error:
            messagebox.showerror("Error", str(error))
            return

        dialog = tk.Toplevel(self.parent)
        dialog.title("Algorithm Comparison")
        dialog.geometry("600x300")
        dialog.configure(bg=COLORS["bg_panel"])

        text = tk.Text(dialog, bg=COLORS["bg_panel"], fg=COLORS["text_primary"], font=FONTS["mono"])
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text.insert(tk.END, f"{'Algorithm':<15} {'Allocated':>10} {'Free':>10} {'Internal':>10} {'External':>10}\n")
        text.insert(tk.END, "-" * 60 + "\n")

        for algo, result in results.items():
            text.insert(tk.END,
                f"{algo.value.replace('_', ' ').title():<15} "
                f"{result.allocated_memory:>10} {result.free_memory:>10} "
                f"{result.internal_fragmentation:>10} {result.external_fragmentation:>10}\n"
            )

        text.insert(tk.END, "\nExternal = Free - largest available block (bytes).\n"
                    "Adjacent input blocks remain separate; no coalescing.")
        text.config(state=tk.DISABLED)

    def _display_fragmentation_result(self, result: FragmentationResult):
        """Display fragmentation result."""
        self.frag_metrics["allocated"].config(text=str(result.allocated_memory))
        self.frag_metrics["free"].config(text=str(result.free_memory))
        self.frag_metrics["internal"].config(text=str(result.internal_fragmentation))
        self.frag_metrics["external"].config(text=str(result.external_fragmentation))

        self.frag_log.configure(state=tk.NORMAL)
        self.frag_log.delete(1.0, tk.END)
        self.frag_log.insert(tk.END, f"Algorithm: {result.algorithm.value.replace('_', ' ').title()}\n\n")

        for pid, size, start, success in result.allocations:
            if success:
                self.frag_log.insert(tk.END, f"Yes {pid}: {size} bytes -> address {start}\n", "success")
            else:
                self.frag_log.insert(tk.END, f"No {pid}: {size} bytes -> ALLOCATION FAILED\n", "fail")

        self.frag_log.tag_config("success", foreground=COLORS["success"])
        self.frag_log.tag_config("fail", foreground=COLORS["danger"])
        largest = max((b.size for b in result.final_blocks if not b.allocated), default=0)
        self.frag_log.insert(tk.END, f"\nExternal frag. estimate = {result.free_memory} - {largest} = {result.external_fragmentation} bytes\n"
                             "Separate blocks; no coalescing. Internal frag. = 0 (exact splitting).")
        self.frag_log.configure(state=tk.DISABLED)
        self._draw_fragmentation_visualization(result)

    def _draw_fragmentation_visualization(self,result=None):
        blocks=result.final_blocks if result else self.memory_blocks
        colors=['#6c8cff','#f87171','#4ade80','#fbbf24','#a78bfa','#60a5fa','#34d399','#fb923c']
        parts=[]
        self.frag_map_blocks=[]
        self.frag_map_details.set('Click an allocated or free block to view its size.')
        # Reserve a stable color for each PID in request order, independent of fit algorithm.
        for pid, _ in self.process_requests:
            if pid not in self.frag_process_colors:
                self.frag_process_colors[pid] = colors[len(self.frag_process_colors) % len(colors)]
        for block in sorted(blocks,key=lambda b:b.start):
            label=str(block.process_id) if block.allocated else 'Free'
            if block.allocated and block.process_id not in self.frag_process_colors:
                self.frag_process_colors[block.process_id] = colors[len(self.frag_process_colors) % len(colors)]
            color=self.frag_process_colors[block.process_id] if block.allocated else COLORS['bg_input']
            parts.append((block.start,block.size,label,color,not block.allocated))
            self.frag_map_blocks.append((block.start,block.size,
                f'{label} (allocated)' if block.allocated else 'Free memory'))
        title='Memory Layout - '+result.algorithm.value.replace('_',' ').title() if result else 'Initial Memory Layout'
        self._draw_address_map('frag',parts,title)

    # ==================== COMMON ====================

    def _load_sample_data(self):
        """Load all sample data."""
        # Paging
        self.paging_config = generate_sample_paging_config()
        self.logical_mem_var.set(self.paging_config.logical_memory_size // 1024)
        self.physical_mem_var.set(self.paging_config.physical_memory_size // 1024)
        self.page_size_var.set(self.paging_config.page_size // 1024)
        self._apply_paging_config()

        # Page Replacement
        self.ref_string_var.set(",".join(map(str, generate_sample_page_references())))
        self.num_frames_var.set(3)

        # Segmentation
        self.segments = generate_sample_segments()
        self._refresh_segments()
        self._draw_segmentation_visualization()

        # Fragmentation
        self.memory_blocks = generate_sample_memory_blocks()
        self.process_requests = generate_sample_process_requests()
        self._refresh_blocks()
        self._refresh_requests()
        self._clear_fragmentation_results()


def create_memory_module(parent_window, content_frame):
    """Factory function to create memory manager module."""
    return MemoryWindow(parent_window, content_frame)