import os
import time
import random

memory_holder = []

def crash():
    os._exit(1)

def cpu_spike():
    while True:
        pass

def memory_leak():
    while True:
        memory_holder.append("leak" * 1000000)

def latency():
    time.sleep(10)

def random_error():
    if random.random() > 0.5:
        raise Exception("Random failure triggered")