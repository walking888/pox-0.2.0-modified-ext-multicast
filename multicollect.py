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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
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
from multitopo import *
from pox.lib.packet import arp, ipv4, igmp
from pox.lib.packet.ethernet import ethernet
from pox.lib.addresses import IPAddr, EthAddr
import time

log = core.getLogger()

# We don't want to flood immediately when a switch connects.
# Can be overriden on commandline.
_flood_delay = 0

groups = {}

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
    #          str(self.transparent))

  def _handle_PacketIn (self, event):
    """
    Handle packet in messages from the switch to implement above algorithm.
    """

    packet = event.parsed

    def wdyHandleMulticast ():
      dpid = event.dpid
      port = event.port
      src = [(dpid, port)]
      ip_packet = packet.payload
      dst = []
      if ip_packet.dstip in groups.keys():
        dst = groups[ip_packet.dstip]
      else:
        drop()
      if len(dst) is 0:
        log.info("group is none")
        return
      match = of.ofp_match.from_packet(packet, event.port)
      tree = WdyMultiTree(src=src, dst=dst, match=match)

    def wdyHandleIGMP ():
      ip_packet = packet.payload
      igmp_packet = ip_packet.payload
      hddst = packet.dst
      hdsrc = packet.src
      ipsrc = ip_packet.srcip
      ipdst = ip_packet.dstip
      dpid = event.dpid
      port = event.port
      for i in range(igmp_packet.num_records):
        groupAddr = igmp_packet.grs[i][4]
        if groupAddr in groups.keys():
          groupPort = groups[groupAddr]
          if igmp_packet.grs[0][1] == 4:
            if (dpid, port) in groupPort:
              drop()
            else:
              groups[groupAddr].append((dpid, port))
          elif igmp_packet.grs[0][1] == 3:
            if (dpid, port) in groupPort:
              groups[groupAddr].remove((dpid, port))
            drop()
          else:
            drop()
        else:
          groups[groupAddr] = [(dpid, port)]
          drop()









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
        pass
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
      elif event.ofp.buffer_id is not None:
        msg = of.ofp_packet_out()
        msg.buffer_id = event.ofp.buffer_id
        msg.in_port = event.port
        self.connection.send(msg)

    self.macToPort[packet.src] = event.port # 1

    if not self.transparent: # 2
      if packet.type == packet.LLDP_TYPE or packet.dst.isBridgeFiltered():
        drop() # 2a
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



    else:
      if packet.dst not in self.macToPort: # 4
        flood("Port for %s unknown -- flooding" % (packet.dst,)) # 4a
      else:
        port = self.macToPort[packet.dst]
        if port == event.port: # 5
          # 5a
          log.warning("Same port for packet from %s -> %s on %s.%s.  Drop."
              % (packet.src, packet.dst, dpid_to_str(event.dpid), port))
          drop(10)
          return
        # 6
        log.debug("installing flow for %s.%i -> %s.%i" %
                  (packet.src, event.port, packet.dst, port))
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet, event.port)
        msg.idle_timeout = 10
        msg.hard_timeout = 30
        msg.actions.append(of.ofp_action_output(port = port))
        msg.data = event.ofp # 6a
        self.connection.send(msg)


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
