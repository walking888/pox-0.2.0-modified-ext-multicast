
from topo_and_path_algorithm import *

import time
import pickle
import itertools

from ctypes import *
import inspect, os
from copy import deepcopy
import random
import exceptions
import pdb

class NC_Function(object):
	def __init__(self, path):
		self.test = cdll.LoadLibrary(path+'/libgf256.so')
		self.test.initMulDivTab(path+'/muldiv.tab')

	def cMulvAdd(self, vec1, vec2, size, co):
		#print "start mulvadd:", vec1, vec2, size, co
		for i in range(size):
			vec1[i] = self.test.gfadd(vec1[i], self.test.gfmul(co, vec2[i]))
		#print vec1
		return vec1

	def mathmulti(self, vec1, vec2, size):
		tmp = 0
		for i in range(size):
			tmp = self.test.gfadd(tmp, self.test.gfadd(vec1[i], vec2[i]))
		return tmp

	def cDiv(self, vec1, size, co):
		for i in range(size):
			vec1[i] = self.test.gfdiv(vec1[i], co)
		return vec1
	
	def cMul(self, vec1, size, co):
		for i in range(size):
			vec1[i] = self.test.gfmul(vec1[i], co)
		return vec1

	def gfadd(self, a, b):
		return self.test.gfadd(a,b)

	def gfdiv(self, a, b):
		return self.test.gfdiv(a,b)

	def gfmul(self, a, b):
		return self.test.gfmul(a,b)

	def get_I(self):
		return 1

	def random_Num(self):
		return random.randint(0,255)

this_file_XXXX = inspect.getfile(inspect.currentframe())
this_path_XXXX = os.path.abspath(os.path.dirname(this_file_XXXX))
nc_func = NC_Function(this_path_XXXX + '/forcode')

# need to add buffer management
# need add
def get_buffer_id(*args):
	return 0

# all actions create op is here
# l_normal_action_forward\ l_nc_action_forward

def actions_add(a, s, msg):
	try:
		a[(s, msg.match.in_port)].actions.extend(msg.actions)
		print "an action is extend to another!"
		print msg.match
		print str(s)
	except:
		a[(s, msg.match.in_port)] = msg
		"""
		k = (s, msg.match.in_port)
		print k
		ss = ""
		for act in msg.actions:
			ss += str(act)
		print "	"+ ss
		"""

def l_normal_action_forward(paths):
	def switches_add(a, s, inp, outp):
		try:
			a[s]
		except:
			a[s] = {}
		try:
			a[s][inp].append(outp)
		except:
			a[s][inp] = [outp]

	x = {}
	for k in paths['path']:
		ps = paths['path'][k]['path']
		for p in ps:
			last_p = paths['src'][1]
			for l in p:
				port = paths['link-to-port'](l[0], l[1])
				switches_add(x, l[0], last_p, port)
				last_p = paths['link-to-port'](l[1], l[0])
			# add dst
			for p  in paths['port'][k[1]]:
				switches_add(x, l[1], last_p, p)
	
	for (s, inp, outps) in paths['add_forward']:
		for outp in outps:
			switches_add(x, s, inp, outp)

	actions = {}
	"""
	for s in x.keys():
		for inp in x[s].keys():
			outps = x[s][inp]
			msg = create_msg(paths['match'])
			msg.match.in_port = inp
			for  outp in outps:
				msg.actions.append(of.ofp_action_output(port = outp))
			actions_add(actions, s, msg)
	"""
	return actions

# here is nc actions, they are in a set, different set may not switch
# this have functions :
#		get_init_code
#			---->  l_static_get_init_code
#			---->  l_random_get_init_code
#		action_init
#			---->  l_static_action_init
#			---->  l_random_action_init
#		get_encode_code
#			---->  l_static_get_encode_code
#			---->  l_random_get_encode_code
#		action_encode
#			---->  l_static_action_encode
#			---->  l_random_action_encode
#		action_decode
#			---->  l_action_decode
#		action_forward	
#			---->  l_nc_action_forward

def l_nc_action_forward(paths):
	def switches_add(a, s, inp, outp):
		try:
			a[s]
		except:
			a[s] = {}
		try:
			a[s][inp].append(outp)
		except:
			a[s][inp] = [outp]

	x = {}
	for k in paths['paths']:
		ps = paths['paths'][k]['path']
		for p in ps:
			last_p = 99999
			for l in p:
				# link has src is init node
				if last_p != 99999:
					port = paths['link-to-port'](l[0], l[1])
					# link in encode link need encode so ignore them
					if l not in paths['encode_link']:
						switches_add(x, l[0], last_p, port)
				last_p = paths['link-to-port'](l[1], l[0])
			# here dst is ignored because of decode

	# remove the same port from the same inport
	for s in x.keys():
		for inp in x[s].keys():
			x[s][inp] = {}.fromkeys(x[s][inp]).keys()

	actions = {}
	"""
	for s in x.keys():
		for inp in x[s].keys():
			outps = x[s][inp]
			msg = create_msg(paths['shift_match'])
			msg.match.in_port = inp
			for  outp in outps:
				msg.actions.append(of.ofp_action_output(port = outp))
			actions_add(actions, s, msg)
	#print "forward_actions"
	#print actions
	#print x
	for (s, inp, outps) in paths['add_forward']:
		msg = create_msg(paths['match'])
		msg.match.in_port = inp
		for outp in outps:
			msg.actions.append(of.ofp_action_output(port = outp))
		actions_add(actions, s, msg)
	"""
	return actions

NCvector = {}
NCmatrix = {}
NCvector[2] = [[1, 0], [0, 1], [1, 1], [3, 49], [140, 123], [118, 134], [100, 223], [188, 97]]
NCmatrix[2] = {(0,): [0, 1], (1,): [1, 0], (2,): [1, 1], (3,): [134, 1], (4,): [184, 1], (5,): [234, 1], (6,): [26, 1], (7,): [32, 1]}
NCvector[3] = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 1], [85, 76, 2], [180, 109, 186], [170, 223, 27], [160, 254, 177]]
NCmatrix[3] = {(4, 7): [199, 149, 1], (1, 3): [0, 0, 1], (5, 6): [63, 150, 1], (0, 7): [0, 0, 1], (1, 6): [0, 0, 1], (3, 7): [216, 185, 1], (2, 5): [0, 0, 1], (0, 3): [0, 0, 1], (1, 2): [1, 0, 0], (6, 7): [150, 42, 1], (1, 5): [0, 0, 1], (3, 6): [135, 201, 1], (0, 4): [0, 0, 1], (2, 7): [0, 0, 1], (2, 6): [0, 0, 1], (4, 5): [160, 109, 1], (1, 4): [0, 0, 1], (2, 3): [0, 0, 1], (3, 5): [150, 227, 1], (0, 1): [0, 0, 1], (4, 6): [58, 171, 1], (5, 7): [240, 155, 1], (0, 2): [0, 1, 0], (0, 6): [0, 0, 1], (1, 7): [0, 0, 1], (0, 5): [0, 0, 1], (3, 4): [37, 95, 1], (2, 4): [0, 0, 1]}
NCvector[4] = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1], [1, 1, 1, 1], [183, 8, 69, 7], [209, 28, 39, 117], [253, 76, 165, 176]]
NCmatrix[4] = {(3, 4, 6): [0, 0, 0, 1], (2, 3, 5): [0, 0, 0, 1], (1, 2, 7): [0, 0, 0, 1], (0, 4, 5): [0, 0, 0, 1], (2, 5, 6): [0, 0, 0, 1], (1, 4, 7): [0, 0, 0, 1], (0, 1, 2): [0, 0, 0, 1], (3, 4, 7): [0, 0, 0, 1], (1, 4, 5): [0, 0, 0, 1], (2, 3, 7): [0, 0, 0, 1], (0, 1, 4): [0, 0, 0, 1], (0, 5, 7): [0, 0, 0, 1], (0, 2, 7): [0, 0, 0, 1], (0, 1, 5): [0, 0, 0, 1], (2, 3, 6): [0, 0, 0, 1], (2, 6, 7): [0, 0, 0, 1], (5, 6, 7): [193, 0, 138, 1], (0, 1, 6): [0, 0, 0, 1], (0, 2, 3): [0, 1, 0, 0], (0, 1, 7): [0, 0, 0, 1], (2, 5, 7): [0, 0, 0, 1], (0, 5, 6): [0, 0, 0, 1], (0, 2, 5): [0, 0, 0, 1], (0, 3, 6): [0, 0, 0, 1], (3, 6, 7): [0, 0, 0, 1], (0, 2, 4): [0, 0, 0, 1], (1, 6, 7): [0, 0, 0, 1], (0, 2, 6): [0, 0, 0, 1], (2, 4, 7): [0, 0, 0, 1], (2, 4, 5): [0, 0, 0, 1], (2, 4, 6): [0, 0, 0, 1], (1, 2, 3): [1, 0, 0, 0], (0, 3, 7): [0, 0, 0, 1], (1, 2, 4): [0, 0, 0, 1], (1, 4, 6): [0, 0, 0, 1], (0, 3, 4): [0, 0, 0, 1], (0, 1, 3): [0, 0, 1, 0], (4, 5, 6): [235, 0, 135, 1], (1, 2, 5): [0, 0, 0, 1], (1, 3, 7): [0, 0, 0, 1], (4, 5, 7): [183, 0, 210, 1], (1, 2, 6): [0, 0, 0, 1], (1, 5, 7): [0, 0, 0, 1], (1, 3, 6): [0, 0, 0, 1], (0, 3, 5): [0, 0, 0, 1], (3, 5, 7): [0, 0, 0, 1], (1, 5, 6): [0, 0, 0, 1], (1, 3, 5): [0, 0, 0, 1], (0, 6, 7): [0, 0, 0, 1], (3, 5, 6): [0, 0, 0, 1], (0, 4, 7): [0, 0, 0, 1], (1, 3, 4): [0, 0, 0, 1], (3, 4, 5): [0, 0, 0, 1], (2, 3, 4): [0, 0, 0, 1], (4, 6, 7): [161, 0, 41, 1], (0, 4, 6): [0, 0, 0, 1]}
NCvector[5] = [[1, 0, 0, 0, 0], [0, 1, 0, 0, 0], [0, 0, 1, 0, 0], [0, 0, 0, 1, 0], [0, 0, 0, 0, 1], [1, 1, 1, 1, 1], [60, 79, 49, 58, 34], [205, 61, 250, 120, 227]]
NCmatrix[5] = {(0, 2, 3, 6): [0, 0, 0, 0, 1], (2, 3, 6, 7): [0, 0, 0, 0, 1], (1, 2, 4, 6): [0, 0, 0, 0, 1], (3, 5, 6, 7): [0, 0, 0, 0, 1], (0, 1, 6, 7): [0, 0, 0, 0, 1], (0, 2, 4, 6): [0, 0, 0, 0, 1], (0, 1, 2, 3): [0, 0, 0, 0, 1], (1, 2, 3, 7): [0, 0, 0, 0, 1], (0, 3, 6, 7): [0, 0, 0, 0, 1], (0, 2, 4, 5): [0, 0, 0, 0, 1], (0, 1, 2, 5): [0, 0, 0, 0, 1], (0, 1, 5, 7): [0, 0, 0, 0, 1], (1, 3, 4, 5): [0, 0, 0, 0, 1], (2, 3, 4, 5): [0, 0, 0, 0, 1], (0, 5, 6, 7): [0, 0, 0, 0, 1], (0, 1, 4, 5): [0, 0, 0, 0, 1], (0, 3, 4, 6): [0, 0, 0, 0, 1], (2, 3, 4, 6): [0, 0, 0, 0, 1], (1, 3, 5, 6): [0, 0, 0, 0, 1], (0, 1, 3, 4): [0, 0, 1, 0, 0], (1, 2, 5, 7): [0, 0, 0, 0, 1], (0, 2, 3, 7): [0, 0, 0, 0, 1], (0, 1, 3, 6): [0, 0, 0, 0, 1], (0, 3, 4, 7): [0, 0, 0, 0, 1], (2, 5, 6, 7): [0, 0, 0, 0, 1], (0, 2, 6, 7): [0, 0, 0, 0, 1], (2, 3, 5, 7): [0, 0, 0, 0, 1], (1, 2, 3, 6): [0, 0, 0, 0, 1], (2, 4, 5, 7): [0, 0, 0, 0, 1], (0, 1, 2, 6): [0, 0, 0, 0, 1], (1, 2, 3, 5): [0, 0, 0, 0, 1], (2, 4, 5, 6): [0, 0, 0, 0, 1], (0, 3, 4, 5): [0, 0, 0, 0, 1], (0, 4, 5, 6): [0, 0, 0, 0, 1], (0, 3, 5, 7): [0, 0, 0, 0, 1], (0, 1, 4, 6): [0, 0, 0, 0, 1], (1, 2, 6, 7): [0, 0, 0, 0, 1], (2, 4, 6, 7): [0, 0, 0, 0, 1], (1, 4, 6, 7): [0, 0, 0, 0, 1], (0, 2, 5, 6): [0, 0, 0, 0, 1], (3, 4, 5, 7): [0, 0, 0, 0, 1], (1, 3, 6, 7): [0, 0, 0, 0, 1], (1, 4, 5, 7): [0, 0, 0, 0, 1], (0, 2, 5, 7): [0, 0, 0, 0, 1], (1, 2, 5, 6): [0, 0, 0, 0, 1], (0, 2, 3, 4): [0, 1, 0, 0, 0], (0, 1, 2, 7): [0, 0, 0, 0, 1], (1, 5, 6, 7): [0, 0, 0, 0, 1], (0, 1, 3, 7): [0, 0, 0, 0, 1], (2, 3, 5, 6): [0, 0, 0, 0, 1], (4, 5, 6, 7): [0, 0, 0, 0, 1], (2, 3, 4, 7): [0, 0, 0, 0, 1], (0, 2, 4, 7): [0, 0, 0, 0, 1], (3, 4, 6, 7): [0, 0, 0, 0, 1], (1, 2, 3, 4): [1, 0, 0, 0, 0], (0, 1, 5, 6): [0, 0, 0, 0, 1], (0, 1, 2, 4): [0, 0, 0, 1, 0], (0, 4, 5, 7): [0, 0, 0, 0, 1], (0, 3, 5, 6): [0, 0, 0, 0, 1], (0, 1, 4, 7): [0, 0, 0, 0, 1], (0, 4, 6, 7): [0, 0, 0, 0, 1], (1, 3, 4, 6): [0, 0, 0, 0, 1], (3, 4, 5, 6): [0, 0, 0, 0, 1], (1, 3, 5, 7): [0, 0, 0, 0, 1], (1, 4, 5, 6): [0, 0, 0, 0, 1], (1, 3, 4, 7): [0, 0, 0, 0, 1], (0, 2, 3, 5): [0, 0, 0, 0, 1], (0, 1, 3, 5): [0, 0, 0, 0, 1], (1, 2, 4, 7): [0, 0, 0, 0, 1], (1, 2, 4, 5): [0, 0, 0, 0, 1]}
NCvector[6] = [[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0], [0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 1, 0], [0, 0, 0, 0, 0, 1], [1, 1, 1, 1, 1, 1], [230, 11, 203, 30, 108, 152]]
NCmatrix[6] = {(1, 2, 3, 4, 6): [0, 0, 0, 0, 0, 1], (1, 2, 5, 6, 7): [0, 0, 0, 0, 0, 1], (0, 2, 3, 4, 7): [0, 0, 0, 0, 0, 1], (0, 1, 2, 5, 6): [0, 0, 0, 0, 0, 1], (0, 1, 3, 4, 5): [0, 0, 1, 0, 0, 0], (0, 2, 3, 4, 5): [0, 1, 0, 0, 0, 0], (0, 1, 3, 6, 7): [0, 0, 0, 0, 0, 1], (0, 2, 3, 6, 7): [0, 0, 0, 0, 0, 1], (0, 1, 2, 3, 4): [0, 0, 0, 0, 0, 1], (3, 4, 5, 6, 7): [0, 0, 0, 0, 0, 1], (0, 1, 4, 6, 7): [0, 0, 0, 0, 0, 1], (2, 4, 5, 6, 7): [0, 0, 0, 0, 0, 1], (1, 2, 4, 5, 7): [0, 0, 0, 0, 0, 1], (1, 3, 4, 5, 6): [0, 0, 0, 0, 0, 1], (0, 2, 3, 5, 7): [0, 0, 0, 0, 0, 1], (0, 3, 4, 5, 6): [0, 0, 0, 0, 0, 1], (0, 1, 4, 5, 6): [0, 0, 0, 0, 0, 1], (0, 2, 5, 6, 7): [0, 0, 0, 0, 0, 1], (0, 2, 3, 4, 6): [0, 0, 0, 0, 0, 1], (2, 3, 4, 5, 6): [0, 0, 0, 0, 0, 1], (1, 2, 3, 5, 6): [0, 0, 0, 0, 0, 1], (0, 1, 4, 5, 7): [0, 0, 0, 0, 0, 1], (0, 2, 4, 5, 7): [0, 0, 0, 0, 0, 1], (1, 2, 3, 4, 7): [0, 0, 0, 0, 0, 1], (0, 1, 3, 5, 6): [0, 0, 0, 0, 0, 1], (0, 1, 2, 4, 7): [0, 0, 0, 0, 0, 1], (1, 3, 4, 6, 7): [0, 0, 0, 0, 0, 1], (0, 1, 3, 4, 6): [0, 0, 0, 0, 0, 1], (1, 4, 5, 6, 7): [0, 0, 0, 0, 0, 1], (0, 1, 5, 6, 7): [0, 0, 0, 0, 0, 1], (1, 2, 3, 4, 5): [1, 0, 0, 0, 0, 0], (0, 3, 4, 6, 7): [0, 0, 0, 0, 0, 1], (0, 1, 2, 3, 5): [0, 0, 0, 0, 1, 0], (0, 1, 2, 4, 5): [0, 0, 0, 1, 0, 0], (2, 3, 5, 6, 7): [0, 0, 0, 0, 0, 1], (0, 1, 2, 5, 7): [0, 0, 0, 0, 0, 1], (1, 2, 3, 6, 7): [0, 0, 0, 0, 0, 1], (0, 1, 2, 6, 7): [0, 0, 0, 0, 0, 1], (0, 2, 4, 6, 7): [0, 0, 0, 0, 0, 1], (1, 2, 4, 6, 7): [0, 0, 0, 0, 0, 1], (0, 4, 5, 6, 7): [0, 0, 0, 0, 0, 1], (0, 3, 4, 5, 7): [0, 0, 0, 0, 0, 1], (0, 1, 2, 3, 7): [0, 0, 0, 0, 0, 1], (1, 2, 4, 5, 6): [0, 0, 0, 0, 0, 1], (2, 3, 4, 5, 7): [0, 0, 0, 0, 0, 1], (0, 1, 2, 3, 6): [0, 0, 0, 0, 0, 1], (0, 2, 3, 5, 6): [0, 0, 0, 0, 0, 1], (0, 2, 4, 5, 6): [0, 0, 0, 0, 0, 1], (0, 1, 3, 5, 7): [0, 0, 0, 0, 0, 1], (1, 3, 5, 6, 7): [0, 0, 0, 0, 0, 1], (0, 1, 2, 4, 6): [0, 0, 0, 0, 0, 1], (0, 3, 5, 6, 7): [0, 0, 0, 0, 0, 1], (0, 1, 3, 4, 7): [0, 0, 0, 0, 0, 1], (1, 3, 4, 5, 7): [0, 0, 0, 0, 0, 1], (1, 2, 3, 5, 7): [0, 0, 0, 0, 0, 1], (2, 3, 4, 6, 7): [0, 0, 0, 0, 0, 1]}
NCvector[7] = [[1, 0, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0, 0], [0, 0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 0, 1, 0], [0, 0, 0, 0, 0, 0, 1], [1, 1, 1, 1, 1, 1, 1]]
NCmatrix[7] = {(0, 2, 3, 5, 6, 7): [0, 0, 0, 0, 0, 0, 1], (0, 1, 3, 5, 6, 7): [0, 0, 0, 0, 0, 0, 1], (0, 3, 4, 5, 6, 7): [0, 0, 0, 0, 0, 0, 1], (1, 2, 3, 4, 5, 7): [0, 0, 0, 0, 0, 0, 1], (0, 1, 2, 3, 4, 7): [0, 0, 0, 0, 0, 0, 1], (0, 2, 3, 4, 5, 6): [0, 1, 0, 0, 0, 0, 0], (1, 2, 3, 4, 6, 7): [0, 0, 0, 0, 0, 0, 1], (0, 1, 2, 4, 5, 7): [0, 0, 0, 0, 0, 0, 1], (0, 1, 4, 5, 6, 7): [0, 0, 0, 0, 0, 0, 1], (1, 2, 3, 4, 5, 6): [1, 0, 0, 0, 0, 0, 0], (0, 2, 3, 4, 5, 7): [0, 0, 0, 0, 0, 0, 1], (0, 1, 2, 5, 6, 7): [0, 0, 0, 0, 0, 0, 1], (0, 1, 2, 3, 6, 7): [0, 0, 0, 0, 0, 0, 1], (2, 3, 4, 5, 6, 7): [0, 0, 0, 0, 0, 0, 1], (1, 2, 3, 5, 6, 7): [0, 0, 0, 0, 0, 0, 1], (0, 1, 3, 4, 5, 7): [0, 0, 0, 0, 0, 0, 1], (0, 2, 3, 4, 6, 7): [0, 0, 0, 0, 0, 0, 1], (0, 1, 3, 4, 6, 7): [0, 0, 0, 0, 0, 0, 1], (1, 3, 4, 5, 6, 7): [0, 0, 0, 0, 0, 0, 1], (0, 1, 2, 3, 4, 5): [0, 0, 0, 0, 0, 0, 1], (1, 2, 4, 5, 6, 7): [0, 0, 0, 0, 0, 0, 1], (0, 1, 3, 4, 5, 6): [0, 0, 1, 0, 0, 0, 0], (0, 1, 2, 3, 5, 7): [0, 0, 0, 0, 0, 0, 1], (0, 1, 2, 4, 5, 6): [0, 0, 0, 1, 0, 0, 0], (0, 1, 2, 3, 4, 6): [0, 0, 0, 0, 0, 1, 0], (0, 2, 4, 5, 6, 7): [0, 0, 0, 0, 0, 0, 1], (0, 1, 2, 3, 5, 6): [0, 0, 0, 0, 1, 0, 0], (0, 1, 2, 4, 6, 7): [0, 0, 0, 0, 0, 0, 1]}
def l_static_get_init_code(paths):
	# some global statics
	init_num = len(paths['init_link'])
	if init_num > len(NCvector[2]):
		return False
	dst_num = len(paths['port'].keys())
	paths['init_code'] = NCvector[paths['path_num']][:init_num]
	return True

def add_used_buffer(paths, s, bid):
	try:
		paths['used_buffer'][s].append(bid)
	except:
		paths['used_buffer'][s]= [bid]


def l_static_action_init(paths):
	"""
	outps = []
	for l in paths['init_link']:
		outps.append(paths['link-to-port'](l[0], l[1]))
	msg = create_msg(paths['match'])
	msg.match.in_port = paths['src'][1]
	b_id = get_buffer_id(paths['a_src'])
	msg.actions.append(nc.nc_action_init_coding(vector_off = 0,
			buffer_id = b_id, packet_num = paths['path_num'], port_num = len(outps),
			packet_len = 1024, outports = outps, vector = paths['init_code']))
	"""
	actions = {}
	"""
	actions_add(actions, paths['a_src'], msg)
	add_used_buffer(paths, paths['a_src'], b_id)
	"""
	return actions

def l_random_get_init_code(paths):
	paths['init_code'] = [0 for x in range(len(paths['init_link']))]
	return True

def l_random_action_init(paths):
	"""
	outps = []
	for l in paths['init_link']:
		outps.append(paths['link-to-port'](l[0],l[1]))
	msg = create_msg(paths['match'])
	msg.match.in_port = paths['src'][1]
	b_id = get_buffer_id(paths['a_src'])
	msg.actions.append(nc.nc_action_init_coding(vector_off = 0, 
		buffer_id = b_id, packet_num = path['path_num'], port_num = len(outps),
		packet_len = 1024, port_id = outps))
	"""
	actions = {}
	"""
	actions_add(actions, paths['a_src'], msg)
	add_used_buffer(paths, paths['a_src'], b_id)
	"""
	return actions

def l_static_get_encode_code(paths):
	paths['encode_code'] = {}
	B = {}
	a = {}
	src = paths['a_src']
	path_num = paths['path_num']
	for i in range(len(paths['a_dst'])):
		B[i] = {}
		a[i] = {}
		tmpall = []
		tmpdst = paths['a_dst'][i]
		for j in range(path_num):
			index = paths['path_id'][(src, tmpdst)][j]
			B[i][j] = deepcopy(paths['init_code'][index])
			tmpall.append(index)
		for j in range(path_num):
			tmpall1 = deepcopy(tmpall)
			del tmpall1[j]
			tmpall1.sort()
			tmpall1 = tuple(tmpall1)
			a[i][j] = deepcopy(NCmatrix[path_num][tmpall1])

	for l in paths['encode_link']:
		code_len = len(paths['encode_relate'][l])
		outputcode = [nc_func.get_I() for x in range(code_len)]
		if 0:
			for i in range(code_len):
				outputcode[i] = nc_func.random_Num()
		iscodewrong = 1
		while iscodewrong:
			flag = 0
			tmpb = [0 for x in range(path_num)]
			for j in range(code_len):
				(x,y,zzz) = paths['encode_relate'][l][j]
				tmpb = nc_func.cMulvAdd(tmpb, B[x][y], path_num, outputcode[j])
			for j in range(code_len):
				e = nc_func.mathmulti(tmpb, a[x][y], path_num)
				if e == 0:
					flag = 1
					break
			if flag:
				for i in range(code_len):
					outputcode[i] = nc_func.random_Num()
			else:
				# code is fine 
				for j in range(code_len):
					(x, y, zzz) = paths['encode_relate'][l][j]
					B[x][y] = tmpb
					tmpa = deepcopy(a[x][y])
					nc_func.cDiv(tmpa, path_num, nc_func.mathmulti(tmpb, a[x][y], path_num))
					for z in range(path_num):
						tmpa1 = deepcopy(tmpa)
						nc_func.cMul(tmpa1, path_num, nc_func.mathmulti(tmpb, a[x][z], path_num))
						for u in range(path_num):
							a[x][z][u] = nc_func.gfadd(a[x][z][u], tmpa1[u])
				# finish cahgne and finish this round, record the result
				iscodewrong = 0
				paths['encode_code'][l] = outputcode

def l_static_action_encode(paths):
	actions = {}
	"""
	for l in paths['encode_link']:
		in_num = len(paths['encode_relate'][l])
		i = 0
		outport = paths['link-to-port'](l[0], l[1])
		b_id = get_buffer_id(l[0])
		for (x,y,z) in paths['encode_relate'][l]:
			msg = create_msg(paths['shift_match'])
			msg.match.in_port = z
			msg.actions.append(nc.nc_action_encode(buffer_id = b_id, port_num = in_num,
				port_id = i, buffer_size = 512, output_port = outport, packet_len = 1024,
				packet_num = in_num, data = paths['encode_code'][l]))
			actions_add(actions, l[0], msg)
			i += 1
		add_used_buffer(paths, l[0], b_id)
	"""
	return actions

def l_random_get_encode_code(paths):
	return True

def l_random_action_encode(paths):
	actions = {}
	"""
	for l in paths['encode_link']:
		in_num = len(paths['encode_relate'][l])
		i = 0
		outport = paths['link-to-port'](l[0], l[1])
		b_id = get_buffer_id(l[0])
		for (x,y,z) in paths['encode_relate'][l]:
			msg = create_msg(paths['shift_match'])
			msg.match.in_port = z
			msg.actions.append(nc.nc_action_encode(buffer_id = b_id, port_num = in_num,
				port_id = i, buffer_size = 512, output_port = outport, packet_len = 1024,
				packet_num = len(inports)))
			actions_add(actions, l[0], msg)
			i += 1
		add_used_buffer(paths, l[0], b_id)
	"""
	return actions
	# not finish, add actions

def l_action_decode(paths):
	actions = {}
	"""
	for k in paths['a_dst']:
		ins = []
		for path in paths['paths'][(paths['a_src'],k)]['path']:
			l = path[-1]
			ins.append(paths['link-to-port'](l[1], l[0]))
		b_id = get_buffer_id(k)
		for i in range(len(ins)):
			msg = create_msg(paths['shift_match'])
			msg.match.in_port = ins[i]
			msg.actions.append(nc.nc_action_decode(buffer_id = b_id, port_id = i,
				packet_num = len(ins), output_num = len(paths['port'][k]),
				packet_len = 1024, buffer_size = 512, outports = paths['port'][k]))
			actions_add(actions, k, msg)
		add_used_buffer(paths, k, b_id)
	"""
	return actions

def l_change_match(paths):
	"""
	match = of.ofp_match()
	tmp = paths['match']
	match.dl_type = tmp.dl_type
	match.dl_src = tmp.dl_src
	match.dl_dst = tmp.dl_dst
	match.nw_src = tmp.nw_src
	match.nw_dst = tmp.nw_dst
	paths['shift_match'] = match
	"""

Dijikstra_Multicast_ops = {
		'action_forward':l_normal_action_forward,
		'path_algorithm':path_algorithm_multicast_implement['Dijikstra']
		}

Static_NC_ops = {
		'action_forward':l_nc_action_forward,
		'path_algorithm':path_algorithm_nc_implement['Max_Flow'],
		'get_init_code':l_static_get_init_code,
		'action_init':l_static_action_init,
		'change_match':l_change_match,
		'get_encode_code':l_static_get_encode_code,
		'action_encode':l_static_action_encode,
		'action_decode':l_action_decode
		}

Random_NC_ops = {
		'action_forward':l_nc_action_forward,
		'path_algorithm':path_algorithm_nc_implement['Max_Flow'],
		'get_init_code':l_random_get_init_code,
		'action_init':l_random_action_init,
		'change_match':l_change_match,
		'get_encode_code':l_random_get_encode_code,
		'action_encode':l_random_action_encode,
		'action_decode':l_action_decode
		}

class Multicast_Abstract():
	def __init__(self, ops):
		self.ops = ops
		self.action_forward = ops['action_forward']
		self.path_algorithm = ops['path_algorithm']
	# get_Paths\ get_Actions\ install_Actions 
	# here src is a tuple and dst is a tuple list
	def multicast_Plan(self, src, dst, event, prune_restrain, isrecord=True):
		paths = {}
		paths['src'] = src
		paths['dst'] = dst
		paths['event'] = event
		paths['link-to-port'] = my_test.status['topo'].link_to_Port
		return paths

	def get_Results(self):
		return (self.paths, self.actions)

	# delete if src in dst
	# if dst is from the same switch, make them one
	# src is a tuple, dst is a tuple list
	# this function will change 'src' 'dst' and add 'add_forward' 'port'
	def before_Start(self, paths):
		s = paths['src']
		if s in paths['dst']:
			paths['dst'].remove(s)
		port = {}
		for d in paths['dst']:
			try:
				port[d[0]].append(d[1])
			except:
				port[d[0]] = [d[1]]
		if s[0] in port.keys():
			t = [(s[0], s[1], port.pop(s[0]))]
		else:
			t = []
		
		paths['add_forward'] = t
		paths['port'] = port
		paths['a_dst'] = port.keys()
		paths['a_src'] = s[0]

	def prune_Topo(self, topo, prune_restrain):
		return topo
	
	def install(self, actions, src, event, isrecord):
		return 

	def error_Handle(self, *args):
		print "some thing is wrong in multicast!!"
		raise Exception

class Normal_Multicast(Multicast_Abstract):
	def multicast_Plan(self, src, dst, event, prune_restrain, isrecord=True):
		paths = Multicast_Abstract.multicast_Plan(self, src, dst, event, prune_restrain)
		port = self.before_Start(paths)
		tmptopo = self.prune_Topo(my_test.status['topo'], prune_restrain)
		if len(paths['a_dst']) == 0:
			paths['path'] = {}
		else:
			paths['path'] = self.path_algorithm.get_Paths(tmptopo, paths['a_src'], paths['a_dst'])
		actions = self.action_forward(paths)
		self.install(actions, src, paths['event'], isrecord)
		self.paths = paths
		self.actions = actions

Dijikstra_Normal_Multicast = Normal_Multicast(Dijikstra_Multicast_ops)

class NC_Multicast(Multicast_Abstract):
	def __init__(self, ops):
		Multicast_Abstract.__init__(self, ops)
		self.get_init_code = ops['get_init_code']
		self.action_init = ops['action_init']
		self.change_match = ops['change_match']
		self.get_encode_code = ops['get_encode_code']
		self.action_encode = ops['action_encode']
		self.action_decode = ops['action_decode']
	# make src out-degree bigger than 2 and so is dst in-degree
	# this function call after prune_Topo
	# will change 'dst' 'src' 'port' 'a_dst' 'a_src'
	def before_Start_After_Prune(self, paths, topo):
		src = paths['a_src']
		dst = paths['a_dst']
		tmpdst = []
		t = []
		for d in dst:
			links = []
			n = topo.get_Neighbours(d)
			tmp = d
			flag = len(n) > 1
			while not flag:
				links.append((n[0], tmp))
				tmp1 = tmp
				tmp = n[0]
				n = deepcopy(topo.get_Neighbours(tmp))
				#print "topo:" + str(topo.adjacent)
				#print "n:" + str(n) + ";tmp1:"+ str(tmp1)
				n.remove(tmp1)
				flag = len(n) > 1 or tmp == src
			if tmp != d:
				links.reverse()
				inport = paths['link-to-port'](links[0][1], links[0][0])
				for l in links[1:]:
					t.append((l[0],inport,[paths['link-to-port'](l[0],l[1])]))
					inport = paths['link-to-port'](l[1],l[0])
				t.append((d,inport,paths['port'][d]))
				outport = paths['link-to-port'](links[0][0], links[0][1])
				if tmp != src:
					tmpdst.append((tmp,outport))
				else:
					t.append((src, paths['src'][1], [outport]))
			else:
				ps = paths['port'][d]
				for p in ps:
					tmpdst.append((d,p))
		paths['dst'] = tmpdst
		port = {}
		for (d, p) in tmpdst:
			try:
				port[d].append(p)
			except:
				port[d] = [p]
		paths['a_dst'] = port.keys()
		paths['port'] = port

		# improve src
		if len(paths['a_dst']) != 0:
			# need to route
			n = topo.get_Neighbours(src)
			tmp = src
			flag = len(n) - 1
			links = []
			while not flag:
				links.append((tmp, n[0]))
				tmp1 = tmp
				tmp = n[0]
				n = deepcopy(topo.get_Neighbours(tmp))
				n.remove(tmp1)
				flag = len(n) > 1 or tmp in paths['a_dst']
			if tmp != src:
				inport = paths['src'][1]
				for l in links:
					t.append(l[0], inport, [paths['link-to-port'](l[0], l[1])])
					inport = paths['link-to-port'](l[1],l[0])
				paths['src'] = (l[1], inport)
				paths['a_src'] = l[1]
				if l[1] in port.keys():
					t.append((l[1], inport, port[l[1]]))
					ps = paths['port'].pop(l[1])
					paths['a_dst'].remove(l[1])
					for p in ps:
						paths['dst'].remove((l[1], p))

		paths['add_forward'].extend(t)

	def error_Handle(self, *args):
		self.paths = None
		self.actions = None

	def multicast_Plan(self, src, dst, event, prune_restrain, isrecord=True):
		paths = Multicast_Abstract.multicast_Plan(self, src, dst, event, prune_restrain)
		self.before_Start(paths)
		tmptopo = self.prune_Topo(my_test.status['topo'], prune_restrain)
		self.before_Start_After_Prune(paths, tmptopo)
		paths['paths'] = self.path_algorithm.get_Paths(tmptopo, paths['a_src'], paths['a_dst'])
		if len(paths['a_dst']) != 0:
			self.order_Path(paths)
			self.find_Encode_Node(paths)
			if not self.code_Order(paths):
				print "have cycles in encode links"
				self.error_Handle(src, dst, event, prune_restrain)
				return
			self.change_match(paths)
			if not self.get_init_code(paths):
				#print "init wrong, mainly because of too much outlinks of src"
				self.error_Handle(src, dst, event, prune_restrain)
				return
			self.get_encode_code(paths)
		self.paths = paths
		# here because a same match from a same switch can not generate two actions, so we just update
		actions = self.action_forward(paths)
		if len(paths['a_dst']) != 0:
			paths['used_buffer'] = {}
			actions.update(self.action_init(paths))
			actions.update(self.action_encode(paths))
			actions.update(self.action_decode(paths))
		self.actions = actions
		self.install(actions, src, paths['event'], isrecord)
		#print paths

	def order_Path(self, paths):
		ps = paths['paths']
		difflinks = []
		for k in ps.keys():
			for p in ps[k]['path']:
				l = p[0]
				if l not in difflinks:
					difflinks.append(l)
		path_id = {}
		for k in ps.keys():
			path_id[k] = []
			for p in ps[k]['path']:
				path_id[k].append(difflinks.index(p[0]))
		paths['init_link'] = difflinks
		paths['path_id'] = path_id
		paths['path_num'] = len(path_id[k])

	def find_Encode_Node(self, paths):
		pp = paths['paths']
		links = {}
		relate = {}
		dst = paths['a_dst']
		for k in pp.keys():
			i = dst.index(k[1])
			j = 0
			for p in pp[k]['path']:
				tmpl = p[0]
				# the link has src cannot be the encode link
				for l in p[1:]:
					port = paths['link-to-port'](tmpl[1], tmpl[0])
					try:
						links[l]
						try:
							links[l].index(tmpl)
						except:
							links[l].append(tmpl)
						relate[l].append((i,j,port))
					except:
						links[l] = [tmpl]
						relate[l] = [(i,j,port)]
					tmpl = l
				j = j + 1
		encode_node = []
		for k in links.keys():
			if len(links[k]) >= 2:
				encode_node.append(k)
		paths['encode_link'] = encode_node
		paths['encode_relate'] = relate
		return True

	def code_Order(self, paths):
		# encode link topo seq
		switches = {}
		codedlinks = paths['encode_link']

		switches[paths['a_src']] = []
		for key in paths['paths'].keys():
			for path in paths['paths'][key]['path']:
				tmp = paths['a_src']
				for link in path:
					if link in codedlinks:
						try:
							switches[tmp].append(link)
						except:
							switches[tmp] = [link]
						tmp = link

		for link in codedlinks:
			try:
				switches[link]
			except:
				switches[link] = []
		
		for key in switches.keys():
			switches[key] = list(set(switches[key]))

		#print switches
		topoorder = []
		color = dict.fromkeys(switches.keys(), 0)
		#print color
		def DFS(u, color):
			color[u] = 1
			for k in switches[u]:
				if color[k] == 0: # this node is not visited
					if not DFS(k, color) :
						return False
				if color[k] == 1: # circle is find
					print "src: " + str(self.src)
					print "dst: " + str(self.dst)
					print "encode node: " + str(self.codednode)
					print "switches:" + str(switches)
					print "circle node:" + str(u)
					return False
			color[u] = 2
			topoorder.append(u)
			return True
		
		if not DFS(paths['a_src'], color):
			return False
		topoorder.remove(paths['a_src'])
		topoorder.reverse()

		paths['encode_link'] = topoorder
		return True
	

Static_NC_Multicast = NC_Multicast(Static_NC_ops)
Random_NC_Multicast = NC_Multicast(Random_NC_ops)

def test_xor_encode():
	list1 = [3,6,11,16,21,26,31,36]
	method = Static_NC_Multicast
	for n in list1:
		total = 0
		I_num = 0
		print "dst_num = " + str(n-1)
		for i in range(10):
			ran_nodes = my_test.rand_Gen_Nodes(my_test.status['topo'].nodenum, n)
			src = (ran_nodes[0], 999)
			dst = [(x, 999) for x in ran_nodes[1:]]
			method.multicast_Plan(src, dst, 0, None)
			(info, xxxx) = method.get_Results()
			if info == None:
				continue
			for l in info['encode_link']:
				in_num = len(info['encode_relate'][l])
				total = total + in_num
				for x in info['encode_code'][l]:
					if x == nc_func.get_I():
						I_num = I_num + 1
		print "total is " + str(total) +  "; I_num is " + str(I_num)
test_xor_encode()
