print("main.py")


# Start the pyprofibus application.
# Modify this to your needs.
# This function should never return. If it does nevertheless, a reboot is attempted.
def start_pyprofibus():
	print("Starting pyprofibus...")

	# Start dummy example that uses virtual bus hardware.
	import example_dummy
	example_dummy.main() # Run main loop
	return

	# Start the S7-312-2DP example.
	#import example_s7_315_2dp
	#example_s7_315_2dp.main() # Run main loop
	#return

	# Start the ET200S example.
	#import example_et200s
	#example_et200s.main() # Run main loop
	#return


# Main execution loop.
# This runs start_pyprofibus and does its best to catch exceptions.
count = 0
while True:
	try:
		count += 1
		import gc
		gc.collect()
		start_pyprofibus()
	except KeyboardInterrupt as e:
		raise e
	except Exception as e:
		try:
			print("FATAL exception: " + str(e))
		except: pass
	except: pass
	try:
		if count >= 5:
			count = 0
			import machine
			machine.reset()
	except: pass
