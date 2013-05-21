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
from pox.openflow.libopenflow_01 import xid_generator
from pox.openflow.flow_table import FlowTable,FlowTableModification,TableEntry
from pox.lib.util import dpidToStr
from pox.lib.addresses import *

import pickle
import itertools

# After a switch disconnects, it has this many seconds to reconnect in
# order to reactivate the same OpenFlowSwitch object.  After this, if
# it reconnects, it will be a new switch object.
RECONNECT_TIMEOUT = 30

log = core.getLogger()

class OpenFlowTopology (object):
  """
  Listens to various OpenFlow-specific events and uses those to manipulate
  Topology accordingly.
  """
    # WdyLink = namedtuple("WdyLink",("dpid1","port1","dpid2","port2"))

  def __init__ (self):
    core.listen_to_dependencies(self, ['topology'], short_attrs=True)
    # self.wdylinks = {}

  def _handle_openflow_discovery_LinkEvent (self, event):
    """
    The discovery module simply sends out LLDP packets, and triggers
    LinkEvents for discovered switches. It's our job to take these
    LinkEvents and update pox.topology.
    """
    link = event.link
    sw1 = self.topology.getEntityByID(link.dpid1)
    sw2 = self.topology.getEntityByID(link.dpid2)
    if sw1 is None or sw2 is None: return
    if link.port1 not in sw1.ports or link.port2 not in sw2.ports: return
    if event.added:
      sw1.ports[link.port1].addEntity(sw2, single=True)
      sw2.ports[link.port2].addEntity(sw1, single=True)
    elif event.removed:
      sw1.ports[link.port1].entities.discard(sw2)
      sw2.ports[link.port2].entities.discard(sw1)

  def _handle_openflow_ConnectionUp (self, event):
    sw = self.topology.getEntityByID(event.dpid)
    add = False
    if sw is None:
      sw = OpenFlowSwitch(event.dpid)
      add = True
    else:
      if sw._connection is not None:
        log.warn("Switch %s connected, but... it's already connected!" %
                 (dpidToStr(event.dpid),))
    sw._setConnection(event.connection, event.ofp)
    log.info("Switch " + dpidToStr(event.dpid) + " connected")
    if add:
      self.topology.addEntity(sw)
      sw.raiseEvent(SwitchJoin, sw)

  def _handle_openflow_ConnectionDown (self, event):
    sw = self.topology.getEntityByID(event.dpid)
    if sw is None:
      log.warn("Switch %s disconnected, but... it doesn't exist!" %
               (dpidToStr(event.dpid),))
    else:
      if sw._connection is None:
        log.warn("Switch %s disconnected, but... it's wasn't connected!" %
                 (dpidToStr(event.dpid),))
      sw._connection = None
      log.info("Switch " + str(event.dpid) + " disconnected")
      
class WdyMultiTree (OpenFlowTopology):
  def __init__ (self, src=[], dst=[], match=None):
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
    
    if self.wdyIsCorrect():
      self.wdyMultiTree()
      self.wdyInstallFlowForTree(match=match)
    
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
    #  msg.actions.append(of.ofp_action_dl_addr.set_dst(EthAddr('ff:ff:ff:ff:ff:ff')))
    for i in range(2, len(switchPort)):
      msg.actions.append(of.ofp_action_output(port = switchPort[i]))
    s = self.topology.getEntityByID(switchPort[1])
    # if s is not None:
    s._connection.send(msg)
    # print "done"
    
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
    #   len(self.entities) <= 2  ?
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
      #    self._pending_barrier_to_ops[barrier.xid])
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
    core.register("openflow_topology", WdyMultiTree())
