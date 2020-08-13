# Start the watchdog first.
import machine
watchdog = machine.WDT(timeout=5000).feed

print("boot.py")
import sys, gc

# Add stubs to Python path.
sys.path.insert(0, "/stublibs")

# Enable gc after allocation of this many bytes:
gc.threshold(2**11)
gc.collect()
