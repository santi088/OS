"""
CPU Scheduling Algorithms for Mini OS Simulator.

Implements:
- FCFS (First Come First Serve)
- SJF (Shortest Job First) - Non-preemptive
- SRTF (Shortest Remaining Time First) - Preemptive
- Priority Scheduling - Non-preemptive
- Priority Scheduling - Preemptive
- Round Robin
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import copy


class AlgorithmType(Enum):
    FCFS = "fcfs"
    SJF = "sjf"
    SRTF = "srtf"
    PRIORITY_NONPREEMPTIVE = "priority_nonpreemptive"
    PRIORITY_PREEMPTIVE = "priority_preemptive"
    ROUND_ROBIN = "round_robin"


@dataclass
class Process:
    """Represents a process for CPU scheduling."""
    pid: str
    arrival_time: float
    burst_time: float
    priority: int = 0
    remaining_time: float = 0.0
    start_time: float = -1.0
    completion_time: float = 0.0
    turnaround_time: float = 0.0
    waiting_time: float = 0.0
    response_time: float = 0.0
    
    def __post_init__(self):
        self.remaining_time = self.burst_time
    
    def copy(self) -> 'Process':
        return copy.deepcopy(self)


@dataclass
class GanttEntry:
    """Single entry in a Gantt chart."""
    pid: str
    start_time: float
    end_time: float
    is_idle: bool = False
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class SchedulingResult:
    """Results from a scheduling simulation."""
    algorithm: AlgorithmType
    processes: List[Process]
    gantt_chart: List[GanttEntry]
    avg_turnaround_time: float
    avg_waiting_time: float
    avg_response_time: float
    cpu_utilization: float
    throughput: float
    context_switches: int
    total_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm.value,
            "processes": [
                {
                    "pid": p.pid,
                    "arrival_time": p.arrival_time,
                    "burst_time": p.burst_time,
                    "priority": p.priority,
                    "completion_time": p.completion_time,
                    "turnaround_time": p.turnaround_time,
                    "waiting_time": p.waiting_time,
                    "response_time": p.response_time,
                }
                for p in self.processes
            ],
            "gantt_chart": [
                {
                    "pid": g.pid,
                    "start_time": g.start_time,
                    "end_time": g.end_time,
                    "duration": g.duration,
                    "is_idle": g.is_idle,
                }
                for g in self.gantt_chart
            ],
            "avg_turnaround_time": self.avg_turnaround_time,
            "avg_waiting_time": self.avg_waiting_time,
            "avg_response_time": self.avg_response_time,
            "cpu_utilization": self.cpu_utilization,
            "throughput": self.throughput,
            "context_switches": self.context_switches,
            "total_time": self.total_time,
        }


class CPUScheduler:
    """CPU Scheduling algorithm implementations."""
    
    @staticmethod
    def validate_processes(processes: List[Process]) -> List[str]:
        """Validate process list and return errors."""
        errors = []
        if not processes:
            errors.append("At least one process is required")
            return errors
        
        for i, p in enumerate(processes):
            if p.arrival_time < 0:
                errors.append(f"Process {p.pid}: Arrival time cannot be negative")
            if p.burst_time <= 0:
                errors.append(f"Process {p.pid}: Burst time must be positive")
            if p.priority < 0:
                errors.append(f"Process {p.pid}: Priority cannot be negative")
        
        # Check for duplicate PIDs
        pids = [p.pid for p in processes]
        if len(pids) != len(set(pids)):
            errors.append("Duplicate process IDs found")
        
        return errors
    
    @staticmethod
    def fcfs(processes: List[Process]) -> SchedulingResult:
        """First Come First Serve scheduling."""
        procs = sorted([p.copy() for p in processes], key=lambda x: (x.arrival_time, x.pid))
        gantt = []
        current_time = 0.0
        context_switches = 0
        prev_pid = None
        
        for proc in procs:
            # Handle CPU idle time
            if current_time < proc.arrival_time:
                if current_time < proc.arrival_time:
                    gantt.append(GanttEntry("IDLE", current_time, proc.arrival_time, is_idle=True))
                current_time = proc.arrival_time
            
            # Context switch
            if prev_pid is not None and prev_pid != proc.pid:
                context_switches += 1
            
            proc.start_time = current_time
            proc.completion_time = current_time + proc.burst_time
            gantt.append(GanttEntry(proc.pid, current_time, proc.completion_time))
            current_time = proc.completion_time
            prev_pid = proc.pid
        
        # Calculate metrics
        CPUScheduler._calculate_metrics(procs)
        
        return SchedulingResult(
            algorithm=AlgorithmType.FCFS,
            processes=procs,
            gantt_chart=gantt,
            avg_turnaround_time=sum(p.turnaround_time for p in procs) / len(procs),
            avg_waiting_time=sum(p.waiting_time for p in procs) / len(procs),
            avg_response_time=sum(p.response_time for p in procs) / len(procs),
            cpu_utilization=CPUScheduler._calc_cpu_utilization(gantt, current_time),
            throughput=len(procs) / current_time if current_time > 0 else 0,
            context_switches=context_switches,
            total_time=current_time,
        )
    
    @staticmethod
    def sjf(processes: List[Process]) -> SchedulingResult:
        """Shortest Job First (Non-preemptive) scheduling."""
        procs = [p.copy() for p in processes]
        gantt = []
        current_time = 0.0
        context_switches = 0
        completed = []
        prev_pid = None
        ready_queue = []
        
        while len(completed) < len(procs):
            # Add arrived processes to ready queue
            for proc in procs:
                if proc.arrival_time <= current_time and proc not in completed and proc not in ready_queue:
                    ready_queue.append(proc)
            
            if not ready_queue:
                # CPU idle - find next arrival
                next_arrival = min(p.arrival_time for p in procs if p not in completed)
                if current_time < next_arrival:
                    gantt.append(GanttEntry("IDLE", current_time, next_arrival, is_idle=True))
                current_time = next_arrival
                continue
            
            # Select shortest job
            ready_queue.sort(key=lambda x: (x.burst_time, x.arrival_time, x.pid))
            proc = ready_queue.pop(0)
            
            # Context switch
            if prev_pid is not None and prev_pid != proc.pid:
                context_switches += 1
            
            proc.start_time = current_time
            proc.completion_time = current_time + proc.burst_time
            gantt.append(GanttEntry(proc.pid, current_time, proc.completion_time))
            current_time = proc.completion_time
            completed.append(proc)
            prev_pid = proc.pid
        
        CPUScheduler._calculate_metrics(completed)
        
        return SchedulingResult(
            algorithm=AlgorithmType.SJF,
            processes=completed,
            gantt_chart=gantt,
            avg_turnaround_time=sum(p.turnaround_time for p in completed) / len(completed),
            avg_waiting_time=sum(p.waiting_time for p in completed) / len(completed),
            avg_response_time=sum(p.response_time for p in completed) / len(completed),
            cpu_utilization=CPUScheduler._calc_cpu_utilization(gantt, current_time),
            throughput=len(completed) / current_time if current_time > 0 else 0,
            context_switches=context_switches,
            total_time=current_time,
        )
    
    @staticmethod
    def srtf(processes: List[Process]) -> SchedulingResult:
        """Shortest Remaining Time First (Preemptive) scheduling."""
        procs = [p.copy() for p in processes]
        gantt = []
        current_time = 0.0
        context_switches = 0
        completed = []
        current_proc = None
        prev_pid = None
        
        while len(completed) < len(procs):
            # Find arrived processes
            arrived = [p for p in procs if p.arrival_time <= current_time and p not in completed]
            
            if not arrived:
                # CPU idle
                next_arrival = min(p.arrival_time for p in procs if p not in completed)
                if current_time < next_arrival:
                    gantt.append(GanttEntry("IDLE", current_time, next_arrival, is_idle=True))
                current_time = next_arrival
                continue
            
            # Select process with shortest remaining time
            arrived.sort(key=lambda x: (x.remaining_time, x.arrival_time, x.pid))
            next_proc = arrived[0]
            
            # Context switch: different running process
            if prev_pid is not None and prev_pid != next_proc.pid:
                context_switches += 1
            
            if current_proc != next_proc:
                if current_proc:
                    # End current Gantt entry
                    if gantt and gantt[-1].pid == current_proc.pid and not gantt[-1].is_idle:
                        gantt[-1].end_time = current_time
                current_proc = next_proc
                prev_pid = next_proc.pid  # Track PID for context switch counting
            
            # Execute for 1 time unit (or until next arrival/completion)
            # Record the actual first execution time
            if current_proc.start_time < 0:
                current_proc.start_time = current_time

            next_event_time = float('inf')
            
            # Next arrival that could preempt
            for p in procs:
                if p.arrival_time > current_time and p.arrival_time < next_event_time:
                    if p.remaining_time < current_proc.remaining_time:
                        next_event_time = p.arrival_time
            
            # Current process completion
            completion_time = current_time + current_proc.remaining_time
            if completion_time < next_event_time:
                next_event_time = completion_time
            
            # Update Gantt chart
            if gantt and gantt[-1].pid == current_proc.pid and not gantt[-1].is_idle:
                gantt[-1].end_time = next_event_time
            else:
                gantt.append(GanttEntry(current_proc.pid, current_time, next_event_time))
            
            current_proc.remaining_time -= (next_event_time - current_time)
            current_time = next_event_time
            
            # Check if process completed
            if current_proc.remaining_time <= 0.001:  # Floating point tolerance
                current_proc.completion_time = current_time
                completed.append(current_proc)
                prev_pid = current_proc.pid  # Save PID before clearing
                current_proc = None
        
        CPUScheduler._calculate_metrics(completed)
        
        return SchedulingResult(
            algorithm=AlgorithmType.SRTF,
            processes=completed,
            gantt_chart=gantt,
            avg_turnaround_time=sum(p.turnaround_time for p in completed) / len(completed),
            avg_waiting_time=sum(p.waiting_time for p in completed) / len(completed),
            avg_response_time=sum(p.response_time for p in completed) / len(completed),
            cpu_utilization=CPUScheduler._calc_cpu_utilization(gantt, current_time),
            throughput=len(completed) / current_time if current_time > 0 else 0,
            context_switches=context_switches,
            total_time=current_time,
        )
    
    @staticmethod
    def priority_nonpreemptive(processes: List[Process]) -> SchedulingResult:
        """Priority Scheduling (Non-preemptive) - Lower number = Higher priority."""
        procs = [p.copy() for p in processes]
        gantt = []
        current_time = 0.0
        context_switches = 0
        completed = []
        prev_pid = None
        ready_queue = []
        
        while len(completed) < len(procs):
            # Add arrived processes
            for proc in procs:
                if proc.arrival_time <= current_time and proc not in completed and proc not in ready_queue:
                    ready_queue.append(proc)
            
            if not ready_queue:
                next_arrival = min(p.arrival_time for p in procs if p not in completed)
                if current_time < next_arrival:
                    gantt.append(GanttEntry("IDLE", current_time, next_arrival, is_idle=True))
                current_time = next_arrival
                continue
            
            # Select highest priority (lowest number)
            ready_queue.sort(key=lambda x: (x.priority, x.arrival_time, x.pid))
            proc = ready_queue.pop(0)
            
            if prev_pid is not None and prev_pid != proc.pid:
                context_switches += 1
            
            proc.start_time = current_time
            proc.completion_time = current_time + proc.burst_time
            gantt.append(GanttEntry(proc.pid, current_time, proc.completion_time))
            current_time = proc.completion_time
            completed.append(proc)
            prev_pid = proc.pid
        
        CPUScheduler._calculate_metrics(completed)
        
        return SchedulingResult(
            algorithm=AlgorithmType.PRIORITY_NONPREEMPTIVE,
            processes=completed,
            gantt_chart=gantt,
            avg_turnaround_time=sum(p.turnaround_time for p in completed) / len(completed),
            avg_waiting_time=sum(p.waiting_time for p in completed) / len(completed),
            avg_response_time=sum(p.response_time for p in completed) / len(completed),
            cpu_utilization=CPUScheduler._calc_cpu_utilization(gantt, current_time),
            throughput=len(completed) / current_time if current_time > 0 else 0,
            context_switches=context_switches,
            total_time=current_time,
        )
    
    @staticmethod
    def priority_preemptive(processes: List[Process]) -> SchedulingResult:
        """Priority Scheduling (Preemptive) - Lower number = Higher priority."""
        procs = [p.copy() for p in processes]
        gantt = []
        current_time = 0.0
        context_switches = 0
        completed = []
        current_proc = None
        prev_pid = None
        
        while len(completed) < len(procs):
            arrived = [p for p in procs if p.arrival_time <= current_time and p not in completed]
            
            if not arrived:
                next_arrival = min(p.arrival_time for p in procs if p not in completed)
                if current_time < next_arrival:
                    gantt.append(GanttEntry("IDLE", current_time, next_arrival, is_idle=True))
                current_time = next_arrival
                continue
            
            # Select highest priority
            arrived.sort(key=lambda x: (x.priority, x.arrival_time, x.pid))
            next_proc = arrived[0]
            
            # Context switch: different running process
            if prev_pid is not None and prev_pid != next_proc.pid:
                context_switches += 1
            
            if current_proc != next_proc:
                if current_proc:
                    if gantt and gantt[-1].pid == current_proc.pid and not gantt[-1].is_idle:
                        gantt[-1].end_time = current_time
                current_proc = next_proc
                prev_pid = next_proc.pid  # Track PID for context switch counting
            
            # Record the actual first execution time
            if current_proc.start_time < 0:
                current_proc.start_time = current_time

            # Next event: arrival of higher priority process or completion
            next_event_time = float('inf')
            for p in procs:
                if p.arrival_time > current_time and p.arrival_time < next_event_time:
                    if p.priority < current_proc.priority:
                        next_event_time = p.arrival_time
            
            completion_time = current_time + current_proc.remaining_time
            if completion_time < next_event_time:
                next_event_time = completion_time
            
            if gantt and gantt[-1].pid == current_proc.pid and not gantt[-1].is_idle:
                gantt[-1].end_time = next_event_time
            else:
                gantt.append(GanttEntry(current_proc.pid, current_time, next_event_time))
            
            current_proc.remaining_time -= (next_event_time - current_time)
            current_time = next_event_time
            
            if current_proc.remaining_time <= 0.001:
                current_proc.completion_time = current_time
                completed.append(current_proc)
                prev_pid = current_proc.pid  # Save PID before clearing
                current_proc = None
        
        CPUScheduler._calculate_metrics(completed)
        
        return SchedulingResult(
            algorithm=AlgorithmType.PRIORITY_PREEMPTIVE,
            processes=completed,
            gantt_chart=gantt,
            avg_turnaround_time=sum(p.turnaround_time for p in completed) / len(completed),
            avg_waiting_time=sum(p.waiting_time for p in completed) / len(completed),
            avg_response_time=sum(p.response_time for p in completed) / len(completed),
            cpu_utilization=CPUScheduler._calc_cpu_utilization(gantt, current_time),
            throughput=len(completed) / current_time if current_time > 0 else 0,
            context_switches=context_switches,
            total_time=current_time,
        )
    
    @staticmethod
    def round_robin(processes: List[Process], time_quantum: float) -> SchedulingResult:
        """Round Robin scheduling."""
        if time_quantum <= 0:
            raise ValueError("Time quantum must be positive")
        
        procs = [p.copy() for p in processes]
        gantt = []
        current_time = 0.0
        context_switches = 0
        completed = []
        ready_queue = []
        current_proc = None
        prev_pid = None
        
        # Sort by arrival time initially
        procs.sort(key=lambda x: (x.arrival_time, x.pid))
        next_arrival_idx = 0
        
        while len(completed) < len(procs):
            # Add newly arrived processes
            while next_arrival_idx < len(procs) and procs[next_arrival_idx].arrival_time <= current_time:
                ready_queue.append(procs[next_arrival_idx])
                next_arrival_idx += 1
            
            if not ready_queue and not current_proc:
                # CPU idle
                if next_arrival_idx < len(procs):
                    next_arrival = procs[next_arrival_idx].arrival_time
                    if current_time < next_arrival:
                        gantt.append(GanttEntry("IDLE", current_time, next_arrival, is_idle=True))
                    current_time = next_arrival
                    continue
            
            if not current_proc and ready_queue:
                current_proc = ready_queue.pop(0)
                if current_proc.start_time < 0:
                    current_proc.start_time = current_time
                if prev_pid is not None and prev_pid != current_proc.pid:
                    context_switches += 1
                prev_pid = current_proc.pid
            
            if current_proc:
                exec_time = min(time_quantum, current_proc.remaining_time)
                next_time = current_time + exec_time
                
                # Add any arrivals during this quantum
                arrivals_during = []
                while next_arrival_idx < len(procs) and procs[next_arrival_idx].arrival_time < next_time:
                    arrivals_during.append(procs[next_arrival_idx])
                    next_arrival_idx += 1
                
                # Update Gantt
                if gantt and gantt[-1].pid == current_proc.pid and not gantt[-1].is_idle:
                    gantt[-1].end_time = next_time
                else:
                    gantt.append(GanttEntry(current_proc.pid, current_time, next_time))
                
                current_proc.remaining_time -= exec_time
                current_time = next_time
                
                # Add arrivals that happened during execution
                ready_queue.extend(arrivals_during)
                
                if current_proc.remaining_time <= 0.001:
                    current_proc.completion_time = current_time
                    completed.append(current_proc)
                    current_proc = None
                else:
                    # Preempted - add back to ready queue
                    ready_queue.append(current_proc)
                    current_proc = None
        
        CPUScheduler._calculate_metrics(completed)
        
        return SchedulingResult(
            algorithm=AlgorithmType.ROUND_ROBIN,
            processes=completed,
            gantt_chart=gantt,
            avg_turnaround_time=sum(p.turnaround_time for p in completed) / len(completed),
            avg_waiting_time=sum(p.waiting_time for p in completed) / len(completed),
            avg_response_time=sum(p.response_time for p in completed) / len(completed),
            cpu_utilization=CPUScheduler._calc_cpu_utilization(gantt, current_time),
            throughput=len(completed) / current_time if current_time > 0 else 0,
            context_switches=context_switches,
            total_time=current_time,
        )
    
    @staticmethod
    def _calculate_metrics(processes: List[Process]):
        """Calculate turnaround, waiting, and response times."""
        for proc in processes:
            proc.turnaround_time = proc.completion_time - proc.arrival_time
            proc.waiting_time = proc.turnaround_time - proc.burst_time
            proc.response_time = proc.start_time - proc.arrival_time
    
    @staticmethod
    def _calc_cpu_utilization(gantt: List[GanttEntry], total_time: float) -> float:
        """Calculate CPU utilization percentage."""
        if total_time <= 0:
            return 0.0
        busy_time = sum(g.duration for g in gantt if not g.is_idle)
        return (busy_time / total_time) * 100
    
    @staticmethod
    def run_algorithm(
        algorithm: AlgorithmType,
        processes: List[Process],
        time_quantum: float = 2.0
    ) -> SchedulingResult:
        """Run the specified scheduling algorithm."""
        errors = CPUScheduler.validate_processes(processes)
        if errors:
            raise ValueError("; ".join(errors))
        
        if algorithm == AlgorithmType.FCFS:
            return CPUScheduler.fcfs(processes)
        elif algorithm == AlgorithmType.SJF:
            return CPUScheduler.sjf(processes)
        elif algorithm == AlgorithmType.SRTF:
            return CPUScheduler.srtf(processes)
        elif algorithm == AlgorithmType.PRIORITY_NONPREEMPTIVE:
            return CPUScheduler.priority_nonpreemptive(processes)
        elif algorithm == AlgorithmType.PRIORITY_PREEMPTIVE:
            return CPUScheduler.priority_preemptive(processes)
        elif algorithm == AlgorithmType.ROUND_ROBIN:
            return CPUScheduler.round_robin(processes, time_quantum)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")
    
    @staticmethod
    def generate_simulation_events(result: SchedulingResult) -> Tuple[List, List]:
        """Generate simulation events and snapshots from scheduling result."""
        from simulation.engine import SimulationEvent, SimulationSnapshot
        
        events = []
        snapshots = []
        
        # Create initial snapshot
        initial_state = {
            "processes": {p.pid: {"remaining": p.burst_time, "state": "NEW"} for p in result.processes},
            "current_time": 0,
            "ready_queue": [],
            "running": None,
        }
        snapshots.append(SimulationSnapshot(0, initial_state, "Simulation started"))
        
        # Generate events from Gantt chart
        for entry in result.gantt_chart:
            if entry.is_idle:
                event_type = "IDLE"
                desc = f"CPU idle from {entry.start_time:.2f} to {entry.end_time:.2f}"
            else:
                event_type = "EXECUTE"
                proc = next(p for p in result.processes if p.pid == entry.pid)
                desc = f"Process {entry.pid} executes from {entry.start_time:.2f} to {entry.end_time:.2f}"
            
            events.append(SimulationEvent(
                time=entry.start_time,
                event_type=event_type,
                description=desc,
                data={"pid": entry.pid, "start": entry.start_time, "end": entry.end_time, "is_idle": entry.is_idle}
            ))
        
        # Final snapshot
        final_state = {
            "processes": {
                p.pid: {
                    "completion": p.completion_time,
                    "turnaround": p.turnaround_time,
                    "waiting": p.waiting_time,
                    "response": p.response_time,
                    "state": "TERMINATED"
                } for p in result.processes
            },
            "current_time": result.total_time,
            "ready_queue": [],
            "running": None,
        }
        snapshots.append(SimulationSnapshot(result.total_time, final_state, "All processes completed"))
        
        return events, snapshots


# Convenience function for running all algorithms
def run_all_algorithms(processes: List[Process], time_quantum: float = 2.0) -> Dict[AlgorithmType, SchedulingResult]:
    """Run all scheduling algorithms and return results."""
    results = {}
    for algo in AlgorithmType:
        try:
            results[algo] = CPUScheduler.run_algorithm(algo, processes, time_quantum)
        except Exception as e:
            results[algo] = None  # Or store error
    return results