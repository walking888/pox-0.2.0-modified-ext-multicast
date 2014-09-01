from ctypes import *
import inspect, os
from copy import deepcopy
import random
import exceptions
import pdb

class Topo_Abstract(object):
	def __init__(self):
		self.adjacent = {}
		self.link = {}
		self.flag = 0

	def get_All_Nodes(self):
		return self.adjacent.keys()

	def get_Neighbours(self, u):
		return self.adjacent[u]

	def add_Link(self, link):
		try:
			self.adjacent[link[0]].index(link[1])
		except:
			self.adjacent[link[0]].append(link[1])

class Gen_Topo(Topo_Abstract):
	def __init__(self, file_path):
		Topo_Abstract.__init__(self)
		self.topofile = open(file_path, 'r')
		self.nodenum = 0
		self.linknum = 0
		lastword = file_path.split('.')[-1]
		if lastword == 'topgen' :
			self._getTopoTopgen()
		elif lastword == 'brite' :
			self._getTopoBrite()
		else :
			print "file is not topgen file!"
			raise Exception

	def link_to_Port(self, a, b):
		return b

	def _getTopoBrite(self):
		"""
		read .brite file into topo 
		here stage means where we are:
		0  indicate start, when meet nodes change to stage 1
		1  indicate now is node information, end with nothing, when meet Edges to change
		2  indicate now is edges process , until the file is end
		"""
		stage = 0
		stagelinenum = 1
		while True:
			line = self.topofile.readline()
			if not line: break
			words = line.split()
			if stage == 0:
				if line == "\n":
					stage = stage + 1
					stagelinenum = 0
				stagelinenum = stagelinenum + 1
			elif stage == 1:
				if line == "\n":
					stage = stage + 1
					stagelinenum = 0
				if stagelinenum > 1 and stagelinenum < 2 + nodenum:
					if int(words[3]) > 1:
						self.nodenum = self.nodenum + 1
						self.adjacent[int(words[0])] = []
				stagelinenum = stagelinenum + 1
			elif stage == 2:
				if line != "\n" and words[0] != "Edges:":
					if self.adjacent.has_key((int(words[1]))) and self.adjacent.has_key((int(words[2]))):
						self.adjacent[int(words[1])].append(int(words[2]))
						self.adjacent[int(words[2])].append(int(words[1]))
						self.link[(int(words[1]), int(words[2]))] = {}
						self.link[(int(words[2]), int(words[1]))] = {}
						self.linknum = self.linknum + 1
				stagelinenum = stagelinenum + 1
			else:
				streamout("wrong file")
				raise ValueError
			
	# node id for 1 to nodenum
	def _getTopoTopgen(self):
		"""
		read .topgen file into topo 
		here stage means where we are:
		0  indicate start, have some statistics, when meet empty line change to stage 1
		1  indicate now is node information, when meet empty line change to stage 2
		2  indicate now is edge inform , until the file is end
		"""
		stage = 0
		stagelinenum = 1
		while True:
			line = self.topofile.readline()
			if not line: break
			words = line.split()
			if len(words) == 0 :
				stage = stage + 1
				stagelinenum = 1
				continue

			if stage == 0:
				if stagelinenum == 2:
					self.nodenum = int(words[-1].split(':')[-1])
				if stagelinenum == 3:
					self.linknum = int(words[-1].split(':')[-1])
			elif stage == 1:
				self.adjacent[int(words[0])] = []
			elif stage == 2:
				if self.adjacent.has_key((int(words[1]))) and self.adjacent.has_key((int(words[2]))):
						self.adjacent[int(words[1])].append(int(words[2]))
						self.adjacent[int(words[2])].append(int(words[1]))
						self.link[(int(words[1]), int(words[2]))] = {}
						self.link[(int(words[2]), int(words[1]))] = {}
				else:
					print "topo file is error!"
					raise Exception
			stagelinenum = stagelinenum + 1

	def rand_Gen_Flow(self, low_bound, up_bound):
		for u in self.adjacent.keys():
			for v in self.get_Neighbours(u):
				self.link[(u,v)]['max_flow'] =	round(random.uniform(low_bound, up_bound))
	

class Dict_Topo(Topo_Abstract):
	def __init__(self, d):
		self.adjacent = d
		self.link = {}
		self.flag = 0

class Level_Topo(Topo_Abstract):
	OUTRANGE = 999999
	def __init__(self, myt, s):
		self.src = s
		self.levelt = self.level_Topo(myt)

	def get_Neighbours(self, s):
		return self.levelt[s][1]

	def get_All_Nodes(self):
		return self.levelt.keys()
	
	def level_Topo(self, myt):
		level_topo = {}
		for u in myt.get_All_Nodes():
			level_topo[u] = [self.OUTRANGE,deepcopy(myt.get_Neighbours(u))]
		step = 0
		level_topo[self.src][0] = step
		new_add_node = [self.src]
		add_node = []
		while len(new_add_node):
			step = step + 1
			for u in new_add_node:
				tmpnodes = myt.get_Neighbours(u)
				for v in tmpnodes:
					if level_topo[v][0] == self.OUTRANGE:
						add_node.append(v)
						level_topo[v][0] = step

			new_add_node = add_node
			add_node = []
			
		return level_topo

	def get_Level(self, s):
		return self.levelt[s][0]

	def remove_Path(self, path):
		for link in path:
			self.levelt[link[0]][1].remove(link[1])
			self.levelt[link[1]][1].append(link[0])
			
	def re_Level(self):
		for u in self.levelt.keys():
			self.levelt[u][0] = self.OUTRANGE
		step = 0
		self.levelt[self.src][0] = step
		new_add_node = [self.src]
		add_node = []
		while len(new_add_node):
			step = step + 1
			for u in new_add_node:
				tmpnodes = self.get_Neighbours(u)
				for v in tmpnodes:
					if self.levelt[v][0] == self.OUTRANGE:
						add_node.append(v)
						self.levelt[v][0] = step

			new_add_node = add_node
			add_node = []
			
# this topo is only for Network Coding, multipath topo
# that means this is only for directed acycle graph
#####################	 not finished ##################
"""
class Virtual_Topo_One_to_Many(Topo_Abstract):
	VIRTUAL_NODE_START = 10000
	def __init__(self, paths, s):
		self.map = {}
		self.adjacent = {}
		self.link = {}
		self.linkmap = {}
		self.shape_Topo(paths, s)
		self.shape_link(paths, s)
		self.flag = 1

	def get_Orig_Id(self, u):
		return self.map[u]

	def shape_Topo(self, in_topo, s):
		maptovirtual = {}
		start = self.VIRTUAL_NODE_START
		nodes = []
			
		for p in paths.keys():
			for links in paths[p]['path']:
				for (u,v) in links:
					def init_maptovirtual(s):
						try:
							maptovirtual[s]
						except:
							maptovirtual[s] = {}
							maptovirtual[s]['in'] = []
							maptovirtual[s]['out'] = []
							nodes.append(s)
					init_maptovirtual(u)
					init_maptovirtual(v)
					maptovirtual[v]['in'].append((u,v))
					maptovirtual[u]['out'].append((u,v))
				
		
		need_virtual = []
		for u in nodes:
			maptovirtual[u]['in'] = list(set(maptovirtual[u]['in']))
			maptovirtual[u]['out'] = list(set(maptovirtual[u]['out']))
			if len(maptovirtual[u]['in']) > 1 and len(maptovirtual[u]['out']) > 1:
				need_virtual.append(u)
				maptovirtual[u]['map'] = {}
				for link in maptovirtual[u]['in'] + maptovirtual[u]['out']:
					maptovirtual[u]['map'][link] = start
					start = start + 1
				
		map_paths = {}
		for p in paths.keys():
			map_paths[p] = {}
			map_paths[p]['path'] = []
			for links in paths[p]['path']:
				tmppath = []
				tmp = links[0][0]
				for link in links:
					if tmp >= self.VIRTUAL_NODE_START:
						# this link start from a virtual node
						k = maptovirtual[link[0]]['map'][link]
						tmppath.append((tmp, k))
						self.linkmap[(tmp,k)] = []
						tmp = k
					if link[1] in need_virtual:
						k = maptovirtual[link[1]]['map'][link]
						self.linkmap[(tmp,k)] = [link]
					else:
						k = links[1]
						# stop here
					tmppath.append((tmp, k))
					tmp = k

				map_paths[p]['path'].append(tmppath)
						
		for p in map_paths.keys():
			for links in paths[p]['path']
"""

## weight algorithm, is in state keep area
def always_One(link):
	return 1


min_cost_weight_states = {}
def change_Weight(link):
	try:
		min_cost_weight_states['change_weight'][link]
	except:
		print min_cost_weight_states
	return min_cost_weight_states['change_weight'][link]

weight_states = {}
def add_Link_Weight(link):
	if link in weight_states['change_weight'].keys():
		return weight_states['change_weight'][link][0]
	else:
		tmp = weight_states['get_weight']
		return tmp(link)
	
# Path algorithm base class
class Path_Algorithm_Abstract(object):
	MAX_WEIGHT = 9999
	def __init__(self, gw = always_One):
		self.get_Weight = gw
		
	def get_Paths(self, topo, src, dst, num = 1):
		return {}

	def error_Handle(self, *args):
		print "error in Path Algorithm"
		raise Exception

	def set_Weight(self, gw):
		self.get_Weight = gw
	
	def get_Weight_Algorithm(self):
		return self.get_Weight
# here dst is list
class Topo_to_Path(Path_Algorithm_Abstract):
	# this function must be rewrite 
	def algorithm(self, topo, src, dst):
		return {}
	
	def get_Paths(self, topo, src, dst, num = 1):
		tmp_links = self.algorithm(topo, src, dst)
		tmp_paths = self.reverse_Topo_to_Path(tmp_links, src, dst)
		if tmp_paths == None:
			return self.error_Handle(tmp_paths)
		return tmp_paths

	def reverse_Topo_to_Path(self, linklist, src, dst):
		route = {}
		for nextdes in dst :
			tmpdst = nextdes
			path = []
			while nextdes != src :
				if linklist.has_key(nextdes):
					link = linklist[nextdes]
					path.append(link)
					nextdes = link[0]
				else :
					return None 
			path.reverse()
			route[(src, tmpdst)] = {}
			route[(src, tmpdst)]['path'] = [path]

		return route

	def error_Handle(self, *args):
		print "src and dst is not connected!1"
		raise Exception

class SPFA(Topo_to_Path):
	def algorithm(self, topo, src, dst):
		mydst = dst
		queen = [src]
		dist = {src:0}
		linklist = {} 
		while len(queen) != 0:
			u = queen.pop(0)
			sn = topo.get_Neighbours(u) 
			for adju in sn:
				if not dist.get(adju) :
					dist[adju] = self.MAX_WEIGHT
				tmp = dist[u] + self.get_Weight((u, adju))	#here we think weight is always 1
				if dist[adju] > tmp :
					dist[adju] = tmp
					linklist[adju] = (u, adju)
					if adju not in queen :
						queen.append(adju)
		return linklist
	
class Dijikstra(Topo_to_Path):
	def algorithm(self, topo, src, dst):
		def extract_Min(x, w):
			tmp_weight = self.MAX_WEIGHT * len(x)
			index = 0
			for u in x:
				tmp = w[u]
				if tmp < tmp_weight:
					index = u
					tmp_weight = tmp
			return index
		
		linklist = {}
		S = []
		dist = {}
		Q = topo.get_All_Nodes()
		for node in Q:
			dist[node] = self.MAX_WEIGHT * len(Q)
		dist[src] = 0
		flag = len(dst)
		while len(Q) > 0 or flag > 0:
			u = extract_Min(Q, dist)
			if u == 0:
				# Graph is not connected 
				break
			Q.remove(u)
			S.append(u)
			if u in dst:
				flag = flag - 1
			for v in topo.get_Neighbours(u):
				tmp = dist[u] + self.get_Weight((u, v))
				if dist[v] > tmp:
					dist[v] = tmp
					linklist[v] = (u, v)
		return linklist

# here, dst is a node_id, can not be a list
class One_to_One_Multipath(Path_Algorithm_Abstract):
	def __init__(self, a):
		self.path_algorithm = a
		self.get_Weight = add_Link_Weight
		self.path_num = 2

	def set_Path_Num(self, num):
		self.path_num = num

	def get_Path_Num(self):
		return self.path_num

	def get_Paths(self, topo, src, dst):
		weight_states['get_weight'] = self.path_algorithm.get_Weight
		weight_states['change_weight'] = {}
		self.set_Weight(self.get_Weight)
		
		paths = {}
		paths[(src,dst)] = {}
		tmppaths = []
		tmptopo = deepcopy(topo)
		for i in range(self.path_num):
			# find n path
			tmp = self.path_algorithm.get_Paths(tmptopo, src, [dst])
			def is_Link_OK(p):
				for l in p:
					if self.get_Weight(l) == self.MAX_WEIGHT:
						return True
				return False
					
			if tmp == None or is_Link_OK(tmp[(src,dst)]['path'][0]):
				return self.error_Handle(topo, src, dst, tmppath)
			tmppath = tmp[(src,dst)]['path'][0]
			self.delete_Link(tmptopo, tmppath)
			tmppaths.append(tmppath)

		
		# success find num path
		#print src, dst
		#print tmppaths
		paths[(src,dst)]['path'] = self.delete_Reverse_Link(tmppaths, src, dst)
		#print paths[(src, dst)]['path']
		self.set_Weight(weight_states['get_weight'])
		return paths

	def delete_Link(self, topo, tmppath):
		for link in tmppath:
			rev_link = (link[1], link[0])
			try:
				weight_states['change_weight'][rev_link].append(self.get_Weight(link))
			except:
				weight_states['change_weight'][rev_link] = [self.get_Weight(link)]
				# add_link is in topo?
				# we just change weight to reflect this delete link
				if link[0] in topo.get_Neighbours(link[1]):
					# in the topo
					weight_states['change_weight'][rev_link].append(self.get_Weight(rev_link))
				else:
					# reverse link is not at topo, we must add it
					topo.add_Link(rev_link)
				
			if link in weight_states['change_weight'].keys():
				weight_states['change_weight'][link].pop(0)
				if len(weight_states['change_weight'][link]) == 0:
					weight_states['change_weight'][link].append(self.MAX_WEIGHT)
			else:
				weight_states['change_weight'][link] = [self.MAX_WEIGHT]

			weight_states['change_weight'][rev_link].sort()

	def set_Weight(self, gw):
		self.path_algorithm.set_Weight(gw)

	def get_Weight_Algorithm(self):
		return self.path_algorithm.get_Weight

	def delete_Reverse_Link(self, paths, src, dst):
		xxx = {}
		tmpsrc = src
		tmpdst = dst
		for path in paths:
			for (u,v) in path:
				try:
					# test if have a reverse link,
					# if have delete it
					xxx[v].remove(u)		
				except:
					# if donot have add this link to adjacent
					try:
						xxx[u].append(v)
					except:
						xxx[u] = [v]
		# now change the topo to paths
		# because is disjoint path so we can simplify the procedure
		result = []
		for u in xxx[tmpsrc]:
			yyy = [(tmpsrc, u)]
			v = u
			while  v != tmpdst:
				v = xxx[u][0]
				yyy.append((u,v))
				xxx[u].remove(v)
				u = v
			result.append(yyy)

		return result

	def error_Handle(self, *args):
		return None

class Max_Flow(Path_Algorithm_Abstract):
	def get_Paths(self, topo, src, dst):
		self.src = src
		self.levelt = Level_Topo(topo, src)
		paths = {}
		self.topo = topo
		paths[(src, dst)] = {}
		paths[(src, dst)]['path'] = self.max_Flows(dst)
		if paths[(src, dst)]['path'] == None:
			self.error_Handle(topo, src, dst)
		return paths
			
	def max_Flows(self, d):
		path = []
		tmplevelt = deepcopy(self.levelt)

		while tmplevelt.get_Level(d) != tmplevelt.OUTRANGE:
			#this means leveltopo has node d
			stack = [self.src]
			link = []
			# start dfs
			while len(stack):
				u = stack.pop()
				if u == 0:
					link.pop()
					continue
				else:
					link.append(u)
					stack.append(0)
				if u == d:
					#find a path
					tmppath = []
					x = 0
					for y in link:
						if x != 0:
							tmppath.append((x,y))
						x = y
					path.append(tmppath)
					tmplevelt.remove_Path(tmppath)
					
					while len(link) > 1:
						u = stack.pop()
						if u == 0:
							link.pop()
				elif u > 0:
					tmps = tmplevelt.get_Neighbours(u)
					deep = tmplevelt.get_Level(u)
					for v in tmps:
						if tmplevelt.get_Level(v) == deep + 1:
							stack.append(v)
			# end of a dfs
			tmplevelt.re_Level()
		# end of first while
		# delete reverse links
		switches = {}
		for links in path:
			for link in links:
				try:
					switches[link[0]]
				except:
					switches[link[0]] = []
				try:
					switches[link[1]]
				except:
					switches[link[1]] = []
				try:
					switches[link[1]].remove(link[0])
				except:
					# no reverse link
					switches[link[0]].append(link[1])
		"""
		#print d
		#print self.levelt.levelt
		#print switches
		#print path
		try:
			switches[self.src]
		except:
			print self.topo.adjacent
			raise Exception
		"""
		path = []
		while len(switches[self.src]):
			link = []
			v = self.src
			while v != d:
				u = v
				v = switches[u].pop()
				link.append((u,v))
			path.append(link)
		return path
	
class One_to_Many_NC(One_to_One_Multipath):
	def __init__(self, a):
		self.path_algorithm = a
		self.get_Weight = a.get_Weight_Algorithm()
		self.flag_improve = 1

	def set_Is_Improve(self, flag):
		self.flag_improve = flag
		
	def get_Paths(self, topo, src, dst):
		paths = {}
		if len(dst) == 0:
			return paths
		min_num = 999
		path_num = {}
		for d in dst:
			paths[(src, d)] = {}
			k = self.path_algorithm.get_Paths(topo, src, d)
			if k == None:
				return self.error_Handle(topo, src, dst, k)
			paths.update(k)
			path_num[(src, d)] = len(paths[(src, d)]['path'])
			if path_num[(src, d)] < min_num :
				min_num = path_num[(src, d)]
			
		for d in dst:
			while path_num[(src, d)] > min_num:
				self.delete_Worst_Path(paths[(src, d)]['path'])
				path_num[(src, d)] = path_num[(src, d)] - 1
				
		if self.flag_improve != 0:
			 weight_algorithm_stack = self.get_Weight
			 self.set_Weight(change_Weight)
			 self.min_Global(paths, src, dst)
			 self.set_Weight(weight_algorithm_stack)
		return paths

	def get_Mixed_Topo(self, paths, my_src, my_dst):
		tmptopo = {}
		for d in my_dst:
			path_list = paths[(my_src, d)]['path']
			for path in path_list:
				for (u,v) in path:
					try:
						tmptopo[u].index(v)
					except:
						try:
							tmptopo[u].append(v)
						except:
							tmptopo[u] = [v]
					try:
						tmptopo[v]
					except:
						tmptopo[v] = []
			#print tmptopo
		return Dict_Topo(tmptopo)
	
	def zero_One_Weight(self, paths, my_src, ps1, ps2):
		weight = {}
		for d in ps1:
			path_list = paths[(my_src, d)]['path']
			for path in path_list:
				for link in path:
					weight[link] = 0
		for d in ps2:
			path_list = paths[(my_src, d)]['path']
			for path in path_list:
				for link in path:
					try:
						weight[link]
					except:
						weight[link] = 1
		return weight


	def min_Local(self, paths, my_src, d1, d2):
		#print d1, d2
		#print paths
		paths_num = len(paths[(my_src, d1)]['path'])
		tmptopo = self.get_Mixed_Topo(paths, my_src, [d1, d2])
		min_cost_weight_states['change_weight'] = {}
		min_cost_weight_states['change_weight'].update(self.zero_One_Weight(paths, my_src, [d1], [d2]))
		tmp_paths = self.path_algorithm.get_Paths(tmptopo, my_src, d2)
		#print tmp_paths
		paths[(my_src, d2)]['path'] = tmp_paths[(my_src, d2)]['path']
		#print paths
		tmptopo = self.get_Mixed_Topo(paths, my_src, [d1, d2])
		min_cost_weight_states['change_weight'].clear()
		min_cost_weight_states['change_weight'] = self.zero_One_Weight(paths, my_src, [d2], [d1])
		#print tmptopo.adjacent
		#print min_cost_weight_states
		#if (d1, d2) == (14,2):
		#	pdb.set_trace()
		tmp_paths = self.path_algorithm.get_Paths(tmptopo, my_src, d1)
		#print tmp_paths

		paths[(my_src, d1)]['path'] = tmp_paths[(my_src,d1)]['path']
		
		#print "paths:" + str(paths)


	def min_Global(self, paths, my_src, my_dst):
		P = []
		ps2 = my_dst
		paths_num = len(paths[(my_src, my_dst[0])]['path'])
		for i in range(len(ps2)):
			for n in ps2[i+1:]:
				#print n,ps2[i],i
				self.min_Local(paths, my_src, n, ps2[i])

	def delete_Worst_Path(self, path_s):
		index = 99999
		max_cost = 0
		i = 0
		for path in path_s:
			total_cost = 0
			for link in path:
				total_cost = total_cost + self.get_Weight(link)
			if total_cost > max_cost:
				index = i
				max_cost = total_cost
			i = i + 1
		if index == 9999:
			raise Exception
		else:
			path_s.pop(index)	  

##	here is all path algorithm we support:
#	multicast : Dijikstra \ SPFA
#	NC:			Dijikstra \ SPFA \ Max_Flow
path_algorithm_multicast_implement = {
	'Dijikstra' :Dijikstra(),
	'SPFA'		:SPFA()
	}
path_algorithm_multipath_implement = {
	'Dijikstra' :One_to_One_Multipath(Dijikstra()),
	'SPFA'		:One_to_One_Multipath(SPFA()),
	'Max_Flow'	:Max_Flow()
	}
# here flag_improve is 1, if donot want this improve please set it 0
path_algorithm_nc_implement = {
	'Dijikstra' :One_to_Many_NC(One_to_One_Multipath(Dijikstra())),
	'SPFA'		:One_to_Many_NC(One_to_One_Multipath(SPFA())),
	'Max_Flow'	:One_to_Many_NC(Max_Flow())
	}


class Test_Path_Algorithm():
	def __init__(self, topo, dst_percentage = 0.1):
		self.status = {
			'topo' : topo,
			'dst_num' : topo.nodenum * dst_percentage,
			'test_time' : 1,
			'one_test_run_time' : 10
			}

	def set_Status(self, a, value):
		self.status[a] = value

	def get_Status(self, a):
		try:
			return self.status[a]
		except:
			print "donot have that status"

	# random generate num number from [1-upbound]
	def rand_Gen_Nodes(self, upbound, num):
		nodes = []
		gen = 0
		if num <= upbound/2:
			gen = num
		else:
			gen = upbound - num

		i = 0
		while (i<gen):
			k= random.randint(1, upbound)
			if k not in nodes:
				nodes.append(k)
				i = i + 1

		if num <= upbound/2:
			return nodes
		else:
			tmp = [x+1 for x in range(upbound)]
			return [x for x in tmp if x not in nodes]

	def test(self, path_algorithm):
		import time
		ave_time = []
		print "start test!"
		for i in range(self.status['test_time']):
			ran_nodes = self.rand_Gen_Nodes(self.status['topo'].nodenum, self.status['dst_num'] + 1)
			src = ran_nodes[0]
			dst = ran_nodes[1:]
			#print ran_nodes
			start_time = time.time()
			for j in range(self.status['one_test_run_time']):
				path_algorithm.get_Paths(self.status['topo'], src, dst)

			end_time = time.time()
			use_time = end_time - start_time
			ave_time.append(use_time/ self.status['one_test_run_time'])

		t1 = 0
		for t in ave_time:
			t1 = t1 + t
		print 'ave time:' + str(t1/self.status['test_time'])

aaa_test_or_not = 1
if aaa_test_or_not:
	my_test = Test_Path_Algorithm(Gen_Topo('/home/lsch/trace/topo60.topgen'))
"""
my_test.set_Status('test_time', 10)
#my_test.set_Status('one_test_run_time', 1)
path_algorithm_nc_implement['SPFA'].set_Is_Improve(1)
my_test.test(path_algorithm_nc_implement['SPFA'])

"""
def find_Encode_Node(paths):
	links = {}
	for k in paths.keys():
		for p in paths[k]['path']:
			tmpl = p[0]
			for l in p[1:]:
				try:
					links[l]
					try:
						links[l].index(tmpl)
					except:
						links[l].append(tmpl)
				except:
					links[l] = [tmpl]
				tmpl = l
	encode_node = []
	for k in links.keys():
		if len(links[k]) >= 2:
			encode_node.append(k)
	return len(encode_node)

def compare_test():
	def calculate_link(paths):
		links = []
		for k in paths.keys():
			for path in paths[k]['path']:
				for l in path:
					if l not in links:
						links.append(l)
		return len(links)

	list1 = [3,6,11,16,21,26,31,36]
	k = path_algorithm_nc_implement['Dijikstra']
	for n in list1:
		print "dst_num = " + str(n -1)
		"""
		"""
		for i in range(100):
			ran_nodes = my_test.rand_Gen_Nodes(my_test.status['topo'].nodenum, n)
			if 1:
				src = ran_nodes[0]
				dst = ran_nodes[1:]
			else:
				src = 8
				dst = [2,4,13,14]
			#print 'src:' + str(src)
			#print 'dst:' + str(dst)
							
			"""
			k.set_Is_Improve(0)
			paths = k.get_Paths(my_test.status['topo'], src, dst)
			print 'have links:' + str(calculate_link(paths))
			print 'have encode node: '+str(find_Encode_Node(paths))
			#print my_test.status['topo'].adjacent
			k.set_Is_Improve(1)
			paths = k.get_Paths(my_test.status['topo'], src, dst)
			print 'have links:' + str(calculate_link(paths))
			print 'have encode node: '+str(find_Encode_Node(paths))
			#print paths
			"""
			#print my_test.status['topo'].adjacent
			k.set_Is_Improve(0)
			paths = k.get_Paths(my_test.status['topo'], src, dst)
			a = str(calculate_link(paths)) + ' ' + str(find_Encode_Node(paths))
			k.set_Is_Improve(1)
			paths = k.get_Paths(my_test.status['topo'], src, dst)
			a += ' ' + str(calculate_link(paths)) + ' ' + str(find_Encode_Node(paths))
			print a
"""
if aaa_test_or_not:
	compare_test()
"""
