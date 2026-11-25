"""
Memory Management Algorithms for Mini OS Simulator.

Implements:
- Paging (logical to physical address translation)
- Page Replacement (FIFO, LRU, Optimal)
- Segmentation
- Memory Fragmentation (First Fit, Best Fit, Worst Fit)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from copy import deepcopy


class PageReplacementAlgorithm(Enum):
    FIFO = "fifo"
    LRU = "lru"
    OPTIMAL = "optimal"


class AllocationAlgorithm(Enum):
    FIRST_FIT = "first_fit"
    BEST_FIT = "best_fit"
    WORST_FIT = "worst_fit"


@dataclass
class PageTableEntry:
    """Single page table entry."""
    frame_number: int = -1
    valid: bool = False
    referenced: bool = False
    modified: bool = False
    protection: str = "RW"  # RW, RO, RX, etc.


@dataclass
class PagingConfig:
    """Paging configuration."""
    logical_memory_size: int  # in bytes
    physical_memory_size: int  # in bytes
    page_size: int  # in bytes
    
    @property
    def num_pages(self) -> int:
        return self.logical_memory_size // self.page_size
    
    @property
    def num_frames(self) -> int:
        return self.physical_memory_size // self.page_size


@dataclass
class PageReference:
    """Page reference for replacement simulation."""
    page_number: int
    timestamp: int = 0


@dataclass
class ReplacementResult:
    """Result of page replacement simulation."""
    algorithm: PageReplacementAlgorithm
    reference_string: List[int]
    num_frames: int
    frame_states: List[List[Optional[int]]]  # Frame contents at each step
    page_faults: List[bool]
    replaced_pages: List[Optional[int]]
    total_faults: int
    total_hits: int
    fault_rate: float
    hit_rate: float


@dataclass
class Segment:
    """Memory segment."""
    segment_id: int
    name: str
    base: int
    limit: int  # size
    
    @property
    def end(self) -> int:
        return self.base + self.limit - 1


@dataclass
class SegmentationResult:
    """Result of address translation."""
    segment_id: int
    offset: int
    physical_address: Optional[int]
    valid: bool
    error: Optional[str] = None


@dataclass
class MemoryBlock:
    """Memory block for fragmentation simulation."""
    start: int
    size: int
    allocated: bool = False
    process_id: Optional[str] = None
    
    @property
    def end(self) -> int:
        return self.start + self.size - 1


@dataclass
class FragmentationResult:
    """Result of memory allocation simulation."""
    algorithm: AllocationAlgorithm
    initial_blocks: List[MemoryBlock]
    final_blocks: List[MemoryBlock]
    allocations: List[Tuple[str, int, int, bool]]  # (process_id, size, start_addr, success)
    internal_fragmentation: int
    external_fragmentation: int
    allocated_memory: int
    free_memory: int


class PagingSimulator:
    """Paging simulation."""
    
    @staticmethod
    def translate_address(config: PagingConfig, logical_address: int, page_table: List[PageTableEntry]) -> Tuple[Optional[int], bool, str]:
        """
        Translate logical address to physical address.
        
        Returns: (physical_address, valid, explanation)
        """
        if logical_address < 0 or logical_address >= config.logical_memory_size:
            return None, False, f"Address {logical_address} out of logical memory range (0-{config.logical_memory_size-1})"
        
        page_num = logical_address // config.page_size
        offset = logical_address % config.page_size
        
        if page_num >= len(page_table):
            return None, False, f"Page number {page_num} exceeds page table size ({len(page_table)})"
        
        entry = page_table[page_num]
        
        if not entry.valid:
            return None, False, f"Page {page_num} not in memory (invalid bit)"
        
        if not 0 <= entry.frame_number < config.num_frames:
            return None, False, f"Frame number {entry.frame_number} outside valid range (0-{config.num_frames-1})"
        
        physical_address = entry.frame_number * config.page_size + offset
        
        explanation = (
            f"Logical Address: {logical_address}\n"
            f"  Page Number: {logical_address} // {config.page_size} = {page_num}\n"
            f"  Offset: {logical_address} % {config.page_size} = {offset}\n"
            f"  Page Table[{page_num}]: Frame = {entry.frame_number}, Valid = {entry.valid}\n"
            f"  Physical Address: {entry.frame_number} * {config.page_size} + {offset} = {physical_address}"
        )
        
        return physical_address, True, explanation
    
    @staticmethod
    def create_page_table(config: PagingConfig, frame_assignments: Dict[int, int]) -> List[PageTableEntry]:
        """Create page table from frame assignments."""
        page_table = [PageTableEntry() for _ in range(config.num_pages)]
        for page, frame in frame_assignments.items():
            if 0 <= page < config.num_pages and 0 <= frame < config.num_frames:
                page_table[page] = PageTableEntry(frame_number=frame, valid=True)
        return page_table


class PageReplacementSimulator:
    """Page replacement algorithm simulation."""
    
    @staticmethod
    def fifo(reference_string: List[int], num_frames: int) -> ReplacementResult:
        """FIFO page replacement."""
        frames = [None] * num_frames
        frame_states = []
        page_faults = []
        replaced_pages = []
        queue = []  # Track frame order for FIFO
        
        for step, page in enumerate(reference_string):
            if page in frames:
                # Page hit
                page_faults.append(False)
                replaced_pages.append(None)
                frame_states.append(frames.copy())
            else:
                # Page fault
                page_faults.append(True)
                
                if None in frames:
                    # Free frame available
                    idx = frames.index(None)
                    frames[idx] = page
                    queue.append(idx)
                    replaced_pages.append(None)
                else:
                    # Replace oldest
                    idx = queue.pop(0)
                    replaced = frames[idx]
                    frames[idx] = page
                    queue.append(idx)
                    replaced_pages.append(replaced)
                
                frame_states.append(frames.copy())
        
        total_faults = sum(page_faults)
        total_hits = len(page_faults) - total_faults
        
        return ReplacementResult(
            algorithm=PageReplacementAlgorithm.FIFO,
            reference_string=reference_string,
            num_frames=num_frames,
            frame_states=frame_states,
            page_faults=page_faults,
            replaced_pages=replaced_pages,
            total_faults=total_faults,
            total_hits=total_hits,
            fault_rate=total_faults / len(reference_string) if reference_string else 0,
            hit_rate=total_hits / len(reference_string) if reference_string else 0,
        )
    
    @staticmethod
    def lru(reference_string: List[int], num_frames: int) -> ReplacementResult:
        """LRU page replacement."""
        frames = [None] * num_frames
        frame_states = []
        page_faults = []
        replaced_pages = []
        last_used = {}  # page -> last access time
        
        for step, page in enumerate(reference_string):
            last_used[page] = step
            
            if page in frames:
                page_faults.append(False)
                replaced_pages.append(None)
                frame_states.append(frames.copy())
            else:
                page_faults.append(True)
                
                if None in frames:
                    idx = frames.index(None)
                    frames[idx] = page
                    replaced_pages.append(None)
                else:
                    # Find least recently used
                    lru_page = min(frames, key=lambda p: last_used.get(p, -1))
                    idx = frames.index(lru_page)
                    replaced = frames[idx]
                    frames[idx] = page
                    replaced_pages.append(replaced)
                
                frame_states.append(frames.copy())
        
        total_faults = sum(page_faults)
        total_hits = len(page_faults) - total_faults
        
        return ReplacementResult(
            algorithm=PageReplacementAlgorithm.LRU,
            reference_string=reference_string,
            num_frames=num_frames,
            frame_states=frame_states,
            page_faults=page_faults,
            replaced_pages=replaced_pages,
            total_faults=total_faults,
            total_hits=total_hits,
            fault_rate=total_faults / len(reference_string) if reference_string else 0,
            hit_rate=total_hits / len(reference_string) if reference_string else 0,
        )
    
    @staticmethod
    def optimal(reference_string: List[int], num_frames: int) -> ReplacementResult:
        """Optimal page replacement."""
        frames = [None] * num_frames
        frame_states = []
        page_faults = []
        replaced_pages = []
        
        for step, page in enumerate(reference_string):
            if page in frames:
                page_faults.append(False)
                replaced_pages.append(None)
                frame_states.append(frames.copy())
            else:
                page_faults.append(True)
                
                if None in frames:
                    idx = frames.index(None)
                    frames[idx] = page
                    replaced_pages.append(None)
                else:
                    # Find page used farthest in future (or never)
                    future_uses = {}
                    for i, future_page in enumerate(reference_string[step+1:], start=step+1):
                        if future_page in frames and future_page not in future_uses:
                            future_uses[future_page] = i
                    
                    # Pages never used again
                    never_used = [p for p in frames if p not in future_uses]
                    if never_used:
                        victim = never_used[0]
                    else:
                        victim = max(frames, key=lambda p: future_uses.get(p, float('inf')))
                    
                    idx = frames.index(victim)
                    replaced = frames[idx]
                    frames[idx] = page
                    replaced_pages.append(replaced)
                
                frame_states.append(frames.copy())
        
        total_faults = sum(page_faults)
        total_hits = len(page_faults) - total_faults
        
        return ReplacementResult(
            algorithm=PageReplacementAlgorithm.OPTIMAL,
            reference_string=reference_string,
            num_frames=num_frames,
            frame_states=frame_states,
            page_faults=page_faults,
            replaced_pages=replaced_pages,
            total_faults=total_faults,
            total_hits=total_hits,
            fault_rate=total_faults / len(reference_string) if reference_string else 0,
            hit_rate=total_hits / len(reference_string) if reference_string else 0,
        )
    
    @staticmethod
    def run_algorithm(algorithm: PageReplacementAlgorithm, reference_string: List[int], num_frames: int) -> ReplacementResult:
        """Run specified page replacement algorithm."""
        if num_frames <= 0:
            raise ValueError("Number of frames must be positive")
        if not reference_string:
            raise ValueError("Reference string cannot be empty")
        
        if algorithm == PageReplacementAlgorithm.FIFO:
            return PageReplacementSimulator.fifo(reference_string, num_frames)
        elif algorithm == PageReplacementAlgorithm.LRU:
            return PageReplacementSimulator.lru(reference_string, num_frames)
        elif algorithm == PageReplacementAlgorithm.OPTIMAL:
            return PageReplacementSimulator.optimal(reference_string, num_frames)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")
    
    @staticmethod
    def compare_all(reference_string: List[int], num_frames: int) -> Dict[PageReplacementAlgorithm, ReplacementResult]:
        """Run all algorithms for comparison."""
        results = {}
        for algo in PageReplacementAlgorithm:
            results[algo] = PageReplacementSimulator.run_algorithm(algo, reference_string, num_frames)
        return results


class SegmentationSimulator:
    """Segmentation simulation."""
    
    @staticmethod
    def translate_address(segments: List[Segment], logical_address: Tuple[int, int]) -> SegmentationResult:
        """
        Translate segmented logical address (segment_id, offset) to physical address.
        
        Returns SegmentationResult.
        """
        segment_id, offset = logical_address
        
        # Find segment
        segment = None
        for s in segments:
            if s.segment_id == segment_id:
                segment = s
                break
        
        if segment is None:
            return SegmentationResult(
                segment_id=segment_id,
                offset=offset,
                physical_address=None,
                valid=False,
                error=f"Segment {segment_id} does not exist"
            )
        
        if offset < 0 or offset >= segment.limit:
            return SegmentationResult(
                segment_id=segment_id,
                offset=offset,
                physical_address=None,
                valid=False,
                error=f"Offset {offset} exceeds segment limit {segment.limit} (segmentation fault)"
            )
        
        physical_address = segment.base + offset
        
        return SegmentationResult(
            segment_id=segment_id,
            offset=offset,
            physical_address=physical_address,
            valid=True,
            error=None
        )
    
    @staticmethod
    def explain_translation(segments: List[Segment], logical_address: Tuple[int, int]) -> str:
        """Generate explanation for address translation."""
        segment_id, offset = logical_address
        result = SegmentationSimulator.translate_address(segments, logical_address)
        
        explanation = f"Logical Address: (Segment={segment_id}, Offset={offset})\n"
        
        segment = next((s for s in segments if s.segment_id == segment_id), None)
        if segment:
            explanation += f"  Segment {segment_id} ({segment.name}): Base={segment.base}, Limit={segment.limit}\n"
            explanation += f"  Check: 0 <= {offset} < {segment.limit} "
            if result.valid:
                explanation += "✓\n"
                explanation += f"  Physical Address = Base + Offset = {segment.base} + {offset} = {result.physical_address}"
            else:
                explanation += "✗ (Segmentation Fault)\n"
                explanation += f"  Error: {result.error}"
        else:
            explanation += f"  Error: Segment {segment_id} not found"
        
        return explanation


class FragmentationSimulator:
    """Memory fragmentation simulation."""
    
    @staticmethod
    def allocate(
        algorithm: AllocationAlgorithm,
        memory_blocks: List[MemoryBlock],
        process_requests: List[Tuple[str, int]]
    ) -> FragmentationResult:
        """
        Simulate memory allocation.
        
        Args:
            algorithm: Allocation algorithm
            memory_blocks: Initial free memory blocks
            process_requests: List of (process_id, size) requests
        
        Returns:
            FragmentationResult
        """
        # Reject invalid inputs before allocating; adjacent supplied blocks remain independent.
        if any(b.start < 0 or b.size <= 0 for b in memory_blocks):
            raise ValueError("Memory block start must be non-negative and size positive")
        ordered = sorted(memory_blocks, key=lambda b: b.start)
        if any(left.end >= right.start for left, right in zip(ordered, ordered[1:])):
            raise ValueError("Memory blocks must not overlap")
        if any(not pid.strip() or size <= 0 for pid, size in process_requests):
            raise ValueError("Process IDs must be non-empty and sizes positive")
        if len({pid for pid, _ in process_requests}) != len(process_requests):
            raise ValueError("Process IDs must be unique")
        # Work with copies
        blocks = [MemoryBlock(b.start, b.size, b.allocated, b.process_id) for b in memory_blocks]
        allocations = []
        
        for pid, size in process_requests:
            allocated = False
            start_addr = -1
            
            if algorithm == AllocationAlgorithm.FIRST_FIT:
                # Find first block that fits
                for i, block in enumerate(blocks):
                    if not block.allocated and block.size >= size:
                        # Allocate at start of block
                        start_addr = block.start
                        allocated = True
                        
                        if block.size == size:
                            # Exact fit
                            blocks[i].allocated = True
                            blocks[i].process_id = pid
                        else:
                            # Split block
                            old_size = block.size
                            blocks[i].size = size
                            blocks[i].allocated = True
                            blocks[i].process_id = pid
                            # Insert remaining as free block
                            blocks.insert(i + 1, MemoryBlock(
                                start=block.start + size,
                                size=old_size - size,
                                allocated=False
                            ))
                        break
            
            elif algorithm == AllocationAlgorithm.BEST_FIT:
                # Find smallest block that fits
                best_idx = -1
                best_size = float('inf')
                for i, block in enumerate(blocks):
                    if not block.allocated and block.size >= size and block.size < best_size:
                        best_idx = i
                        best_size = block.size
                
                if best_idx >= 0:
                    block = blocks[best_idx]
                    start_addr = block.start
                    allocated = True
                    
                    if block.size == size:
                        blocks[best_idx].allocated = True
                        blocks[best_idx].process_id = pid
                    else:
                        old_size = block.size
                        blocks[best_idx].size = size
                        blocks[best_idx].allocated = True
                        blocks[best_idx].process_id = pid
                        blocks.insert(best_idx + 1, MemoryBlock(
                            start=block.start + size,
                            size=old_size - size,
                            allocated=False
                        ))
            
            elif algorithm == AllocationAlgorithm.WORST_FIT:
                # Find largest block
                worst_idx = -1
                worst_size = -1
                for i, block in enumerate(blocks):
                    if not block.allocated and block.size >= size and block.size > worst_size:
                        worst_idx = i
                        worst_size = block.size
                
                if worst_idx >= 0:
                    block = blocks[worst_idx]
                    start_addr = block.start
                    allocated = True
                    
                    if block.size == size:
                        blocks[worst_idx].allocated = True
                        blocks[worst_idx].process_id = pid
                    else:
                        old_size = block.size
                        blocks[worst_idx].size = size
                        blocks[worst_idx].allocated = True
                        blocks[worst_idx].process_id = pid
                        blocks.insert(worst_idx + 1, MemoryBlock(
                            start=block.start + size,
                            size=old_size - size,
                            allocated=False
                        ))
            
            allocations.append((pid, size, start_addr, allocated))
        
        # Calculate fragmentation
        internal_frag = 0
        largest_free = 0
        allocated_mem = 0
        free_mem = 0
        
        for block in blocks:
            if block.allocated:
                allocated_mem += block.size
            else:
                free_mem += block.size
                largest_free = max(largest_free, block.size)

        # Size-based estimate: free space outside the largest available block.
        # The simulator treats supplied blocks as separate holes (no coalescing).
        external_frag = free_mem - largest_free
        
        # Internal fragmentation would be calculated if we tracked exact process sizes
        # For simplicity, we assume no internal fragmentation in this model
        # (since we split blocks exactly)
        
        return FragmentationResult(
            algorithm=algorithm,
            initial_blocks=memory_blocks,
            final_blocks=blocks,
            allocations=allocations,
            internal_fragmentation=internal_frag,
            external_fragmentation=external_frag,
            allocated_memory=allocated_mem,
            free_memory=free_mem,
        )
    
    @staticmethod
    def compare_all(memory_blocks: List[MemoryBlock], process_requests: List[Tuple[str, int]]) -> Dict[AllocationAlgorithm, FragmentationResult]:
        """Run all allocation algorithms for comparison."""
        results = {}
        for algo in AllocationAlgorithm:
            results[algo] = FragmentationSimulator.allocate(algo, memory_blocks, process_requests)
        return results


def generate_sample_paging_config() -> PagingConfig:
    """Generate sample paging configuration."""
    return PagingConfig(
        logical_memory_size=64 * 1024,  # 64 KB
        physical_memory_size=32 * 1024,  # 32 KB
        page_size=4 * 1024  # 4 KB
    )


def generate_sample_page_references() -> List[int]:
    """Generate sample page reference string."""
    return [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]


def generate_sample_segments() -> List[Segment]:
    """Generate sample segments."""
    return [
        Segment(0, "Code", 0, 1024),
        Segment(1, "Data", 1024, 2048),
        Segment(2, "Stack", 4096, 1024),
        Segment(3, "Heap", 6144, 4096),
    ]


def generate_sample_memory_blocks() -> List[MemoryBlock]:
    """Generate sample memory blocks for fragmentation."""
    return [
        MemoryBlock(0, 100),
        MemoryBlock(100, 500),
        MemoryBlock(600, 200),
        MemoryBlock(800, 300),
        MemoryBlock(1100, 400),
    ]


def generate_sample_process_requests() -> List[Tuple[str, int]]:
    """Generate sample process memory requests."""
    return [
        ("P1", 212),
        ("P2", 417),
        ("P3", 112),
        ("P4", 426),
    ]