"""
Process Manager - Multiprogramming and Multiprocessing Simulation.

Simulates process state transitions, multiprogramming, and multiprocessing.
Supports FCFS, SJF, SRTF and Round Robin.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from copy import deepcopy
import random
import math
from decimal import Decimal


class ProcessState(Enum):
    NEW = "new"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"  # Blocked for I/O
    TERMINATED = "terminated"


class TransitionReason(Enum):
    CREATED = "created"
    SCHEDULED = "scheduled"
    IO_REQUEST = "io_request"
    IO_COMPLETE = "io_complete"
    TIMEOUT = "timeout"
    TERMINATED = "terminated"
    PREEMPTED = "preempted"


class SchedulingAlgorithm(Enum):
    FCFS = "fcfs"
    SJF = "sjf"
    SRTF = "srtf"
    ROUND_ROBIN = "round_robin"


@dataclass
class SimulatedProcess:
    """Process in the simulation."""
    pid: str
    arrival_time: float
    burst_time: float
    io_frequency: float = 0.0  # Cumulative CPU burst between I/O requests (0 = never)
    priority: int = 0           # Lower number = higher priority

    # Dynamic state
    state: ProcessState = ProcessState.NEW
    remaining_time: float = 0.0
    cpu_time_used: float = 0.0      # Total CPU time consumed
    cpu_since_io: float = 0.0       # CPU time since last I/O (for I/O frequency)
    io_time_remaining: float = 0.0
    start_time: float = -1.0
    completion_time: float = 0.0
    turnaround_time: float = 0.0
    waiting_time: float = 0.0       # Time spent in the READY state only
    response_time: float = 0.0      # First CPU start - Arrival
    core_id: int = -1               # Which core it's running on (-1 = none)

    # For visualization
    state_history: List[Tuple[float, ProcessState, str]] = field(default_factory=list)

    def __post_init__(self):
        self.remaining_time = self.burst_time
        # Record initial state
        self.state_history.append((self.arrival_time, ProcessState.NEW, "initialized"))

    def record_state_change(self, time: float, new_state: ProcessState, reason: str):
        self.state_history.append((time, new_state, reason))
        self.state = new_state


@dataclass
class CPUScheduleEvent:
    """Event in CPU schedule."""
    time: float
    event_type: str  # "start", "preempt", "io", "io_complete", "complete"
    process_id: str
    core_id: int
    details: str


@dataclass
class MultiprogrammingResult:
    """Result of multiprogramming simulation."""
    processes: List[SimulatedProcess]
    schedule: List[CPUScheduleEvent]
    cpu_utilization: float
    throughput: float
    avg_turnaround: float
    avg_waiting: float
    avg_response: float
    context_switches: int
    total_time: float
    degree_of_multiprogramming: int  # Max processes in memory at once
    algorithm: str


@dataclass
class MultiprocessingResult:
    """Result of multiprocessing simulation."""
    processes: List[SimulatedProcess]
    core_schedules: Dict[int, List[CPUScheduleEvent]]  # Per-core schedule
    core_utilizations: Dict[int, float]
    total_time: float
    overall_cpu_utilization: float
    throughput: float
    avg_turnaround: float
    avg_waiting: float
    avg_response: float


def _simulate(processes, algorithm, time_slice, max_time, cores):
    """Event-driven CPU/I/O model; independent I/O waits, zero switch overhead.

    Equal-time arrivals and I/O completions enter the queue before expired
    quanta. SJF/SRTF use the next CPU burst (known in this teaching model).
    Context switches count dispatches from idle or a different PID, not
    immediate continuation of the same process. Decimal clocks avoid drift.
    """
    if not isinstance(algorithm, SchedulingAlgorithm):
        raise ValueError("Unknown scheduling algorithm")
    if not isinstance(cores, int) or cores < 1:
        raise ValueError("Number of cores must be a positive integer")
    if not math.isfinite(max_time) or max_time <= 0:
        raise ValueError("Maximum simulation time must be positive and finite")
    if algorithm == SchedulingAlgorithm.ROUND_ROBIN and (not math.isfinite(time_slice) or time_slice <= 0):
        raise ValueError("Time slice must be positive and finite")
    D = lambda x: Decimal(str(x))
    zero = D(0)
    limit = D(max_time)
    quantum = D(time_slice) if algorithm == SchedulingAlgorithm.ROUND_ROBIN else None
    procs = []
    seen = set()
    for p in processes:
        if not isinstance(p.pid, str) or not p.pid.strip() or p.pid in seen:
            raise ValueError("Process IDs must be nonempty and unique")
        seen.add(p.pid)
        if not all(math.isfinite(v) for v in (p.arrival_time, p.burst_time, p.io_frequency)) or p.arrival_time < 0 or p.burst_time <= 0 or p.io_frequency < 0:
            raise ValueError("Arrival and I/O frequency must be nonnegative; burst must be positive; all must be finite")
        procs.append(SimulatedProcess(p.pid, p.arrival_time, p.burst_time, p.io_frequency, p.priority))
    procs.sort(key=lambda p: (p.arrival_time, p.pid))
    rem = {p.pid: D(p.burst_time) for p in procs}
    since = {p.pid: zero for p in procs}
    freq = {p.pid: D(p.io_frequency) for p in procs}
    ready_at = {}
    wait = {p.pid: zero for p in procs}
    ready, blocked = [], []
    running = [None]*cores
    left = [zero]*cores
    last = [None]*cores
    busy = [zero]*cores
    logs = {i: [] for i in range(cores)}
    t = zero
    idx = done = switches = peak = 0
    def log(core, kind, p, details):
        logs[core].append(CPUScheduleEvent(float(t), kind, p.pid, core, details))
    def enqueue(p, reason):
        p.core_id = -1
        p.record_state_change(float(t), ProcessState.READY, reason.value)
        ready_at[p.pid] = t
        ready.append(p)
    def next_burst(p):
        return min(rem[p.pid], freq[p.pid]-since[p.pid]) if freq[p.pid] else rem[p.pid]
    def pick():
        if algorithm in (SchedulingAlgorithm.SJF, SchedulingAlgorithm.SRTF):
            return min(ready, key=lambda p: (next_burst(p), p.arrival_time, p.pid))
        return ready[0]
    def dispatch(core, p):
        nonlocal switches
        ready.remove(p)
        wait[p.pid] += t-ready_at.pop(p.pid)
        if last[core] != p.pid:
            switches += 1
        last[core] = p.pid
        running[core] = p
        left[core] = quantum if quantum is not None else zero
        if p.start_time < 0:
            p.start_time = float(t)
            p.response_time = float(t-D(p.arrival_time))
        p.core_id = core
        p.record_state_change(float(t), ProcessState.RUNNING, TransitionReason.SCHEDULED.value)
        log(core, "start", p, f"Dispatched on CPU {core}")
    event_count = 0
    while done < len(procs):
        event_count += 1
        if event_count > 50000:
            raise ValueError("Too many simulation events; increase the time slice or I/O frequency, or reduce workload.")
        # Admit external events before requeueing expired CPU quanta.
        while idx < len(procs) and D(procs[idx].arrival_time) <= t:
            p = procs[idx]; idx += 1
            enqueue(p, TransitionReason.CREATED)
            log(0, "ready", p, "Arrived; entered ready queue")
        blocked.sort(key=lambda entry: entry[0])
        while blocked and blocked[0][0] <= t:
            _, p, core = blocked.pop(0)
            p.io_time_remaining = 0.0
            enqueue(p, TransitionReason.IO_COMPLETE)
            log(core, "io_complete", p, "I/O complete; entered ready queue")
        for core,p in enumerate(running):
            if p is None: continue
            pid=p.pid
            if rem[pid] == zero:
                p.completion_time=float(t)
                p.turnaround_time=float(t-D(p.arrival_time))
                p.waiting_time=float(wait[pid])
                p.core_id=-1
                p.record_state_change(float(t), ProcessState.TERMINATED, TransitionReason.TERMINATED.value)
                log(core,"complete",p,"Process terminated")
                running[core]=None; done+=1
            elif freq[pid] and since[pid] == freq[pid]:
                since[pid]=zero; p.cpu_since_io=0.0
                duration=D(random.uniform(0.5,3.0))
                p.io_time_remaining=float(duration); p.core_id=-1
                p.record_state_change(float(t), ProcessState.WAITING, TransitionReason.IO_REQUEST.value)
                log(core,"io",p,f"I/O request (duration: {float(duration):.2f})")
                blocked.append((t+duration,p,core)); running[core]=None
            elif quantum is not None and left[core] == zero:
                if ready:
                    enqueue(p,TransitionReason.TIMEOUT)
                    log(core,"preempt",p,"Time slice expired")
                    running[core]=None
                else:
                    left[core]=quantum
        peak=max(peak,sum(p.state not in (ProcessState.NEW,ProcessState.TERMINATED) for p in procs))
        if done == len(procs) or t >= limit: break
        if algorithm == SchedulingAlgorithm.SRTF and running[0] is not None and ready:
            p=running[0]; candidate=pick()
            if next_burst(candidate)<next_burst(p):
                enqueue(p,TransitionReason.PREEMPTED)
                log(0,"preempt",p,f"Preempted by {candidate.pid}")
                dispatch(0,candidate)
        for core in range(cores):
            if running[core] is None and ready: dispatch(core,pick())
        times=[limit]
        if idx < len(procs): times.append(D(procs[idx].arrival_time))
        times.extend(end for end,_,_ in blocked)
        for core,p in enumerate(running):
            if p is None: continue
            times.append(t+next_burst(p))
            if quantum is not None: times.append(t+left[core])
        new_t=min(times); delta=new_t-t
        if delta <= zero: raise RuntimeError("Simulation clock failed to advance")
        for core,p in enumerate(running):
            if p is None:
                last[core]=None  # real idle interval
                continue
            pid=p.pid
            rem[pid]-=delta; since[pid]+=delta; busy[core]+=delta
            if quantum is not None: left[core]-=delta
            p.remaining_time=float(rem[pid]); p.cpu_time_used=float(D(p.burst_time)-rem[pid]); p.cpu_since_io=float(since[pid])
        t=new_t
    # Report partial runs honestly rather than inventing completion metrics.
    for p in procs:
        if p.pid in ready_at: p.waiting_time=float(wait[p.pid]+t-ready_at[p.pid])
        elif p.state != ProcessState.TERMINATED: p.waiting_time=float(wait[p.pid])
        if p.state == ProcessState.WAITING:
            p.io_time_remaining=float(next(end-t for end,q,_ in blocked if q is p))
    completed=[p for p in procs if p.state == ProcessState.TERMINATED]
    avg=lambda key: sum(getattr(p,key) for p in completed)/len(completed) if completed else 0.0
    elapsed=float(t)
    utils={i: float(busy[i]/t*100) if t else 0.0 for i in range(cores)}
    throughput=len(completed)/elapsed if elapsed else 0.0
    return procs,logs,utils,elapsed,throughput,avg("turnaround_time"),avg("waiting_time"),avg("response_time"),switches,peak


class ProcessManager:
    """Process management simulation."""
    @staticmethod
    def simulate_multiprogramming(processes, algorithm=SchedulingAlgorithm.ROUND_ROBIN, time_slice=2.0, max_time=1000.0):
        p,logs,u,t,th,ta,w,r,cs,peak=_simulate(processes,algorithm,time_slice,max_time,1)
        return MultiprogrammingResult(p,logs[0],u[0],th,ta,w,r,cs,t,peak,algorithm.value)

    @staticmethod
    def simulate_multiprocessing(processes,num_cores=2,time_slice=2.0,max_time=1000.0):
        p,logs,u,t,th,ta,w,r,_,_=_simulate(processes,SchedulingAlgorithm.ROUND_ROBIN,time_slice,max_time,num_cores)
        return MultiprocessingResult(p,logs,u,t,sum(u.values())/num_cores,th,ta,w,r)


def generate_sample_processes() -> List[SimulatedProcess]:
    """Generate sample processes for simulation."""
    return [
        SimulatedProcess("P1", 0.0, 10.0, io_frequency=5.0, priority=2),
        SimulatedProcess("P2", 1.0, 8.0, io_frequency=3.0, priority=1),
        SimulatedProcess("P3", 2.0, 12.0, io_frequency=0.0, priority=3),
        SimulatedProcess("P4", 3.0, 6.0, io_frequency=4.0, priority=2),
        SimulatedProcess("P5", 5.0, 9.0, io_frequency=6.0, priority=1),
    ]
