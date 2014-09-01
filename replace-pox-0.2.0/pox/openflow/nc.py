# by Liu Sicheng
# mail : liusicheng888@gmail.com

from pox.core import core
from pox.lib.util import initHelper
from pox.lib.util import hexdump
from pox.lib.addresses import parse_cidr, IPAddr, EthAddr

import pox.openflow.libopenflow_01 as of
from pox.openflow.libopenflow_01 import ofp_header, ofp_vendor_base
from pox.openflow.libopenflow_01 import _PAD, _PAD2, _PAD4, _PAD6
from pox.openflow.libopenflow_01 import _unpack, _read, _skip

import struct


NC_VENDOR_ID = 0x00003333

def _init_constants ():
	actions = [
			"NC_NULL",
			"NC_INIT_CODING",
			"NC_ENCODE",
			"NC_DECODE",
			]
	for i,name in enumerate(actions):
		globals()[name] = i

_init_constants()


def align_eight(l):
	return (l + 7)/8 * 8

class nc_action_init_coding (of.ofp_action_vendor_base):
	def _init (self, kw):
		self.vendor = NC_VENDOR_ID
		self.subtype = NC_INIT_CODING
		self.buffer_id = 0
		self.packet_num = 0
		self.port_num = 0
		self.vector_off = 0
		self.packet_len = 0
		self.outports = []
		self.vector = []
	
	def _eq (self, other):
		if self.subtype != other.subtype: 
			return False
		return True

	def _pack_body (self):
		p = struct.pack('!H', self.subtype)
		p += struct.pack("!BBBBH", self.buffer_id, self.packet_num, self.port_num, self.vector_off, self.packet_len)
		for i in range(self.port_num):
			p += struct.pack("!H", self.outports[i])
		for i in range(self.port_num):
			for j in range(self.packet_num):
				p += struct.pack("!B", self.vector[i][j])
		j = 2 + 6 + self.port_num * 2 + self.port_num * self.packet_num * 1
		add = align_eight(j) - j
		for i in range(add):
			p += _PAD
		return p

	def _unpack_body (self, raw, offset, avail):
		return offset

	def _body_length (self):
		j = 6 + self.port_num * 2 + self.port_num * self.packet_num * 1
		return align_eight(j)

	def _show (self, prefix):
		return None
class nc_action_encode (of.ofp_action_vendor_base):
	def _init (self, kw):
		self.vendor = NC_VENDOR_ID
		self.subtype = NC_ENCODE
		self.buffer_id = 0
		self.port_num = 0
		self.buffer_size = 0
		self.output_port = 0
		self.packet_len = 0
		self.packet_num = 0
		self.port_id = 0
		self.data = []
	
	def _eq (self, other):
		if self.subtype != other.subtype: 
			return False
		return True

	def _pack_body (self):
		p = struct.pack('!H', self.subtype)
		p += struct.pack("!BBHHHHH", self.buffer_id, self.port_num, self.buffer_size, self.output_port, self.packet_len, self.packet_num, self.port_id)
		for i in range(self.packet_num):
			p += struct.pack("!B", self.data[i])
		j = 2 + 12 + self.packet_num * 1
		add = align_eight(j) - j
		for i in range(add):
			p += _PAD
		return p

	def _unpack_body (self, raw, offset, avail):
		return offset

	def _body_length (self):
		j = 12 + self.packet_num * 1
		return align_eight(j)

	def _show (self, prefix):
		return None
class nc_action_decode (of.ofp_action_vendor_base):
	def _init (self, kw):
		self.vendor = NC_VENDOR_ID
		self.subtype = NC_DECODE
		self.buffer_id = 0
		self.packet_num = 0
		self.buffer_size = 0
		self.output_num = 0
		self.packet_len = 0
		self.port_id = 0
		self.outports = []
	
	def _eq (self, other):
		if self.subtype != other.subtype: 
			return False
		return True

	def _pack_body (self):
		p = struct.pack('!H', self.subtype)
		p += struct.pack("!BBHHHH", self.buffer_id, self.packet_num, self.buffer_size, self.output_num, self.packet_len, self.port_id)
		for i in range(self.output_num):
			p += struct.pack("!H", self.outports[i])
		j = 2 + 10 + self.output_num * 2
		add = align_eight(j) - j
		for i in range(add):
			p += _PAD
		return p

	def _unpack_body (self, raw, offset, avail):
		return offset

	def _body_length (self):
		j = 10 + self.output_num * 2
		return align_eight(j)

	def _show (self, prefix):
		return None
