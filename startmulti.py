def launch ():
  from multicast.multicollect import launch
  launch()
  from multicast.multicast_route import launch
  launch()
  from topology import launch
  launch()
  from openflow.discovery import launch
  launch()
  from openflow.spanning_tree import launch
  launch(no_flood=True, hold_down=True)
