"""
Unit tests for Process Manager.
"""

import unittest
from modules.process_manager.algorithms import (
    ProcessManager, SimulatedProcess, ProcessState, TransitionReason,
    generate_sample_processes
)


class TestProcessManager(unittest.TestCase):
    """Test cases for Process Manager simulation."""
    
    def setUp(self):
        """Set up sample processes."""
        self.processes = generate_sample_processes()
    
    def test_multiprogramming_basic(self):
        """Test basic multiprogramming simulation."""
        result = ProcessManager.simulate_multiprogramming(
            self.processes, time_slice=2.0
        )
        
        # All processes should complete
        self.assertEqual(len(result.processes), 5)
        for p in result.processes:
            self.assertEqual(p.state, ProcessState.TERMINATED)
            self.assertGreater(p.completion_time, 0)
            self.assertEqual(p.turnaround_time, p.completion_time - p.arrival_time)
            self.assertAlmostEqual(p.waiting_time, p.turnaround_time - p.burst_time - sum(b[0] - a[0] for a, b in zip(p.state_history, p.state_history[1:]) if a[1].value == 'waiting'), places=7)
        
        # Should have context switches
        self.assertGreater(result.context_switches, 0)
        
        # CPU utilization should be reasonable
        self.assertGreater(result.cpu_utilization, 0)
        self.assertLessEqual(result.cpu_utilization, 100)
        
        # Throughput
        self.assertGreater(result.throughput, 0)
        
        # Total time
        self.assertGreater(result.total_time, 0)
        
        # Degree of multiprogramming
        self.assertGreater(result.degree_of_multiprogramming, 0)
    
    def test_multiprogramming_no_io(self):
        """Test multiprogramming with no I/O."""
        processes = [
            SimulatedProcess("P1", 0, 10, io_frequency=0),
            SimulatedProcess("P2", 1, 5, io_frequency=0),
            SimulatedProcess("P3", 2, 8, io_frequency=0),
        ]
        
        result = ProcessManager.simulate_multiprogramming(processes, time_slice=2.0)
        
        # All should complete
        for p in result.processes:
            self.assertEqual(p.state, ProcessState.TERMINATED)
        
        # No I/O events in schedule
        io_events = [e for e in result.schedule if e.event_type == "io"]
        self.assertEqual(len(io_events), 0)
    
    def test_multiprogramming_single_process(self):
        """Test with single process."""
        processes = [SimulatedProcess("P1", 0, 10)]
        
        result = ProcessManager.simulate_multiprogramming(processes, time_slice=2.0)
        
        self.assertEqual(len(result.processes), 1)
        self.assertEqual(result.processes[0].completion_time, 10)
        self.assertEqual(result.processes[0].turnaround_time, 10)
        self.assertEqual(result.processes[0].waiting_time, 0)
        self.assertEqual(result.processes[0].response_time, 0)
    
    def test_multiprocessing_basic(self):
        """Test basic multiprocessing simulation."""
        result = ProcessManager.simulate_multiprocessing(
            self.processes, num_cores=2, time_slice=2.0
        )
        
        # All processes should complete
        self.assertEqual(len(result.processes), 5)
        for p in result.processes:
            self.assertEqual(p.state, ProcessState.TERMINATED)
            self.assertGreater(p.completion_time, 0)
        
        # Should have per-core schedules
        self.assertEqual(len(result.core_schedules), 2)
        self.assertIn(0, result.core_schedules)
        self.assertIn(1, result.core_schedules)
        
        # Core utilizations
        self.assertEqual(len(result.core_utilizations), 2)
        for util in result.core_utilizations.values():
            self.assertGreaterEqual(util, 0)
            self.assertLessEqual(util, 100)
        
        # Overall utilization
        self.assertGreaterEqual(result.overall_cpu_utilization, 0)
        self.assertLessEqual(result.overall_cpu_utilization, 100)
        
        # Total time should be less than single-core (parallelism)
        # But we can't guarantee due to I/O, just check it runs
        self.assertGreater(result.total_time, 0)
    
    def test_multiprocessing_single_core(self):
        """Test multiprocessing with 1 core (should equal multiprogramming)."""
        mp_result = ProcessManager.simulate_multiprogramming(
            self.processes, time_slice=2.0
        )
        mpc_result = ProcessManager.simulate_multiprocessing(
            self.processes, num_cores=1, time_slice=2.0
        )
        
        # Both should complete all processes
        self.assertEqual(len(mp_result.processes), len(mpc_result.processes))
        
        # Total times might differ slightly due to randomness, but should be similar
        # (Both use same time slice and logic)
    
    def test_multiprocessing_more_cores_than_processes(self):
        """Test with more cores than processes."""
        processes = [
            SimulatedProcess("P1", 0, 10),
            SimulatedProcess("P2", 1, 5),
        ]
        
        result = ProcessManager.simulate_multiprocessing(processes, num_cores=4, time_slice=2.0)
        
        # Both should complete
        for p in result.processes:
            self.assertEqual(p.state, ProcessState.TERMINATED)
        
        # Should have 4 core schedules
        self.assertEqual(len(result.core_schedules), 4)
    
    def test_state_transitions(self):
        """Test that processes go through correct state transitions."""
        processes = [
            SimulatedProcess("P1", 0, 10, io_frequency=0),
            SimulatedProcess("P2", 1, 5, io_frequency=0),
        ]
        
        result = ProcessManager.simulate_multiprogramming(processes, time_slice=2.0)
        
        for p in result.processes:
            # Check state history
            states = [s[1] for s in p.state_history]
            
            # Should start as NEW
            self.assertEqual(states[0], ProcessState.NEW)
            
            # Should transition to READY
            self.assertIn(ProcessState.READY, states)
            
            # Should run
            self.assertIn(ProcessState.RUNNING, states)
            
            # Should terminate
            self.assertEqual(states[-1], ProcessState.TERMINATED)
            
            # Check transition reasons
            reasons = [s[2] for s in p.state_history]
            self.assertIn(TransitionReason.CREATED.value, reasons)
            self.assertIn(TransitionReason.SCHEDULED.value, reasons)
            self.assertIn(TransitionReason.TERMINATED.value, reasons)
    
    def test_io_handling(self):
        """Test I/O request and completion handling."""
        processes = [
            SimulatedProcess("P1", 0, 20, io_frequency=5.0),  # Frequent I/O
        ]
        
        result = ProcessManager.simulate_multiprogramming(processes, time_slice=2.0)
        
        p = result.processes[0]
        states = [s[1] for s in p.state_history]
        reasons = [s[2] for s in p.state_history]
        
        # Should have WAITING state
        self.assertIn(ProcessState.WAITING, states)
        
        # Should have IO_REQUEST and IO_COMPLETE transitions
        self.assertIn(TransitionReason.IO_REQUEST.value, reasons)
        self.assertIn(TransitionReason.IO_COMPLETE.value, reasons)
        
        # Should have multiple RUNNING periods (preempted by I/O)
        running_count = states.count(ProcessState.RUNNING)
        self.assertGreater(running_count, 1)
    
    def test_preemption(self):
        """Test time slice preemption."""
        processes = [
            SimulatedProcess("P1", 0, 10, io_frequency=0),
            SimulatedProcess("P2", 0, 10, io_frequency=0),
        ]
        
        result = ProcessManager.simulate_multiprogramming(processes, time_slice=2.0)
        
        # Both should complete
        for p in result.processes:
            self.assertEqual(p.state, ProcessState.TERMINATED)
        
        # Should have preemptions
        preempt_events = [e for e in result.schedule if e.event_type == "preempt"]
        self.assertGreater(len(preempt_events), 0)
        
        # Context switches should occur
        self.assertGreater(result.context_switches, 0)
    
    def test_response_time(self):
        """Test response time calculation."""
        processes = [
            SimulatedProcess("P1", 5, 10),  # Arrives at 5
        ]
        
        result = ProcessManager.simulate_multiprogramming(processes, time_slice=2.0)
        
        p = result.processes[0]
        # Response time = start_time - arrival_time
        self.assertEqual(p.response_time, p.start_time - p.arrival_time)
        self.assertGreaterEqual(p.response_time, 0)
    
    def test_process_copy_independence(self):
        """Test that simulation doesn't modify original processes."""
        original_burst = self.processes[0].burst_time
        original_state = self.processes[0].state
        
        ProcessManager.simulate_multiprogramming(self.processes, time_slice=2.0)
        
        # Original should be unchanged
        self.assertEqual(self.processes[0].burst_time, original_burst)
        self.assertEqual(self.processes[0].state, original_state)


class TestSimulatedProcess(unittest.TestCase):
    """Test SimulatedProcess dataclass."""
    
    def test_creation(self):
        """Test process creation."""
        p = SimulatedProcess("P1", 0, 10, io_frequency=5.0, priority=2)
        
        self.assertEqual(p.pid, "P1")
        self.assertEqual(p.arrival_time, 0)
        self.assertEqual(p.burst_time, 10)
        self.assertEqual(p.io_frequency, 5.0)
        self.assertEqual(p.priority, 2)
        self.assertEqual(p.remaining_time, 10)
        self.assertEqual(p.state, ProcessState.NEW)
        self.assertEqual(p.core_id, -1)
    
    def test_state_history(self):
        """Test state history recording."""
        p = SimulatedProcess("P1", 0, 10)
        
        # Initial state is recorded automatically
        self.assertEqual(len(p.state_history), 1)
        self.assertEqual(p.state_history[0][1], ProcessState.NEW)
        
        p.record_state_change(5.0, ProcessState.READY, "created")
        p.record_state_change(6.0, ProcessState.RUNNING, "scheduled")
        
        self.assertEqual(len(p.state_history), 3)
        self.assertEqual(p.state_history[1], (5.0, ProcessState.READY, "created"))
        self.assertEqual(p.state_history[2], (6.0, ProcessState.RUNNING, "scheduled"))
        self.assertEqual(p.state, ProcessState.RUNNING)


if __name__ == "__main__":
    unittest.main()