"""
this is an attempt to convert a readable patt format (similar to the ones compatible with arbitrarypatterngenerator) into the 4-word format that can be cat into pattern generator v2
it reads pattfile written in the following format and generate the corresponding dpatt:
	#triggered input_line use_table threshold_counts_per_second if_success_table if_failure_table time_to_trigger [bits to turn on(0-25)]
	#sequential [repeat_table(at least 0)] use_table end_table time [bits to turn on(0-25)]
	#conditional input_line use_table if_success_table trigger_width [bits to turn on(0-25)]
in this version, 
1) internal counters 0 and 1 are always loaded with 10 and 100 to deal with '>3ms' and '>30ms' scale signal
counters 2 and 3 is used if sequential repeats (which means only two sequential can repeat currently)
2) toupper func is not implemented, so the comparison is case-sensitive
3) triggered accepts only 1-line pattern
4) hooks are not implemented yet
5) fixed directory to save dpatt
7) always start from row 0 and table 0
8) at sequential loops, the loading of counter will introduce a 10ns shift; if next-table existed, the additional line to jump to next-table will also introduce 10ns shift
9) conditional is implemented
10) check number of lines before the file is being cat'ed
updated on 10/7/2019

Update on 2/1/2020 by Chin Chean:
1) table_dic, table_lst, and rep_count are cleared every time generator is called from the GUI.
2) When uploading scripts multiple times, adding a config 0; at the start of the .word file might prevent crashing of device. This command is now appended on the generated file.

@author: Chang Hoong  QO LAB, NUS
"""

mode_list = ['','.','triggered','sequential','conditional']
unit_list = ['','ns','us','ms']
error_list = ['no error (0)','invalid token (1)','too many sequential loop (2)', 'invalid output (3)', 'invalid number (4)', 'no unit found (5)', 'shorter than clock cycle (6)', 'repeated output warning (7)', 'invalid termination (8)','null error (9)','repeated table number (10)','multiple thresholds for same input (11)', 'pattern too long (12)']


table_dic = {}	#contains information about address of each table for branching
table_lst = []	#contains all patterns to be applied
rep_count = []	#contains additional internal counters being used
# format of table_lst
# (if triggered) [table_no, success_table_no, fail_table_no, input_line, threshold_counts, num_clock_cycle, output] (7 components)
# (if sequential) [table_no, next_table, repeat, num_clock_cycle, output] (5 components)
# (if conditional) [table_no success_table_no, NULL, input_line, num_clock_cycle, output] (6 components)
# number of components can decide mode type
# 'output' consists of a two-element array (left right word)

# find token and return token_nb, ptr_in_str 
def find_token(argument,token_list):
	num_list = len(token_list)
	for i in range(num_list-1,0,-1):
		ptr=argument.find(token_list[i])
		if(ptr >= 0):
			return i,ptr
	return 0,-1 # invalid token

# return the readout number + remaining string
# if number not found, output -1 and ''
def parse_number(argument):
	newpos = 0
	# take out empty spaces
	while(argument[newpos]==' ' or argument[newpos]=='\t' or argument[newpos]==':' or argument[newpos]==','):
		newpos = newpos + 1
	if (argument[newpos]=='\n'):
		print(error_list[4])
		return -1,''
	num_str = ''
	while(True):
		c = argument[newpos]
		# ASCII comparison
		if ((c<'0') or (c >'9')):
			break; # end of number
		else:
			num_str = num_str + c
			newpos = newpos+1
	if num_str=='':
		return -1,argument[newpos:]
	return int(num_str),argument[newpos:]
	
# need old token so that 2nd line of sequential can be interpredated as sequential
# return the old token and the remaining argument
def parse_command(argument, old_token):
	global table_lst
	# argument is a long string
	newpos = 0
	# take out empty spaces
	while(argument[newpos]==' ' or argument[newpos]=='\t' or argument[newpos]==':' or argument[newpos]==','):
		newpos = newpos + 1
	if (argument[newpos]=='\n'):
		return old_token, argument[newpos:]	#end of line
	token, ptr=find_token(argument[newpos:],mode_list)
	# 0: invalid token, 1: termination, 2: triggered, 3: sequential, 4: conditional
	if (token==0 and old_token==3):
		# use the previous input table number
		new_argmt = interpret_seq([-1], argument[newpos:])
		return 3, new_argmt
	elif token==0: #no token found
		raise Exception(error_list[1]) #error
	elif token==1: #termination
		return 1, ''
	elif token==2: #trigger
		new_argmt = interpret_tri(argument[(ptr+9):])
		return 2, new_argmt
	elif token==4: #conditional
		new_argmt = interpret_con(argument[(ptr+11):])
		return 4, new_argmt
	else: # sequential
		# extract information for repeat, table_no, and next_table
		new_argmt = argument[(ptr+10):]
		repeat, new_argmt = parse_number(new_argmt) # first argument is repeat
		if (repeat < 0 or repeat>65535):
	                raise Exception('Invalid repeat number at sequential.')
		table_no, new_argmt = parse_number(new_argmt) # 2nd argument is table_no
		if (table_no < 0):
	                raise Exception('Invalid table number at sequential.')
		next_table, new_argmt = parse_number(new_argmt) # 3rd argument is next_table
		if (next_table < 0):
	                raise Exception('Invalid next-table number at sequential.')
		# standard interpretation for sequential, read TIME and output bit
		new_argmt = interpret_seq([table_no,next_table,repeat],new_argmt) # rearrange the information to facilitate construction
		return 3, new_argmt


Max_cyclenumber_per_line = 65536

def time_balancer(left_output, right_output, Nclockcycle, table_str, addr_ptr, inputline=-1):
	Ncounter_temp = int(Nclockcycle/Max_cyclenumber_per_line)
	if Ncounter_temp < 5:	# <3.28ms, don't need loop
		num_step_loop = Nclockcycle
		if inputline!=-1: # trigger
			table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, 0, 4096+2**(inputline),addr_ptr) #load counters, 4096->special command	
			addr_ptr = addr_ptr + 1 # next line
		while(num_step_loop>Max_cyclenumber_per_line):
			table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, Max_cyclenumber_per_line-1, addr_ptr+1,addr_ptr)
			num_step_loop = num_step_loop - Max_cyclenumber_per_line
			addr_ptr = addr_ptr + 1
		if num_step_loop == 0:
			num_step_loop = 1
			print('Duration remainder = 0!')
		table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, num_step_loop-1, addr_ptr+1,addr_ptr)
		addr_ptr = addr_ptr + 1

	elif Ncounter_temp <= 50: # 3.28ms<t<32.8ms, we use loop with counter 10
		Nclockcycle = Nclockcycle - 1 # correction to take into account the first step used for counter loading
		num_step_loop = int(Nclockcycle/10) # number of clock cycle per loop
		# the if-else condition here ensures we can allocate time into "decrement" and "conditional check"
		if num_step_loop <= Max_cyclenumber_per_line:
			loop_step_size = int((num_step_loop-1)/2)
		else:
			loop_step_size = Max_cyclenumber_per_line # maximum step size
		remainder = Nclockcycle%10
		if inputline!=-1: # trigger
			table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, remainder, 4096+16+2**(inputline),addr_ptr) #load counters, 4096->special command, 16->intcounter for 10
		else:
			table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, remainder, 4096+16,addr_ptr) #load counters, 4096->special command, 16->intcounter for 10
		addr_ptr = addr_ptr + 1 # next line
		loop_start = addr_ptr
		while(num_step_loop!=0):
			if num_step_loop > loop_step_size:
				if (loop_start==addr_ptr):
					table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output,right_output,loop_step_size-1,4352,addr_ptr) # decrement on int counter 0 (4096+256)
				else:
					table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output,right_output,loop_step_size-1,addr_ptr+1,addr_ptr) # decrement on int counter 0 (4096+256)
				addr_ptr = addr_ptr + 1
				num_step_loop = num_step_loop - loop_step_size
			else:
				# last step of the loop
				table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output,right_output,num_step_loop-1,49152+loop_start,addr_ptr) # jump to loop_start on nonzero int counter 0 (49152 + loop_start)
				addr_ptr = addr_ptr + 1
				break;

	else: # longer than 32.8ms operation
		Nclockcycle = Nclockcycle - 1 # correction to take into account the first step used for counter loading
		num_step_loop = int(Nclockcycle/100) # number of clock cycle per loop
		if num_step_loop <= Max_cyclenumber_per_line:
			loop_step_size = int((num_step_loop-1)/2)
		else:
			loop_step_size = Max_cyclenumber_per_line # maximum step size
		remainder = Nclockcycle%100
		if inputline!=-1: # trigger
			table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, remainder, 4096+32+2**(inputline),addr_ptr) #load counters, 4096->special command, 32->intcounter for 100
		else:
			table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, remainder, 4096+32,addr_ptr) #load counters, 4096->special command, 32->intcounter for 100
		addr_ptr = addr_ptr + 1 # next line
		loop_start = addr_ptr
		while(num_step_loop!=0):
			if num_step_loop > loop_step_size:
				if (loop_start==addr_ptr):
					table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output,right_output,loop_step_size-1,4608,addr_ptr) # decrement on int counter 1 (4096+512)
				else:
					table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output,right_output,loop_step_size-1,addr_ptr+1,addr_ptr)
				addr_ptr = addr_ptr + 1
				num_step_loop = num_step_loop - loop_step_size
			else:
				# last step of the loop
				table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output,right_output,num_step_loop-1,53248+loop_start,addr_ptr) # jump to loop_start on nonzero int counter 1 (49152 + loop_start)
				addr_ptr = addr_ptr + 1
				break;

	return table_str, addr_ptr

# output the remaining string
# should read duration and output bits
def interpret_seq(table_no_arr, argument):
	global table_lst
	temp_action_table = []
	if table_no_arr[0]==-1:
		# use the previous table settings
		temp_action_table.append(table_lst[-1][0]) # table_no
		temp_action_table.append(table_lst[-1][1]) # next_table
		temp_action_table.append(table_lst[-1][2]) # repeat
	else:
		temp_action_table.append(table_no_arr[0]) # table_no
		temp_action_table.append(table_no_arr[1]) # next table
		temp_action_table.append(table_no_arr[2]) # repeat
	# read time
	dura, new_argmt = parse_number(argument)
	# identify unit
	token, ptr = find_token(new_argmt, unit_list)
	if token == 0:
		raise Exception(error_list[5]+' :'+argument)
	elif token == 1: # ns
		if dura < 10:
			print(error_list[6]+', '+str(dura)+'ns is round up to 10ns')
			n_cycle = 1
		else:
			n_cycle = int(dura/10)
	elif token == 2: # us
		n_cycle = int(1000*dura/10)
	elif token == 3: # ms
		n_cycle = int(1000000*dura/10)
	else:
		raise Exception('interpret_seq error')
	temp_action_table.append(n_cycle)

	# READ OUTPUT BITS
	new_argmt = new_argmt[ptr+2:]	
	outputbitarray = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0] # to store on off
	while (True):
		outbit, new_argmt = parse_number(new_argmt)
		if outbit==-1:
			break
		elif outbit > 31:
			raise Exception(error_list[3])
		elif outputbitarray[outbit] == 1:
			print(error_list[7])
		else:
			outputbitarray[outbit] = 1
	decsum_l,decsum_r = 0,0
	for i in range(16):
		decsum_l = decsum_l + outputbitarray[i]*2**i
		decsum_r = decsum_r + outputbitarray[i+16]*2**i
	temp_action_table.append([int(decsum_l),int(decsum_r)])

	newpos = 0
	# take out empty spaces
	while(new_argmt[newpos]==' ' or new_argmt[newpos]=='\t' or new_argmt[newpos]==':' or new_argmt[newpos]==','):
		newpos = newpos + 1
	if new_argmt[newpos]!=';':
		raise Exception(error_list[8]+': ";"')
	# upload to main action table list
	table_lst.append(temp_action_table)
	#print(temp_action_table) #debug
	return new_argmt

# output the remaining string
# should read input_line use_table threshold_counts_per_second if_success_table if_failure_table time_to_trigger [bits to turn on(0-25)]
def interpret_tri(argument):
	global table_lst
	temp_action_table = []
	input_line, new_argmt = parse_number(argument) 	# input_line
	if (input_line < 0 or input_line > 3):
		raise Exception('Invalid input line at trigger.')
	use_table, new_argmt = parse_number(new_argmt) 		# use_table
	if (use_table < 0):
                raise Exception('Invalid table number at trigger.')	
	threshold, new_argmt = parse_number(new_argmt) 		# threshold
	if (threshold <= 0):
		raise Exception('Invalid trigger threshold')
	goto_table, new_argmt = parse_number(new_argmt) 	# goto_table
	if (goto_table < 0):
                raise Exception('Invalid success_table number at trigger.')
	fail_table, new_argmt = parse_number(new_argmt) 	# fail_table
	if (fail_table < 0):
                raise Exception('Invalid fail_table number at trigger.')
	#[table_no, success_table_no, fail_table_no, input_line, threshold_counts, num_clock_cycle, output]
	temp_action_table.append(use_table)
	temp_action_table.append(goto_table)
	temp_action_table.append(fail_table)
	temp_action_table.append(input_line)
	temp_action_table.append(threshold)

	# read time
	dura, new_argmt = parse_number(new_argmt)
	# identify unit
	token, ptr = find_token(new_argmt, unit_list)
	if token == 0:
		raise Exception(error_list[5]+' :'+argument)
	elif token == 1: # ns
		if dura < 10:
			print(error_list[6]+', '+str(dura)+'ns is round up to 10ns')
			n_cycle = 1
		else:
			n_cycle = int(dura/10)
	elif token == 2: # us
		n_cycle = int(1000*dura/10)
	elif token == 3: # ms
		n_cycle = int(1000000*dura/10)
	else:
		raise Exception('interpret_tri error')
	# replace threshold per second with threshold counts
	temp_action_table[-1] = int(temp_action_table[-1]*n_cycle*10e-9)
	temp_action_table.append(n_cycle)

	# READ OUTPUT BITS
	new_argmt = new_argmt[ptr+2:]	
	outputbitarray = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0] # to store on off
	while (True):
		outbit, new_argmt = parse_number(new_argmt)
		if outbit==-1:
			break
		elif outbit > 31:
			raise Exception(error_list[3])
		elif outputbitarray[outbit] == 1:
			print(error_list[7])
		else:
			outputbitarray[outbit] = 1
	decsum_l,decsum_r = 0,0
	for i in range(16):
		decsum_l = decsum_l + outputbitarray[i]*2**i
		decsum_r = decsum_r + outputbitarray[i+16]*2**i
	temp_action_table.append([int(decsum_l),int(decsum_r)])

	newpos = 0
	# take out empty spaces
	while(new_argmt[newpos]==' ' or new_argmt[newpos]=='\t' or new_argmt[newpos]==':' or new_argmt[newpos]==','):
		newpos = newpos + 1
	if new_argmt[newpos]!=';':
		raise Exception(error_list[8]+': ";"')
	# upload to main action table list
	table_lst.append(temp_action_table)
	#print(temp_action_table) #debug
	return new_argmt

# output the remaining string
# should read input_line use_table if_success_table if_failure_table time_to_trigger [bits to turn on(0-25)]
def interpret_con(argument):
	global table_lst
	temp_action_table = []
	input_line, new_argmt = parse_number(argument) 	# input_line
	if (input_line < 0 or input_line > 3):
		raise Exception('Invalid input line at conditional.')
	use_table, new_argmt = parse_number(new_argmt) 		# use_table
	if (use_table < 0):
                raise Exception('Invalid table number at conditional.')	
	goto_table, new_argmt = parse_number(new_argmt) 	# goto_table
	if (goto_table < 0):
                raise Exception('Invalid success_table number at conditional.')
	#[table_no, success_table_no, fail_table_no, input_line, num_clock_cycle, output]
	temp_action_table.append(use_table)
	temp_action_table.append(goto_table)
	temp_action_table.append('NULL')
	temp_action_table.append(input_line)

	# read time
	dura, new_argmt = parse_number(new_argmt)
	# identify unit
	token, ptr = find_token(new_argmt, unit_list)
	if token == 0:
		raise Exception(error_list[5]+' :'+argument)
	elif token == 1: # ns
		if dura < 10:
			print(error_list[6]+', '+str(dura)+'ns is round up to 10ns')
			n_cycle = 1
		else:
			n_cycle = int(dura/10)
	elif token == 2: # us
		n_cycle = int(1000*dura/10)

	elif token == 3: # ms
		n_cycle = int(1000000*dura/10)
	else:
		raise Exception('interpret_tri error')
	temp_action_table.append(n_cycle)

	# READ OUTPUT BITS
	new_argmt = new_argmt[ptr+2:]	
	outputbitarray = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0] # to store on off
	while (True):
		outbit, new_argmt = parse_number(new_argmt)
		if outbit==-1:
			break
		elif outbit > 31:
			raise Exception(error_list[3])
		elif outputbitarray[outbit] == 1:
			print(error_list[7])
		else:
			outputbitarray[outbit] = 1
	decsum_l,decsum_r = 0,0
	for i in range(16):
		decsum_l = decsum_l + outputbitarray[i]*2**i
		decsum_r = decsum_r + outputbitarray[i+16]*2**i
	temp_action_table.append([int(decsum_l),int(decsum_r)])

	newpos = 0
	# take out empty spaces
	while(new_argmt[newpos]==' ' or new_argmt[newpos]=='\t' or new_argmt[newpos]==':' or new_argmt[newpos]==','):
		newpos = newpos + 1
	if new_argmt[newpos]!=';':
		raise Exception(error_list[8]+': ";"')
	# upload to main action table list
	table_lst.append(temp_action_table)
	#print(temp_action_table) #debug
	return new_argmt

def flush(): #reading termination
	# last check before generation of dpatt
	global table_lst
	global table_dic
	global rep_count
	#print(table_lst) #for debugging

	# construct a dictionary for each table
	table_dic = {}
	rep_count = [] # to record number of internal counters dedicated to loop seq, keeps the table_no
	ext_counter = [0,0,0,0]	# to prevent funny situations where same counter has multiple threshold 
	# key (table_no), val (counter_no)
	for i in range(len(table_lst)):
		if len(table_lst[i])==7: #triggered
			if table_lst[i][0] in table_dic:	# repeated table number
				raise Exception(error_list[10])
			table_dic[table_lst[i][0]]=0
			if ext_counter[table_lst[i][3]]==0:	#if the external counter hasnt been used previously
				ext_counter[table_lst[i][3]] = table_lst[i][4]
			elif ext_counter[table_lst[i][3]] != table_lst[i][4]:	#recorded threshold != current threshold
				print(error_list[11])
				ext_counter[table_lst[i][3]] = min(ext_counter[table_lst[i][3]], table_lst[i][4])
				# in current setting, it will pick the smallest threshold value
		elif len(table_lst[i])==5: # sequential
			if table_lst[i][0] in table_dic:
				if i==0:
					raise Exception(error_list[10])
				elif table_lst[i-1][0]!=table_lst[i][0]:
					raise Exception(error_list[10])
			else:
				table_dic[table_lst[i][0]]=table_lst[i][2]
				if table_lst[i][2] > 0:
					rep_count.append(table_lst[i][2])
		else: # conditional
			if table_lst[i][0] in table_dic:	# repeated table number
				raise Exception(error_list[10])
			table_dic[table_lst[i][0]]=0
	#print(table_dic) # for debugging

	num_lep_count = len(rep_count)
	if num_lep_count > 2: # too many loop sequentials
		raise Exception(error_list[2])
	elif num_lep_count == 1:
		rep_count.append(0)
	elif num_lep_count == 0:
		rep_count.append(0)
		rep_count.append(0)
	# will only encode in parameter if rep_count > 0
	param_rep_count = [0,0]
	if rep_count[0] > 0: # loop 2 times when rep_count = 1
		param_rep_count[0] = rep_count[0] + 1
	if rep_count[1] > 0:
		param_rep_count[1] = rep_count[1] + 1
	# start encoding
	dpatt_str = ''
	# parameter registers
	dpatt_str = dpatt_str + '#parameter registers\n'
	# Add config 0 to clear memory before programming to prevent crash at device.
	dpatt_str = dpatt_str + 'config 0;\n'
	# internal counters 0 and 1 are always kept as 10 and 100 for long duration actions
	dpatt_str = dpatt_str + ('param 0 %d %d %d %d 10 100 %d %d;\n' %(ext_counter[0],ext_counter[1],ext_counter[2],ext_counter[3],param_rep_count[0],param_rep_count[1]))
	dpatt_str = dpatt_str + 'holdadr; ramprog;\n'

	# use the previous dictionary to store address of each table, initiation to -1
	for table_no_temp in table_dic:
		table_dic[table_no_temp] = -1
	# start ram programming here
	addr_ptr = 0
	table_no_temp = 0
	table_pos = program_table(table_no_temp)
	if len(table_lst[table_pos])==7: #triggered
		table_dic[table_no_temp]=addr_ptr # assign address for this soon-to-be-programmed table
		action_str, new_addr = trigger_encode(table_lst[table_pos],addr_ptr)
	elif len(table_lst[i])==5: # sequential
		table_dic[table_no_temp]=addr_ptr # assign address for this soon-to-be-programmed table
		action_str, new_addr = sequential_encode(table_pos,addr_ptr)
	else: # conditional
		table_dic[table_no_temp]=addr_ptr 
		action_str, new_addr = conditional_encode(table_lst[table_pos],addr_ptr)
	dpatt_str = dpatt_str + action_str # combined
	dpatt_str = dpatt_str + 'run; #start sequences\n'
	#print(dpatt_str) # debug
	# check if there is unprogrammed tables
	for table_no_temp in table_dic:
		if(table_dic[table_no_temp]==-1):
			print('warning: %d is not programmed.'%table_no_temp)
	return dpatt_str

def program_table(table_no):
	global table_lst
	for i in range(len(table_lst)):
		if (table_lst[i][0]==table_no):
			return i # this is the table we want to programme
			# for sequentials, it always returns the first occurance
	raise Exception('Table %d not found.' %table_no)

# return chain of str for this table, and the new addr_ptr
def trigger_encode(action_table,addr_ptr):
	global table_dic
	global table_lst
	table_str = '#table %d\n' %action_table[0] #table_no
	# branches between two tables, check ext counter 
	left_output = action_table[6][0]
	right_output = action_table[6][1]
	# internal counter to implement, num_of_step per loop, duration_per_step
	if action_table[5] < 100000: # less than 1 ms
		print('Warning: trigger duration is shorter than 1ms')
	table_str, addr_ptr = time_balancer(left_output, right_output, action_table[5], table_str, addr_ptr, action_table[3])
	# check external counter
	# if the fail_table is unprogrammed then put fail_table after this trigger_table
	fail_table_no = action_table[2]
	if table_dic[fail_table_no]==-1: # unprogrammed
		table_dic[fail_table_no]=addr_ptr+2 # addr_ptr is failed condition, +1 is success condition, +2 is start of new table
		# fail
		table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output,right_output,0,((8+action_table[3])<<12)+table_dic[fail_table_no],addr_ptr) # jump to fail_table on nonzero ext cnt			
		addr_ptr = addr_ptr + 1 	# now addr_ptr is success condition, +1 is failed table
		# program the fail_table
		table_pos = program_table(fail_table_no)
		if len(table_lst[table_pos])==7: #triggered
			next_str, next_ptr = trigger_encode(table_lst[table_pos],addr_ptr+1)
		elif len(table_lst[table_pos])==5: 
			next_str, next_ptr = sequential_encode(table_pos,addr_ptr+1)
		else:
			next_str, next_ptr = conditional_encode(table_lst[table_pos],addr_ptr+1)
		# next_ptr is after fail_table, new table
	else:	# failed table already exists
		table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output,right_output,0,((8+action_table[3])<<12)+table_dic[fail_table_no],addr_ptr) # jump to fail_table on nonzero ext cnt
		addr_ptr = addr_ptr + 1 # now addr_ptr is success condition, +1 is failed table
		next_str = ''
		next_ptr = addr_ptr+1 # here addr is the success condtion, +1 is the new table, next_adr is the new table
	# success, start the sucess table
	success_table_no = action_table[1]
	if table_dic[success_table_no]==-1: # unprogrammed
		table_dic[success_table_no]=next_ptr # addr_ptr is success condition, +1 is start of new table
		table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output,right_output,0,table_dic[success_table_no],addr_ptr) # jump to success table
		addr_ptr = addr_ptr + 1 	# here addr is new table after success condition
		table_pos = program_table(success_table_no)
		if len(table_lst[table_pos])==7: #triggered
			next2_str, next2_ptr = trigger_encode(table_lst[table_pos],next_ptr)
		elif len(table_lst[table_pos])==5:
			next2_str, next2_ptr = sequential_encode(table_pos,next_ptr)
		else:
			next2_str, next2_ptr = conditional_encode(table_lst[table_pos],next_ptr)
	else: # success table already exists			
		table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output,right_output,0,table_dic[success_table_no],addr_ptr) # jump to success table
		addr_ptr = addr_ptr + 1
		next2_str = ''
	table_str = table_str + next_str + next2_str
	return table_str, addr_ptr


def sequential_encode(table_pos,addr_ptr,first_occurance=True):
	global table_dic
	global table_lst
	global rep_count
	action_table = table_lst[table_pos]
	[left_output,right_output]=action_table[4]
	table_str = ''
	if first_occurance:
		table_str = '#table %d\n' %action_table[0] #table_no
		# check if it is a loop sequential
		if action_table[2] > 0:
			#find counter, counter 0 and 1 are for durations, so always start from 2
			if rep_count[0]==action_table[2]:
				loop_counter = 2
			else:
				loop_counter = 3
			table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, 0, 4096+2**(loop_counter+4),addr_ptr) #load counters, 4096->special command, 2**(loop_counter+4)
			addr_ptr = addr_ptr + 1
			table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, 0, 4096+2**(loop_counter+8),addr_ptr) #load counters, 4096->special command, decrement on counter
			addr_ptr = addr_ptr + 1
			action_table[3] = action_table[3]-1 # correction due to decrement step

	# correction for the last action before check, ERRATUM
	# if (table_pos+1<len(table_lst)): # still within table_lst
	# 	if (table_lst[table_pos+1][0]!=action_table[0]): #new table
	# 		next_table_no = action_table[1]
	# 		if table_dic[next_table_no]==-1: # unprogrammed
	# 			if action_table[2] > 0: # loop sequential
	# 		 		action_table[3] = action_table[3]-1
	# 		else:	# existed, need additional step to redirect
	# 			if action_table[2] > 0: # loop sequential
	# 				action_table[3] = action_table[3]-2
	# 			else:
	# 	 			action_table[3] = action_table[3]-1
	# else: #end of the list, there will be a redirect to new table action, conditional statement if loop sequential
	# 	if action_table[2] > 0: # loop sequential
	# 		action_table[3] = action_table[3]-2
	# 	else:
	# 		action_table[3] = action_table[3]-1

	# last action of the table
	if (table_pos+1<len(table_lst)): # still within table_lst
		if (table_lst[table_pos+1][0]!=action_table[0]): #new table
	# correction for the conditional check
			if action_table[2] > 0: # loop sequential
				action_table[3] = action_table[3]-1 #correction for conditional check
	else:
		if action_table[2] > 0: # loop sequential
			action_table[3] = action_table[3]-1 #correction for conditional check

	# timing loop
	table_str, addr_ptr = time_balancer(left_output, right_output, action_table[3], table_str, addr_ptr)
	# check if this is the end of this sequential table
	next_str = ''
	if (table_pos+1<len(table_lst)):
		if (table_lst[table_pos+1][0]==action_table[0]): #same table
			next_str, addr_ptr = sequential_encode(table_pos+1,addr_ptr,False)
			table_str = table_str + next_str
		# NEXT IS ALREADY A NEW TABLE
		else:
			# end of loop
			if action_table[2] > 0:
				#find counter, counter 0 and 1 are for durations, so always start from 2
				if rep_count[0]==action_table[2]:
					loop_counter = 2
				else:
					loop_counter = 3
				table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, 0,((loop_counter+12)<<12)+table_dic[action_table[0]]+1,addr_ptr) #jump to start of sequential with nonzero counter value
				addr_ptr = addr_ptr + 1
			# go into new table, check what they are again
			next_table_no = action_table[1]
			if table_dic[next_table_no]==-1: # unprogrammed
				table_dic[next_table_no]=addr_ptr
				table_pos = program_table(next_table_no)
				if len(table_lst[table_pos])==7: #triggered
					next_str, addr_ptr = trigger_encode(table_lst[table_pos],addr_ptr)
				elif len(table_lst[table_pos])==5:
					next_str, addr_ptr = sequential_encode(table_pos,addr_ptr)
				else:
					next_str, addr_ptr = conditional_encode(table_lst[table_pos],addr_ptr)
			else: #table already exist, bring it back to branch					
				next_str = 'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, 0, table_dic[next_table_no],addr_ptr)
				addr_ptr = addr_ptr + 1
			table_str = table_str + next_str
	else:
		if action_table[2] > 0:
			#find counter, counter 0 and 1 are for durations, so always start from 2
			if rep_count[0]==action_table[2]:
				loop_counter = 2
			else:
				loop_counter = 3
			table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, 0,((loop_counter+12)<<12)+table_dic[action_table[0]]+1,addr_ptr) #jump to start of sequential with nonzero counter value
			addr_ptr = addr_ptr + 1
		# go into new table, check what they are again
		next_table_no = action_table[1]
		if table_dic[next_table_no]==-1: # unprogrammed
			table_dic[next_table_no]=addr_ptr
			table_pos = program_table(next_table_no)
			if len(table_lst[table_pos])==7: #triggered
				next_str, addr_ptr = trigger_encode(table_lst[table_pos],addr_ptr)
			elif len(table_lst[table_pos])==5:
				next_str, addr_ptr = sequential_encode(table_pos,addr_ptr)
			else:
				next_str, addr_ptr = conditional_encode(table_lst[table_pos],addr_ptr)
		else: #table already exist, bring it back to branch
			next_str = 'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, 0, table_dic[next_table_no],addr_ptr)
			addr_ptr = addr_ptr + 1
		table_str = table_str + next_str
	return table_str, addr_ptr


def conditional_encode(action_table,addr_ptr):
	global table_dic
	global table_lst
	table_str = '#table %d\n' %action_table[0] #table_no
	# branches between two tables, check ext counter 
	left_output = action_table[5][0]
	right_output = action_table[5][1]
	if action_table[4] > Max_cyclenumber_per_line:
		tri_width = Max_cyclenumber_per_line
		# introduce a wait time first
		table_str, addr_ptr = time_balancer(left_output, right_output, action_table[4]-Max_cyclenumber_per_line, table_str, addr_ptr)
		print('Warning: conditional wait time is longer than 655.36us.')
	else:
		tri_width = action_table[4]
	# conditional statement, first detect if success table is created
	success_table_no = action_table[1]
	if table_dic[success_table_no]==-1: # unprogrammed
		next_addr = addr_ptr + 2 #addr_ptr = the conditional check, +1 is the go back statement, +2 is new table
	else: 
		next_addr = table_dic[success_table_no]
	table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output,right_output,tri_width-1,((4+action_table[3])<<12)+next_addr,addr_ptr)
	addr_ptr = addr_ptr + 1 	
	# go back up statement
	if tri_width < Max_cyclenumber_per_line:
		table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output,right_output,tri_width-1,table_dic[action_table[0]],addr_ptr)
		addr_ptr = addr_ptr + 1 
	else:
		# only spend a maximum of 655.36us here
		table_str = table_str+'writew %d,%d,%d,%d;#row %d\n' %(left_output,right_output,Max_cyclenumber_per_line-1,table_dic[action_table[0]],addr_ptr)
		addr_ptr = addr_ptr + 1
	if table_dic[success_table_no]==-1: # unprogrammed
		table_dic[success_table_no]=addr_ptr
		table_pos = program_table(success_table_no)
		if len(table_lst[table_pos])==7: #triggered
			next_str, addr_ptr = trigger_encode(table_lst[table_pos],addr_ptr)
		elif len(table_lst[table_pos])==5: #triggered:
			next_str, addr_ptr = sequential_encode(table_pos,addr_ptr)
		else:
			next_str, addr_ptr = conditional_encode(table_lst[table_pos],addr_ptr)
	else: #table already exist, bring it back to branch
		next_str = 'writew %d,%d,%d,%d;#row %d\n' %(left_output, right_output, 0, table_dic[success_table_no],addr_ptr)
		addr_ptr = addr_ptr + 1
	table_str = table_str + next_str
	# go to next table
	return table_str, addr_ptr

def generator(pattfile):

	global table_lst
	global table_dic
	global rep_count

	table_lst.clear()
	table_dic.clear()
	rep_count.clear()
	output = ''

	#take out commented regions
	#and also cases where we have skip lines \n
	file_line = pattfile.readline()
	# take care of the comments
	ptr = file_line.find('#')
	if ptr >= 0: #if commented, replace the commented part with skip line
					file_line = file_line[:ptr]+str('\n')
	# initial token value
	token = 0
	while(True):
		while (file_line[0] == '\n' or file_line[0]=='\r'): # requires to skip a line
			file_line = pattfile.readline()
			# take care of the comments
			ptr = file_line.find('#')
			if ptr >= 0: #if commented, replace the commented part with skip line
				file_line = file_line[:ptr]+str('\n')
		
		#print(file_line) #debug
		token, file_line = parse_command(file_line,token)
		if token==1:	# termination
			output = flush()
			break

		if file_line == '':
			raise Exception(error_list[8]+"''")	#invalid termination
		else:
			if token==0:
				raise Exception(error_list[1])
			newpos = 0
			# take out empty spaces
			while(file_line[newpos]==' ' or file_line[newpos]=='\t' or file_line[newpos]==':' or file_line[newpos]==','):
				newpos = newpos + 1
			if file_line[newpos:]=='':
				raise Exception(error_list[8]+': '+file_line)	#invalid termination
			file_line = file_line[newpos:]
			if (file_line[0] == '\n' or file_line[0]=='\r'): # requires to skip a line
				file_line = pattfile.readline()
				# take care of the comments
				ptr = file_line.find('#')
				if ptr >= 0: #if commented, replace the commented part with skip line
					file_line = file_line[:ptr]+str('\n')
			elif (file_line[0] == ';'): # 
				file_line = file_line[1:]
			else:
				raise Exception(error_list[8]+': '+file_line)	#invalid termination
	return output

# if __name__ == '__main__':
# 	import argparse
# 	parser = argparse.ArgumentParser(description='Generate dpatt from patt')
# 	parser.add_argument('-i','--inputstr',type=str,default='load_atom_redu.patt')
# 	parser.add_argument('-o','--outputstr',type=str,default='isto.dat')
# 	args = parser.parse_args()
# 	pattfile = open(args.inputstr,'r')
# 	outputfile = open(args.outputstr,'w+')
#
# 	output = main(pattfile)
# 	outputfile.write(output)
#
# 	pattfile.close()
# 	outputfile.close()
#
# 	num_lines = sum(1 for line in open(args.outputstr,'r'))
# 	#print(num_lines-len(table_dic)-4) #for debugging
# 	if (num_lines-len(table_dic)-4) > 256:
# 		raise Exception(error_list[12])
