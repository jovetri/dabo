""" Grid.py

This is the base Dabo dGrid, usually used for showing a set of records
in a dataset, and optionally allowing the fields to be edited.
"""
import datetime
import locale
import wx
import wx.grid
import dabo
if __name__ == "__main__":
	dabo.ui.loadUI("wx")
import dabo.dEvents as dEvents
import dabo.dException as dException
from dabo.dLocalize import _, n_
import dControlMixin as cm
import dKeys
import dUICursors

# See if the new decimal module is present. This is necessary 
# because if running under Python 2.4 or later and using MySQLdb,
# some values will be returned as decimals, and we need to 
# conditionally convert them for display.
_USE_DECIMAL = True
try:
	from decimal import Decimal
except ImportError:
	_USE_DECIMAL = False

# wx versions < 2.6 don't have the GetDefaultPyEncoding function:
try:
	defaultEncoding = wx.GetDefaultPyEncoding()
except AttributeError:
	defaultEncoding = "latin-1"
		

class dGridDataTable(wx.grid.PyGridTableBase):
	def __init__(self, parent):
		super(dGridDataTable, self).__init__()

		self.grid = parent
		# This is specific to the datanav grids
# 		self.preview = self.grid.Form.preview
		self.bizobj = None		#self.grid.Form.getBizobj(parent.DataSource) 
		# Holds a copy of the current data to prevent unnecessary re-drawing
		self.__currData = []
		self._initTable()


	def _initTable(self):
		self.relativeColumns = []
		self.colLabels = []
		self.colNames = []
		self.colDefs = []
		self.dataTypes = []
		self.imageBaseThumbnails = []
		self.imageLists = {}
		self.data = []
		self.rowLabels = []
		# Call the hook
		self.initTable()
	def initTable(self): pass


	def setRowLabels(self, rowLbls):
		self.rowLabels = rowLbls
		
	
	def GetRowLabelValue(self, row):
		try:
			return self.rowLabels[row]
		except:
			return ""
	
	def GetColLabelValue(self, col):
		try:
			return self.colDefs[col].Caption
		except:
			return ""
		
			
	def setColumns(self, colDefs):
		"""This method receives a list of column definitions, and creates
		the appropriate columns.
		"""
		# Column order should already be in the definition. If there is a custom
		# setting by the user, override it.
		idx = 0
		colFlds = []
#		# Make a copy
#		colDefs = list(colDefs)
		# See if the defs have changed. If not, update any column info,
		# and return. If so, clear the data to force a re-draw of the table.
		if colDefs == self.colDefs:
			self.setColumnInfo()
			return
		else:
			self.__currData = []
		for col in colDefs:
			nm = col.Field
			while not nm:
				nm = str(idx)
				idx += 1
				if nm in colFlds:
					nm = ""
			colFlds.append(nm)
			colName = "Column_%s" % nm
			if col.Order == -1:
				pos = self.grid.Application.getUserSetting("%s.%s.%s.%s" % (
						self.grid.Form.Name, 
						self.grid.Name,
						colName,
						"ColumnOrder"))
				if pos is not None:
					col.Order = pos
			# If the data types are actual types and not strings, convert
			# them to common strings.
			if isinstance(type(col.DataType), type):
				typeDict = {
						str : "string", 
						unicode : "unicode", 
						bool : "bool",
						int : "integer",
						float : "float", 
						long : "long", 
						datetime.date : "date", 
						datetime.datetime : "datetime", 
						datetime.time : "time" }
				if _USE_DECIMAL:
					typeDict[Decimal] = "decimal"
				try:
					col.DataType = typeDict[col.DataType]
				except: pass
				
		# Make sure that all cols have an Order set
		for num in range(len(colDefs)):
			col = colDefs[num]
			if col.Order < 0:
				col.Order = num
		colDefs.sort(self.orderSort)
		self.colDefs = colDefs
		self.setColumnInfo()
		
	
	def orderSort(self, col1, col2):
		return cmp(col1.Order, col2.Order)
		
		
	def setColumnInfo(self):
		self.colLabels = [col.Caption for col in self.colDefs]
		self.dataTypes = [self.convertType(col.DataType) 
				for col in self.colDefs]
		self.colNames = [col.Field for col in self.colDefs]


	def convertType(self, typ):
		"""Convert common types, names and abbreviations for 
		data types into the constants needed by the wx.grid.
		"""
		# Default
		ret = wx.grid.GRID_VALUE_STRING
		if type(typ) == str:
			lowtyp = typ.lower()
		else:
			lowtyp = typ
			if _USE_DECIMAL:
				if typ is Decimal:
					lowtyp = "decimal"
		if lowtyp in (bool, "bool", "boolean", "logical", "l"):
			ret = wx.grid.GRID_VALUE_BOOL
		if lowtyp in (int, long, "int", "integer", "bigint", "i", "long"):
			ret = wx.grid.GRID_VALUE_NUMBER
		elif lowtyp in (str, unicode, "char", "varchar", "text", "c", "s"):
			ret = wx.grid.GRID_VALUE_STRING
		elif lowtyp in (float, "float", "f", "decimal"):
			ret = wx.grid.GRID_VALUE_FLOAT
		elif lowtyp in (datetime.date, datetime.datetime, datetime.time, 
				"date", "datetime", "time", "d", "t"):
			ret = wx.grid.GRID_VALUE_DATETIME
		return ret

	
	def CanGetValueAs(self, row, col, typ):
		if self.grid.useCustomGetValue:
			return self.grid.customCanGetValueAs(row, col, typ)
		else:
			return typ == self.dataTypes[col]

	def CanSetValueAs(self, row, col, typ):
		if self.grid.useCustomSetValue:
			return self.grid.customCanSetValueAs(row, col, typ)
		else:
			return typ == self.dataTypes[col]

		
	def fillTable(self, force=False):
		""" Fill the grid's data table to match the data set."""
		rows = self.GetNumberRows()
		oldRow = self.grid.CurrentColumn  # current row per the grid
		oldCol = self.grid.CurrentColumn  # current column per the grid
		if not oldCol:
			oldCol = 0
		# Get the data from the parent grid.
		dataSet = self.grid.getDataSet()
		if not force:
			if self.__currData == dataSet:
				# Nothing's changed; no need to re-fill the table
				return
		else:
			self.__currData = dataSet
		
		self.Clear()
		self.data = []
		encod = self.grid.Encoding
		for record in dataSet:
			recordFmt = self.formatRowForData(record)
			self.data.append(recordFmt)
		self.grid.BeginBatch()
		# The data table is now current, but the grid needs to be
		# notified.
		if len(self.data) > rows:
			# tell the grid we've added row(s)
			num = len(self.data) - rows
			msg = wx.grid.GridTableMessage(self,         # The table
				wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED,  # what we did to it
				num)                                     # how many
			
		elif rows > len(self.data):
			# tell the grid we've deleted row(s)
			num = rows - len(self.data) 
			msg = wx.grid.GridTableMessage(self,        # The table
				wx.grid.GRIDTABLE_NOTIFY_ROWS_DELETED,  # what we did to it
				0,                                      # position
				num)                                    # how many
		else:
			msg = None
		if msg:        
			self.grid.ProcessTableMessage(msg)
		# Column widths come from dApp user settings, the fieldSpecs, or get sensible
		# defaults based on field type.
		idx = 0
		for col in self.colDefs:
			fld = col.Field
			colName = "Column_%s" % fld
			gridCol = idx
			fieldType = col.DataType.lower()

			width = None
			# 1) Try to get the column width from the fieldspecs:
			if col.Width != -1:
				width = col.Width

			# 2) Try to get the column width from the saved user settings:
			if width is None:
				width = self.grid.Application.getUserSetting("%s.%s.%s.%s" % (
						self.grid.Form.Name, self.grid.Name, colName, "Width"))
			
			# 3) Get sensible default width if the above two methods failed:
			if width is None or (width < 0):
				# old way
				minWidth = 10 * len(col.Caption)   ## Fudge!
				
				if fieldType[:3] == "int":
					width = 50
				elif fieldType[:3] in ("num", "flo", "dou"):
					width = 75
				elif fieldType[:4] == "bool":
					width = 75
				else:
					width = 200
				width = max(width, minWidth)
			
			self.grid.SetColSize(gridCol, width)
			idx += 1
		# Show the row labels, if any
		for ii in range(len(self.rowLabels)):
			self.SetRowLabelValue(ii, self.rowLabels[ii])
		self.grid.EndBatch()

	
	def formatRowForData(self, rec):
		"""Takes a row from a record set, and contructs a list
		that matches the column layout. Also encodes all unicode
		values to properly display.
		"""
		returnFmt = []
		for col in self.colDefs:
			fld = col.Field
			if rec.has_key(fld):
				recVal = rec[fld]
				recType = type(recVal)
				if recVal is None:
					recVal = self.grid.NoneDisplay
				recType = type(recVal)
				if isinstance(recVal, basestring):
					if recType is unicode:
						recVal = recVal.encode(defaultEncoding)
					else:
						recVal = unicode(recVal, defaultEncoding)
					# Limit to first 'n' chars...
					recVal = recVal[:self.grid.stringDisplayLen]
				elif col.DataType.lower() == "bool":
					# coerce to bool (could have been 0/1)
					if isinstance(recVal, basestring):
						recVal = bool(int(recVal))
					else:
						recVal = bool(recVal)
			else:
				# If there is no such value, don't display anything
				recVal = ""
			returnFmt.append(recVal)
		return returnFmt
	
	
	def addTempRow(self, row):
		"""Used by the autosize routine to add an individual row 
		containing the captions for the columns so that the autosize
		function takes them into account. It is then followed by a
		call to self.removeTempRow() to restore the data back to its
		original state.
		"""
		rowFmt = self.formatRowForData(row)
		self.data.append(rowFmt)
		self.grid.BeginBatch()
		msg = wx.grid.GridTableMessage(self,
				wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED, 1)
		self.grid.ProcessTableMessage(msg)
		self.grid.EndBatch()


	def removeTempRow(self):
		"""Removes the temp row that was added in a prior call to 
		addTempRow(). This method assumes that the last row
		in the data set is the row to remove.
		"""
		tmp = self.data.pop()
		self.grid.BeginBatch()
		msg = wx.grid.GridTableMessage(self,
				wx.grid.GRIDTABLE_NOTIFY_ROWS_DELETED,
				len(self.data), 1)
		self.grid.ProcessTableMessage(msg)
		self.grid.EndBatch()
	

	# The following methods are required by the grid, to find out certain
	# important details about the underlying table.                
	def GetNumberRows(self):
		try:
			num = len(self.data)
		except:
			num = 0
		return num

	def GetNumberCols(self):
		try:
			num = len(self.colLabels)
		except:
			num = 0
		return num


	def IsEmptyCell(self, row, col):
		try:
			return not self.data[row][col]
		except IndexError:
			return True

	def GetValue(self, row, col):
		try:
			ret = self.data[row][col]
		except:
			ret = ""
		return ret

	def SetValue(self, row, col, value):
		self.data[row][col] = value



class dColumn(dabo.common.dObject):
	""" These aren't the actual columns that appear in the grid; rather,
	they provide a way to interact with the underlying grid table in a more
	straightforward manner.
	"""
	def __init__(self, parent=None, *args, **kwargs):
		super(dColumn, self).__init__()
			
		# This class doesn't have support for the typical Dabo 
		# technique of passing in property settings in the 
		# constructor, so fake it here.
		try: self._caption = kwargs["Caption"]
		except: self._caption = "Column"
		try: self._order = kwargs["Order"]
		except: self._order = -1
		try: self._width = kwargs["Width"]
		except: self._width = -1
		try: self._parent = kwargs["Parent"]
		except: self._parent = parent
		try: self._name = kwargs["Name"]
		except: self._name = ""
		try: self._field = kwargs["Field"]
		except: self._field = ""
		try: self._dataType = kwargs["DataType"]
		except: self._dataType = ""
		try: self._capBkColor = kwargs["HeaderBackgroundColor"]
		except: self._hdrBkColor = None

		# Can this column be sorted? Default: True
		self.canSort = True
		# Do we run incremental search with this column? Default: True
		self.canIncrSearch = True
		
	def changeMsg(self, prop):
		if self.Parent:
			self.Parent.onColumnChange(self, prop)
	
	def _getCap(self):
		return self._caption
	def _setCap(self, val):
		self._caption = val
		self.changeMsg("caption")
	
	def _getDTyp(self):
		return self._dataType
	def _setDTyp(self, val):
		self._dataType = val
		self.changeMsg("datatype")
	
	def _getFld(self):
		return self._field
	def _setFld(self, val):
		self._field = val
		self.changeMsg("field")
	
	def _getHdrBkColor(self):
		return self._hdrBkColor
	def _setHdrBkColor(self, val):
		if isinstance(val, basestring):
			try:
				val = dColors.colorTupleFromName(val)
			except: pass
		self._hdrBkColor = val
		self.Parent.Refresh()
	
	def _getName(self):
		return self._name
	def _setName(self, val):
		self._name = val
	
	def _getOrd(self):
		return self._order
	def _setOrd(self, val):
		self._order = val
		self.changeMsg("order")
	
	def _getParent(self):
		return self._parent
	def _setParent(self, val):
		self._parent = val
	
	def _getWd(self):
		return self._width
	def _setWd(self, val):
		self._width = val
		self.changeMsg("width")
	
	Caption = property(_getCap, _setCap, None,
			_("Caption displayed in this column's header  (str)") )

	DataType = property(_getDTyp, _setDTyp, None,
			_("Description of the data type for this column  (str)") )

	Field = property(_getFld, _setFld, None,
			_("Field key in the data set to which this column is bound.  (str)") )

	HeaderBackgroundColor = property(_getHdrBkColor, _setHdrBkColor, None,
			_("Optional color for the background of the column header  (str)") )

	Name = property(_getName, _setName, None,
			_("Name of this column  (str)") )

	Order = property(_getOrd, _setOrd, None,
			_("Order of this column  (int)") )

	Parent = property(_getParent, _setParent, None,
			_("Parent of this object.  (dGrid)") )
	
	Width = property(_getWd, _setWd, None,
			_("Width of this column  (int)") )
	


class dGrid(wx.grid.Grid, cm.dControlMixin):
	_IsContainer = False
	
	def __init__(self, parent, properties=None, *args, **kwargs):
		self._baseClass = dGrid
		preClass = wx.grid.Grid
		
		# Grab the DataSet parameter if passed
		self._passedDataSet = self.extractKey(kwargs, "DataSet")
		self.dataSet = []
		# List of column specs
		self.Columns = []
		# List of Row Labels, if any
		self._rowLabels = []

		cm.dControlMixin.__init__(self, preClass, parent, properties, *args, **kwargs)
		
		
	def _afterInit(self):
		self.bizobj = None
		self._header = None
		self.fieldSpecs = {}
		# This value is in miliseconds
		self._searchDelay = 600
		# When doing an incremental search, do we stop
		# at the nearest matching value?
		self.searchNearest = True
		# Do we do case-sensitive incremental searches?
		self.searchCaseSensitive = False
		# How many characters of strings do we display?
		self.stringDisplayLen = 64
		
		# Do we enforce that all rows are the same height? This
		# would normally be a property, but I'm making it a simple att
		# for now, since I don't see the immediate need for getter/setter
		# actions.
		self.SameSizeRows = True
		# Internal tracker for row height
		self._rowHeight = self.GetDefaultRowSize()
		# Columns notify the grid when their properties change
		# Sometimes the grid itself initiated the change, and doesn't
		# need to be notified.
		self._ignoreColUpdates = False
		# When calculating auto-size widths, we don't want to use
		# the normal means of getting data sets.
		self.inAutoSizeCalc = False

		self.currSearchStr = ""
		self.incSearchTimer = dabo.ui.dTimer(self)
		self.incSearchTimer.bindEvent(dEvents.Hit, self.onSearchTimer)

		self.sortedColumn = None
		self.sortOrder = ""
		self.caseSensitiveSorting = False
		# If there is a custom sort method, set this to True
		self.customSort = False

		# By default, row labels are not shown. They can be displayed
		# if desired by setting ShowRowLabels = True, and their size
		# can be adjusted by setting RowLabelWidth = <width>
		self._rowLabelWidth = self.GetDefaultRowLabelSize()
		self._showRowLabels = False
		self.SetRowLabelSize(0)
		self._editable = False
		self.EnableEditing(self._editable)
		
		# These need to be set to True, and custom methods provided,
		# if a grid with variable types in a single column is used.
		self.useCustomGetValue = False
		self.useCustomSetValue = False
		
		# Cell renderer and editor classes
		self.defaultRenderers = {
			"str" : wx.grid.GridCellStringRenderer, 
			"string" : wx.grid.GridCellStringRenderer, 
			"bool" : wx.grid.GridCellBoolRenderer, 
			"int" : wx.grid.GridCellNumberRenderer, 
			"long" : wx.grid.GridCellNumberRenderer, 
			"float" : wx.grid.GridCellFloatRenderer, 
			"list" : wx.grid.GridCellStringRenderer  }
		self.defaultEditors = {
			"str" : wx.grid.GridCellTextEditor, 
			"string" : wx.grid.GridCellTextEditor, 
			"bool" : wx.grid.GridCellBoolEditor, 
			"int" : wx.grid.GridCellNumberEditor, 
			"long" : wx.grid.GridCellNumberEditor, 
			"float" : wx.grid.GridCellFloatEditor, 
			"list" : wx.grid.GridCellChoiceEditor  }
		# If you want a custom editor/renderer for any column, 
		# add an entry to these dicts with the field name
		# as the key.
		self.customRenderers = {}
		self.customEditors = {}
		# The list editors require a list to construct them. Add a key
		# containing the field name and the corresponding list for
		# that field to this dict.
		self.listEditors = {}
		# Type of encoding to use with unicode data
		self.defaultEncoding = defaultEncoding
		# What color should the little sort indicator arrow be?
		self.sortArrowColor = "Orange"

		self.headerDragging = False    # flag used by mouse motion event handler
		self.headerDragFrom = 0
		self.headerDragTo = 0
		self.headerSizing = False
		#Call the default behavior
		super(dGrid, self)._afterInit()
		
		# Set the header props/events
		self.initHeader()		
		# If a data set was passed to the constructor, create the grid
		self.buildFromDataSet(self._passedDataSet)


	def initEvents(self):
		self.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self.__onWxMouseLeftDoubleClick)
		self.Bind(wx.grid.EVT_GRID_ROW_SIZE, self.__onWxGridRowSize)
		self.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.__onWxGridSelectCell)
		self.Bind(wx.grid.EVT_GRID_COL_SIZE, self.__onWxColSize)
		self.Bind(wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.__onWxRightClick)
		self.Bind(wx.grid.EVT_GRID_CELL_CHANGE, self.__onWxCellChange)

		self.bindEvent(dEvents.KeyDown, self.onKeyDown)
		self.bindEvent(dEvents.MouseLeftDoubleClick, self.onLeftDClick)
		self.bindEvent(dEvents.GridRowSize, self._onGridRowSize)
		self.bindEvent(dEvents.GridSelectCell, self._onGridSelectCell)
		self.bindEvent(dEvents.GridColSize, self._onGridColSize)
		self.bindEvent(dEvents.GridRightClick, self.onGridRightClick)
		self.bindEvent(dEvents.GridCellEdited, self._onGridCellEdited)


	def initHeader(self):
		""" Initialize behavior for the grid header region."""
		header = self.Header
		self.defaultHdrCursor = header.GetCursor()

		header.Bind(wx.EVT_LEFT_DCLICK, self.__onWxMouseLeftDoubleClick)
		header.Bind(wx.EVT_LEFT_DOWN, self.__onWxMouseLeftDown)
		header.Bind(wx.EVT_LEFT_UP, self.__onWxMouseLeftUp)
		header.Bind(wx.EVT_RIGHT_UP, self.__onWxMouseRightUp)
		header.Bind(wx.EVT_MOTION, self.__onWxMouseMotion)
		header.Bind(wx.EVT_PAINT, self.__onWxHeaderPaint)

		self.bindEvent(dEvents.MouseLeftDown, self.onMouseLeftDown)
		self.bindEvent(dEvents.MouseLeftUp, self.onMouseLeftUp)
		self.bindEvent(dEvents.MouseRightUp, self.onMouseRightUp)
		self.bindEvent(dEvents.MouseMove, self.onMouseMove)
		self.bindEvent(dEvents.Paint, self.onHeaderPaint)


	def GetCellValue(self, row, col):
		try:
			ret = self._Table.GetValue(row, col)
		except:
			ret = super(dGrid, self).GetCellValue(row, col)
		return ret

	def GetValue(self, row, col):
		try:
			ret = self._Table.GetValue(row, col)
		except:
			ret = super(dGrid, self).GetValue(row, col)
		return ret

	def SetValue(self, row, col, val):
		try:
			self._Table.SetValue(row, col, val)
		except StandardError, e:
			super(dGrid, self).SetCellValue(row, col, val)
		# Update the main data source
		try:
			fld = self.Columns[col].Field
			self.dataSet[row][fld] = val
		except StandardError, e:
			dabo.errorLog.write("Cannot update data set: %s" % e)

	# Wrapper methods to Dabo-ize these calls.
	def getValue(self, row, col):
		return self.GetValue(row, col)
	def setValue(self, row, col, val):
		return self.SetValue(row, col, val)

	# These two methods need to be customized if a grid has columns
	# with more than one type of data in them.	
	def customCanGetValueAs(self, row, col, typ): pass
	def customCanSetValueAs(self, row, col, typ): pass
			
		
	def fillGrid(self, force=False):
		""" Refresh the grid to match the data in the data set."""
		# Save the focus, if any
		currFocus = self.FindFocus()
		# Get the default row size from dApp's user settings
		s = self.Application.getUserSetting("%s.%s.%s" % (self.Form.Name, 
				self.GetName(), "RowSize"))
		if s:
			self.SetDefaultRowSize(s)
		tbl = self._Table
		
		tbl.setColumns(self.Columns)
		tbl.setRowLabels(self.RowLabels)
		tbl.fillTable(force)
		
		if force:
			row = max(0, self.CurrentRow)
			col = max(0, self.CurrentColumn)
			# Needed on Linux to get the grid to have the focus:
			for window in self.Children:
				window.SetFocus()
			# Needed on win and mac to get the grid to have the focus:
			self.GetGridWindow().SetFocus()
			if  not self.IsVisible(row, col):
				self.MakeCellVisible(row, col)
				self.MakeCellVisible(row, col)
			self.SetGridCursor(row, col)
		
		self.SetColLabelAlignment(wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
		# Set the types
		for ii in range(len(self.Columns)):
			col = self.Columns[ii]
			fld = col.Field
			typ = col.DataType
			if self.customRenderers.has_key(fld):
				rndClass = self.customRenderers[fld]
				for rr in range(self.RowCount):
					self.SetCellRenderer(rr, ii, rndClass())
			else:
				if col.DataType == "bool":
					self.SetColFormatBool(ii)
				elif col.DataType in ("int", "long"):
					self.SetColFormatNumber(ii)
				elif col.DataType == "float":
					self.SetColFormatFloat(ii)
			if self.Editable:
				if self.customEditors.has_key(fld):
					edtClass = self.customEditors[fld]
				else:
					edtClass = self.defaultEditors[col.DataType]
				if typ == "list":
					# There should be a custom list specified for this field
					if self.listEditors.has_key(fld):
						lst = self.listEditors[fld]
					else:
						lst = []
					for rr in range(self.RowCount):
						self.SetCellEditor(rr, ii, edtClass(choices=lst))
				else:
					# Non-list values
					for rr in range(self.RowCount):
						self.SetCellEditor(rr, ii, edtClass())
		
		if currFocus is not None:
			try:
				currFocus.SetFocus()
			except: pass
		
	
	
	def buildFromDataSet(self, ds, keyCaption=None, 
			columnsToSkip=[], colOrder={}, autoSizeCols=True):
		"""This method will create a grid for a given data set.
		A 'data set' is a sequence of dicts, each containing field/
		value pairs. The columns will be taken from ds[0].keys(),
		with each column header being set to the key name, unless
		the optional keyCaption parameter is passed. This parameter
		is a 1:1 dict containing the data set keys as its keys,
		and the desired caption as the corresponding value.
		If the columnsToSkip parameter is set, any column in the 
		data with a key in that list will not be added to the grid.
		The columns will be in the order returned by ds.keys(), unless
		the optional colOrder parameter is passed. Like the keyCaption
		property, this is a 1:1 dict containing key:order.
		"""
		if not ds:
			return
#		self.Form.lockDisplay()
		origColNum = self.ColumnCount
		self.Columns = []
		self.dataSet = ds
		firstRec = ds[0]
		# Dabo cursors add some columns to the data set. These
		# artifacts need to be removed. They all begin with 'dabo-'.
		colKeys = [key for key in firstRec.keys()
				if (key[:5] != "dabo-") and (key not in columnsToSkip)]
		# Update the number of columns
		colChange = len(colKeys) - origColNum 
		if colChange != 0:
			msg = ""
			if colChange < 0:
				msg = wx.grid.GridTableMessage(self._Table,
						wx.grid.GRIDTABLE_NOTIFY_COLS_DELETED,
						origColNum-1, abs(colChange))
			else:
				msg = wx.grid.GridTableMessage(self._Table,
						wx.grid.GRIDTABLE_NOTIFY_COLS_APPENDED,
						colChange)
			if msg:
				self.BeginBatch()
				self.ProcessTableMessage(msg)
				self.EndBatch()
		# Add the columns
		self._ignoreColUpdates = True
		for colKey in colKeys:
			# Use the keyCaption values, if possible
			try:
				cap = keyCaption[colKey]
			except:
				cap = colKey
			col = dColumn(self)
			col.Caption = cap
			col.Field = colKey
			dt = col.DataType = type(firstRec[colKey])
			if dt is type(None):
				for rec in ds[1:]:
					val = rec[colKey]
					if val is not None:
						dt = type(val)
						break
				col.DataType = dt
			if dt is type(None):
				# Default to string type
				dt = col.DataType = str
				
			# See if any order was specified
			if colOrder.has_key(colKey):
				col.Order = colOrder[colKey]
			# Use a default width
			col.Width = -1
			self.Columns.append(col)
		# Populate the grid
		self.fillGrid(True)
		if autoSizeCols:
			self.autoSizeCol("all")
		self._ignoreColUpdates = False
#		self.Form.unlockDisplay()


	def autoSizeCol(self, colNum):
		"""This sets the requested column to the minimum width 
		necessary to display its data. You can pass 'all' instead, and
		all columns will be auto-sized.
		"""	
		# lock the screen
		self.lockDisplay()
		# Changing the columns' Width prop will send an update
		# message back to this grid. We want to ignore that
		self._ignoreColUpdates = True
		# We also don't want the Table's call to grid.getDataSet()
		# to wipe out our temporary changes.
		self.inAutoSizeCalc = True
		# We need to account for header caption width, too. Add
		# a row to the data set containing the header captions, and 
		# then remove the row afterwards.
		capRow = {}
		for col in self.Columns:
			capRow[col.Field] = col.Caption
		self._Table.addTempRow(capRow)
		try:
			# Having a problem with Unicode in the native
			# AutoSize() function.
			if isinstance(colNum, str):
				#They passed "all"
				self.AutoSizeColumns(setAsMin=False)
				for ii in range(len(self.Columns)):
					self.Columns[ii].Width = self.GetColSize(ii)
			elif isinstance(colNum, (int, long)):
				self.AutoSizeColumn(colNum, setAsMin=False)
				self.Columns[colNum].Width = self.GetColSize(colNum)
		except:
			pass
		self._Table.removeTempRow()
		self.inAutoSizeCalc = False
		self._ignoreColUpdates = False
		self.unlockDisplay()		


	def getDataSet(self):
		"""Customize to your needs. Default is to use an internal property,
		and if that is empty, simply ask the form."""
		ret = self.dataSet
		if not ret:
			try:
				ret = self.Form.getDataSet()
			except:
				ret = []
		return ret
		

	def _onGridCellEdited(self, evt):
		row, col = evt.EventData["row"], evt.EventData["col"]
		rowData = self.getDataSet()[row]
		fld = self.Columns[col].Field
		newVal = self.GetCellValue(row, col)
		oldVal = rowData[fld]
		if newVal != oldVal:
			# Update the local copy of the data
			rowData[fld] = self.GetCellValue(row, col)
			# Call the hook
			self.onGridCellEdited(row, col, newVal)

	def onGridCellEdited(self, row, col, newVal): 
		"""Called when the user has edited a cell
		and changed the value. Changes to the cell
		can be written back to the data source if 
		desired.
		"""
		pass


	def _onGridColSize(self, evt):
		"Occurs when the user resizes the width of the column."
		colNum = evt.EventData["rowOrCol"]
		col = self.Columns[colNum]
		colName = "Column_%s" % col.Field
		width = self.GetColSize(colNum)
		col.Width = width
		self.onGridColSize(evt)
	
	def onGridColSize(self, evt): pass


	def _onGridSelectCell(self, evt):
		""" Occurs when the grid's cell focus has changed."""
		oldRow = self.CurrentRow
		newRow = evt.EventData["row"]
		
		if oldRow != newRow:
			if self.bizobj:
				self.bizobj.RowNumber = newRow
		self.Form.refreshControls()
		self.onGridSelectCell(evt)

	def onGridSelectCell(self, evt): pass


	def onColumnChange(self, col, chgType):
		"""Called by the grid columns whenever any of their properties
		are directly changed, allowing the grid to react.
		"""
		if chgType == "width":
			self.Application.setUserSetting("%s.%s.%s.%s" % (
					self.Form.Name, self.Name, "Column_%s" % col.Field, 
					"Width"), col.Width)
		elif chgType == "order":
			self.Application.setUserSetting("%s.%s.%s.%s" % (
					self.Form.Name, self.Name, "Column_%s" % col.Field,
					"ColumnOrder"), (col.Order * 10) )
		if self._ignoreColUpdates:
			# The column is being updated after a grid change, so
			# no need to update the grid again.
			return
		# Update the grid
		self.fillGrid(True)
		

	def __onWxHeaderPaint(self, evt):
		self.raiseEvent(dEvents.Paint, evt)
	def onHeaderPaint(self, evt):
		""" Occurs when it is time to paint the grid column headers."""
# 		dabo.ui.callAfter(self.hdrPaint)
# 	
# 	def hdrPaint(self):
		w = self.Header
		dc = wx.ClientDC(w)
		clientRect = w.GetClientRect()
		font = dc.GetFont()

		# Thanks Roger Binns for the correction to totColSize
		totColSize = -self.GetViewStart()[0] * self.GetScrollPixelsPerUnit()[0]

		# Get the height
		ht = self.GetColLabelSize()

		for col in range(self.ColumnCount):
			dc.SetBrush(wx.Brush("WHEAT", wx.TRANSPARENT))
			dc.SetTextForeground(wx.BLACK)
			colSize = self.GetColSize(col)
			rect = (totColSize, 0, colSize, ht)
			colObj = self.Columns[col]
			if colObj.HeaderBackgroundColor is not None:
				holdBrush = dc.GetBrush()
				dc.SetBrush(wx.Brush(colObj.HeaderBackgroundColor, wx.SOLID))
				dc.DrawRectangle(rect[0] - (col != 0 and 1 or 0), 
						rect[1], 
						rect[2] + (col != 0 and 1 or 0), 
						rect[3])
				dc.SetBrush(holdBrush)
			totColSize += colSize

			if self.Columns[col].Field == self.sortedColumn:
				font.SetWeight(wx.BOLD)
				# draw a triangle, pointed up or down, at the top left 
				# of the column. TODO: Perhaps replace with prettier icons
				left = rect[0] + 3
				top = rect[1] + 3

				dc.SetBrush(wx.Brush(self.sortArrowColor, wx.SOLID))
				if self.sortOrder == "DESC":
					# Down arrow
					dc.DrawPolygon([(left,top), (left+6,top), (left+3,top+6)])
				elif self.sortOrder == "ASC":
					# Up arrow
					dc.DrawPolygon([(left+3,top), (left+6, top+6), (left, top+6)])
				else:
					# Column is not sorted, so don't draw.
					pass    
			else:
				font.SetWeight(wx.NORMAL)

# 			dc.SetFont(font)
# 			dc.DrawLabel("%s" % self.GetTable().colLabels[col],
# 					rect, wx.ALIGN_CENTER | wx.ALIGN_TOP)


	def MoveColumn(self, colNum, toNum):
		""" Move the column to a new position."""
		self._ignoreColUpdates = True
		oldCol = self.Columns[colNum]
		self.Columns.remove(oldCol)
		if toNum > colNum:
			self.Columns.insert(toNum-1, oldCol)
		else:
			self.Columns.insert(toNum, oldCol)
		for col in self.Columns:
			col.Order = self.Columns.index(col) * 10
			self.Application.setUserSetting("%s.%s.%s.%s" % (
					self.Form.Name,
					self.Name,
					"Column_%s" % col.Field,
					"ColumnOrder"), col.Order )
		self.fillGrid(True)
		self._ignoreColUpdates = False


	def onSearchTimer(self, evt):
		""" Occurs when the incremental search timer reaches its interval. 
		It is time to run the search, if there is any search in the buffer.
		"""
		if len(self.currSearchStr) > 0:
			self.runIncSearch()
		else:
			self.incSearchTimer.stop()


	def __onWxMouseMotion(self, evt):
		self.raiseEvent(dEvents.MouseMove, evt)
	def onMouseMove(self, evt):
		evt.Continue = False
		if evt.EventData.has_key("row"):
			self.onGridMouseMove(evt)
		else:
			self.onHeaderMouseMove(evt)
	def onGridMouseMove(self, evt):
		""" Occurs when the left mouse button moves over the grid."""
		pass
	def onHeaderMouseMove(self, evt):
		""" Occurs when the mouse moves in the grid header."""
		headerIsDragging = self.headerDragging
		headerIsSizing = self.headerSizing
		dragging = evt.EventData["mouseDown"]
		header = self.Header

		if dragging:
			x,y = evt.EventData["mousePosition"]

			if not headerIsSizing and (
				self.getColByX(x) == self.getColByX(x-2) == self.getColByX(x+2)):
				if not headerIsDragging:
					# A header reposition is beginning
					self.headerDragging = True
					self.headerDragFrom = (x,y)

				else:
					# already dragging.
					begCol = self.getColByX(self.headerDragFrom[0])
					curCol = self.getColByX(x)

					# The visual indicators (changing the mouse cursor) isn't currently
					# working. It would work without the evt.Skip() below, but that is 
					# needed for when the column is resized.
					uic = dUICursors
					if begCol == curCol:
						# Give visual indication that a move is initiated
						header.SetCursor(uic.getStockCursor(uic.Cursor_Size_WE))
					else:
						# Give visual indication that this is an acceptable drop target
						header.SetCursor(uic.getStockCursor(uic.Cursor_Bullseye))
			else:
				# A size action is happening
				self.headerSizing = True


	def __onWxMouseLeftUp(self, evt):
		self.raiseEvent(dEvents.MouseLeftUp, evt)
	def onMouseLeftUp(self, evt):
		evt.Continue = False
		if evt.EventData.has_key("row"):
			self.onGridLeftUp(evt)
		else:
			self.onHeaderLeftUp(evt)
	def onGridLeftUp(self, evt):
		""" Occurs when the left mouse button is released in the grid."""
		pass
	def onHeaderLeftUp(self, evt):
		""" Occurs when the left mouse button is released in the grid header.

		Basically, this comes down to two possibilities: the end of a drag
		operation, or a single-click operation. If we were dragging, then
		it is possible a column needs to change position. If we were clicking,
		then it is a sort operation.
		"""
		x,y = evt.EventData["mousePosition"]
		if self.headerDragging:
			# A drag action is ending
			self.headerDragTo = (x,y)

			begCol = self.getColByX(self.headerDragFrom[0])
			curCol = self.getColByX(x)

			if begCol != curCol:
				if curCol > begCol:
					curCol += 1
				self.MoveColumn(begCol, curCol)
			self.Header.SetCursor(self.defaultHdrCursor)
		elif self.headerSizing:
			pass
		else:
			# we weren't dragging, and the mouse was just released.
			# Find out the column we are in based on the x-coord, and
			# do a processSort() on that column.
			col = self.getColByX(x)
			self.processSort(col)
		self.headerDragging = False
		self.headerSizing = False
 		evt.Continue = False


	def __onWxMouseLeftDown(self, evt):
		self.raiseEvent(dEvents.MouseLeftDown, evt)
	def onMouseLeftDown(self, evt):
		evt.Continue = False
		if evt.EventData.has_key("row"):
			self.onGridLeftDown(evt)
		else:
			self.onHeaderLeftDown(evt)
	def onGridLeftDown(self, evt):
		""" Occurs when the left mouse button is pressed in the grid."""
		pass
	def onHeaderLeftDown(self, evt):
		""" Occurs when the left mouse button is pressed in the grid header."""
		evt.Continue = False


	def onHeaderLeftDClick(self, evt):
		""" Occurs when the left mouse button is double-clicked in the grid header."""
		pass


	def __onWxMouseRightUp(self, evt):
		self.raiseEvent(dEvents.MouseRightUp, evt)
	def onMouseRightUp(self, evt):
		evt.Continue = False
		if evt.EventData.has_key("row"):
			self.onGridRightUp(evt)
		else:
			self.onHeaderRightUp(evt)
	def onGridRightUp(self, evt):
		""" Occurs when the right mouse button goes up in the grid."""
		pass
	def onHeaderRightUp(self, evt):
		""" Occurs when the right mouse button goes up in the grid header."""
		pass
		self.autoSizeCol( self.getColByX(evt.GetX()))

	
	def onLeftDClick(self, evt): 
		"""Occurs when the user double-clicks anywhere in the grid."""
		if evt.EventData.has_key("row"):
			# User double-clicked on a cell
			self.onGridLeftDClick(evt)
		else:
			# On the header
			self.onHeaderLeftDClick(evt)


	def onGridLeftDClick(self, evt):
		"""The user double-clicked on a cell in the grid."""
		pass


	def onGridRightClick(self, evt):
		""" Occurs when the user right-clicks a cell in the grid. 
		By default, this is interpreted as a request to display the popup 
		menu, as defined in self.popupMenu().
		NOTE: evt is a wxPython event, not a Dabo event.
		"""
		# Select the cell that was right-clicked upon
		self.CurrentRow = evt.GetRow()
		self.CurrentColumn = evt.GetCol()

		# Make the popup menu appear in the location that was clicked
		self.mousePosition = evt.GetPosition()

		# Display the popup menu, if any
		self.popupMenu()


	def OnGridLabelLeftClick(self, evt):
		""" Occurs when the user left-clicks a grid column label. 
		By default, this is interpreted as a request to sort the column.
		NOTE: evt is a wxPython event, not a Dabo event.
		"""
		self.processSort(evt.GetCol())
	
	
	def onEnterKeyAction(self):
		"Customize in subclasses"
		pass
		
	def onDeleteKeyAction(self):
		"Customize in subclasses"
		pass
	
	def onEscapeAction(self):
		"Customize in subclasses"
		pass
	
	def processKeyPress(self, char):
		"""Hook method for classes that need to process 
		keys in addition to Enter, Delete and Escape.
		Example:
			if keyCode == dKeys.keyStrings["f2"]:    # F2
				self.processSort()
		"""
		pass
		

	def onKeyDown(self, evt): 
		""" Occurs when the user presses a key inside the grid. 
		Default actions depend on the key being pressed:
					Enter:  edit the record
						Del:  delete the record
						F2:  sort the current column
				AlphaNumeric:  incremental search
		"""
		if self.Editable:
			# Can't search and edit at the same time
			return

		keyCode = evt.EventData["keyCode"]
		try:
			char = chr(keyCode)
		except ValueError:       # keycode not in ascii range
			char = None

		if keyCode == dKeys.keyStrings["enter"]:           # Enter
			self.onEnterKeyAction()
			evt.stop()
		else:
			if keyCode == dKeys.keyStrings["delete"]:      # Del
				self.onDeleteKeyAction()
				evt.stop()
			elif keyCode == dKeys.keyStrings["escape"]:
				self.onEscapeAction()
				evt.stop()
			elif char and (char.isalnum() or char.isspace()) and not evt.HasModifiers():
				self.addToSearchStr(char)
				# For some reason, without this the key happens twice
				evt.stop()
			else:
				if self.processKeyPress(keyCode):
					# Key was handled
					evt.stop()
				


	def processSort(self, gridCol=None):
		""" Sort the grid column.

		Toggle between ascending and descending. If the grid column index isn't 
		passed, the currently active grid column will be sorted.
		"""
		if gridCol == None:
			gridCol = self.CurrentColumn
		
		if isinstance(gridCol, dColumn):
			canSort = gridCol.canSort
			columnToSort = gridCol
			sortCol = self.Columns.index(gridCol)
		else:
			sortCol = gridCol
			columnToSort = self.Columns[gridCol].Field
			canSort = self.Columns[gridCol].canSort

		if not canSort:
			# Some columns, especially those with mixed values,
			# should not be sorted.
			return
			
		sortOrder="ASC"
		if columnToSort == self.sortedColumn:
			sortOrder = self.sortOrder
			if sortOrder == "ASC":
				sortOrder = "DESC"
			else:
				sortOrder = "ASC"
		self.sortOrder = sortOrder
		self.sortedColumn = columnToSort
		
		if self.customSort:
			# Grids tied to bizobj cursors may want to use their own
			# sorting.
			self.sort()
		else:
			# Create the list to hold the rows for sorting
			caseSensitive = self.caseSensitiveSorting
			sortList = []
			rowNum = 0
			for row in self.dataSet:
				if self.RowLabels:
					sortList.append([row[columnToSort], row, self.RowLabels[rowNum]])
					rowNum += 1
				else:
					sortList.append([row[columnToSort], row])
			# At this point we have a list consisting of lists. Each of these member
			# lists contain the sort value in the zeroth element, and the row as
			# the first element.
			# First, see if we are comparing strings
			sortingStrings = isinstance(sortList[0][0], basestring)
			if sortingStrings and not caseSensitive:
				# Use a case-insensitive sort.
				sortList.sort(lambda x, y: cmp(x[0].lower(), y[0].lower()))
			else:
				sortList.sort()
	
			# Unless DESC was specified as the sort order, we're done sorting
			if sortOrder == "DESC":
				sortList.reverse()
			# Extract the rows into a new list, then set the dataSet to the new list
			newRows = []
			newLabels = []
			for elem in sortList:
				newRows.append(elem[1])
				if self.RowLabels:
					newLabels.append(elem[2])
			self.dataSet = newRows
			self.RowLabels = newLabels
		self.fillGrid(True)


	def runIncSearch(self):
		""" Run the incremental search."""
		gridCol = self.CurrentColumn
		if gridCol < 0:
			gridCol = 0
		fld = self.Columns[gridCol].Field
		if self.RowCount <= 0:
			# Nothing to seek within!
			return
		if not self.Columns[gridCol].canIncrSearch:
			# Doesn't apply to this column.
			self.currSearchStr = ""
			return
		newRow = self.CurrentRow
		ds = self.getDataSet()
		srchStr = origSrchStr = self.currSearchStr
		self.currSearchStr = ""
		near = self.searchNearest
		caseSensitive = self.searchCaseSensitive
		# Copy the specified field vals and their row numbers to a list, and 
		# add those lists to the sort list
		sortList = []
		for i in range(0, self.RowCount):
			sortList.append( [ds[i][fld], i] )

		# Determine if we are seeking string values
		compString = isinstance(sortList[0][0], basestring)
		if not compString:
			# coerce srchStr to be the same type as the field type
			if isinstance(sortList[0][0], int):
				try:
					srchStr = int(srchStr)
				except ValueError:
					srchStr = int(0)
			elif isinstance(sortList[0][0], long):
				try:
					srchStr = long(srchStr)
				except ValueError:
					srchStr = long(0)
			elif isinstance(sortList[0][0], float):
				try:
					srchStr = float(srchStr)
				except ValueError:
					srchStr = float(0)

		if compString and not caseSensitive:
			# Use a case-insensitive sort.
			sortList.sort(lambda x, y: cmp(x[0].lower(), y[0].lower()))
		else:
			sortList.sort()

		# Now iterate through the list to find the matching value. I know that 
		# there are more efficient search algorithms, but for this purpose, we'll
		# just use brute force
		for fldval, row in sortList:
			if not compString or caseSensitive:
				match = (fldval == srchStr)
			else:
				# Case-insensitive string search.
				match = (fldval.lower() == srchStr.lower())
			if match:
				newRow = row
				break
			else:
				if near:
					newRow = row
				# If we are doing a near search, see if the row is less than the
				# requested matching value. If so, update the value of 'ret'. If not,
				# we have passed the matching value, so there's no point in 
				# continuing the search, but we mu
				if compString and not caseSensitive:
					toofar = fldval.lower() > srchStr.lower()
				else:
					toofar = fldval > srchStr
				if toofar:
					break
		self.CurrentRow = newRow

		# Add a '.' to the status bar to signify that the search is
		# done, and clear the search string for next time.
		self.Form.setStatusText("Search: %s." % origSrchStr)
		self.currSearchStr = ""


	def addToSearchStr(self, key):
		""" Add a character to the current incremental search.

		Called by KeyDown when the user pressed an alphanumeric key. Add the 
		key to the current search and start the timer.        
		"""
		self.incSearchTimer.stop()
		self.currSearchStr = "".join((self.currSearchStr, key))
		self.Form.setStatusText("Search: %s"
				% self.currSearchStr)
		self.incSearchTimer.start(self.SearchDelay)


	def popupMenu(self):
		""" Display a popup menu of relevant choices. 
		By default, the choices are 'New', 'Edit', and 'Delete'.
		"""
		popup = dabo.ui.dMenu()
		popup.append("Dabo Grid")
		popup.append("Default Popup")
		self.PopupMenu(popup, self.mousePosition)
		popup.release()


	def _onGridRowSize(self, evt):
		""" Occurs when the user sizes the height of the row. If the
		property 'SameSizeRows' is True, Dabo overrides the wxPython 
		default and applies that size change to all rows, not just the row 
		the user sized.
		"""
		row = evt.GetRowOrCol()
		size = self.GetRowSize(row)

		# Persist the new size
		self.Application.setUserSetting("%s.%s.%s" % (
				self.Form.Name, self.Name, "RowSize"), size)
		
		if self.SameSizeRows:
			self.SetDefaultRowSize(size, True)
			self.ForceRefresh()
		# Call the user hook
		self.onGridRowSize(evt)
		
	def onGridRowSize(self, evt): pass


	def getHTML(self, justStub=True, tableHeaders=True):
		""" Get HTML suitable for printing out the data in this grid.

		This can be used by client code to get a quick and dirty report
		via wxHtmlEasyPrinting, for example. 

		If justStub is False, it will be a standalone HTML file complete 
		with <html><head> etc...
		"""
		cols = self.GetNumberCols()
		rows = self.GetNumberRows()

		if not justStub:
			html = ["<html><body>"]
		else:
			html = []

		html.append("""<table border="1" cellpadding="2" cellspacing="0" width="100%">""")

		# get the column widths as proportional percentages:
		gridWidth = 0
		for col in range(cols):
			gridWidth += self.GetColSize(col)

		if tableHeaders:
			html.append("<tr>")
			for col in range(cols):
				colSize = str(int((100 * self.GetColSize(col)) / gridWidth) - 2) + "%"
				#colSize = self.GetColSize(col)
				colValue = self.GetTable().colLabels[col]
				html.append("""<td align="center" valign="center" width="%s"><b>%s</b></td>"""
								% (colSize,colValue))
			html.append("</tr>")

		for row in range(rows):
			html.append("<tr>")
			for col in range(cols):
				colName = self.GetTable().colNames[col]
				colVal = self.GetTable().data[row][col]
				html.append("""<td align="left" valign="top"><font size="1">%s</font></td>"""
								% colVal)
			html.append("</tr>")

		html.append("</table>")

		if not justStub:
			html.append("</body></html>")
		return "\n".join(html)


#- pkm: these don't appear to be used
#-	def getRowHeight(self, row):
#-		return self.GetRowSize(row)
	
#-	def setRowHeight(self, row, ht):
#-		if self.SameSizeRows:
#-			self.SetDefaultRowSize(ht, True)
#-			self.ForceRefresh()
#-		else:
#-			self.SetRowSize(row, ht)
			
	
	def getColByX(self, x):
		""" Given the x-coordinate, return the column number.
		"""
		col = self.XToCol(x + (self.GetViewStart()[0]*self.GetScrollPixelsPerUnit()[0]))
		if col == wx.NOT_FOUND:
			col = -1
		return col


	def __onWxGridRowSize(self, evt):
		self.raiseEvent(dEvents.GridRowSize, evt)
		evt.Skip()

	def __onWxColSize(self, evt):
		self.raiseEvent(dEvents.GridColSize, evt)
		evt.Skip()
		
	def __onWxGridSelectCell(self, evt):
		self.raiseEvent(dEvents.GridSelectCell, evt)
		evt.Skip()

	def __onWxRightClick(self, evt):
		self.raiseEvent(dEvents.GridRightClick, evt)
		evt.Skip()

	def __onWxMouseLeftDoubleClick(self, evt):
		self.raiseEvent(dEvents.MouseLeftDoubleClick, evt)
		evt.Skip()

	def __onWxCellChange(self, evt):
		self.raiseEvent(dEvents.GridCellEdited, evt)
		evt.Skip()


	def maxColOrder(self):
		""" Return the highest value of Order for all columns."""
		ret = -1
		if len(self.Columns) > 0:
			ret = max([cc.Order for cc in self.Columns])
		return ret
		
		
	def addColumn(self, col=None, inBatch=False):
		""" Adds a column to the grid. If no column is passed, a 
		blank column is added, which can be customized later.
		"""
		if col is None:
			col = dColumn(self)
		if col.Order == -1:
			col.Order = self.maxColOrder() + 10
		self.Columns.append(col)
		if not inBatch:
			msg = wx.grid.GridTableMessage(self._Table,
					wx.grid.GRIDTABLE_NOTIFY_COLS_APPENDED,
					1)
			self.ProcessTableMessage(msg)
			self.fillGrid(True)


	def removeColumn(self, col=None):
		""" Removes a column to the grid. If no column is passed, 
		the last column is removed.
		"""
		colNum = None
		if col is None:
			colNum = self.ColumnCount - 1
		elif isinstance(col, int):
			colNum = col
		else:
			# They probably passed a specific column instance
			colNum = self.Columns.index(col)
			if colNum == -1:
				# No such column
				# raise an error?
				return
		del self.Columns[colNum]
		msg = wx.grid.GridTableMessage(self._Table,
				wx.grid.GRIDTABLE_NOTIFY_COLS_DELETED,
				colNum, 1)
		self.ProcessTableMessage(msg)
		self.fillGrid(True)

	
		
	def cell(self, row, col):
		class GridCell(object):
			def __init__(self, parent, row, col):
				self.parent = parent
				self.row = row
				self.col = col
			
			def _getVal(self):
				return self.parent.GetValue(self.row, self.col)
			def _setVal(self, val):
				self.parent.SetValue(self.row, self.col, val)
			Value = property(_getVal, _setVal)
		return GridCell(self, row, col)
		
	
	def _getColumnCount(self):
		return len(self.Columns)

	def _setColumnCount(self, val):
		if self._constructed():
			msg = None
			if val > -1:
				colChange = val - self.ColumnCount 
				self.BeginBatch()
				if colChange == 0:
					# No change
					return
				elif colChange < 0:
					msg = wx.grid.GridTableMessage(self._Table,
							wx.grid.GRIDTABLE_NOTIFY_COLS_DELETED,
							val, abs(colChange))
					self.Columns = self.Columns[:val]
				else:
					msg = wx.grid.GridTableMessage(self._Table,
							wx.grid.GRIDTABLE_NOTIFY_COLS_APPENDED,
							colChange)
					for cc in range(colChange):
						self.addColumn(inBatch=True)
				if msg:
					self.ProcessTableMessage(msg)
				self.EndBatch()
				self.fillGrid(True)
		else:
			self._properties["ColumnCount"] = val


	def _getColLbls(self):
		ret = []
		for col in range(self.ColumnCount):
			ret.append(self.GetColLabelValue(col))
		return ret


	def _getHeader(self):
		if not self._header:
			self._header = self.GetGridColLabelWindow()
		return self._header


	def _getHeaderHt(self):
		return self.GetColLabelSize()
	def _setHeaderHt(self, val):
		self.SetColLabelSize(val)
	
	
	def _getNoneDisp(self):
		try:
			# See if the Application has a value set
			ret = self.Application.NoneDisplay
		except:
			ret = _("<null>")
		return ret
		

	def _getRowCount(self):
		return self._Table.GetNumberRows()
		
	def _getCurrCellVal(self):
		return self.GetValue(self.GetGridCursorRow(), self.GetGridCursorCol())	

	def _setCurrCellVal(self, val):
		self.SetValue(self.GetGridCursorRow(), self.GetGridCursorCol(), val)	
		self.Refresh()


	def _getCurrentColumn(self):
		return self.GetGridCursorCol()

	def _setCurrentColumn(self, val):
		if self._constructed():
			if val > -1:
				val = min(val, self.ColumnCount)
				rn = self.CurrentRow
				self.SetGridCursor(rn, val)
				self.MakeCellVisible(rn, val)
		else:
			self._properties["CurrentColumn"] = val
		

	def _getCurrentField(self):
		return self.Columns[self.GetGridCursorCol()].Field

	def _setCurrentField(self, val):
		if self._constructed():
			for ii in range(len(self.Columns)):
				if self.Columns[ii].Field == val:
					self.CurrentColumn = ii
					break
		else:	
			self._properties["CurrentField"] = val


	def _getCurrentRow(self):
		return self.GetGridCursorRow()

	def _setCurrentRow(self, val):
		if self._constructed():
			val = min(val, self.RowCount-1)	
			if val > -1:
				cn = self.CurrentColumn
				self.SetGridCursor(val, cn)
				self.MakeCellVisible(val, cn)
		else:
			self._properties["CurrentRow"] = val		


	def _getEditable(self):
		return self._editable

	def _setEditable(self, val):
		if self._constructed():
			self._editable = val
			self.EnableEditing(val)
		else:
			self._properties["Editable"] = val
	
	
	def _getEncoding(self):
		if self.bizobj:
			ret = self.bizobj.Encoding
		else:
			ret = self.defaultEncoding
		return ret
		

	def _getRowHeight(self):
		return self._rowHeight

	def _setRowHeight(self, val):
		if self._constructed():
			if val != self._rowHeight:
				self._rowHeight = val
				self.SetDefaultRowSize(val, True)
				self.ForceRefresh()
				# Persist the new size
				self.Application.setUserSetting("%s.%s.%s" % (
						self.Form.Name, self.Name, "RowSize"), val)
		else:
				self._properties["RowHeight"] = val


	def _getRowLbls(self):
		return self._rowLabels
	
	def _setRowLbls(self, val):
		self._rowLabels = val
		self.fillGrid()


	def _getShowRowLabels(self):
		return self._showRowLabels

	def _setShowRowLabels(self, val):
		if self._constructed():
			self._showRowLabels = val
			if val:
				self.SetRowLabelSize(self._rowLabelWidth)
			else:
				self.SetRowLabelSize(0)
		else:
			self._properties["ShowRowLabels"] = val


	def _getRowLabelWidth(self):
		return self._rowLabelWidth

	def _setRowLabelWidth(self, val):
		if self._constructed():
			self._rowLabelWidth = val
			if self._showRowLabels:
				self.SetRowLabelSize(self._rowLabelWidth)
		else:
			self._properties["RowLabelWidth"] = val


	def _getSearchDelay(self):
		return self._searchDelay

	def _setSearchDelay(self, val):
		self._searchDelay = val
		

	def _getTable(self):
		tbl = self.GetTable()
		if not tbl:
			tbl = dGridDataTable(self)
			self.SetTable(tbl, True)
		return tbl	

	def _setTable(self, tbl):
		if self._constructed():
			self.SetTable(tbl, True)
		else:
			self._properties["Table"] = value


	ColumnCount = property(_getColumnCount, _setColumnCount, None, 
			_("Number of columns in the grid.  (int)") )
	
	ColumnLabels = property(_getColLbls, None, None, 
			_("List of the column labels.  (list)") )
	
	CurrentCellValue = property(_getCurrCellVal, _setCurrCellVal, None,
			_("Value of the currently selected grid cell  (varies)") )
			
	CurrentColumn = property(_getCurrentColumn, _setCurrentColumn, None,
			_("Currently selected column  (int)") )
			
	CurrentField = property(_getCurrentField, _setCurrentField, None,
			_("Field for the currently selected column  (str)") )
			
	CurrentRow = property(_getCurrentRow, _setCurrentRow, None,
			_("Currently selected row  (int)") )
			
	Editable = property(_getEditable, _setEditable, None,
			_("Can the contents of the grid be edited?  (bool)") )
			
	Encoding = property(_getEncoding, None, None,
			_("Name of encoding to use for unicode  (str)") )
			
	Header = property(_getHeader, None, None,
			_("Reference to the grid header window.  (header object?)") )
			
	HeaderHeight = property(_getHeaderHt, _setHeaderHt, None, 
			_("Height of the column headers.  (int)") )
	
	NoneDisplay = property(_getNoneDisp, None, None, 
			_("Text to display for null (None) values.  (str)") )
	
	RowCount = property(_getRowCount, None, None, 
			_("Number of rows in the grid.  (int)") )

	RowHeight = property(_getRowHeight, _setRowHeight, None,
			_("Row Height for all rows of the grid  (int)"))

	RowLabels = property(_getRowLbls, _setRowLbls, None, 
			_("List of the row labels.  (list)") )
	
	RowLabelWidth = property(_getRowLabelWidth, _setRowLabelWidth, None,
			_("""Width of the label on the left side of the rows. This only changes
			the grid if ShowRowLabels is True.  (int)"""))

	SearchDelay = property(_getSearchDelay, _setSearchDelay, None,
			_("""Delay in miliseconds between keystrokes before the 
			incremental search clears  (int)""") )
			
	ShowRowLabels = property(_getShowRowLabels, _setShowRowLabels, None,
			_("Are row labels shown?  (bool)") )

	_Table = property(_getTable, _setTable, None,
			_("Reference to the internal table class  (dGridDataTable)") )



	

if __name__ == '__main__':

	class TestForm(dabo.ui.dForm):
		def afterInit(self):
			self.BackColor = "khaki"
			g = self.grid = dGrid(self)
			self.Sizer.append(g, 1, "x", border=40, borderFlags="all")
			
			g.dataSet = [{"name" : "Ed Leafe", "age" : 47, "coder" :  True},
					{"name" : "Mike Leafe", "age" : 18, "coder" :  False} ]

			col = dColumn(g)
			col.Name = "Person"
			col.Order = 10
			col.Field = "name"
			col.DataType = "string"
			col.Width = 300
			col.Caption = "Customer Name"
			g.addColumn(col)
		
			col = dColumn(g)
			col.Name = "Age"
			col.Order = 30
			col.Field = "age"
			col.DataType = "integer"
			col.Width = 40
			col.Caption = "Age"
			g.addColumn(col)
		
		
		def getDataSet(self):
			return self.dataSet

			
			
	app = dabo.dApp()
	app.MainFormClass = TestForm
	app.setup()
	app.start()
