print("main.py")
while True:
	try:
		print("Starting pyprofibus...")
		import gc
		gc.collect()

		# Start dummy example that uses virtual bus hardware.
		import example_dummy
		example_dummy.main()

		# Start the S7-312-2DP example.
		#import example_s7_315_2dp
		#example_s7_315_2dp.main()

		# Start the ET200S example.
		#import example_et200s
		#example_et200s.main()

	except Exception as e:
		print("FATAL: " + str(e))
