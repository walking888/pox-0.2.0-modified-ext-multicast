# Copyright 2011 James McCauley
#
# This file is part of POX.
#
# POX is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# POX is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX.  If not, see <http://www.gnu.org/licenses/>.

"""
OpenFlow doesn't know anything about Topology, and Topology doesn't
know anything about OpenFlow.  This module knows something about both,
and hooks the two of them together.

Specifically, this module is somewhat like an adapter that listens to
events from other parts of the openflow substem (such as discovery), and
uses them to populate and manipulate Topology.
"""

import itertools

from pox.lib.revent import *
import pox.openflow.libopenflow_01 as of
from pox.openflow import *
from pox.core import core
from pox.topology.topology import *
from pox.openflow.discovery import *
from pox.openflow.topology import OpenFlowTopology
from pox.openflow.libopenflow_01 import xid_generator
from pox.openflow.flow_table import FlowTable,FlowTableModification,TableEntry
from pox.lib.util import dpidToStr
from pox.lib.addresses import *

import pickle
import itertools

from ctypes import *
import inspect, os
from copy import deepcopy
import random
import pox.openflow.nc as nc
import pdb
import exceptions

# After a switch disconnects, it has this many seconds to reconnect in
# order to reactivate the same OpenFlowSwitch object.  After this, if
# it reconnects, it will be a new switch object.
RECONNECT_TIMEOUT = 30

log = core.getLogger()

class OpenFlowTopology_Improve1(OpenFlowTopology):
	_core_name = "openflow_topology"
	def __init__(self):
		OpenFlowTopology.__init__(self)
		self.adjacent = {}
	
	def __add_adjacent(self, dic, key, value):
		try:
			dic[key].append(value)
		except:
			dic[key] = [value]

	def __del_adjacent(self, dic, key, value):
		if dic.has_key(key):
			try:
				dic[key].remove(value)
			except:
				print "do not have this value, wrong del"

	def _handle_openflow_discovery_LinkEvent(self, event):
		OpenFlowTopology._handle_openflow_discovery_LinkEvent(self, event)
		link = event.link
		if event.added:
			self.__add_adjacent(self.adjacent, link.dpid1, link.dpid2)
			self.__add_adjacent(self.adjacent, link.dpid2, link.dpid1)
		elif event.removed:
			self.__del_adjacent(self.adjacent, link.dpid1, link.dpid2)
			self.__del_adjacent(self.adjacent, link.dpid2, link.dpid1)

	def _handle_openflow_ConnectionUp(self, event):
		OpenFlowTopology._handle_openflow_ConnectionUp(self, event)
		try:
			self.adjacent[event.dpid]
		except:
			self.adjacent[event.dpid] = []

	def _handle_openflow_ConnectionDown(self, event):
		OpenFlowTopology._handle_openflow_ConnectionDown(self, event)
		try:
			self.adjacent.pop(event.dpid)
		except:
			print "switch is not in adjacent matrix!"
	
	#here we use this function without check 
	def link_to_port(self, dpid1, dpid2):
		s1 = self.topology.getEntityByID(dpid1)
		s2 = self.topology.getEntityByID(dpid2)
		for port in s1.ports:
			if s2 in s1.ports[port].entities:
				return port
		raise Exception


class MulticastSPF(object):
	MAX_WEIGHT = 1023

	def __init__(self, src, dst, match):
		self.src = src
		self.dst = dst
		self.path = {}
		self.pathtoaction = {}
		self.actions = {}
		self.flag = 0
		self.version = 1
		self.match = match
		if len(src) == 1:
			if self.dst.count((src[0])) != 0:
				self.dst = list(set(self.dst)-set(self.src))
			print "src:"+str(self.src)
			print "dst:"+str(self.dst)
		else:
			# we only deal with one src at this version
			print "src must be one value"
			raise ValueError
		if self.IsCorrect():
			self.path = self.__MultiPath()
			if self.path is None:
				print "topo is not connected graph"
				raise Exception
			self.pathtoaction = self.__OutputActionPerSwitch()
			self.actions = self.__CanculateAction()
			self.InstallActions()
			print "path is: ", self.path
		else :
			print "wrong dst id or src id!"


	def IsCorrect(self):
		if len(self.dst) != 0:
			sw = core.openflow_topology.topology.getEntityByID(self.src[0][0])
			if len(sw.ports[self.src[0][1]].entities) == 0 :
				return True
			return False

	def __weight(self, u, adju):
		return 1

	def __MultiPath(self):
		mydst = []
		for i in self.dst:
			mydst.append(i[0])
		
		queen = [self.src[0][0]]
		dist = {self.src[0][0]:0}
		linklist = {}
		while len(queen) != 0:
			u = queen.pop(0)
			sn = core.openflow_topology.adjacent[u] 
			for adju in sn:
				if not dist.get(adju) :
					dist[adju] = self.MAX_WEIGHT
				tmp = dist[u] + self.__weight(u, adju)	#here we think weight is always 1
				if dist[adju] > tmp :
					dist[adju] = tmp
					linklist[adju] = (u, adju)
					if adju not in queen :
						queen.append(adju)
		route = {}
		for nextdes in mydst :
			path = []
			route[nextdes] = path
			while nextdes != self.src[0][0] :
				if linklist.has_key(nextdes):
					link = linklist[nextdes]
					path.append(link)
					nextdes = link[0]
				else :
					return None 
			path.reverse()
		return route

	def __OutputActionPerSwitch(self):
		switches = {}

		def switches_add(switch, sw, inport, outport):
			try:
				switch[sw]
			except:
				switch[sw] = {}
			try:
				switch[sw][inport].append(outport)
			except:
				switch[sw][inport] = [outport]
			
		for dst in self.path.keys():
			path = self.path[dst]
			tmpport = self.src[0][1]
			for link in path:
				port = core.openflow_topology.link_to_port(link[0] ,link[1])
				switches_add(switches, link[0], tmpport, port)
				tmpport = core.openflow_topology.link_to_port(link[1], link[0])
				if link[1] == dst:
					for i in self.dst:
						if i[0] == dst:
							switches_add(switches, link[1], tmpport, i[1])
		return switches

	def __create_msg(self, match):
		msg = of.ofp_flow_mod()
		msg.idle_timeout = 120
		msg.hard_timeout = 120
		msg.match = deepcopy(match)
		return msg

	def __CanculateAction(self):
		actions = {}
		for sw in self.pathtoaction.keys():
			actions[sw] = []
			act = self.pathtoaction[sw]
			for inport in act.keys():
				outports = act[inport]
				self.match.in_port = inport
				msg = self.__create_msg(self.match)
				for outport in outports:
					msg.actions.append(of.ofp_action_output(port = outport))
				actions[sw].append(msg)
		return actions


	def InstallActions(self):
		for sw in self.actions.keys():
			if sw != self.src[0][0]:
				s =  core.openflow_topology.topology.getEntityByID(sw)
				for msg in self.actions[sw]:
					s._connection.send(msg)
		# last send the src actions to start the flow
		s = core.openflow_topology.topology.getEntityByID(self.src[0][0])
		for msg in self.actions[self.src[0][0]]:
			s._connection.send(msg)

class MulticastNC(MulticastSPF):
	# this is all class MulticastNC shared variable 
	this_file = inspect.getfile(inspect.currentframe())
	this_path = os.path.abspath(os.path.dirname(this_file))
	test = cdll.LoadLibrary(this_path + '/forcode/libgf256.so')
	test.initMulDivTab(this_path + '/forcode/muldiv.tab')
	# some global statics
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
		
	
	def __init__(self, src, dst, match, pathnum = 2, shift = 0):
		self.src = src
		self.dst = dst
		self.path = {}
		self.pathnum = pathnum
		self.pathtoaction = {}
		self.actions = {}
		self.flag = 0
		self.version = 2
		self.shift = g_id
		self.match = match
		self.codednode = {}
		self.initcode = {}
		self.topoorder = []
		self.encode = {}
		self.difflinks = []
		self.match_change = deepcopy(match)
		self.match_change.nw_proto = 200 + self.shift

		if len(src) == 1:
			if self.dst.count((src[0])) != 0:
				self.dst = list(set(self.dst)-set(self.src))
			print "src:"+str(self.src)
			print "dst:"+str(self.dst)
		else:
			# we only deal with one src at this version
			print "src must be one value"
			raise ValueError
		if self.IsCorrect():
			# here we set 224.0.0.0/24 to be NC multicast group
			# and other multicast address will use shortest path
			if match.nw_dst.inNetwork("224.0.0.0/24"):
				if self.__NCStart():
					self.flag = 1
					self.encode = self.__GetCode()
					self.actions = self.__CanculateNCAction()
					self.InstallActions()
					print "path :", self.path
					print "codednode :", self.codednode
					print "initcode :", self.initcode
					print "encode :", self.encode
					return
			self.path = self.__MultiPath()
			if self.path is None:
				print "topo is not connected graph"
				raise Exception
			self.pathtoaction = self.__OutputActionPerSwitch()
			self.actions = self.__CanculateAction()
			self.InstallActions()
			print "path is: ", self.path
		else :
			print "wrong dst id or src id!"


	def cMulvAdd(self, vec1, vec2, size, co):
		#print "start mulvadd:", vec1, vec2, size, co
		for i in range(size):
			vec1[i] = self.test.gfadd(vec1[i], self.test.gfmul(co, vec2[i]))
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
	
	def __NCStart(self):
		self.path = self.__MultiNCPath()
		if self.path is None:
			return False
		self.pathtoaction = self.__OutputActionPerSwitchNC()
		self.initcode = self.__InitializationCode()
		if self.initcode is None:
			print "need init code we donot support!"
			return False
		self.codednode = self.__FindCodedNode()
		self.topoorder = self.__CodeOrder()
		if self.topoorder is not False:
			return True
		else:
			print "have cycles!"
			return False
	
	def __weight(self, u, adju):
		if (u, adju) in self.exceptlinks:
			return self.MAX_WEIGHT
		return 1

	def __MultiNCPath(self):
		path = {}
		for dst in self.dst:
			self.exceptlinks = []
			for j in range(self.pathnum):
				tmppath = self.__MultiPath()
				if tmppath is None:
					return None
				path[(dst[0],j)] = tmppath[dst[0]]
				self.exceptlinks.extend(tmppath[dst[0]])
		return path 


	def __InitializationCode(self):
		initcode = {}
		srcmy = self.src[0][0]
		for outport in self.pathtoaction[srcmy][0][self.src[0][1]]:
			self.difflinks.append((self.src[0][1], outport))
		for i in range(len(self.difflinks)):
			tmppathids = self.pathtoaction[srcmy][2][self.difflinks[i]]
			for tmppathid in tmppathids:
				self.initcode[tmppathid] = i
		return initcode

	def __OutputActionPerSwitchNC(self):
		switches = {}
		
		def switches_add(switch, sw, inport, outport, pathid):
			try:
				switch[sw]
			except:
				switch[sw] = [{},{},{}]
			try:
				switch[sw][0][inport].append(outport)
			except:
				switch[sw][0][inport] = [outport]
			try:
				switch[sw][1][outport].append(inport)
			except:
				switch[sw][1][outport] = [inport]
			try:
				switch[sw][2][(inport,outport)].append(pathid)
			except:
				switch[sw][2][(inport,outport)] = [pathid]
		
		tmpdst = []
		for dst in self.dst:
			tmpdst.append(dst[0])

		for dst in self.path.keys():
			path = self.path[dst]
			tmpport = self.src[0][1]
			for link in path:
				port = core.openflow_topology.link_to_port(link[0] ,link[1])
				pathid = (tmpdst.index(dst[0]), dst[1])
				switches_add(switches, link[0], tmpport, port, pathid)
				tmpport = core.openflow_topology.link_to_port(link[1], link[0])
				if link[1] == dst[0]:
					ii = tmpdst.index(dst[0])
					pathid = (tmpdst.index(dst[0]), dst[1])
					switches_add(switches, link[1], tmpport, self.dst[ii][1], pathid)
		# remove duplicates
		for sw in switches.keys():
			[ins, outs] = switches[sw]
			for inport in ins.keys():
				ins[inport] = list(set(ins[inport]))
			for outport in outs.keys():
				outs[outport] = list(set(outs[outport]))
		return switches

	def __FindCodedNode(self):
		needcode = {}
		for sw in self.pathtoaction.keys():
			[ins, outs, pathinfo] = self.pathtoaction[sw]
			for outport in outs.keys():
				if len(outs[outport]) > 1 :
					try:
						needcode[sw].append(outport)
					except:
						needcode[sw] = [outport]
		return needcode

	def __CodeOrder(self):
		switches = {}
		for key in self.path.keys():
			path = self.path[key]
			tmp = path[0][0]
			for link in path:
				if link[1] in self.codednode.keys():
					try:
						switches[tmp].append(link[1])
					except:
						switches[tmp] = [link[1]]
					tmp = link[1]
			try:
				switches[tmp].append(key[0])
			except:
				switches[tmp] = [key[0]]
			try:
				switches[key[0]]
			except:
				switches[key[0]] = []

		topoorder = []
		color = dict.fromkeys(switches.keys(), 0)
		def DFS(u, color):
			color[u] = 1
			for k in switches[u].keys():
				if color[k] == 0: # this node is not visited
					if not DFS(k, color) :
						return False
				if color[k] == 1: # circle is find
					return False
			color[u] = 2
			topoorder.append(u)
			return True
		
		if not DFS(self.src[0][0], color):
			return False
		topoorder.reverse()

		return topoorder

	def __GetCode(self):
		# 
		myswitch = {}
			
		B = {}
		a = {}
		tmpall = []
		for i in range(len(self.dst)):
			B[i] = {}
			a[i] = {}
			tmpall = []
			for j in range(self.pathnum):
				B[i][j] = deepcopy(self.NCvector[self.pathnum][self.initcode[(i, j)]])
				try:
					tmpall.append(self.initcode[(i, j)])
				except IndexError:
					print "link "+ str(path[0]) + " is not in difflinks!"
			for j in range(self.pathnum):
				tmpall1 = deepcopy(tmpall)
				del tmpall1[j]
				tmpall1 = tuple(tmpall1)
				a[i][j] = self.NCmatrix[self.pathnum][tmpall1]
		
		for sw in self.topoorder:
			outports = self.needcode[sw]
			for outport in outports:
				codelen = len(self.pathtoaction[sw][1][outport])

				# init outputcode
				outputcode = [1 for x in range(codelen)]
				
				tmppathids = []
				j = 0
				for inport in  self.pathtoaction[sw][1][outport]:
					tmppathids.append(self.pathtoaction[sw][2][(inport, outport)])
					j = j + 1
				iscodewrong = 1
				while iscodewrong :
					for i in range(codelen):
						outputcode[i] = random.randint(0, 255)
					tmpb = [0 for x in range(self.pathnum)]
					for j in range(codelen):
						tmpb = self.cMulvAdd(tmpb, self.B[tmppathids[j][0]][tmppathids[j][1]], self.pathnum, outputcode[j])

					for j in range(codelen):
						e = self.mathmulti(tmpb, self.a[tmppathids[j][0]][tmppathids[j][1]], self.pathnum)
						if e == 0:
							iscodewrong = iscodewrong + 1
							# code is not right, end this round 
							break;


					# code is fine 
					for j in range(codelen):
						(x,y) = tmppathids[j]
						self.B[x][y] = tmpb
						tmpa = deepcopy(self.a[x][y])
						self.cDiv(tmpa, self.h, self.mathmulti(tmpb, self.a[x][y], self.h))
						for  z  in range(self.pathnum):
							tmpa1 = deepcopy(tmpa)
							self.cMul(tmpa1, self.pathnum, self.mathmulti(tmpb, self.a[x][z], self.pathnum))
							for u in range(self.pathnum):
								self.a[x][z][u] = self.test.gfadd(self.a[x][z][u], tmpa1[u])
					#finish change and finish this round
					iscodewrong = 0
				myswitch[(sw, outport)] = (outputcode, tmppathids)
		return myswtich

	def __CanculateNCAction(self):

		actions = {}
		# forwarding actions
		for sw in self.pathtoaction.keys():
			if sw != self.src[0][0]:
				# node is not init node
				for outport in self.pathtoaction[sw][1].keys():
					inports = self.pathtoaction[sw][1][outport]
					if len(inports) == 1:
						# this is forwarding action
						self.match_change.in_port = inports[0]
						if actions.has_key((sw, self.match_change)):
							actions[(sw, self.match_change)].actions.append(of.ofp_action_output(port = outport))
						else:
							msg = self.__initmsg(self.match_change)
							msg.actions.append(of.ofp_action_output(port = outport))
							actions[(sw, self.match_change)] = msg
		# add encode node
		# now can only support one nc app on switch
		for (s, outport) in self.encode.keys():
			(code, pathids) = self.encode[(s, outport)]
			inports = self.pathtoaction[s][1][outport]
			for i in range(len(inports)):
				self.match_change.in_port = inports[i]
				# here packet_len buffer_sized can futher improved

				if actions.has_key((s, self.match_change)):
					actions[(s, self.match_change)].actions.append(nc.nc_action_encode( \
						buffer_id = 0, port_num = len(inports), \
						port_id = i, buffer_size = 512, output_port = outport,\
						packet_len = 1024, packet_num = len(inports), data = code))
				else:
					msg = self.__initmsg(self.match_change)
					msg.actions.append(nc.nc_action_encode( \
							buffer_id = 0, port_num = len(inports), \
							port_id = i, buffer_size = 512, output_port = outport,\
							packet_len = 1024, packet_num = len(inports), data = code))
					actions[(s, msg.match)] = msg

		# for decode
		for i in range(self.dst):
			dst = self.dst[i]
			inports = []
			for j in range(self.pathnum):
				link = self.path[(i, j)][-1]
				myinp = core.openflow_topology.link_to_port(link[1], link[0])
				self.match_change.in_port = myinp
				tmpoutport = dst[1]
				if actions.has_key((dst[0], self.match_change)):
					actions[(s, self.match_change)].actions.append(nc.nc_action_decode( \
						buffer_id = 0, packet_num = self.path_num, \
						output_port = tmpoutport, packet_len = 1024, \
						port_id = j, buffer_size = 512))
				else :
					msg = self.__initmsg(self.match_change)
					msg.actions.append(nc.nc_action_decode( \
						buffer_id = 0, packet_num = self.path_num, \
						output_port = tmpoutport, packet_len = 1024, \
						port_id = j, buffer_size = 512))
					actions[(s, msg.match)] = msg

		# for init 
		outports = []
		tmpmatrix = []
		for i in range(self.difflinks):
			link = self.difflinks[i]
			outports.append(link[1])
			tmpmatrix.append(self.NCvector[self.pathnum][i])
		msg = self.__initmsg(self.match)
		msg.match.in_port = self.src[0][1]
		msg.actions.append(nc.nc_action_init_coding( \
				vector_off = 0, buffer_id = 0 + (shift << 7), packet_num = self.path_num, \
				port_num = len(outports), packet_len = 1024, \
				port_id = outports, vector = tmpmatrix))
		if actions.has_key((self.src[0][0], msg.match)):
			print "canculate is wrong"
			raise Exception
		else:
			actions[(self.src[0][0], msg.match)] = msg
		
		return actions

class CanculateCode():
	def __init__(self, t, h = 2):
		self.h = h	# h means throughput
		self.t = t	# t means dst num
		self.this_file = inspect.getfile(inspect.currentframe())
		self.this_path = os.path.abspath(os.path.dirname(self.this_file))
		self.test = cdll.LoadLibrary(self.this_path + '/forcode/libgf256.so')
		self.test.initMulDivTab(self.this_path + '/forcode/muldiv.tab')
		self.B = {}
		self.xorflag = 1	#by default we think xor is fine
		for i in range(t):
			self.B[i] = {}
			for j in range(h):
				self.B[i][j] = [0 for x in range(h)]
				self.B[i][j][j] = 1
		self.a = deepcopy(self.B)
		self.topoorder = []
		self.needcode = []
		self.route = {}
		self.switches = {}
		self.code = {}
		self.START = 8888

	def DFS(self, u, color):
		color[u] = 1
		for k in self.switches[u].keys():
			if color[k] == 0: #this node is not visited
				if(not self.DFS(k, color)) :
					return False
			if color[k] == 1: #circle is find
				return False
		color[u] = 2
		self.topoorder.append(u)
		return True
		
	def topolinks(self, route, src):
		self.route = deepcopy(route)
		self.switches = {}
		for path in route.keys():
			tmp = self.START  # 8888 means init source
			for link in route[path] :
				if self.switches.has_key(link[0]):
					if self.switches[link[0]].has_key(link[1]):
						self.  switches[link[0]][link[1]].append((tmp, path))
					else :
						self.switches[link[0]][link[1]] = [(tmp, path)]
				else :
					self.switches[link[0]] = {}
					self.switches[link[0]][link[1]] = [(tmp, path)]
				tmp = link[0]
			if not self.switches.has_key(link[1]):
				self.switches[link[1]] = {}

		self.needcode = []
		for i in self.switches.keys():
			for outport in self.switches[i].keys():
				if len(self.switches[i][outport]) > 1:
					self.needcode.append((i,outport))

		# DFS canculate topo link
		self.topoorder = []
		self.src = src
		color = dict.fromkeys(self.switches.keys(), 0)
		if not self.DFS(src, color):
			return False
		self.topoorder.reverse()
		
		return True

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
	
	def getcode(self, pathnum):
		"""
		we do not handle init coding now
		"""
		# first we canculate whether init need code or not
		difflink = {}
		for path in self.route.keys():
			link = self.route[path][0]
			if not difflink.has_key(link):
				difflink[link] = [path]
			else :
				difflink[link].append(path)
		if len(difflink) > pathnum:
			return False

		# change route order so same start link path can be the same num
		startlinks = {}
		i = 0 
		for link in difflink.keys():
			startlinks[link] = i
			i = i + 1
		tmproute = {}
		for path in self.route.keys():
			link = self.route[path][0]
			tmproute[(path[0], startlinks[link])] = self.route[path]
		self.route = tmproute

		print 'topo order:' ,self.topoorder
		self.code = {}
		self.xorflag = 1
		for switch in self.topoorder:
			for (s, o) in self.needcode:
				if s == switch : #need to code
					# find weather infomation is different
					flag = 0
					i = -1
					xx = []
					for (tmp, path) in self.switches[s][o]:
						if i == -1:
							i = tmp
						else :
							if i != tmp:
								flag = 1  # need to code
						xx.append(tmp)
					if flag == 0 :	# this node no need to code
						self.needcode.remove((s, o))
					if flag == 1 :	 # start canculate code
						outputcode = [1 for x in range(len(self.switches[s][o]))]
						for i in range(len(self.switches[s][o])):
							outputcode[i] = random.randint(0, 255)
						iscodewrong = 1
						while iscodewrong :
							tmpb = [0 for x in range(self.h)]
							j = 0
							for (tmp, path) in self.switches[s][o]:
								# self.B[t][path_id]
								# self.a[t][path_id]
								tmpb = self.cMulvAdd(tmpb, self.B[path[0]][path[1]], self.h, outputcode[j])
								j = j + 1
							for (tmp, path) in self.switches[s][o]:
								e = self.mathmulti(tmpb, self.a[path[0]][path[1]], self.h)
								if e == 0 :
									iscodewrong = iscodewrong + 1
									# code is not right , get a new one
									for i in range(len(self.switches[s][o])):
										outputcode[i] = random.randint(0, 255)
									break

							
							if iscodewrong >= 2:
								print iscodewrong, outputcode
								self.xorflag = 0
								break

							# code is fine
							for (tmp, (x,y)) in self.switches[s][o]:
								self.B[x][y] = tmpb
								tmpa = deepcopy(self.a[x][y])
								self.cDiv(tmpa, self.h, self.mathmulti(tmpb, self.a[x][y], self.h))
								for z in range(self.h):
									tmpa1 = deepcopy(tmpa)
									self.cMul(tmpa1, self.h, self.mathmulti(tmpb, self.a[x][z], self.h))
									for u in range(self.h):
										self.a[x][z][u] = self.test.gfadd(self.a[x][z][u], tmpa1[u])
							# finish change and finish this round
							iscodewrong = 0
				
						self.code[(s, o)] = (outputcode, xx)
		self.forflow = {}
		for s in self.switches.keys():
			for port in self.switches[s].keys():
				if not self.code.has_key((s, port)):
					#this port do not need to code
					(inport, path) = self.switches[s][port][0]
					if self.forflow.has_key((s, inport)):
						self.forflow[(s, inport)].append(port)
					else :
						self.forflow[(s, inport)] = [port]
		return True
			
"""
for datapath canculate by Liu Sicheng
usage : x = LiuTopology()
		x.initByOpenFlowTopology(openflowtopo)
		x.initsrc(src)
		x.adddes([des1,....])
		x.getNCPath()  #this function will return nc if it can, otherwise it
					 #return just multicast
"""
class LiuTopology(object):
	def __init__(self):
		self.topo = {}
		self.des = []
		self.src = None
		self.route = {}
		self.ncflag = 0  # 0 indicate do not use NC

	def FindNeighbours (self, sw):
		sp = sw.ports
		sn = []
		for i in sp.keys():
			if len(sp[i].entities) != 0:
				for e in sp[i].entities:
					sn.append(e.dpid)
		return sn

	def printTopo(self):
		for i in self.topo.keys():
			print i , ' :', self.topo[i]
			
	def initByOpenFlowTopology(self, openflowtopo):
		"""
		change openflowtopo to our topo for more function
		"""
		sw = openflowtopo.getEntitiesOfType(Switch)
		for ss in sw:
			self.topo[ss.dpid] = self.FindNeighbours(ss)

	def initsrc(self, src):
		self.src = src

	def adddes(self, des):
		self.des.extend(des)

	def deldes(self, des):
		for i in des :
			self.des.remove(i)

	def delpath(self, path):
		for link in path:
			self.topo[link[0]].remove(link[1])
		return self.topo
	
	def addpath(self, path):
		for link in path:
			self.topo[link[0]].append(link[1])
		return self.topo

	def SPFA(self, src, des):
		queen = []
		queen.append(src)
		dist = {src:0}
		linklist = {}
		MAX_WEIGHT = 1023
		while len(queen) != 0:
			u = queen.pop(0)
			sn = self.topo[u]
			for adju in sn:
				if not dist.get(adju) :
					dist[adju] = MAX_WEIGHT
				tmp = dist[u] + 1  #here we think weight is always 1
				if dist[adju] > tmp :
					dist[adju] = tmp
					linklist[adju] = (u, adju)
					if adju not in queen :
						queen.append(adju)
		route = {}
		for nextdes in des :
			path = []
			route[nextdes] = path
			while nextdes != src :
				if linklist.has_key(nextdes):
					link = linklist[nextdes]
					path.append(link)
					nextdes = link[0]
				else :
					return None 
			path.reverse()
		return route

	def getNCPath(self, pathnum):
		i = 0
		flag = 1
		for dst in self.des:
			path = []
			for j in range(pathnum):
				tmppath = self.SPFA(self.src, [dst])
				if tmppath == None :
					flag = 0
					break
				self.route[(i, j)] = tmppath[dst]
				self.delpath(tmppath[dst])
				path.append(tmppath[dst])
			for p in path:
				self.addpath(p)
			if not flag:
				break
			i = i + 1
		
		if not flag :
			self.route = self.SPFA(self.src, self.des)

		self.ncflag = flag

class NCMultiPath (object):
	def __init__(self, openflowtopo, src, dst, path_num = 2):
		self.topo = LiuTopology()
		self.topo.initByOpenFlowTopology(openflowtopo)
		self.topo.initsrc(src[0][0])
		for i in dst:
			self.topo.adddes([i[0]])
		self.src = src[0]
		self.dst = dst
		self.path_num = path_num
		self.code = CanculateCode(len(dst), path_num)
		self.realtopo = openflowtopo

	def findportid(self, openflowtopo, src, dst):
		s1 = openflowtopo.getEntityByID(src)
		s2 = openflowtopo.getEntityByID(dst)
		port0 = 0
		port1 = 0
		for port in s1.ports:
			if s2 in s1.ports[port].entities:
				port0 = port
		for port in s2.ports:
			if s1 in s2.ports[port].entities:
				port1 = port
		return (port0, port1)

	def initmsg(self, match, inport):
		msg = of.ofp_flow_mod()
		msg.idle_timeout = 120
		msg.hard_timeout = 120
		# first we test no port num
		if match :
			msg.match.dl_type = match.dl_type
			msg.match.dl_src = match.dl_src
			msg.match.dl_dst = match.dl_dst
			msg.match.nw_src = match.nw_src
			msg.match.nw_dst = match.nw_dst
		msg.match.in_port = inport
		return msg

	def printaction(self, obj):
		for i in obj.__dict__.keys():
			print i, ":", obj.__dict__[i]

	def installactions(self, match, shift):
		actions = {} # it contains the msg it will send, use the (switch, match) : msg
		for (s, inport) in self.code.forflow.keys():
			tmpports = []
			if inport != self.code.START and len(self.code.forflow[(s, inport)]):
				#add normal output
				(outp, myinp) = self.findportid(self.realtopo, inport, s)
				for outs in self.code.forflow[(s, inport)]:
					(outp, inp) = self.findportid(self.realtopo, s, outs)
					tmpports.append(outp)
				msg = self.initmsg(match, myinp)
				msg.match.nw_proto = 200 + shift
				if actions.has_key((s, msg.match)):
					for i in tmpports:
						actions[(s, msg.match)].actions.append(of.ofp_action_output(port = i))
				else :
					for i in tmpports:
						msg.actions.append(of.ofp_action_output(port = i))
					actions[(s, msg.match)] = msg
		"""
		# for test forwarding
		for (s, inport) in self.code.forflow.keys():
			if inport == self.code.START:
				tmpports = []
				for outs in self.code.forflow[(s, inport)]:
					(myoutp, inp) = self.findportid(self.realtopo, s, outs)
					tmpports.append(myoutp)
				msg = self.initmsg(match, self.src[1])
				for i in tmpports:
				   msg.actions.append(of.ofp_action_output(port = i))
				#send the msg to switch
				switch = self.realtopo.getEntityByID(s)
				switch._connection.send(msg)
		"""
		#add encode node
		# now can only support one nc app on switch
		tmpcode = self.code.code
		for (s, outport) in tmpcode.keys():
			(code, inports) = tmpcode[(s, outport)]
			i = 0
			pnum = len(inports)
			for p in inports:
				(outp, myinp) = self.findportid(self.realtopo, p, s)
				(myoutp, inp) = self.findportid(self.realtopo, s, outport)
				msg = self.initmsg(match, myinp)
				msg.match.nw_proto = 200 + shift
				# here packet_len buffer_size can futher improve
				msg.actions.append(nc.nc_action_encode( \
						buffer_id = 0, port_num = pnum, \
						port_id = i, buffer_size = 512, output_port = myoutp,\
						packet_len = 1024, packet_num = pnum, data = code))
				
				if actions.has_key((s, msg.match)):
					print "canculate is wrong!"
				else :
					actions[(s, msg.match)] = msg
				i = i + 1

		#add decode node
		decode_portid = {}
		for i in range(len(self.dst)):
			decode_portid[i] = 0
		for path in self.code.route.keys():
			link = self.code.route[path][-1]
			(outp, myinp) = self.findportid(self.realtopo, link[0], link[1])
			msg = self.initmsg(match, myinp)
			msg.match.nw_proto = 200 + shift
			tmpoutport = self.dst[path[0]][1]
			tmpport_id = decode_portid[path[0]]
			#save actions
			s = link[1]
			if actions.has_key((s, msg.match)):
				actions[(s, msg.match)].actions.append(nc.nc_action_decode( \
					buffer_id = 0, packet_num = self.path_num, \
					output_port = tmpoutport, packet_len = 1024, \
					port_id = tmpport_id, buffer_size = 512))
			else :
				msg.actions.append(nc.nc_action_decode( \
					buffer_id = 0, packet_num = self.path_num, \
					output_port = tmpoutport, packet_len = 1024, \
					port_id = tmpport_id, buffer_size = 512))
				actions[(s, msg.match)] = msg
			decode_portid[path[0]] = decode_portid[path[0]] + 1
			"""
			actions[(s, msg.match)] = msg
			"""
		#add init node
		for (s, inport) in self.code.forflow.keys():
			if inport == self.code.START:
				outport_id = []
				for p in self.code.forflow[(s, inport)]:
					(myoutp, inp) = self.findportid(self.realtopo, s, p)
					outport_id.append(myoutp)
				myvector = []
				for i in range(len(outport_id)):
					tmpv = [0] * self.path_num
					tmpv[i] = 1
					myvector.append(tmpv)
				msg = self.initmsg(match, self.src[1])
				msg.actions.append(nc.nc_action_init_coding( \
						vector_off = 0, buffer_id = 0 + (shift << 7), packet_num = self.path_num, \
						port_num = len(outport_id), packet_len = 1024, \
						port_id = outport_id, vector = myvector))
				if actions.has_key((s, msg.match)):
					print "canculate is wrong!"
				else :
					actions[(s, msg.match)] = msg 
				
		#install actions:
		# first install not src node actions
		for (s, match) in actions.keys():
			if s != self.src[0]:
				switch = self.realtopo.getEntityByID(s)
				switch._connection.send(actions[(s, match)])

		for (s, match) in actions.keys():
			if s == self.src[0]:
				switch = self.realtopo.getEntityByID(s)
				switch._connection.send(actions[(s, match)])

		#print actions
		"""
		"""

		return 

	def getcode(self, match, shift):
		self.topo.getNCPath(self.path_num)
		#print 'route is :', self.topo.route
		if self.topo.ncflag:
			if self.code.topolinks(self.topo.route, self.topo.src):
				#this means there is no circle on links
				if not self.code.getcode(self.path_num):
					#here means need init code, now we donot support that
					return False
				self.installactions(match, shift)
				return True
		# have circle or do not have path_num disjoint path on at least one of the s,d pairs
		return False 

class WdyMultiTree (OpenFlowTopology):
	def __init__ (self, src=[], dst=[], match=None, shift = 0):
		OpenFlowTopology.__init__(self)
		# source value: int
		self.wdySrcSwitch = src
		# dst value: int
		self.wdyDstSwitch = dst
		if len(src) != 0:
			if self.wdyDstSwitch.count((src[0])) != 0:
				self.wdyDstSwitch = list(set(self.wdyDstSwitch)-set(self.wdySrcSwitch))
		print self.wdySrcSwitch
		print self.wdyDstSwitch
		# links value: tuple (v1, v2)
		self.wdyLinks = []
		# dpids value: int
		self.wdyDpids = []
		# routes key: int (dst)
		# routes value: list of tuple [(src, vi), ... (vi,dst),]
		self.wdyRoutes = {}
		self.wdyFlows = []
		self.wdySwitchFlows = []
		self.isNC = 0
		if self.wdyIsCorrect():
			# here we set 224.0.0.0/24 to be NC multicast group
			# and other multicast address will use shortest path
			if match.nw_dst.inNetwork("224.0.0.0/24"):
				self.ncpath = NCMultiPath(self.topology, src, dst, 2)
				if self.ncpath.getcode(match, shift):
				#if 0:
					print 'route', self.ncpath.code.route
					print 'switches', self.ncpath.code.switches
					print 'output: ', self.ncpath.code.forflow
					print 'needcode : ', self.ncpath.code.needcode
					print 'code is : ', self.ncpath.code.code
					self.isNC = 1
					return 
				else :
					self.wdyMultiTree()
					print "route is :",self.wdyRoutes
					self.wdyInstallFlowForTree(match=match)
					self.isNC = 0
			else :
				self.wdyMultiTree()
				print "route is :", self.wdyRoutes
				self.wdyInstallFlowForTree(match=match)
				self.isNC = 0
		"""
		if self.wdyIsCorrect():
			self.wdyMultiTree()
			print "route is :", self.wdyRoutes
			self.wdyInstallFlowForTree(match=match)
			self.isNC = 0
		""" 
		return 

	def wdyIsCorrect (self):
		if len(self.wdySrcSwitch) != 0 and len(self.wdyDstSwitch) != 0:
			sw = self.topology.getEntityByID(self.wdySrcSwitch[0][0])
			if len(sw.ports[self.wdySrcSwitch[0][1]].entities) == 0:
				return True
		return False

	def wdyFindNeighbours (self, dpid):
		sw = self.topology.getEntityByID(dpid)
		if sw is None: return
		sp = sw.ports
		sn = []
		for i in sp.keys():
			if len(sp[i].entities) != 0:
				for e in sp[i].entities:
					sn.append(e.dpid)
		return sn
	
	def wdyIsExistDegree1 (self, dpid):
		for i in range(len(dpid)):
			if dpid.count(dpid[i]) == 1:
				return True
		return False

	def wdyIsLoop (self, links):
		if len(links) == 0:
			return False
		dpid = []
		for l in links:
			dpid.append(l[0])
			dpid.append(l[1])
		while self.wdyIsExistDegree1(dpid):
			for i in range(len(dpid)):
				if i >= len(dpid): break
				if dpid.count(dpid[i]) == 1:
					if i%2 == 0:
						del dpid[i+1]
						del dpid[i]
					else:
						del dpid[i]
						del dpid[i-1]
		if len(dpid) == 0:
			return False
		return True


	def wdyMultiTree (self):
		"""
		queen = []
		queen.append(self.wdySrcSwitch[0][0])
		while len(queen) != 0:
			s = queen.pop(0)
			sn = self.wdyFindNeighbours(s)
			for sdst in sn:
				if sdst not in self.wdyDpids and sdst not in queen:
					link = (s, sdst)
					if not self.wdyIsLoop(self.wdyLinks) and link not in self.wdyLinks:
						self.wdyLinks.append(link)
						queen.append(sdst)
			self.wdyDpids.append(s)
		for dst in self.wdyDstSwitch:
			self.wdyRoutes[dst[0]] = self.wdyFindTreeRoute (self.wdySrcSwitch[0][0], dst[0])
		"""
		liutopo = LiuTopology()
		liutopo.initByOpenFlowTopology(self.topology)
		mydst = []
		for i in self.wdyDstSwitch :
				mydst.append(i[0])
		self.wdyRoutes = liutopo.SPFA(self.wdySrcSwitch[0][0], mydst)

	def wdyFindTreeRoute (self, src, dst):
		route = []
		nextdst = dst
		while nextdst != src:
			for link in self.wdyLinks:
				if nextdst == link[1]:
					route.append(link)
					nextdst = link[0]
		route.reverse()
		return route
	def wdyInstallFlowForSwitch (self, switchPort, match=None):
		# log.info("Installing flow")
		msg = of.ofp_flow_mod()
		msg.idle_timeout = 120
		msg.hard_timeout = 120
		if match is None:
			msg.match.in_port = switchPort[0]
		else:
			msg.match = match
			msg.match.in_port = switchPort[0]
		# if switchPort[1] in self.wdyDstSwitch:
		#	msg.actions.append(of.ofp_action_dl_addr.set_dst(EthAddr('ff:ff:ff:ff:ff:ff')))
		for i in range(2, len(switchPort)):
			msg.actions.append(of.ofp_action_output(port = switchPort[i]))
		s = self.topology.getEntityByID(switchPort[1])
		# if s is not None:
		s._connection.send(msg)
		#print s,"; msg match:", match
		
	def wdyCreateSwitchFlows (self, match=None):
		flow1 = []
		def wdyInFlows (flow):
			for i in range(len(self.wdySwitchFlows)):
				if flow[0] == self.wdySwitchFlows[i][0] and flow[1] == self.wdySwitchFlows[i][1]:
					self.wdySwitchFlows[i].append(flow[2])
					return True
			return False
		for flow in self.wdyFlows:
			flow1.append(flow[1])
		flow1 = list(set(flow1))
		flow1.sort()
		for i in range(len(flow1)):
			for flow in self.wdyFlows:
				if flow1[i] == flow[1]:
					if not wdyInFlows(flow):
						self.wdySwitchFlows.append(flow)
		print "switchFlows: ", self.wdySwitchFlows
		for flow in self.wdySwitchFlows:
			self.wdyInstallFlowForSwitch(flow, match=match)

	def wdyInstallFlowForRoute (self, route):
		if len(route) == 0:
			switchPort = [self.wdySrcSwitch[0][1], self.wdySrcSwitch[0][0], self.wdyDstSwitch[0][1]]
			if switchPort not in self.wdyFlows:
				self.wdyFlows.append(switchPort)
			return

		routePort = []
		for link in route:
			s1 = self.topology.getEntityByID(link[0])
			s2 = self.topology.getEntityByID(link[1])
			port0 = 0
			port1 = 0
			for port in s1.ports:
				if s2 in s1.ports[port].entities:
					port0 = port
			for port in s2.ports:
				if s1 in s2.ports[port].entities:
					port1 = port
			routePort.append((link[0], port0, link[1], port1))
		for i in range(len(routePort)-1):
			switchPort = [routePort[i][3], routePort[i][2], routePort[i+1][1]]
			if switchPort not in self.wdyFlows:
				self.wdyFlows.append(switchPort)
			# switchPortReverse = [switchPort[2], switchPort[1], switchPort[0]] 
			# self.wdyFlows.append(switchPortReverse)
		# ssrc = self.topology.getEntityByID(route[0][0])
		# log.info("ssrc is %s", ssrc)
		# sdst = self.topology.getEntityByID(route[-1][1])
		# log.info("sdst is %s", sdst)
		# srcswitch
		port = self.wdySrcSwitch[0][1]
		switchPort = [port, route[0][0], routePort[0][1]]
		if switchPort not in self.wdyFlows:
			self.wdyFlows.append(switchPort)
		# switchPortReverse = [switchPort[2], switchPort[1], switchPort[0]] 
		# self.wdyFlows.append(switchPortReverse)
		# dstswitch
		for switch in self.wdyDstSwitch:
			if switch[0] == route[-1][1]:
				port = switch[1]
				switchPort = [routePort[-1][3], route[-1][1], port]
				if switchPort not in self.wdyFlows:
					self.wdyFlows.append(switchPort)
				# switchPortReverse = [switchPort[2], switchPort[1], switchPort[0]] 
				# self.wdyFlows.append(switchPortReverse)



	def wdyInstallFlowForTree (self, routes=None, match=None):
		if routes == None:
			routes = self.wdyRoutes
		for dst in routes.keys():
			route = routes[dst]
			self.wdyInstallFlowForRoute(route)
		self.wdyCreateSwitchFlows(match=match)


class OpenFlowPort (Port):
	"""
	A subclass of topology.Port for OpenFlow switch ports.
	
	Adds the notion of "connected entities", which the default
	ofp_phy_port class does not have.

	Note: Not presently used.
	"""
	def __init__ (self, ofp):
		# Passed an ofp_phy_port
		Port.__init__(self, ofp.port_no, ofp.hw_addr, ofp.name)
		self.isController = self.number == of.OFPP_CONTROLLER
		self._update(ofp)
		self.exists = True
		self.entities = set()

	def _update (self, ofp):
		assert self.name == ofp.name
		assert self.number == ofp.port_no
		self.hwAddr = EthAddr(ofp.hw_addr)
		self._config = ofp.config
		self._state = ofp.state

	def __contains__ (self, item):
		""" True if this port connects to the specified entity """
		return item in self.entities

	def addEntity (self, entity, single = False):
		# Invariant (not currently enforced?): 
		#	 len(self.entities) <= 2	?
		if single:
			self.entities = set([entity])
		else:
			self.entities.add(entity)

	def to_ofp_phy_port(self):
		return of.ofp_phy_port(port_no = self.number, hw_addr = self.hwAddr,
					name = self.name, config = self._config, 
					state = self._state)

	def __repr__ (self):
		return "<Port #" + str(self.number) + ">"


class OpenFlowSwitch (EventMixin, Switch):
	"""
	OpenFlowSwitches are Topology entities (inheriting from topology.Switch)
	
	OpenFlowSwitches are persistent; that is, if a switch reconnects, the
	Connection field of the original OpenFlowSwitch object will simply be
	reset to refer to the new connection.
	
	For now, OpenFlowSwitch is primarily a proxy to its underlying connection
	object. Later, we'll possibly add more explicit operations the client can
	perform.
	
	Note that for the purposes of the debugger, we can interpose on
	a switch entity by enumerating all listeners for the events listed
	below, and triggering mock events for those listeners.
	"""
	_eventMixin_events = set([
		SwitchJoin, # Defined in pox.topology
		SwitchLeave,
		SwitchConnectionUp,
		SwitchConnectionDown,

		PortStatus, # Defined in libopenflow_01
		FlowRemoved,
		PacketIn,
		BarrierIn,
	])

	def __init__ (self, dpid):
		if not dpid:
			raise AssertionError("OpenFlowSwitch should have dpid")

		Switch.__init__(self, id=dpid)
		EventMixin.__init__(self)
		self.dpid = dpid
		self.ports = {}
		self.flow_table = OFSyncFlowTable(self)
		self.capabilities = 0
		self._connection = None
		self._listeners = []
		self._reconnectTimeout = None # Timer for reconnection
		self._xid_generator = xid_generator( ((dpid & 0x7FFF) << 16) + 1)

	def _setConnection (self, connection, ofp=None):
		''' ofp - a FeaturesReply message '''
		if self._connection: self._connection.removeListeners(self._listeners)
		self._listeners = []
		self._connection = connection
		if self._reconnectTimeout is not None:
			self._reconnectTimeout.cancel()
			self._reconnectTimeout = None
		if connection is None:
			self._reconnectTimeout = Timer(RECONNECT_TIMEOUT,
						self._timer_ReconnectTimeout)
		if ofp is not None:
			# update capabilities
			self.capabilities = ofp.capabilities
			# update all ports 
			untouched = set(self.ports.keys())
			for p in ofp.ports:
				if p.port_no in self.ports:
					self.ports[p.port_no]._update(p)
					untouched.remove(p.port_no)
				else:
					self.ports[p.port_no] = OpenFlowPort(p)
			for p in untouched:
				self.ports[p].exists = False
				del self.ports[p]
		if connection is not None:
			self._listeners = self.listenTo(connection, prefix="con")
			self.raiseEvent(SwitchConnectionUp(switch = self,
						connection = connection))
		else:
			self.raiseEvent(SwitchConnectionDown(self))


	def _timer_ReconnectTimeout (self):
		""" Called if we've been disconnected for RECONNECT_TIMEOUT seconds """
		self._reconnectTimeout = None
		core.topology.removeEntity(self)
		self.raiseEvent(SwitchLeave, self)

	def _handle_con_PortStatus (self, event):
		p = event.ofp.desc
		if event.ofp.reason == of.OFPPR_DELETE:
			if p.port_no in self.ports:
				self.ports[p.port_no].exists = False
				del self.ports[p.port_no]
		elif event.ofp.reason == of.OFPPR_MODIFY:
			self.ports[p.port_no]._update(p)
		else:
			assert event.ofp.reason == of.OFPPR_ADD
			assert p.port_no not in self.ports
			self.ports[p.port_no] = OpenFlowPort(p)
		self.raiseEvent(event)
		event.halt = False

	def _handle_con_ConnectionDown (self, event):
		self._setConnection(None)
	"""
	def _handle_con_PacketIn (self, event):
		# log.info("---wdy---OpenFlowSwitch._handle_con_PacketIn")
		self.raiseEvent(event)
		event.halt = False
		packet = event.parsed
		if not packet.parsed:
			log.warning("Ignoring incomplete packet")
			return
		packet_in = event.ofp
		log.info(packet.type)
	"""
	def _handle_con_BarrierIn (self, event):
		self.raiseEvent(event)
		event.halt = False

	def _handle_con_FlowRemoved (self, event):
		self.raiseEvent(event)
		self.flowTable.removeFlow(event)
		event.halt = False

	def findPortForEntity (self, entity):
		for p in self.ports.itervalues():
			if entity in p:
				return p
		return None

	@property
	def connected(self):
		return self._connection != None

	def installFlow(self, **kw):
		""" install flow in the local table and the associated switch """
		self.flow_table.install(TableEntry(**kw))

	def serialize (self):
		# Skip over non-serializable data, e.g. sockets
		serializable = OpenFlowSwitch(self.dpid)
		return pickle.dumps(serializable, protocol = 0)

	def send(self, *args, **kw):
		return self._connection.send(*args, **kw)

	def read(self, *args, **kw):
	 return self._connection.read(*args, **kw)

	def __repr__ (self):
		return "<%s %s>" % (self.__class__.__name__, dpidToStr(self.dpid))

	@property
	def name(self):
		return repr(self)


class OFSyncFlowTable (EventMixin):
	_eventMixin_events = set([FlowTableModification])
	"""
	A flow table that keeps in sync with a switch
	"""
	ADD = of.OFPFC_ADD
	REMOVE = of.OFPFC_DELETE
	REMOVE_STRICT = of.OFPFC_DELETE_STRICT
	TIME_OUT = 2

	def __init__ (self, switch=None, **kw):
		EventMixin.__init__(self)
		self.flow_table = FlowTable()
		self.switch = switch

		# a list of pending flow table entries : tuples (ADD|REMOVE, entry)
		self._pending = []

		# a map of pending barriers barrier_xid-> ([entry1,entry2])
		self._pending_barrier_to_ops = {}
		# a map of pending barriers per request entry -> (barrier_xid, time)
		self._pending_op_to_barrier = {}

		self.listenTo(switch)

	def install (self, entries=[]):
		"""
		asynchronously install entries in the flow table
		
		will raise a FlowTableModification event when the change has been
		processed by the switch
		"""
		self._mod(entries, OFSyncFlowTable.ADD)

	def remove_with_wildcards (self, entries=[]):
		"""
		asynchronously remove entries in the flow table
		
		will raise a FlowTableModification event when the change has been
		processed by the switch
		"""
		self._mod(entries, OFSyncFlowTable.REMOVE)

	def remove_strict (self, entries=[]):
		"""
		asynchronously remove entries in the flow table.
		
		will raise a FlowTableModification event when the change has been
		processed by the switch
		"""
		self._mod(entries, OFSyncFlowTable.REMOVE_STRICT)

	@property
	def entries (self):
		return self.flow_table.entries

	@property
	def num_pending (self):
		return len(self._pending)

	def __len__ (self):
		return len(self.flow_table)

	def _mod (self, entries, command):
		if isinstance(entries, TableEntry):
			entries = [ entries ]

		for entry in entries:
			if(command == OFSyncFlowTable.REMOVE):
				self._pending = [(cmd,pentry) for cmd,pentry in self._pending
						if not (cmd == OFSyncFlowTable.ADD
						and entry.matches_with_wildcards(pentry))]
			elif(command == OFSyncFlowTable.REMOVE_STRICT):
				self._pending = [(cmd,pentry) for cmd,pentry in self._pending
						if not (cmd == OFSyncFlowTable.ADD
						and entry == pentry)]

			self._pending.append( (command, entry) )

		self._sync_pending()

	def _sync_pending (self, clear=False):
		if not self.switch.connected:
			return False

		# resync the switch
		if clear:
			self._pending_barrier_to_ops = {}
			self._pending_op_to_barrier = {}
			self._pending = filter(lambda(op): op[0] == OFSyncFlowTable.ADD,
						self._pending)

			self.switch.send(of.ofp_flow_mod(command=of.OFPFC_DELETE,
						match=of.ofp_match()))
			self.switch.send(of.ofp_barrier_request())

			todo = map(lambda(e): (OFSyncFlowTable.ADD, e),
						self.flow_table.entries) + self._pending
		else:
			todo = [op for op in self._pending
						if op not in self._pending_op_to_barrier
						or (self._pending_op_to_barrier[op][1]
						+ OFSyncFlowTable.TIME_OUT) < time.time() ]

		for op in todo:
			fmod_xid = self.switch._xid_generator()
			flow_mod = op[1].to_flow_mod(xid=fmod_xid, command=op[0],
						flags=op[1].flags | of.OFPFF_SEND_FLOW_REM)
			self.switch.send(flow_mod)

		barrier_xid = self.switch._xid_generator()
		self.switch.send(of.ofp_barrier_request(xid=barrier_xid))
		now = time.time()
		self._pending_barrier_to_ops[barrier_xid] = todo

		for op in todo:
			self._pending_op_to_barrier[op] = (barrier_xid, now)

	def _handle_SwitchConnectionUp (self, event):
		# sync all_flows
		self._sync_pending(clear=True)

	def _handle_SwitchConnectionDown (self, event):
		# connection down. too bad for our unconfirmed entries
		self._pending_barrier_to_ops = {}
		self._pending_op_to_barrier = {}

	def _handle_BarrierIn (self, barrier):
		# yeah. barrier in. time to sync some of these flows
		if barrier.xid in self._pending_barrier_to_ops:
			added = []
			removed = []
			#print "barrier in: pending for barrier: %d: %s" % (barrier.xid,
			#		self._pending_barrier_to_ops[barrier.xid])
			for op in self._pending_barrier_to_ops[barrier.xid]:
				(command, entry) = op
				if(command == OFSyncFlowTable.ADD):
					self.flow_table.add_entry(entry)
					added.append(entry)
				else:
					removed.extend(self.flow_table.remove_matching_entries(entry.match,
							entry.priority, strict=command == OFSyncFlowTable.REMOVE_STRICT))
				#print "op: %s, pending: %s" % (op, self._pending)
				if op in self._pending: self._pending.remove(op)
				self._pending_op_to_barrier.pop(op, None)
			del self._pending_barrier_to_ops[barrier.xid]
			self.raiseEvent(FlowTableModification(added = added, removed=removed))
			return EventHalt
		else:
			return EventContinue

	def _handle_FlowRemoved (self, event):
		"""
		process a flow removed event -- remove the matching flow from the table.
		"""
		flow_removed = event.ofp
		for entry in self.flow_table.entries:
			if (flow_removed.match == entry.match
					and flow_removed.priority == entry.priority):
				self.flow_table.remove_entry(entry)
				self.raiseEvent(FlowTableModification(removed=[entry]))
				return EventHalt
		return EventContinue


def launch ():
	if not core.hasComponent("openflow_topology"):
		topo = OpenFlowTopology_Improve1()
		core.register("openflow_topology", topo)
		print "install OpenFlowTopology_Improve1!"
