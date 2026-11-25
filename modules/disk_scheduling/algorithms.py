"""
Disk Scheduling Algorithms for Mini OS Simulator.

Implements:
- FCFS (First Come First Serve)
- SSTF (Shortest Seek Time First)
- SCAN (Elevator)
- C-SCAN (Circular SCAN)
- LOOK
- C-LOOK
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from copy import deepcopy


class DiskAlgorithm(Enum):
    FCFS = "fcfs"
    SSTF = "sstf"
    SCAN = "scan"
    CSCAN = "cscan"
    LOOK = "look"
    CLOOK = "clook"


@dataclass
class DiskConfig:
    """Disk configuration."""
    initial_head: int
    cylinder_range: Tuple[int, int]  # (min, max)
    requests: List[int]
    initial_direction: str = "up"  # "up" or "down"
    
    def __post_init__(self):
        self.min_cylinder, self.max_cylinder = self.cylinder_range
        
        # Cylinder addresses are non-negative integers.
        if any(type(v) is not int for v in (self.min_cylinder, self.max_cylinder, self.initial_head, *self.requests)):
            raise ValueError("Cylinder addresses must be integers")
        if self.min_cylinder < 0 or self.min_cylinder >= self.max_cylinder:
            raise ValueError("Require 0 <= min cylinder < max cylinder")
        # Validate
        if not (self.min_cylinder <= self.initial_head <= self.max_cylinder):
            raise ValueError(f"Initial head {self.initial_head} out of range {self.cylinder_range}")
        
        for req in self.requests:
            if not (self.min_cylinder <= req <= self.max_cylinder):
                raise ValueError(f"Request {req} out of range {self.cylinder_range}")
        
        if self.initial_direction not in ("up", "down"):
            raise ValueError("Direction must be 'up' or 'down'")


@dataclass
class DiskResult:
    """Result of disk scheduling simulation."""
    algorithm: DiskAlgorithm
    config: DiskConfig
    service_order: List[int]
    seek_distances: List[int]
    total_head_movement: int
    avg_seek_distance: float
    execution_path: List[Tuple[int, int, int]]  # (from, to, distance)
    
    # One event per execution_path entry: request, boundary, wrap, wrap_request.
    step_kinds: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm.value,
            "initial_head": self.config.initial_head,
            "cylinder_range": self.config.cylinder_range,
            "requests": self.config.requests,
            "initial_direction": self.config.initial_direction,
            "service_order": self.service_order,
            "seek_distances": self.seek_distances,
            "total_head_movement": self.total_head_movement,
            "avg_seek_distance": self.avg_seek_distance,
            "execution_path": self.execution_path,
            "step_kinds": self.step_kinds,
        }


class DiskScheduler:
    """Disk scheduling algorithm implementations."""
    
    @staticmethod
    def fcfs(config: DiskConfig) -> DiskResult:
        """First Come First Serve."""
        current = config.initial_head
        service_order = []
        seek_distances = []
        execution_path = []
        
        for request in config.requests:
            distance = abs(request - current)
            seek_distances.append(distance)
            execution_path.append((current, request, distance))
            service_order.append(request)
            current = request
        
        total = sum(seek_distances)
        avg = total / len(seek_distances) if seek_distances else 0
        
        return DiskResult(
            algorithm=DiskAlgorithm.FCFS,
            config=config,
            service_order=service_order,
            seek_distances=seek_distances,
            total_head_movement=total,
            avg_seek_distance=avg,
            execution_path=execution_path,
            step_kinds=["request"] * len(execution_path)
        )
    
    @staticmethod
    def sstf(config: DiskConfig) -> DiskResult:
        """Shortest Seek Time First."""
        current = config.initial_head
        remaining = config.requests.copy()
        service_order = []
        seek_distances = []
        execution_path = []
        
        while remaining:
            # Find closest request
            closest = min(remaining, key=lambda r: abs(r - current))
            distance = abs(closest - current)
            
            seek_distances.append(distance)
            execution_path.append((current, closest, distance))
            service_order.append(closest)
            current = closest
            remaining.remove(closest)
        
        total = sum(seek_distances)
        avg = total / len(seek_distances) if seek_distances else 0
        
        return DiskResult(
            algorithm=DiskAlgorithm.SSTF,
            config=config,
            service_order=service_order,
            seek_distances=seek_distances,
            total_head_movement=total,
            avg_seek_distance=avg,
            execution_path=execution_path,
            step_kinds=["request"] * len(execution_path)
        )
    
    @staticmethod
    def _sweep(config: DiskConfig, algorithm: DiskAlgorithm) -> DiskResult:
        """Finite request queue; count every cylinder traversed, including wraps.

        SCAN reverses at a boundary; LOOK reverses at a pending request.
        Circular variants keep their direction and wrap without intermediate service.
        Stop as soon as the last queued request is served.
        """
        current = config.initial_head
        up = config.initial_direction == "up"
        circular = algorithm in (DiskAlgorithm.CSCAN, DiskAlgorithm.CLOOK)
        use_boundary = algorithm in (DiskAlgorithm.SCAN, DiskAlgorithm.CSCAN)
        remaining = config.requests.copy()
        service_order, seek_distances, execution_path, step_kinds = [], [], [], []

        def move(destination, kind):
            nonlocal current
            distance = abs(destination - current)
            execution_path.append((current, destination, distance))
            seek_distances.append(distance)
            step_kinds.append(kind)
            if kind in ("request", "wrap_request"):
                service_order.append(destination)
                remaining.remove(destination)
            current = destination

        while remaining:
            candidates = [r for r in remaining if (r >= current if up else r <= current)]
            if candidates:
                move(min(candidates) if up else max(candidates), "request")
                continue
            if use_boundary:
                boundary = config.max_cylinder if up else config.min_cylinder
                if current != boundary:
                    move(boundary, "boundary")
            if circular:
                if use_boundary:
                    move(config.min_cylinder if up else config.max_cylinder, "wrap")
                else:
                    # C-LOOK services the destination, not requests passed during wrap.
                    move(min(remaining) if up else max(remaining), "wrap_request")
            else:
                up = not up

        total = sum(seek_distances)
        return DiskResult(algorithm, config, service_order, seek_distances,
                          total, total / len(service_order) if service_order else 0,
                          execution_path, step_kinds)

    @staticmethod
    def scan(config: DiskConfig) -> DiskResult:
        return DiskScheduler._sweep(config, DiskAlgorithm.SCAN)

    @staticmethod
    def cscan(config: DiskConfig) -> DiskResult:
        return DiskScheduler._sweep(config, DiskAlgorithm.CSCAN)

    @staticmethod
    def look(config: DiskConfig) -> DiskResult:
        return DiskScheduler._sweep(config, DiskAlgorithm.LOOK)

    @staticmethod
    def clook(config: DiskConfig) -> DiskResult:
        return DiskScheduler._sweep(config, DiskAlgorithm.CLOOK)

    @staticmethod
    def run_algorithm(algorithm: DiskAlgorithm, config: DiskConfig) -> DiskResult:
        """Run specified disk scheduling algorithm."""
        if algorithm == DiskAlgorithm.FCFS:
            return DiskScheduler.fcfs(config)
        elif algorithm == DiskAlgorithm.SSTF:
            return DiskScheduler.sstf(config)
        elif algorithm == DiskAlgorithm.SCAN:
            return DiskScheduler.scan(config)
        elif algorithm == DiskAlgorithm.CSCAN:
            return DiskScheduler.cscan(config)
        elif algorithm == DiskAlgorithm.LOOK:
            return DiskScheduler.look(config)
        elif algorithm == DiskAlgorithm.CLOOK:
            return DiskScheduler.clook(config)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")
    
    @staticmethod
    def compare_all(config: DiskConfig) -> Dict[DiskAlgorithm, DiskResult]:
        """Run all algorithms for comparison."""
        results = {}
        for algo in DiskAlgorithm:
            results[algo] = DiskScheduler.run_algorithm(algo, config)
        return results


def generate_sample_disk_config() -> DiskConfig:
    """Generate sample disk configuration."""
    return DiskConfig(
        initial_head=50,
        cylinder_range=(0, 199),
        requests=[98, 183, 37, 122, 14, 124, 65, 67],
        initial_direction="up"
    )