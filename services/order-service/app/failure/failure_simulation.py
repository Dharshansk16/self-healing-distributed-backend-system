import os
import time
import random

"""
Failure Simulation Methods
    -failure simulation methods for testing the self-healing capabilities of the order service.
    -These methods can be triggered to simulate various failure scenarios
"""

memory_holder = []

#exits the process immediately, simulating a crash
def crash():
    os._exit(1)

#simulates a CPU spike by running an infinite loop consuming 100% CPU
def cpu_spike():
    while True:
        pass

#simulates a memory leak by continuously appending large strings to the memory_holder list consuming more and more memory over time
def memory_leak():
    while True:
        memory_holder.append("leak" * 1000000)

#simulates latency by sleeping for 10 seconds before responding, testing the system's ability to handle slow responses and timeouts
def latency():
    time.sleep(10)

#simulates a random error by randomly raising an exception
def random_error():
    if random.random() > 0.5:
        raise Exception("Random failure triggered")