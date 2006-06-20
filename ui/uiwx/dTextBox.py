import re
import datetime
import wx

try:
	import decimal
except ImportError:
	# decimal is only in Python 2.4 or greater
	decimal = None

import dabo, dabo.ui
if __name__ == "__main__":
	dabo.ui.loadUI("wx")

import dDataControlMixin as dcm
from dabo.dLocalize import _
import dabo.dEvents as dEvents
from dabo.ui import makeDynamicProperty


class dTextBox(wx.TextCtrl, dcm.dDataControlMixin):
	"""Creates a text box for editing one line of string data."""
	def __init__(self, parent, properties=None, *args, **kwargs):
		self._baseClass = dTextBox

		self._dregex = {}
		self._lastDataType = None
		self._forceCase = None

		preClass = wx.PreTextCtrl
		dcm.dDataControlMixin.__init__(self, preClass, parent, properties, 
				*args, **kwargs)
		
		# Keep passwords, etc., from being written to disk
		if self.PasswordEntry:
			self.IsSecret = True

	
	def _initEvents(self):
		super(dTextBox, self)._initEvents()
		self.Bind(wx.EVT_TEXT, self._onWxHit)
		
		
	def flushValue(self):
		# Call the wx SetValue() directly to reset the string value displayed to the user.
		# This resets the value to the string representation as Python shows it. Also, we
		# must save and restore the InsertionPosition because wxGtk at least resets it to
		# 0 upon SetValue().
		insPos = self.InsertionPosition
		self.SetValue(self._getStringValue(self.Value))
		self.InsertionPosition = insPos
		
		# Now that the dabo Value is set properly, the default behavior that flushes 
		# the value to the bizobj can be called:
		super(dTextBox, self).flushValue()
	
	
	def selectAll(self):
		"""Each subclass must define their own selectAll method. This will 
		be called if SelectOnEntry is True when the control gets focus.
		"""
		self.SetSelection(-1, -1)
		
		
	def getBlankValue(self):
		return ""

		
	def _getStringValue(self, value):
		"""Given a value of any data type, return a string rendition.
		
		Used internally by _setValue and flushValue.
		"""
		if isinstance(value, basestring):
			# keep it unicode instead of converting to str
			strVal = value
		elif isinstance(value, datetime.date):
			# Use the ISO 8601 date string format so we can convert
			# back from a known quantity later...
			strVal = value.isoformat()
		elif isinstance(value, datetime.datetime):
			# Use the ISO 8601 datetime string format (with a " " separator
			# instead of "T") 
			strVal = value.isoformat(" ")
		elif isinstance(value, datetime.time):
			# Use the ISO 8601 time string format
			strVal = value.isoformat()
		else:
			# convert all other data types to string:
			strVal = str(value)   # (floats look like 25.55)
			#strVal = repr(value) # (floats look like 25.55000000000001)
		return strVal

		
	def _getDateFromString(self, strVal):
		"""Given a string in an accepted date format, return a 
		datetime.date object, or None.
		"""
		ret = None
		formats = ["ISO8601"]
		if not self.StrictDateEntry:
			# Add some less strict date-entry formats:
			formats.append("YYYYMMDD")
			formats.append("YYMMDD")
			formats.append("MMDD")
			# (define more formats in _getDateRegex, and enter them above
			#  in more explicit -> less explicit order.)

		# Try each format in order:
		for format in formats:
			try:
				regex = self._dregex[format]
			except KeyError:
				regex = self._dregex[format] = self._getDateRegex(format)
			m = regex.match(strVal)
			if m is not None:
				groups = m.groupdict()
				if not groups.has_key("year"):
					curYear = datetime.date.today().year
					if groups.has_key("shortyear"):
						groups["year"] = int("%s%s" % (str(curYear)[:2], 
								groups["shortyear"]))
					else:
						groups["year"] = curYear
				try:		
					ret = datetime.date(int(groups["year"]), 
						int(groups["month"]),
						int(groups["day"]))
				except ValueError:
					# Could be that the day was out of range for the particular month
					# (Sept. only has 30 days but the regex will allow 31, etc.)
					pass
			if ret is not None:
				break	
		return ret


	def _getDateRegex(self, format):
		elements = {}
		elements["year"] = "(?P<year>[0-9]{4,4})"              ## year 0000-9999
		elements["shortyear"] = "(?P<shortyear>[0-9]{2,2})"    ## year 00-99
		elements["month"] = "(?P<month>0[1-9]|1[012])"         ## month 01-12
		elements["day"] = "(?P<day>0[1-9]|[1-2][0-9]|3[0-1])"  ## day 01-31
		
		if format == "ISO8601":
			exp = "^%(year)s-%(month)s-%(day)s$"
		elif format == "YYYYMMDD":
			exp = "^%(year)s%(month)s%(day)s$"
		elif format == "YYMMDD":
			exp = "^%(shortyear)s%(month)s%(day)s$"
		elif format == "MMDD":
			exp = "^%(month)s%(day)s$"
		else:
			return None
		return re.compile(exp % elements)

			
	def _getDateTimeFromString(self, strVal):
		"""Given a string in ISO 8601 datetime format, return a 
		datetime.datetime object.
		"""
		try:
			regex = self._dtregex
		except AttributeError:
			regex = self._dtregex = self._getDateTimeRegex()
		m = regex.match(strVal)
		if m is not None:
			groups = m.groupdict()
			if len(groups["ms"]) == 0:
				# no ms in the expression
				groups["ms"] = 0
			try:		
				return datetime.datetime(int(groups["year"]), 
					int(groups["month"]),
					int(groups["day"]),
					int(groups["hour"]),
					int(groups["minute"]),
					int(groups["second"]),
					int(groups["ms"]))
			except ValueError:
				# Could be that the day was out of range for the particular month
				# (Sept. only has 30 days but the regex will allow 31, etc.)
				return None
		else:
			# The regex didn't match
			return None
	
	
	def _getDateTimeRegex(self):
		exp = {}
		exp["year"] = "(?P<year>[0-9]{4,4})"              ## year 0000-9999
		exp["month"] = "(?P<month>0[1-9]|1[012])"         ## month 01-12
		exp["day"] = "(?P<day>0[1-9]|[1-2][0-9]|3[0-1])"  ## day 01-31
		exp["hour"] = "(?P<hour>[0-1][0-9]|2[0-3])"       ## hour 00-23
		exp["minute"] = "(?P<minute>[0-5][0-9])"          ## minute 00-59
		exp["second"] = "(?P<second>[0-5][0-9])"          ## second 00-59
		exp["ms"] = "\.{0,1}(?P<ms>[0-9]{0,6})"           ## optional ms
		exp["sep"] = "(?P<sep> |T)"
		exps = "^%(year)s-%(month)s-%(day)s%(sep)s%(hour)s:%(minute)s:%(second)s%(ms)s$" % exp
		return re.compile(exps)


	def _getTimeFromString(self, strVal):
		"""Given a string in ISO 8601 time format, return a 
		datetime.time object.
		"""
		try:
			regex = self._tmregex
		except AttributeError:
			regex = self._tmregex = self._getTimeRegex()
		m = regex.match(strVal)
		if m is not None:
			groups = m.groupdict()
			if len(groups["ms"]) == 0:
				# no ms in the expression
				groups["ms"] = 0
			try:		
				return datetime.time(int(groups["hour"]),
					int(groups["minute"]),
					int(groups["second"]),
					int(groups["ms"]))
			except ValueError:
				# Could be that the day was out of range for the particular month
				# (Sept. only has 30 days but the regex will allow 31, etc.)
				return None
		else:
			# The regex didn't match
			return None
	
	
	def _getTimeRegex(self):
		exp = {}
		exp["hour"] = "(?P<hour>[0-1][0-9]|2[0-3])"       ## hour 00-23
		exp["minute"] = "(?P<minute>[0-5][0-9])"          ## minute 00-59
		exp["second"] = "(?P<second>[0-5][0-9])"          ## second 00-59
		exp["ms"] = "\.{0,1}(?P<ms>[0-9]{0,6})"           ## optional ms
		exp["sep"] = "(?P<sep> |T)"
		exps = "^%(hour)s:%(minute)s:%(second)s%(ms)s$" % exp
		return re.compile(exps)


	def __onKeyChar(self, evt):
		"""This handles KeyChar events when ForceCase is set to a non-empty value."""
		if evt.keyChar.isalnum() or evt.keyChar in """,./<>?;':%s[]\\{}|`~!@#$%%^&*()-_=+""" % '"':
			dabo.ui.callAfter(self.__forceCase)
		
	
	def __forceCase(self):
		"""If the ForceCase property is set, casts the current value of the control
		to the specified case.
		"""
		if not isinstance(self.Value, basestring):
			# Don't bother if it isn't a string type
			return
		case = self.ForceCase
		if not case:
			return
		insPos = self.InsertionPosition
		selLen = self.SelectionLength
		changed = False
		if case == "upper":
			self.Value = self.Value.upper()
			changed = True
		elif case == "lower":
			self.Value = self.Value.lower()
			changed = True
		elif case == "title":
			self.Value = self.Value.title()
			changed = True
		if changed:
			#self.SelectionStart = selStart
			self.InsertionPosition = insPos
			self.SelectionLength = selLen
			self.refresh()
		

	# property get/set functions
	def _getAlignment(self):
		if self._hasWindowStyleFlag(wx.TE_RIGHT):
			return "Right"
		elif self._hasWindowStyleFlag(wx.TE_CENTRE):
			return "Center"
		else:
			return "Left"

	def _setAlignment(self, val):
		# Note: alignment doesn't seem to work, at least on GTK2
		self._delWindowStyleFlag(wx.TE_LEFT)
		self._delWindowStyleFlag(wx.TE_CENTRE)
		self._delWindowStyleFlag(wx.TE_RIGHT)
		val = val[0].lower()
		if val == "l":
			self._addWindowStyleFlag(wx.TE_LEFT)
		elif val == "c":
			self._addWindowStyleFlag(wx.TE_CENTRE)
		elif val == "r":
			self._addWindowStyleFlag(wx.TE_RIGHT)
		else:
			raise ValueError, "The only possible values are 'Left', 'Center', and 'Right'"


	def _getForceCase(self):
		return self._forceCase

	def _setForceCase(self, val):
		if self._constructed():
			valKey = val[0].upper()
			self._forceCase = {"U": "upper", "L": "lower", "T": "title"}.get(valKey)
			self.__forceCase()
			self.unbindEvent(dEvents.KeyChar, self.__onKeyChar)
			if self._forceCase:
				self.bindEvent(dEvents.KeyChar, self.__onKeyChar)
		else:
			self._properties["ForceCase"] = val


	def _getInsertionPosition(self):
		return self.GetInsertionPoint()

	def _setInsertionPosition(self, val):
		self.SetInsertionPoint(val)


	def _getPasswordEntry(self):
		return self._hasWindowStyleFlag(wx.TE_PASSWORD)

	def _setPasswordEntry(self, val):
		self._delWindowStyleFlag(wx.TE_PASSWORD)
		if val:
			self._addWindowStyleFlag(wx.TE_PASSWORD)
			self.IsSecret = True

				
	def _getReadOnly(self):
		return not self.IsEditable()
		
	def _setReadOnly(self, val):
		if self._constructed():
			self.SetEditable(not bool(val))
		else:
			self._properties["ReadOnly"] = val


	def _getSelectedText(self):
		return self.GetStringSelection()


	def _getSelectionEnd(self):
		return self.GetSelection()[1]

	def _setSelectionEnd(self, val):
		start, end = self.GetSelection()
		self.SetSelection(start, val)
		self.refresh()


	def _getSelectionLength(self):
		start, end = self.GetSelection()
		return end - start

	def _setSelectionLength(self, val):
		start = self.GetSelection()[0]
		self.SetSelection(start, start + val)
		self.refresh()


	def _getSelectionStart(self):
		return self.GetSelection()[0]

	def _setSelectionStart(self, val):
		start, end = self.GetSelection()
		self.SetSelection(val, end)
		self.refresh()


	def _getSelectOnEntry(self):
		try:
			return self._SelectOnEntry
		except AttributeError:
			return False
			
	def _setSelectOnEntry(self, val):
		self._SelectOnEntry = bool(val)

		
	def _getStrictDateEntry(self):
		try:
			v = self._strictDateEntry
		except AttributeError:
			v = self._strictDateEntry = False
		return v

	def _setStrictDateEntry(self, val):
		self._strictDateEntry = bool(val)


	def _getValue(self):
		# Return the value as reported by wx, but convert it to the data type as
		# reported by self._value.
		try:
			_value = self._value
		except AttributeError:
			_value = self._value = unicode("")
		dataType = type(_value)
		
		# Get the string value as reported by wx, which is the up-to-date 
		# string value of the control:
		strVal = self.GetValue()
		
		if dataType == type(None):
			# The current datatype of the control is NoneType, but more likely it's
			# just that there happened to be a value of None for this field in one of
			# the records. We've saved the last used non-None datatype, so we'll 
			# assume that is the real type to use.
			dataType = self._lastDataType

		# Convert the current string value of the control, as entered by the 
		# user, into the proper data type.
		if dataType == bool:
			# Bools can't convert from string representations, because a zero-
			# length denotes False, and anything else denotes True.
			if strVal == "True":
				retVal = True
			else:
				retVal = False

		elif dataType in (datetime.date, datetime.datetime, datetime.time):
			# We expect the string to be in ISO 8601 format.
			if dataType == datetime.date:
				retVal = self._getDateFromString(strVal)
			elif dataType == datetime.datetime:
				retVal = self._getDateTimeFromString(strVal)
			elif dataType == datetime.time:
				retVal = self._getTimeFromString(strVal)
				
			if retVal is None:
				# String wasn't in ISO 8601 format... put it back to a valid
				# string with the previous value and the user will have to 
				# try again.
				retVal = self._value
				
		elif str(dataType) == "<type 'DateTime'>":
			# mx DateTime type. MySQLdb will use this if mx is installed.
			try:
				import mx.DateTime
				retVal = mx.DateTime.DateTimeFrom(str(strVal))
			except ImportError:
				retVal = self._value
		
		elif str(dataType) == "<type 'DateTimeDelta'>":
			# mx TimeDelta type. MySQLdb will use this for Time columns if mx is installed.
			try:
				import mx.DateTime
				retVal = mx.DateTime.TimeFrom(str(strVal))
			except ImportError:
				retVal = self._value
		
		elif (decimal is not None and dataType == decimal.Decimal):
			try:
				_oldVal = self._oldVal
			except:
				_oldVal = None

			try:
				if type(_oldVal) == decimal.Decimal:
					# Enforce the precision as previously set programatically
					strVal, _oldVal
					retVal = decimal.DefaultContext.quantize(decimal.Decimal(strVal), _oldVal)
				else:
					retVal = decimal.Decimal(strVal)
			except:
				retVal = self._value
				
		else:
			# Other types can convert directly.
			if dataType == str:
				dataType = unicode
			try:
				retVal = dataType(strVal)
			except:
				# The Python object couldn't convert it. Our validator, once 
				# implemented, won't let the user get this far. Just keep the 
				# old value.
				retVal = self._value
		return retVal		
	
	def _setValue(self, val):
		if self._constructed():
			# Must convert all to string for sending to wx, but our internal 
			# _value will always retain the correct type.
		
			# Todo: set up validators based on the type of data we are editing,
			# so the user can't, for example, enter a letter "p" in a textbox
			# that is currently showing numeric data.
		
			strVal = self._getStringValue(val)
			_oldVal = self._oldVal = self.Value
				
			# save the actual value for return by _getValue:
			self._value = val

			if val is not None:
				# Save the type of the value, so that in the case of actual None
				# assignments, we know the datatype to expect.
				self._lastDataType = type(val)

			# Update the display no matter what:
			self.SetValue(strVal)
		
			if type(_oldVal) != type(val) or _oldVal != val:
				self._afterValueChanged()
		else:
			self._properties["Value"] = val

		
	# Property definitions:
	Alignment = property(_getAlignment, _setAlignment, None,
			_("""Specifies the alignment of the text. (str)
			   Left (default)
			   Center
			   Right"""))

	ForceCase = property(_getForceCase, _setForceCase, None,
			_("""Determines if we change the case of entered text. Possible values are:
				None, "" (empty string): No changes made (default)
				"Upper": FORCE TO UPPER CASE
				"Lower": force to lower case
				"Title": Force To Title Case
			These can be abbreviated to "u", "l" or "t"  (str)"""))
	
	InsertionPosition = property(_getInsertionPosition, _setInsertionPosition, None,
			_("Position of the insertion point within the control  (int)"))
	
	PasswordEntry = property(_getPasswordEntry, _setPasswordEntry, None,
			_("Specifies whether plain-text or asterisks are echoed. (bool)"))

	ReadOnly = property(_getReadOnly, _setReadOnly, None, 
			_("Specifies whether or not the text can be edited. (bool)"))
	
	SelectedText = property(_getSelectedText, None, None,
			_("Currently selected text. Returns the empty string if nothing is selected  (str)"))	
	
	SelectionEnd = property(_getSelectionEnd, _setSelectionEnd, None,
			_("""Position of the end of the selected text. If no text is
			selected, returns the Position of the insertion cursor.  (int)"""))
	
	SelectionLength = property(_getSelectionLength, _setSelectionLength, None,
			_("Length of the selected text, or 0 if nothing is selected.  (int)"))
	
	SelectionStart = property(_getSelectionStart, _setSelectionStart, None,
			_("""Position of the beginning of the selected text. If no text is
			selected, returns the Position of the insertion cursor.  (int)"""))
	
	SelectOnEntry = property(_getSelectOnEntry, _setSelectOnEntry, None, 
			_("Specifies whether all text gets selected upon receiving focus. (bool)"))

	StrictDateEntry = property(_getStrictDateEntry, _setStrictDateEntry, None,
			_("""Specifies whether date values must be entered in strict ISO8601 format. Default=False.

			If not strict, dates can be accepted in YYYYMMDD, YYMMDD, and MMDD format,
			which will be coerced into sensible date values automatically."""))

	Value = property(_getValue, _setValue, None,
			_("Specifies the current state of the control (the value of the field). (varies)"))


	# Dynamic property declarations
	DynamicAlignment = makeDynamicProperty(Alignment)
	DynamicInsertionPosition = makeDynamicProperty(InsertionPosition)
	DynamicPasswordEntry = makeDynamicProperty(PasswordEntry)
	DynamicReadOnly = makeDynamicProperty(ReadOnly)
	DynamicSelectionEnd = makeDynamicProperty(SelectionEnd)
	DynamicSelectionLength = makeDynamicProperty(SelectionLength)
	DynamicSelectionStart = makeDynamicProperty(SelectionStart)
	DynamicSelectOnEntry = makeDynamicProperty(SelectOnEntry)
	DynamicStrictDateEntry = makeDynamicProperty(StrictDateEntry)
	DynamicValue = makeDynamicProperty(Value)



class _dTextBox_test(dTextBox):
	def afterInit(self):
		self.Value = "Dabo rules!"
		self.Size = (200, 20)

if __name__ == "__main__":
	import test

	# This test sets up several textboxes, each editing different data types.	
	class TestBase(dTextBox):
		def initProperties(self):
			self.super()
			self.LogEvents = ["ValueChanged",]
			
		def onValueChanged(self, evt):
			if self.IsSecret:
				print "%s changed, but the new value is a secret!" % self.Name
			else:
				print "%s.onValueChanged:" % self.Name, self.Value, type(self.Value)
		

	class IntText(TestBase):
		def afterInit(self):
			self.Value = 23
		
	class FloatText(TestBase):
		def afterInit(self):
			self.Value = 23.5
	
	class BoolText(TestBase):
		def afterInit(self):
			self.Value = False
	
	class StrText(TestBase):
		def afterInit(self):
			self.Value = "Lunchtime"

	class PWText(TestBase):
		def __init__(self, *args, **kwargs):
			kwargs["PasswordEntry"] = True
			super(PWText, self).__init__(*args, **kwargs)
		def afterInit(self):
			self.Value = "TopSecret!"

	class DateText(TestBase):
		def afterInit(self):
			self.Value = datetime.date.today()
	
	class DateTimeText(TestBase):
		def afterInit(self):
			self.Value = datetime.datetime.now()
	
	testParms = [IntText, FloatText, StrText, PWText, BoolText, DateText, DateTimeText]			
	
	try:
		import mx.DateTime
		class MxDateTimeText(TestBase):
			def afterInit(self):
				self.Value = mx.DateTime.now()
				
		testParms.append(MxDateTimeText)
	except ImportError:
		# skip it: mx may not be available
		pass

	try:
		import decimal
		class DecimalText(TestBase):
			def afterInit(self):
				self.Value = decimal.Decimal("23.42")

		testParms.append(DecimalText)

	except ImportError:
		# decimal only in python >= 2.4
		pass

		
	test.Test().runTest(testParms)
