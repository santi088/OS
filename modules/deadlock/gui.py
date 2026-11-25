"""Deadlock Manager UI. Banker's Algorithm remains in algorithms.py."""
import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from gui.theme import COLORS, FONTS
from modules.deadlock.algorithms import BankersAlgorithm, generate_sample_state


class DeadlockWindow:
    def __init__(self, parent_window, content_frame):
        self.parent = parent_window
        self.content_frame = content_frame
        self.state = None
        self.last_safety_result = None
        self._building = False
        self._setup_ui()
        self._load_sample_state()

    def _label(self, parent, text='', **kwargs):
        opts = dict(font=FONTS['body'], anchor='w')
        opts.update(kwargs)
        return ttk.Label(parent, text=text, **opts)

    def _panel(self, parent, title, subtitle=None, **pack):
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        frame.pack(**pack)
        if subtitle:
            self._label(frame, subtitle, font=FONTS['small'], justify='left').pack(fill='x', pady=(0, 5))
        return frame

    def _button(self, parent, text, command, primary=False):
        return ttk.Button(parent, text=text, command=command)

    def _entry(self, parent, var, width=5):
        return ttk.Entry(parent, textvariable=var, width=width, justify='center')

    def _setup_ui(self):
        panes = ttk.PanedWindow(self.content_frame, orient=tk.HORIZONTAL)
        panes.pack(fill='both', expand=True, padx=5, pady=5)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=1)
        self._create_config(left)
        self._create_request(left)
        self._create_matrices(left)
        self._create_results(right)
        # Equal initial widths; allow the user to move the divider afterward.
        def set_sash(event):
            if event.width >= 600:
                panes.sashpos(0, event.width // 2)
                panes.unbind('<Configure>', sash_binding)
        sash_binding = panes.bind('<Configure>', set_sash, add='+')

    def _create_config(self, parent):
        frame = self._panel(parent, 'System Configuration', fill='x', pady=(0, 8))
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=(0, 4))
        self.num_processes_var = tk.StringVar(value='5')
        self.num_resources_var = tk.StringVar(value='3')
        for name, var in [('Processes:', self.num_processes_var), ('Resources:', self.num_resources_var)]:
            self._label(row, name).pack(side='left', padx=(0, 4))
            ttk.Spinbox(row, from_=1, to=10, width=4, textvariable=var).pack(side='left', padx=(0, 8))
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=(0, 6))
        self._button(buttons, 'Apply Dimensions', self._apply_dimensions).pack(side='left', padx=(0, 5))
        self._button(buttons, 'Load Sample', self._load_sample_state).pack(side='left')
        avail = ttk.LabelFrame(frame, text='Available Resources', padding=5)
        avail.pack(fill='x')
        self.available_frame = ttk.Frame(avail)
        self.available_frame.pack(fill='x')

    def _create_request(self, parent):
        frame = self._panel(parent, 'Resource Request', side='bottom', fill='x', pady=(8, 0))
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=(0, 4))
        self._label(row, 'Process:').pack(side='left', padx=(0, 5))
        self.request_process_var = tk.StringVar(value='P0')
        self.request_process_spin = ttk.Combobox(row, textvariable=self.request_process_var, state='readonly', width=5)
        self.request_process_spin.pack(side='left', padx=(0, 10))
        self._button(row, 'Submit Request', self._submit_request).pack(side='left')
        self.request_frame = ttk.Frame(frame)
        self.request_frame.pack(fill='x')

    def _create_matrices(self, parent):
        frame = self._panel(parent, 'Resource Matrices', 'Need = Maximum - Allocation (calculated automatically)', fill='both', expand=True)
        body = ttk.Frame(frame)
        body.pack(fill='both', expand=True)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        bg = ttk.Style(self.content_frame).lookup('TFrame', 'background') or self.content_frame.winfo_toplevel().cget('background')
        self.matrix_canvas = tk.Canvas(body, bg=bg, highlightthickness=0, height=170, width=300)
        self.matrix_canvas.grid(row=0, column=0, sticky='nsew')
        sy = ttk.Scrollbar(body, orient='vertical', command=self.matrix_canvas.yview)
        sx = ttk.Scrollbar(body, orient='horizontal', command=self.matrix_canvas.xview)
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        self.matrix_canvas.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.matrix_container = ttk.Frame(self.matrix_canvas)
        self.matrix_window = self.matrix_canvas.create_window((0, 0), window=self.matrix_container, anchor='nw')
        self.matrix_container.bind('<Configure>', self._matrix_resize)
        self.matrix_canvas.bind('<Configure>', self._matrix_resize)
        self._label(frame, 'Allocation and Maximum are editable. Need is read-only.', font=FONTS['small']).pack(fill='x', pady=(4, 0))

    def _matrix_resize(self, _event=None):
        width = max(self.matrix_canvas.winfo_width(), self.matrix_container.winfo_reqwidth())
        self.matrix_canvas.itemconfigure(self.matrix_window, width=width)
        self.matrix_canvas.configure(scrollregion=self.matrix_canvas.bbox('all'))

    def _create_results(self, parent):
        buttons = ttk.Frame(parent)
        buttons.pack(fill='x', pady=(0, 6))
        self._button(buttons, 'Check Safety', self._check_safety).pack(side='left', padx=(0, 5))
        self._button(buttons, 'Clear Log', self._clear_log).pack(side='left')

        # Keep the analysis and chart visible together, just like the original GUI.
        body = ttk.Frame(parent)
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)
        analysis = ttk.LabelFrame(body, text='Safety Analysis', padding=8)
        analysis.grid(row=0, column=0, sticky='nsew', pady=(0, 6))
        self.status_label = tk.Label(analysis, anchor='w', justify='left',
                                     font=FONTS['heading'], bg=COLORS['bg_panel'], padx=8, pady=6)
        self.status_label.pack(fill='x')
        self.status_detail = tk.Label(analysis, anchor='w', justify='left',
                                      font=FONTS['body'], bg=COLORS['bg_panel'],
                                      fg=COLORS['text_primary'], padx=8, pady=4, wraplength=250)
        self.status_detail.pack(fill='x')
        analysis.bind('<Configure>', lambda e: self.status_detail.configure(wraplength=max(100, e.width-36)))
        log = ttk.Frame(analysis)
        log.pack(fill='both', expand=True)
        self.result_text = tk.Text(log, height=7, width=24, wrap='word',
                                   font=FONTS['mono_small'], bg=COLORS['bg_panel'],
                                   fg=COLORS['text_primary'], padx=8, pady=6, state='disabled')
        scroll = ttk.Scrollbar(log, orient='vertical', command=self.result_text.yview)
        scroll.pack(side='right', fill='y')
        self.result_text.pack(side='left', fill='both', expand=True)
        self.result_text.configure(yscrollcommand=scroll.set)
        self.result_text.tag_config('heading', foreground='#a8baff', spacing1=5)
        self.result_text.tag_config('safe', foreground='#4ade80')
        self.result_text.tag_config('unsafe', foreground='#ff7777')

        viz = ttk.LabelFrame(body, text='Resource Allocation Visualization', padding=8)
        viz.grid(row=1, column=0, sticky='nsew')
        self.fig = Figure(figsize=(3.2, 2.0), dpi=100, facecolor=COLORS['bg_panel'])
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=viz)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

    def _status(self, title, detail, kind='neutral'):
        fg = {'neutral': COLORS['text_primary'], 'safe': '#4ade80',
              'unsafe': '#ff7777', 'warning': '#fbbf24'}[kind]
        self.status_label.configure(text=title, fg=fg)
        self.status_detail.configure(text=detail)

    def _safety_detail(self, result):
        if result is None:
            return ''
        if result.is_safe:
            return 'Safe sequence: ' + ' -> '.join(f'P{i}' for i in result.safe_sequence)
        return 'No complete safe sequence exists. Unsafe does not mean deadlock has occurred.'

    @staticmethod
    def _vec(values):
        return '[' + ', '.join(str(v) for v in values) + ']'

    def _write_log(self, lines):
        self.result_text.configure(state='normal')
        self.result_text.delete('1.0', 'end')
        for line in lines:
            tag = ''
            if 'UNSAFE' in line or 'DENIED' in line or 'ERROR' in line or 'Error:' in line:
                tag = 'unsafe'
            elif 'SAFE state' in line or 'GRANTED' in line:
                tag = 'safe'
            elif line.startswith(('===', '---', 'Step ')):
                tag = 'heading'
            self.result_text.insert('end', line + '\n', tag)
        self.result_text.configure(state='disabled')
        self.result_text.see('1.0')

    def _clear_log(self):
        self.last_safety_result = None
        self._write_log([])
        self._status('Ready', 'Click Check Safety to analyze the current allocation.')

    def _build_fields(self):
        self._building = True
        try:
            n, r = self.state.num_processes, self.state.num_resources
            for frame in (self.available_frame, self.request_frame, self.matrix_container):
                for w in frame.winfo_children():
                    w.destroy()
            self.available_vars, self.request_vars = [], []
            self.alloc_vars, self.max_vars, self.need_labels = [], [], []
            for j in range(r):
                for frame, variables, initial in [(self.available_frame, self.available_vars, self.state.available[j]), (self.request_frame, self.request_vars, 0)]:
                    group = ttk.Frame(frame)
                    group.grid(row=j//5, column=j%5, padx=(0, 8), pady=2, sticky='w')
                    self._label(group, f'R{j}', foreground=ttk.Style(self.content_frame).lookup('TLabel', 'foreground') or 'black', font=FONTS['small']).pack(anchor='w')
                    v = tk.StringVar(value=str(initial))
                    self._entry(group, v, 4).pack()
                    variables.append(v)
                    if frame is self.available_frame:
                        v.trace_add('write', self._inputs_changed)
            self.request_process_spin.configure(values=[f'P{i}' for i in range(n)])
            self.request_process_var.set('P0')
            for section, title in enumerate(['Allocation', 'Maximum', 'Need (auto)']):
                self._label(self.matrix_container, title, anchor='center', font=FONTS['heading'], padding=(0, 4)).grid(row=0, column=1+section*r, columnspan=r, sticky='ew', padx=2)
                for j in range(r):
                    self._label(self.matrix_container, f'R{j}', foreground=ttk.Style(self.content_frame).lookup('TLabel', 'foreground') or 'black', anchor='center').grid(row=1, column=1+section*r+j, sticky='ew', padx=2)
            self._label(self.matrix_container, 'Process', anchor='center', font=FONTS['heading'], padding=(0, 4)).grid(row=0, column=0, sticky='ew', padx=2)
            for i in range(n):
                self._label(self.matrix_container, f'P{i}', anchor='center', font=FONTS['heading']).grid(row=i+2, column=0, padx=7, pady=4)
                av, mv, nv = [], [], []
                for j in range(r):
                    for section, variables, value in [(0, av, self.state.allocation[i][j]), (1, mv, self.state.maximum[i][j])]:
                        var = tk.StringVar(value=str(value))
                        self._entry(self.matrix_container, var, 4).grid(row=i+2, column=1+section*r+j, padx=2, pady=3, sticky='ew')
                        variables.append(var)
                        var.trace_add('write', self._inputs_changed)
                    label = self._label(self.matrix_container, str(self.state.need[i][j]), background=COLORS['bg_card'], foreground=COLORS['text_primary'], anchor='center', padding=(0, 3))
                    label.grid(row=i+2, column=1+2*r+j, padx=2, pady=3, sticky='ew')
                    nv.append(label)
                self.alloc_vars.append(av)
                self.max_vars.append(mv)
                self.need_labels.append(nv)
            for col in range(31):
                self.matrix_container.grid_columnconfigure(col, weight=1 if 0 < col < 1+3*r else 0)
            self.matrix_canvas.xview_moveto(0)
            self.matrix_canvas.yview_moveto(0)
        finally:
            self._building = False
        self._clear_log()
        self._draw_visualization()

    def _inputs_changed(self, *_):
        if self._building:
            return
        for i, row in enumerate(self.need_labels):
            for j, label in enumerate(row):
                try:
                    a, m = int(self.alloc_vars[i][j].get()), int(self.max_vars[i][j].get())
                    valid = 0 <= a <= m
                    label.configure(text=str(m-a) if valid else 'Invalid', foreground=COLORS['text_primary'] if valid else '#ff7777')
                except ValueError:
                    label.configure(text='--', foreground=COLORS['text_primary'])
        self.last_safety_result = None
        self._write_log([])
        self._status('Inputs changed', 'Run Check Safety again. Results from the previous configuration have been cleared.', 'warning')
        self._draw_visualization()

    def _load_sample_state(self):
        self.state = generate_sample_state()
        self.num_processes_var.set(str(self.state.num_processes))
        self.num_resources_var.set(str(self.state.num_resources))
        self._build_fields()

    def _apply_dimensions(self):
        try:
            n, r = int(self.num_processes_var.get()), int(self.num_resources_var.get())
            if not (1 <= n <= 10 and 1 <= r <= 10):
                raise ValueError
        except ValueError:
            messagebox.showerror('Invalid dimensions', 'Enter 1 to 10 processes and 1 to 10 resource types.', parent=self.parent)
            return
        self.state = BankersAlgorithm.create_state(n, r, [0]*r, [[0]*r for _ in range(n)], [[0]*r for _ in range(n)])
        self._build_fields()

    def _read_inputs(self):
        n, r = self.state.num_processes, self.state.num_resources
        def parse(v):
            x = int(v.get())
            if x < 0:
                raise ValueError
            return x
        available = [parse(v) for v in self.available_vars]
        alloc = [[parse(v) for v in row] for row in self.alloc_vars]
        maximum = [[parse(v) for v in row] for row in self.max_vars]
        return BankersAlgorithm.create_state(n, r, available, maximum, alloc)

    def _commit_inputs(self):
        try:
            if (int(self.num_processes_var.get()), int(self.num_resources_var.get())) != (self.state.num_processes, self.state.num_resources):
                messagebox.showerror('Dimensions changed', 'Click Apply Dimensions before analyzing the new configuration.', parent=self.parent)
                return False
            state = self._read_inputs()
        except ValueError:
            messagebox.showerror('Invalid input', 'Use non-negative whole numbers in all resource fields.', parent=self.parent)
            return False
        errors = BankersAlgorithm.validate_state(state)
        if errors:
            messagebox.showerror('Validation error', '\n'.join(errors), parent=self.parent)
            return False
        self.state = state
        return True

    def _check_safety(self):
        if not self._commit_inputs():
            return
        result = BankersAlgorithm.safety_algorithm(self.state)
        self.last_safety_result = result
        self._status('SAFE STATE' if result.is_safe else 'UNSAFE STATE',
                     self._safety_detail(result),
                     'safe' if result.is_safe else 'unsafe')
        self._write_log(result.explanation)
        self._draw_visualization()

    def _submit_request(self):
        if not self._commit_inputs():
            return
        try:
            p = int(self.request_process_var.get()[1:])
            request = [int(v.get()) for v in self.request_vars]
            if not 0 <= p < self.state.num_processes or any(x < 0 for x in request):
                raise ValueError
        except (ValueError, IndexError):
            messagebox.showerror('Invalid request', 'Choose a valid process and enter non-negative whole numbers.', parent=self.parent)
            return
        before = self.state.copy()
        result = BankersAlgorithm.request_algorithm(self.state, p, request)
        safety = result.safety_result
        if result.granted and result.new_state is not None:
            self.state = result.new_state
            self._building = True
            try:
                for j, v in enumerate(self.available_vars):
                    v.set(str(self.state.available[j]))
                for i in range(self.state.num_processes):
                    for j in range(self.state.num_resources):
                        self.alloc_vars[i][j].set(str(self.state.allocation[i][j]))
                        self.max_vars[i][j].set(str(self.state.maximum[i][j]))
                        self.need_labels[i][j].configure(text=str(self.state.need[i][j]), foreground=COLORS['text_primary'])
            finally:
                self._building = False
            self.last_safety_result = safety
            self._status('REQUEST GRANTED', f'P{p} received {self._vec(request)}. ' + self._safety_detail(safety), 'safe')
        else:
            self.state = before
            self.last_safety_result = None
            if safety is not None:
                detail = 'The tentative allocation would be unsafe. Original resources are unchanged.'
            else:
                detail = ('Request exceeds the process maximum claim.' if any(x>y for x,y in zip(request,before.need[p]))
                          else 'Insufficient available resources. The process must wait.' if any(x>y for x,y in zip(request,before.available))
                          else 'Request not accepted. See the analysis log.')
                detail += ' Original resources are unchanged.'
            self._status('REQUEST DENIED', detail, 'unsafe')
        self._write_log(result.explanation)
        self._draw_visualization()

    def _draw_visualization(self):
        if self.state is None or not hasattr(self, 'canvas'):
            return
        ax = self.ax
        ax.clear()
        ax.set_facecolor(COLORS['bg_panel'])
        ax.tick_params(colors=COLORS['text_secondary'], labelsize=9)
        for spine in ax.spines.values():
            spine.set_color(COLORS['border'])
        try:
            state = self._read_inputs()
            if BankersAlgorithm.validate_state(state):
                raise ValueError
        except (ValueError, IndexError, AttributeError):
            ax.text(.5, .5, 'Enter valid resource values.', transform=ax.transAxes,
                    ha='center', va='center', color=COLORS['text_primary'])
            ax.set_xticks([])
            ax.set_yticks([])
            self.canvas.draw_idle()
            return
        colors = ['#6c8cff', '#f87171', '#4ade80', '#fbbf24', '#a78bfa',
                  '#60a5fa', '#34d399', '#fb923c', '#ec72bd', '#9ca3af']
        ids = list(range(state.num_processes))
        bottom = [0] * state.num_processes
        for j in range(state.num_resources):
            values = [row[j] for row in state.allocation]
            ax.bar(ids, values, bottom=bottom, label=f'R{j}', color=colors[j],
                   edgecolor=COLORS['bg_panel'], linewidth=.5)
            bottom = [x+y for x,y in zip(bottom, values)]
        ax.set_xticks(ids, [f'P{i}' for i in ids])
        ax.set_ylim(0, max(1, max(bottom)) * 1.15)
        ax.set_ylabel('Resource instances', color=COLORS['text_primary'], fontsize=9)
        ax.set_title('Allocated resources per process', color=COLORS['text_primary'], fontsize=10)
        ax.legend(loc='upper center', bbox_to_anchor=(.5,-.19), ncol=min(5,state.num_resources),
                  fontsize=8, frameon=False, labelcolor=COLORS['text_primary'])
        self.fig.subplots_adjust(left=.17, right=.97, top=.85, bottom=.30 if state.num_resources<=5 else .39)
        self.canvas.draw_idle()


def create_deadlock_module(parent_window, content_frame):
    return DeadlockWindow(parent_window, content_frame)
