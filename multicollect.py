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
An L2 learning switch.

It is derived from one written live for an SDN crash course.
It is somwhat similar to NOX's pyswitch in that it installs
exact-match rules for each flow.
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from pox.lib.util import str_to_bool
from multicast_route import *
from pox.lib.packet import arp, ipv4, igmp
from pox.lib.packet.ethernet import ethernet
from pox.lib.addresses import IPAddr, EthAddr
from pox.host_tracker import *
import time

log = core.getLogger()

# We don't want to flood immediately when a switch connects.
# Can be overriden on commandline.
_flood_delay = 0

class FlowInfo(object):
	_core_name = "flow_info"
	# here we assume two mac addr cannot have two flows
	def __init__(self, debug = 1):
		self.flows = {}
		self.all_flows = {}
		self.debug = debug
	
	def add_flows(self, match, method):
		if self.debug:
			log.debug("add flow :" + str(match.dl_src) + ">>" + str(match.dl_dst))
			"""
			try :
				(method1, create_time) = self.flows[match]
				print "have this flow already ***" + str(create_time) + "::" + str(time.time())
				print match
				print method1
				print method
			except:
				pass
			"""
			#log.debug(method[1])
		self.flows[match] = (method, time.time())
		self.all_flows[match] = method
	
	def find_flows(self, match):
		try:
			(method, create_time) = self.flows[match]
			if create_time + 2 >= time.time():
				return (method,0)
			else:
				return (method,1)
		except:
			return (None,2)
	
	def del_flows(self, match):
		#print "flows:"
		#print self.flows.keys()
		self.flows.pop(match)
		if self.debug:
			log.debug("del flow :" + str(match.dl_src) + ">>" + str(match.dl_dst))

class GroupInfo (object):
	_core_name = "group_info"
	def __init__(self, debug = 1):
		self.groups = {}
		#self.groupmethod = {}
		self.debug = debug

	# return True means group info has changed
	def insert_in_group(self, group_ip, dpid, port):
		if group_ip not in self.groups.keys():
			self.groups[group_ip] = [[(dpid, port)], 0]
		else :
			[groupPort, g_id] = self.groups[group_ip]
			if (dpid, port) not in groupPort:
				groupPort.append((dpid, port))
				self.groups[group_ip][1] = g_id + 1
			else :
				# the dpid and port is already in the group
				return False
		if self.debug:
			print self.groups
		return True

	# return True means group info has changeed
	def del_in_group(self, group_ip, dpid, port):
		if group_ip in self.groups.keys():
			[groupPort, g_id] = self.groups[group_ip]
			if (dpid, port) in groupPort:
				groupPort.remove((dpid, port))
				self.groups[group_ip][1] = g_id + 1
				if self.debug:
					print self.groups
				return True
		return False

	# return (dst, bool), 
	# if len(dst) == 0 means there is no such group_ip
	# if bool is 0 means the path canculate is newest
	def has_in_group(self, group_ip):
		dst = []
		if group_ip in self.groups.keys():
			[dst, g_id] = self.groups[group_ip]
		return dst
	"""
	def has_in_group(self, group_ip):
		dst = []
		if group_ip in self.groups.keys():
			[dst, g_id] = self.groups[group_ip]
			if self.groupmethod.has_key(group_ip):
				(cg_id, installtime,Mtree) = self.groupmethod[group_ip]
				if cg_id == g_id :
					if installtime + 2 > time.time() :
						return (dst, 0)
					else :
						# here means timeout is happened but topo do not change
						return (dst, 2)
		return (dst, 1)

	def update_method(self, group_ip, method):
		[groupPort, g_id] = self.groups[group_ip]
		self.groupmethod[group_ip] = (g_id, time.time(),method)

	def removed_method(self, group_ip):
		self.groupmethod.pop(group_ip)
		
	# return (flag, method)
	# if flag = 0, method = null
	def get_method(self, group_ip):
		if self.groupmethod.has_key(group_ip):
			return (1,self.groupmethod[group_ip][2])
		else :
			return	(0,None)
	"""
	def get_g_id(self, group_ip):
		[groupPort, g_id] = self.groups[group_ip]
		return g_id

def extract_match(tmp):
	match = of.ofp_match()
	match.dl_type = tmp.dl_type
	match.dl_src = tmp.dl_src
	match.dl_dst = tmp.dl_dst
	match.nw_src = tmp.nw_src
	match.nw_dst = tmp.nw_dst
	match.nw_proto = tmp.nw_proto
	match.tp_src = tmp.tp_src
	match.tp_dst = tmp.tp_dst
	return match

IP_NC_MULTICAST_BOTTOM = IPAddr("224.1.0.0").toUnsigned()
IP_NC_MULTICAST_TOP = IPAddr("224.1.255.255").toUnsigned()

class LearningSwitch (object):
	def __init__ (self, connection, transparent):
		# Switch we'll be adding L2 learning switch capabilities to
		self.connection = connection
		self.transparent = transparent

		# Our table
		self.macToPort = {}

		# We want to hear PacketIn messages, so we listen
		# to the connection
		connection.addListeners(self)

		# We just use this to know when to log a helpful message
		self.hold_down_expired = _flood_delay == 0

		#log.debug("Initializing LearningSwitch, transparent=%s",
		#str(self.transparent))
	
	def _handle_FlowRemoved (self, event):
		# now only nc_init can have this
		flow_removed = event.ofp
		mac_dst = flow_removed.match.dl_dst
		#print "flow_removed.match"  + str(flow_removed.match)
		match = extract_match(flow_removed.match)

		# here deal with buffer reuse
		if mac_dst.is_multicast:
			try:
				dst = flow_removed.match.nw_dst
			except:
				raise Exception
			(tree,flag) = core.flow_info.find_flows(match)
			if flag == 2:
				raise Exception
			else:
				#print tree[0]['used_buffer']
				if 'used_buffer' in tree[0].keys():
					# this is nc and use buffers
					for k in tree[0]['used_buffer'].keys():
						for i in tree[0]['used_buffer'][k]:
							core.openflow_topology.return_Buffer(k,i)
		# here delete flow info
		core.flow_info.del_flows(match)

	def _handle_PacketIn (self, event):
		"""
		Handle packet in messages from the switch to implement above algorithm.
		"""

		packet = event.parsed

		def wdyHandleMulticast ():
			dpid = event.dpid
			port = event.port
			#src = (dpid, port)
			# in order to deal with flow remove in the middle of the transmission
			macentry = core.host_tracker.getMacEntry(packet.src) # 4
			if macentry == None:
				log.warning("donot track this src %s",packet.src)
				raise Exception
			mmsrc = (macentry.dpid, macentry.port)
			ip_packet = packet.payload
			if ip_packet.dstip == "224.224.224.224":
				#log.info("get a packet!")
				log.debug("get statistic from host(%i,%i):"+ str(ip_packet.payload.payload),dpid,port)
				#log.debug("get statistic from host(%i,%i):%s",dpid,port,ip_packet.payload)
				drop()
				return
			dst = core.group_info.has_in_group(ip_packet.dstip)
			match = extract_match(of.ofp_match.from_packet(packet))
			(tree, flag) = core.flow_info.find_flows(match)
			if flag == 0 :
				# this means route canculate is no need to change just follow it
				# but we need handle this packet
				try:
					#print tree[1]
					msg = tree[1][(dpid, event.port)]
				except:
					raise Exception
				newmsg = of.ofp_packet_out()
				newmsg.data = event.ofp
				newmsg.in_port = event.port
				newmsg.actions = msg.actions
				s = ''
				for a in msg.actions:
					s += str(a)
				log.debug("get a packet no need to canculate!"+ s)
				self.connection.send(newmsg)
				"""
				drop()
				"""
				return 
			if len(dst) is 0:
				log.info("group is none")
				return
			kkk = ip_packet.dstip.toUnsigned()
			#print "top,bottom:"+str(IP_NC_MULTICAST_TOP)+","+str(IP_NC_MULTICAST_BOTTOM)
			#print "kkk:"+str(kkk)
			if kkk >= IP_NC_MULTICAST_BOTTOM and kkk <= IP_NC_MULTICAST_TOP:
				multicast_method = Static_NC_Multicast
				#print "use NC"
			else:
				multicast_method = Dijikstra_Normal_Multicast
			#match = of.ofp_match.from_packet(packet, event.port)
			#shift = core.group_info.get_g_id(ip_packet.dstip) % 2
			multicast_method.multicast_Plan(mmsrc, dst, event, None)
			tree = multicast_method.get_Results()
			core.flow_info.add_flows(match, tree)

		def wdyHandleIGMP ():
			ip_packet = packet.payload
			igmp_packet = ip_packet.payload
			hddst = packet.dst
			hdsrc = packet.src
			ipsrc = ip_packet.srcip
			ipdst = ip_packet.dstip
			dpid = event.dpid
			port = event.port
			#print "get IGMP packet at " + str(dpid) + "," + str(port)
			grouphaschange = 0
			# new function instead of the upper 
			for i in range(igmp_packet.num_records):
				groupAddr = igmp_packet.grs[i][4]
				# if it is group menber announcement
				if igmp_packet.grs[0][1] == 4:
					grouphaschange = core.group_info.insert_in_group(groupAddr, dpid, port)
				elif igmp_packet.grs[0][1] == 3:
					grouphaschange = core.group_info.del_in_group(groupAddr, dpid, port)
			drop()
			# require changes on dealing with grouphaschange
			# need add functions




		def flood (message = None):
			""" Floods the packet """
			msg = of.ofp_packet_out()
			if time.time() - self.connection.connect_time >= _flood_delay:
				# Only flood if we've been connected for a little while...

				if self.hold_down_expired is False:
					# Oh yes it is!
					self.hold_down_expired = True
					log.info("%s: Flood hold-down expired -- flooding",
							dpid_to_str(event.dpid))

				if message is not None: log.debug(message)
				#log.debug("%i: flood %s -> %s", event.dpid,packet.src,packet.dst)
				# OFPP_FLOOD is optional; on some switches you may need to change
				# this to OFPP_ALL.
				msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
			else:
				msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
				# pass
				#log.info("Holding down flood for %s", dpid_to_str(event.dpid))
			msg.data = event.ofp
			msg.in_port = event.port
			self.connection.send(msg)

		def drop (duration = None):
			"""
			Drops this packet and optionally installs a flow to continue
			dropping similar ones for a while
			"""
			if duration is not None:
				if not isinstance(duration, tuple):
					duration = (duration,duration)
				msg = of.ofp_flow_mod()
				msg.match = of.ofp_match.from_packet(packet)
				msg.idle_timeout = duration[0]
				msg.hard_timeout = duration[1]
				msg.buffer_id = event.ofp.buffer_id
				self.connection.send(msg)
				print "drop LLDP packet"
			elif event.ofp.buffer_id is not None:
				msg = of.ofp_packet_out()
				msg.buffer_id = event.ofp.buffer_id
				msg.in_port = event.port
				self.connection.send(msg)

		#self.macToPort[packet.src] = event.port # 1

		if not self.transparent: # 2
			if packet.type == packet.LLDP_TYPE or packet.dst.isBridgeFiltered():
				drop((120,120)) # 2a
				return

		if packet.dst.is_multicast:
			if packet.type == ethernet.IP_TYPE:
				ip_packet = packet.payload
				if ip_packet.protocol == ipv4.UDP_PROTOCOL:
					udp_packet = ip_packet.payload
					if udp_packet.dstport == 5353 or udp_packet.dstport == 67:
						# MDNS or DHCP
						flood()
					else:
						wdyHandleMulticast()
				elif ip_packet.protocol == ipv4.IGMP_PROTOCOL:
					wdyHandleIGMP()
				else:
					flood()
			else:
				flood()
			"""
			flood()
			"""
		else:
			macentry = core.host_tracker.getMacEntry(packet.dst) # 4
			dpid = event.dpid
			port = event.port
			if macentry == None:
				flood("Port for %s unknown -- flooding" % (packet.dst,)) # 4a
			else:
				mmdst = (macentry.dpid, macentry.port)
				match = of.ofp_match.from_packet(packet)
				match = extract_match(match)
				method = core.flow_info.find_flows(match)
				if type(method) != int:
					macentry = core.host_tracker.getMacEntry(packet.src) # this information is at record
					mmsrc = (macentry.dpid, macentry.port)
					#print("event packet_in mmsrc:%s; mmdst:%s;event:%d,%d",str(mmsrc),str(mmdst),dpid, port)
					#print "src:" + str(packet.src) + ";dst:"+str(packet.dst)
					if mmsrc != (dpid, port):
						# some problem of locating host, packet flood anywhere
						mmsrc = (dpid, port)
						Dijikstra_Normal_Multicast.multicast_Plan(mmsrc, [mmdst], event, None, False)
					else:
						Dijikstra_Normal_Multicast.multicast_Plan(mmsrc, [mmdst], event, None)
						tree = Dijikstra_Normal_Multicast.get_Results()
						core.flow_info.add_flows(match, tree)
				else:
					# this flow is build just follow it
					try:
						msg = method[1][(dpid, port)]
					except:
						log.debug(method[1])
						log.debug("dp:" + str(dpid) +";port:"+ str(port))
						print 1
						raise Exception
					newmsg = of.ofp_packet_out(data = event.ofp)
					newmsg.in_port = port
					newmsg.actions = msg.actions
					self.connection.send(newmsg)
					log.debug("send a output packet!")

class l2_learning (object):
	"""
	Waits for OpenFlow switches to connect and makes them learning switches.
	"""
	def __init__ (self, transparent):
		core.openflow.addListeners(self)
		self.transparent = transparent
		self.switch = None

	def _handle_ConnectionUp (self, event):
		log.debug("Connection %s" % (event.connection,))
		self.switch = LearningSwitch(event.connection, self.transparent)


def launch (transparent=False, hold_down=_flood_delay):

	# register group_info module
	core.registerNew(GroupInfo)
	core.registerNew(FlowInfo)
	"""
	Starts an L2 learning switch.
	"""
	try:
		global _flood_delay
		_flood_delay = int(str(hold_down), 10)
		assert _flood_delay >= 0
	except:
		raise RuntimeError("Expected hold-down to be a number")

	core.registerNew(l2_learning, str_to_bool(transparent))
