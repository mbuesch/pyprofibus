print("main.py")
import machine, gc, sys

# Start the pyprofibus application.
# Modify this to your needs.
# This function should never return. If it does nevertheless, a reboot is attempted.
def start_pyprofibus():
	print("Starting pyprofibus...")

	# Start dummy example that uses virtual bus hardware.
	import example_dummy_oneslave
	example_dummy_oneslave.main(confdir="examples", watchdog=watchdog) # Run main loop
	return

	# Start the S7-312-2DP example.
	#import example_s7_315_2dp
	#example_s7_315_2dp.main(confdir="examples", watchdog=watchdog) # Run main loop
	#return

	# Start the ET200S example.
	#import example_et200s
	#example_et200s.main(confdir="examples", watchdog=watchdog) # Run main loop
	#return


# Main execution loop.
# This runs start_pyprofibus and does its best to catch exceptions.
count = 0
while True:
	try:
		count += 1
		gc.collect()
		start_pyprofibus()
	except KeyboardInterrupt as e:
		raise e
	except Exception as e:
		try:
			print("FATAL exception:")
			sys.print_exception(e)
		except: pass
	except: pass
	try:
		if count >= 5:
			count = 0
			machine.reset()
	except: pass
