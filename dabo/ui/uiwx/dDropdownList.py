import wx, dabo, dabo.ui
if __name__ == "__main__":
	dabo.ui.loadUI("wx")
import dControlItemMixin as dcm
import dabo.dEvents as dEvents
from dabo.dLocalize import _


class dDropdownList(wx.Choice, dcm.dControlItemMixin):
	""" Allows presenting a choice of items for the user to choose from."""
	def __init__(self, parent, properties=None, *args, **kwargs):
		self._baseClass = dDropdownList
		self._choices = []

		preClass = wx.PreChoice
		dcm.dControlItemMixin.__init__(self, preClass, parent, properties, *args, **kwargs)
	
	def _initEvents(self):
		super(dDropdownList, self)._initEvents()
		self.Bind(wx.EVT_CHOICE, self._onWxHit)

		# Changing the value in a dropdown list should fire the Hit event.
		self.bindEvent(dEvents.ValueChanged, self._onValChanged)
		
		# wx.Choice doesn't seem to emit lostfocus and gotfocus events. Therefore,
		# flush the value on every hit.
		self.bindEvent(dEvents.Hit, self.__onHit)
	
	
	def _onValChanged(self, evt):
		self.raiseEvent(dEvents.Hit)
		
	
	def __onHit(self, evt):
		self.flushValue()
		

class _dDropdownList_test(dDropdownList):
	def initProperties(self):
		# Simulating a database
		developers = ({"lname": "McNett", "fname": "Paul", "iid": 42},
			{"lname": "Leafe", "fname": "Ed", "iid": 23})
			
		choices = []
		keys = {}
		for developer in developers:
			choices.append("%s %s" % (developer['fname'], developer['lname']))
			keys[developer["iid"]] = len(choices) - 1
			
		self.Choices = choices
		self.Keys = keys
		self.ValueMode = "key"
		

	def initEvents(self):
		self.autoBindEvents()
			

	def onHit(self, evt):
		print "KeyValue: ", self.KeyValue
		print "PositionValue: ", self.PositionValue
		print "StringValue: ", self.StringValue
		print "Value: ", self.Value
		

if __name__ == "__main__":
	import test
	test.Test().runTest(_dDropdownList_test)
