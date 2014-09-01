# Fixed by wangdy on support for IGMP v3 Report
# Date: 2013.5.13
# Copyright 2012 James McCauley
# Copyright 2008 (C) Nicira, Inc.
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX.  If not, see <http://www.gnu.org/licenses/>.

# This file is derived from the packet library in NOX, which was
# developed by Nicira, Inc.

#======================================================================
#
#                          IGMP v3 Report 
#
#                        1 1 1 1 1 1 1 1 1 1 2 2 2 2 2 2 2 2 2 2 3 3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   | IGMP TYPE     | RESERVED      | Checksum                      |
#   +-------+-------+---------------+-------------------------------+
#   | RESERVED                      | Number_of_Group_Records(M)    |
#   +-------------------------------+-------------------------------+
#   |                       Group Record[i] (1<=i<=M)               |
#   +-------------------------------+-------------------------------+
#
#                         Group Record
#
#                        1 1 1 1 1 1 1 1 1 1 2 2 2 2 2 2 2 2 2 2 3 3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   | Record Type   | Aux_Data_Len  | Number_of_Group_Sources (N)   |
#   +-------+-------+---------------+-------------------------------+
#   |                       Multicast Address                       |
#   +-------------------------------+-------------------------------+
#   |                       Source Address [i] (0<=i<=N)            |
#   +-------------------------------+-------------------------------+
#   |                       Auxiliary Data                          |
#   +-------------------------------+-------------------------------+
#
#======================================================================

#TODO: Support for IGMP v3 Query

import struct
from packet_utils import *
from packet_base import packet_base
from pox.lib.addresses import *

MEMBERSHIP_QUERY     = 0x11
MEMBERSHIP_REPORT    = 0x12
MEMBERSHIP_REPORT_V2 = 0x16
LEAVE_GROUP_V2       = 0x17
MEMBERSHIP_REPORT_V3 = 0x22

# IGMP multicast address
IGMP_ADDRESS = IPAddr("224.0.0.22")

# IGMP IP protocol
IGMP_PROTOCOL = 2

GR_RECORD_TYPE = 0x1
GR_AUX_DATA_LEN = 0x2
GR_NUM_SRC = 0x3
GR_MULTI_ADDR = 0x4
GR_SRC_ADDR = 0x5
GR_AUX_DATA = 0x6

class igmp (packet_base):
  """
  IGMP Message
  """

  MIN_LEN = 16
  IGMP_ADDRESS = IGMP_ADDRESS
  IGMP_PROTOCOL = IGMP_PROTOCOL

  MEMBERSHIP_QUERY     = MEMBERSHIP_QUERY
  MEMBERSHIP_REPORT    = MEMBERSHIP_REPORT
  MEMBERSHIP_REPORT_V2 = MEMBERSHIP_REPORT_V2
  LEAVE_GROUP_V2       = LEAVE_GROUP_V2
  MEMBERSHIP_REPORT_V3 = MEMBERSHIP_REPORT_V3

  GR_RECORD_TYPE = 0x1
  GR_AUX_DATA_LEN = 0x2
  GR_NUM_SRC = 0x3
  GR_MULTI_ADDR = 0x4
  GR_SRC_ADDR = 0x5
  GR_AUX_DATA = 0x6

  def __init__(self, raw=None, prev=None, **kw):
    packet_base.__init__(self)

    self.prev = prev

    self.ver_and_type = 0
    # self.max_response_time = 0
    self.csum = 0
    # self.address = None
    # self.extra = b''
    
    self.reserved1 = 0
    self.reserved2 = 0
    self.num_records = 0
    self.grs = []
    gr = {}
    gr[GR_RECORD_TYPE]  = 4
    gr[GR_AUX_DATA_LEN] = 0
    gr[GR_NUM_SRC] = 0
    gr[GR_MULTI_ADDR] = None
    gr[GR_SRC_ADDR] = []
    gr[GR_AUX_DATA] = b''
    # self.grs.append(gr)

    if raw is not None:
      self.parse(raw)

    self._init(kw)

  def hdr (self, payload):
    s = struct.pack("!BBHHH", self.ver_and_type, 0, 0, 0, self.num_records)
    for i in range(self.num_records):
      s += struct.pack("!BBHi", self.grs[i][GR_RECORD_TYPE], self.grs[i][GR_AUX_DATA_LEN],
                        self.grs[i][GR_NUM_SRC], self.grs[i][GR_MULTI_ADDR].toSigned(networkOrder=False))
      for j in range(self.grs[i][GR_NUM_SRC]):
        s += struct.pack("!i", self.grs[i][GR_SRC_ADDR][j].toSigned(networkOrder=False))
      s += self.grs[i][GR_AUX_DATA]
    self.csum = checksum(s)
    s = struct.pack("!BBHHH", self.ver_and_type, 0, self.csum, 0, self.num_records)
    for i in range(self.num_records):
      s += struct.pack("!BBHi", self.grs[i][GR_RECORD_TYPE], self.grs[i][GR_AUX_DATA_LEN],
                        self.grs[i][GR_NUM_SRC], self.grs[i][GR_MULTI_ADDR].toSigned(networkOrder=False))
      for j in range(self.grs[i][GR_NUM_SRC]):
        s += struct.pack("!i", self.grs[i][GR_SRC_ADDR][j].toSigned(networkOrder=False))
      s += self.grs[i][GR_AUX_DATA]
    return s

  def parse (self, raw):
    assert isinstance(raw, bytes)
    self.raw = raw
    dlen = len(raw)
    if dlen < self.MIN_LEN:
      self.msg('packet data too short to parse')
      return None
    
    self.ver_and_type, self.reserved1, self.csum, self.reserved2, self.num_records = \
        struct.unpack("!BBHHH", raw[:8])
    raw = raw[8:]
    for i in range(self.num_records):
      gr = {}
      gr[GR_RECORD_TYPE], gr[GR_AUX_DATA_LEN], gr[GR_NUM_SRC], ip = \
          struct.unpack("!BBHi", raw[:8])
      raw = raw[8:]
      gr[GR_MULTI_ADDR] = IPAddr(ip, networkOrder = False)
      for j in range(gr[GR_NUM_SRC]):
        gr[GR_SRC_ADDR] = []
        gr[GR_SRC_ADDR].append(struct.unpack("!i", raw[:4]))
        raw = raw[4:]
      gr[GR_AUX_DATA] = raw[:gr[GR_AUX_DATA_LEN]]
      raw = raw[gr[GR_AUX_DATA_LEN]:]
      self.grs.append(gr)

    s = struct.pack("!BBHHH", self.ver_and_type, 0, 0, 0, self.num_records)
    for i in range(self.num_records):
      s += struct.pack("!BBHi", self.grs[i][GR_RECORD_TYPE], self.grs[i][GR_AUX_DATA_LEN],
                        self.grs[i][GR_NUM_SRC], self.grs[i][GR_MULTI_ADDR].toSigned(networkOrder=False))
      for j in range(self.grs[i][GR_NUM_SRC]):
        s += struct.pack("!i", self.grs[i][GR_SRC_ADDR][j].toSigned(networkOrder=False))
      s += self.grs[i][GR_AUX_DATA]

    csum = checksum(s)
    if csum != self.csum:
      self.err("IGMP hecksums don't match")
    else:
      self.parsed = True

  def __str__ (self):
    s = "[IGMP "
    s += "vt:%02x %s" % (self.ver_and_type, self.gr[GR_MULTI_ADDR])
    return s + "]"
