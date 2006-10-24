import types
import re
import dabo
import dabo.dConstants as k
from dabo.db.dCursorMixin import dCursorMixin
from dabo.dLocalize import _
import dabo.dException as dException
from dabo.dObject import dObject


class dBizobj(dObject):
	""" The middle tier, where the business logic resides."""
	# Class to instantiate for the cursor object
	dCursorMixinClass = dCursorMixin
	# Tell dObject that we'll call before and afterInit manually:
	_call_beforeInit, _call_afterInit, _call_initProperties = False, False, False


	def __init__(self, conn, properties=None, *args, **kwargs):
		""" User code should override beforeInit() and/or afterInit() instead."""
		self.__att_try_setFieldVal = False
		# Collection of cursor objects. MUST be defined first.
		self.__cursors = {}
		# PK of the currently-selected cursor
		self.__currentCursorKey = None

		self._dataStructure = None

		# Dictionary holding any default values to apply when a new record is created. This is
		# now the DefaultValues property (used to be self.defaultValues attribute)
		self._defaultValues = {}

		self._beforeInit()
		self._conn = conn

		super(dBizobj, self).__init__(properties=properties, *args, **kwargs)

		cn = self._conn
		if cn:
			# Base cursor class : the cursor class from the db api
			self.dbapiCursorClass = cn.getDictCursorClass()

			# If there are any problems in the createCursor process, an
			# exception will be raised in that method.
			self.createCursor()


		# We need to make sure the cursor is created *before* the call to
		# initProperties()
		self._initProperties()
		self._afterInit()
		self.__att_try_setFieldVal = True


	def _beforeInit(self):
		# Cursor to manage SQL Builder info.
		self._sqlMgrCursor = None
		self._conn = None
		self.__params = ()		# tuple of params to be merged with the sql in the cursor
		self.__children = []		# Collection of child bizobjs
		self._baseClass = dBizobj
		self.__areThereAnyChanges = False	# Used by the isChanged() method.
		# Next two are used by the scan() method.
		self.__scanRestorePosition = True
		self.__scanReverse = False
		# Used by the LinkField property
		self._linkField = ""
		self._parentLinkField = ""
		# Used the the addChildByRelationDict() method to eliminate infinite loops
		self.__relationDictSet = False
		# Do we try to same on the same record during a requery?
		self._restorePositionOnRequery = True

		# Various attributes used for Properties
		self._caption = ""
		self._dataSource = ""
		self._SQL = ""
		self._requeryOnLoad = False
		self._parent  = None
		self._autoPopulatePK = True
		self._keyField = ""
		self._requeryChildOnSave = False
		self._newRecordOnNewParent = False
		self._newChildOnNew = False
		self._fillLinkFromParent = False
		self.exitScan = False

		##########################################
		### referential integrity stuff ####
		##########################################
		### Possible values for each type (not all are relevant for each action):
		### IGNORE - don't worry about the presence of child records
		### RESTRICT - don't allow action if there are child records
		### CASCADE - changes to the parent are cascaded to the children
		self.deleteChildLogic = k.REFINTEG_CASCADE  # child records will be deleted
		self.updateChildLogic = k.REFINTEG_IGNORE   # parent keys can be changed w/o
		                                            # affecting children
		self.insertChildLogic = k.REFINTEG_IGNORE   # child records can be inserted
		                                            # even if no parent record exists.
		##########################################

		self.beforeInit()


	def getTempCursor(self):
		"""Occasionally it is useful to be able to run ad-hoc queries against
		the database. For these queries, where the results are not meant to
		be managed as in regular bizobj/cursor relationships, a temp cursor
		will allow you to run those queries, get the results, and then dispose
		of the cursor.
		"""
		cn = self._conn
		cursorClass = self._getCursorClass(self.dCursorMixinClass,
				self.dbapiCursorClass)
		crs = cn.getCursor(cursorClass)
		crs.BackendObject = cn.getBackendObject()
		crs.setCursorFactory(cn.getCursor, cursorClass)
		return crs
		

	def createCursor(self, key=None):
		""" Create the cursor that this bizobj will be using for data, and store it
		in the dictionary for cursors, with the passed value of 'key' as its dict key.
		For independent bizobjs, that key will be None.

		Subclasses should override beforeCreateCursor() and/or afterCreateCursor()
		instead of overriding this method, if possible. Returning any non-empty value
		from beforeCreateCursor() will prevent the rest of this method from
		executing.
		"""
		if self.__cursors:
			_dataStructure = getattr(self.__cursors[self.__cursors.keys()[0]], "_dataStructure", None)
		else:
			# The first cursor is being created, before DataStructure is assigned.
			_dataStructure = None
		errMsg = self.beforeCreateCursor()
		if errMsg:
			raise dException.dException, errMsg

		cursorClass = self._getCursorClass(self.dCursorMixinClass,
				self.dbapiCursorClass)

		if key is None:
			key = self.__currentCursorKey

		cn = self._conn
		self.__cursors[key] = cn.getCursor(cursorClass)
		self.__cursors[key].setCursorFactory(cn.getCursor, cursorClass)

		crs = self.__cursors[key]
		if _dataStructure is not None:
			crs._dataStructure = _dataStructure
		crs.KeyField = self.KeyField
		crs.Table = self.DataSource
		crs.AutoPopulatePK = self.AutoPopulatePK
		crs.BackendObject = cn.getBackendObject()
		crs.sqlManager = self.SqlManager
		crs.AutoCommit = self.AutoCommit
		crs.setSQL(self.SQL)
		if self.RequeryOnLoad:
			crs.requery()
			self.first()
		self.afterCreateCursor(crs)


	def _getCursorClass(self, main, secondary):
		class cursorMix(main, secondary):
			superMixin = main
			superCursor = secondary
			def __init__(self, *args, **kwargs):
				if hasattr(main, "__init__"):
					apply(main.__init__,(self,) + args, kwargs)
				if hasattr(secondary, "__init__"):
					apply(secondary.__init__,(self,) + args, kwargs)
		return  cursorMix


	def first(self):
		""" Move to the first record of the data set.

		Any child bizobjs will be requeried to reflect the new parent record. If
		there are no records in the data set, an exception will be raised.
		"""
		errMsg = self.beforeFirst()
		if not errMsg:
			errMsg = self.beforePointerMove()
		if errMsg:
			raise dException.dException, errMsg

		self._CurrentCursor.first()
		self.requeryAllChildren()

		self.afterPointerMove()
		self.afterFirst()


	def prior(self):
		""" Move to the prior record of the data set.

		Any child bizobjs will be requeried to reflect the new parent record. If
		there are no records in the data set, an exception will be raised.
		"""
		errMsg = self.beforePrior()
		if not errMsg:
			errMsg = self.beforePointerMove()
		if errMsg:
			raise dException.dException, errMsg

		self._CurrentCursor.prior()
		self.requeryAllChildren()

		self.afterPointerMove()
		self.afterPrior()


	def next(self):
		""" Move to the next record of the data set.

		Any child bizobjs will be requeried to reflect the new parent record. If
		there are no records in the data set, an exception will be raised.
		"""
		errMsg = self.beforeNext()
		if not errMsg:
			errMsg = self.beforePointerMove()
		if errMsg:
			raise dException.dException, errMsg

		self._CurrentCursor.next()
		self.requeryAllChildren()

		self.afterPointerMove()
		self.afterNext()


	def last(self):
		""" Move to the last record of the data set.

		Any child bizobjs will be requeried to reflect the new parent record. If
		there are no records in the data set, an exception will be raised.
		"""
		errMsg = self.beforeLast()
		if not errMsg:
			errMsg = self.beforePointerMove()
		if errMsg:
			raise dException.dException, errMsg

		self._CurrentCursor.last()
		self.requeryAllChildren()

		self.afterPointerMove()
		self.afterLast()


	def saveAll(self, startTransaction=False, topLevel=True):
		""" Iterates through all the records of the bizobj, and calls save()
		for any record that has pending changes.
		"""
		cursor = self._CurrentCursor
		useTransact = startTransaction or topLevel
		if useTransact:
			# Tell the cursor to begin a transaction, if needed.
			cursor.beginTransaction()

		try:
			self.scan(self._saveRowIfChanged, startTransaction=False, topLevel=False)
		except dException.ConnectionLostException, e:
			raise dException.ConnectionLostException, e
		except dException.DBQueryException, e:
			# Something failed; reset things.
			if useTransact:
				cursor.rollbackTransaction()
			# Pass the exception to the UI
			raise dException.DBQueryException, e
		except dException.dException, e:
			if useTransact:
				cursor.rollbackTransaction()
			raise dException.dException, e

		if useTransact:
			cursor.commitTransaction()


	def _saveRowIfChanged(self, startTransaction, topLevel):
		""" Meant to be called as part of a scan loop. That means that we can
		assume that the current record is the one we want to act on. Also, we
		can pass False for the two parameters, since they will have already been
		accounted for in the calling method.
		"""
		if self.isChanged():
			self.save(startTransaction, topLevel)


	def save(self, startTransaction=False, topLevel=True):
		""" Save any changes that have been made in the data set. If the
		save is successful, the save() of all child bizobjs will be
		called as well.
		"""
		cursor = self._CurrentCursor
		errMsg = self.beforeSave()
		if errMsg:
			raise dException.dException, errMsg

		if self.KeyField is None:
			raise dException.dException, _("No key field defined for table: ") + self.DataSource

		# Validate any changes to the data. If there is data that fails
		# validation, an Exception will be raised.
		self._validate()

		useTransact = startTransaction or topLevel
		if useTransact:
			# Tell the cursor to begin a transaction, if needed.
			cursor.beginTransaction()

		# OK, this actually does the saving to the database
		try:
			cursor.save()
			if self.IsAdding:
				# Call the hook method for saving new records.
				self._onSaveNew()

			# Iterate through the child bizobjs, telling them to save themselves.
			for child in self.__children:
				# No need to start another transaction. And since this is a child bizobj,
				# we need to save all rows that have changed.
				child.saveAll(startTransaction=False, topLevel=False)

			# Finish the transaction, and requery the children if needed.
			if useTransact:
				cursor.commitTransaction()
			if self.RequeryChildOnSave:
				self.requeryAllChildren()

			self.setMemento()

		except dException.ConnectionLostException, e:
			raise dException.ConnectionLostException, e

		except dException.NoRecordsException, e:
			# Nothing to roll back; just throw it back for the form to display
			raise dException.NoRecordsException, e

		except dException.DBQueryException, e:
			# Something failed; reset things.
			if useTransact:
				cursor.rollbackTransaction()
			# Pass the exception to the UI
			raise dException.DBQueryException, e

		except dException.dException, e:
			# Something failed; reset things.
			if useTransact:
				cursor.rollbackTransaction()
			# Pass the exception to the UI
			raise dException.dException, e

		# Some backends (Firebird particularly) need to be told to write
		# their changes even if no explicit transaction was started.
		cursor.flush()

		# Two hook methods: one specific to Save(), and one which is called after any change
		# to the data (either save() or delete()).
		self.afterChange()
		self.afterSave()


	def cancelAll(self):
		""" Iterates through all the records, canceling each in turn. """
		self.scan(self.cancel)


	def cancel(self):
		""" Cancel any changes to the current record, reverting the fields
		back to their original values.
		"""
		errMsg = self.beforeCancel()
		if not errMsg:
			errMsg = self.beforePointerMove()
		if errMsg:
			raise dException.dException, errMsg

		# Tell the cursor to cancel any changes
		self._CurrentCursor.cancel()
		# Tell each child to cancel themselves
		for child in self.__children:
			child.cancelAll()
			child.requery()

		self.setMemento()
		self.afterCancel()


	def delete(self, startTransaction=False):
		""" Delete the current row of the data set."""
		cursor = self._CurrentCursor
		errMsg = self.beforeDelete()
		if not errMsg:
			errMsg = self.beforePointerMove()
		if errMsg:
			raise dException.dException, errMsg

		if self.KeyField is None:
			raise dException.dException, _("No key field defined for table: ") + self.DataSource

		if self.deleteChildLogic == k.REFINTEG_RESTRICT:
			# See if there are any child records
			for child in self.__children:
				if child.RowCount > 0:
					raise dException.dException, _("Deletion prohibited - there are related child records.")

		if startTransaction:
			cursor.beginTransaction()

		try:
			cursor.delete()
			if self.RowCount == 0:
				# Hook method for handling the deletion of the last record in the cursor.
				self.onDeleteLastRecord()
			# Now cycle through any child bizobjs and fire their cancel() methods. This will
			# ensure that any changed data they may have is reverted. They are then requeried to
			# populate them with data for the current record in this bizobj.
			for child in self.__children:
				if self.deleteChildLogic == k.REFINTEG_CASCADE:
					child.deleteAll(startTransaction=False)
				else:
					child.cancelAll()
					child.requery()
					
			if startTransaction:
				cursor.commitTransaction()
				
			# Some backends (Firebird particularly) need to be told to write 
			# their changes even if no explicit transaction was started.
			cursor.flush()
			
			self.afterPointerMove()
			self.afterChange()
			self.afterDelete()
		except dException.DBQueryException, e:
			if startTransaction:
				cursor.rollbackTransaction()
			else:
				raise dException.DBQueryException, e
		except StandardError, e:
			cursor.rollbackTransaction()
			raise StandardError, e


	def deleteAll(self, startTransaction=False):
		""" Delete all rows in the data set."""
		while self.RowCount > 0:
			self.first()
			ret = self.delete(startTransaction)


	def execute(self, sql):
		"""Execute the sql on the cursor. Dangerous. Use executeSafe instead."""
		return self._CurrentCursor.execute(sql)


	def executeSafe(self, sql):
		"""Execute the passed SQL using an auxiliary cursor.

		This is considered 'safe', because it won't harm the contents of the
		main cursor.
		"""
		return self._CurrentCursor.executeSafe(sql)


	def getChangedRecordNumbers(self):
		""" Returns a list of record numbers for which isChanged()
		returns True. The changes may therefore not be in the record
		itself, but in a dependent child record.
		"""
		self.__changedRecordNumbers = []
		self.scan(self._listChangedRecordNumbers)
		return self.__changedRecordNumbers


	def _listChangedRecordNumbers(self):
		""" Called from a scan loop. If the current record is changed,
		append the RowNumber to the list.
		"""
		if self.isChanged():
			self.__changedRecordNumbers.append(self.RowNumber)


	def getRecordStatus(self, rownum=None):
		""" Returns a dictionary containing an element for each changed
		field in the specified record (or the current record if none is specified).
		The field name is the key for each element; the value is a 2-element
		tuple, with the first element being the original value, and the second
		being the current value.
		"""
		if rownum is None:
			rownum = self.RowNumber
		return self._CurrentCursor.getRecordStatus(rownum)


	def scan(self, func, *args, **kwargs):
		"""Iterate over all records and apply the passed function to each.

		Set self.exitScan to True to exit the scan on the next iteration.

		If self.__scanRestorePosition is True, the position of the current
		record in the recordset is restored after the iteration. If
		self.__scanReverse is true, the records are processed in reverse order.
		"""
		if self.RowCount <= 0:
			# Nothing to scan!
			return

		# Flag that the function can set to prematurely exit the scan
		self.exitScan = False
		if self.__scanRestorePosition:
			currRow = self.RowNumber
		try:
			if self.__scanReverse:
				recRange = range(self.RowCount-1, -1, -1)
			else:
				recRange = range(self.RowCount)
			for i in recRange:
				self._moveToRowNum(i)
				func(*args, **kwargs)
				if self.exitScan:
					break
		except dException.dException, e:
			if self.__scanRestorePosition:
				self.RowNumber = currRow
			raise dException.dException, e

		if self.__scanRestorePosition:
			try:
				self.RowNumber = currRow
			except:
				# Perhaps the row was deleted; at any rate, leave the pointer
				# at the end of the data set
				row = self.RowCount  - 1
				if row >= 0:
					self.RowNumber = row


	def getFieldNames(self):
		"""Returns a tuple of all the field names in the cursor."""
		flds = self._CurrentCursor.getFields()
		# This is a tuple of 3-tuples; we just want the names
		return tuple([ff[0] for ff in flds])


	def replace(self, field, valOrExpr, scope=None):
		"""Replaces the value of the specified field with the given value
		or expression. All records matching the scope are affected; if
		no scope is specified, all records are affected.

		'valOrExpr' will be treated as a literal value, unless it is prefixed
		with an equals sign. All expressions will therefore be a string
		beginning with '='. Literals can be of any type.
		"""
		self._CurrentCursor.replace(field, valOrExpr, scope=scope)


	def new(self):
		""" Create a new record and populate it with default values. Default
		values are specified in the DefaultValues dictionary.
		"""
		errMsg = self.beforeNew()
		if not errMsg:
			errMsg = self.beforePointerMove()
		if errMsg:
			raise dException.dException, errMsg

		self._CurrentCursor.new()
		# Hook method for things to do after a new record is created.
		self._onNew()

		# Update all child bizobjs
		self.requeryAllChildren()

		if self.NewChildOnNew:
			# Add records to all children set to have records created on a new parent record.
			for child in self.__children:
				if child.NewRecordOnNewParent:
					child.new()

		self.setMemento()
		self.afterPointerMove()
		self.afterNew()


	def setSQL(self, sql=None):
		""" Set the SQL query that will be executed upon requery().

		This allows you to manually override the sql executed by the cursor. If no
		sql is passed, the SQL will get set to the value returned by getSQL().
		"""
		if sql is None:
			# sql not passed; get it from the sql mixin:
			# Set the appropriate child filter on the link field
			self.setChildLinkFilter()

			self.SQL = self.getSQL()
		else:
			# sql passed; set it explicitly
			self.SQL = sql
		# propagate the SQL downward:
		self._CurrentCursor.setSQL(self.SQL)


	def requery(self):
		""" Requery the data set.

		Refreshes the data set with the current values in the database,
		given the current state of the filtering parameters.
		"""
		errMsg = self.beforeRequery()
		if errMsg:
			raise dException.dException, errMsg
		if self.KeyField is None:
			errMsg = _("No Primary Key defined in the Bizobj for %s") % self.DataSource
			raise dException.MissingPKException, errMsg

		# If this is a dependent (child) bizobj, this will enforce the relation
		self.setChildLinkFilter()

		# Hook method for creating the param list
		params = self.getParams()

		# Record this in case we need to restore the record position
		try:
			currPK = self.getPK()
		except dException.NoRecordsException:
			currPK = None

		# run the requery
		cursor = self._CurrentCursor
		try:
			cursor.requery(params)

		except dException.ConnectionLostException, e:
			raise dException.ConnectionLostException, e

		except dException.DBQueryException, e:
			# Something failed; reset things.
			cursor.rollbackTransaction()
			# Pass the exception to the UI
			raise dException.DBQueryException, e

		except dException.dException, e:
			# Something failed; reset things.
			cursor.rollbackTransaction()
			# Pass the exception to the UI
			raise dException.dException, e

		if self.RestorePositionOnRequery:
			self._moveToPK(currPK)

		try:
			self.requeryAllChildren()
		except dException.NoRecordsException:
			pass
		self.setMemento()
		self.afterRequery()


	def setChildLinkFilter(self):
		""" If this is a child bizobj, its record set is dependent on its parent's
		current PK value. This will add the appropriate WHERE clause to
		filter the child records. If the parent is a new, unsaved record,
		there cannot be any child records saved yet, so an empty query
		is built.
		"""
		if self.DataSource and self.LinkField:
			if self.Parent.IsAdding:
				# Parent is new and not yet saved, so we cannot have child records yet.
				filtExpr = " 1 = 0 "
			else:
				if self.ParentLinkField:
					# The link to the parent is something other than the PK
					val = self.escQuote(self.Parent.getFieldVal(self.ParentLinkField))
				else:
					val = self.escQuote(self.getParentPK())
				linkFieldParts = self.LinkField.split(".")
				if len(linkFieldParts) < 2:
					dataSource = self.DataSource
					linkField = self.LinkField
				else:
					# The source table was specified in the LinkField
					dataSource = linkFieldParts[0]
					linkField = linkFieldParts[1]
				filtExpr = " %s.%s = %s " % (dataSource, linkField, val)
			self._CurrentCursor.setChildFilterClause(filtExpr)


	def sort(self, col, ord=None, caseSensitive=True):
		""" Sort the rows based on values in a specified column.

		Called when the data is to be sorted on a particular column
		in a particular order. All the checking on the parameters is done
		in the cursor.
		"""
		try:
			cc = self._CurrentCursor
		except:
			cc = None
		if cc is not None:
			self._CurrentCursor.sort(col, ord, caseSensitive)


	def setParams(self, params):
		""" Set the query parameters for the cursor.

		Accepts a tuple that will be merged with the sql statement using the
		cursor's standard method for merging.
		"""
		self.__params = params


	def _validate(self):
		""" Internal method. User code should override validateRecord().

		_validate() is called by the save() routine before saving any data.
		If any data fails validation, an exception will be raised, and the
		save() will not be allowed to proceed.
		"""
		errMsg = ""
		if self.isChanged():
			# No need to validate if the data hasn't changed
			message = self.validateRecord()
			if message:
				errMsg += message
		if errMsg:
			raise dException.BusinessRuleViolation, errMsg


	def validateRecord(self):
		""" Hook for subclass business rule validation code.

		This is the method that you should customize in your subclasses
		to create checks on the data entered by the user to be sure that it
		conforms to your business rules. Your validation code should return
		an error message that describes the reason why the data is not
		valid; this message will be propagated back up to the UI where it can
		be displayed to the user so that they can correct the problem.
		Example:

			if not myNonEmptyField:
				return "MyField must not be blank"

		It is assumed that we are on the correct record for testing before
		this method is called.
		"""
		pass


	def fieldValidation(self, fld, val):
		"""This is called by the form when a control that is marked for field-
		level validation loses focus. It handles communication between the
		bizobj methods and the form. When creating Dabo apps, if you want
		to add field-level validation rules, you should override fieldValidation()
		with your specific code.
		"""
		errMsg = ""
		message = self.validateField(fld, val)
		if message:
			errMsg += message
		if errMsg:
			raise dException.BusinessRuleViolation, errMsg


	def validateField(self, fld, val):
		"""This is the method to override if you need field-level validation
		to your app. It will receive the field name and the new value; you can
		then apply your business rules to determine if the new value is
		valid. If not, return a string describing the problem. Any non-empty
		return value from this method will prevent the control's value
		from being changed.
		"""
		pass


	def _moveToRowNum(self, rownum, updateChildren=True):
		""" For internal use only! Should never be called from a developer's code.
		It exists so that a bizobj can move through the records in its cursor
		*without* firing additional code.
		"""
		self._CurrentCursor.moveToRowNum(rownum)
		if updateChildren:
			pk = self.getPK()
			for child in self.__children:
				# Let the child know the current dependent PK
				child.setCurrentParent(pk)


	def _moveToPK(self, pk, updateChildren=True):
		""" For internal use only! Should never be called from a developer's code.
		It exists so that a bizobj can move through the records in its cursor
		*without* firing additional code.
		"""
		self._CurrentCursor.moveToPK(pk)
		if updateChildren:
			for child in self.__children:
				# Let the child know the current dependent PK
				child.setCurrentParent(pk)


	def seek(self, val, fld=None, caseSensitive=False,
			near=False, runRequery=False):
		""" Search for a value in a field, and move the record pointer to the match.

		Used for searching of the bizobj's cursor for a particular value in a
		particular field. Can be optionally case-sensitive.

		If 'near' is True, and no exact match is found in the cursor, the cursor's
		record pointer will be placed at the record whose value in that field
		is closest to the desired value without being greater than the requested
		value.

		If runRequery is True, and the record pointer is moved, all child bizobjs
		will be requeried, and the afterPointerMove() hook method will fire.

		Returns the RowNumber of the found record, or -1 if no match found.
		"""
		ret = self._CurrentCursor.seek(val, fld, caseSensitive, near)
		if ret != -1:
			if runRequery:
				self.requeryAllChildren()
				self.afterPointerMove()
		return ret


	def isAnyChanged(self):
		""" Returns True if any record in the current record set has been
		changed.
		"""
		self.__areThereAnyChanges = False
		self.scan(self._checkForChanges)
		return self.__areThereAnyChanges


	def _checkForChanges(self):
		""" Designed to be called from the scan iteration over the records
		for this bizobj. Once one changed record is found, set the scan's
		exit flag, since we only need to know if anything has changed.
		"""
		if self.isChanged():
			self.__areThereAnyChanges = True
			self.exitScan = True


	def isChanged(self):
		""" Return True if data has changed in this bizobj and any children.

		By default, only the current record is checked. Call isAnyChanged() to
		check all records.
		"""
		try:
			cc = self._CurrentCursor
		except:
			cc = None
		if cc is None:
			# No cursor, no changes.
			return False
		ret = cc.isChanged(allRows = False)

		if not ret:
			# see if any child bizobjs have changed
			for child in self.__children:
				ret = child.isAnyChanged()
				if ret:
					break
		return ret


	def onDeleteLastRecord(self):
		""" Hook called when the last record has been deleted from the data set."""
		pass


	def _onSaveNew(self):
		""" Called after successfully saving a new record."""
		# If this is a new parent record with a new auto-generated PK, pass it on
		# to the children before they save themselves.
		if self.AutoPopulatePK:
			pk = self.getPK()
			for child in self.__children:
				child.setParentFK(pk)
		# Call the custom hook method
		self.onSaveNew()


	def onSaveNew(self):
		""" Hook method called after successfully saving a new record."""
		pass


	def _onNew(self):
		""" Populate the record with any default values.

		User subclasses should leave this alone and instead override onNew().
		"""
		cursor = self._CurrentCursor
		cursor.setDefaults(self.DefaultValues)
		if self.AutoPopulatePK:
			# Provide a temporary PK so that any linked children can be properly
			# identified until the record is saved and a permanent PK is obtained.
			cursor.genTempAutoPK()
		# Fill in the link to the parent record
		if self.Parent and self.FillLinkFromParent and self.LinkField:
			self.setParentFK()
		# Call the custom hook method
		self.onNew()


	def onNew(self):
		""" Hook method called after the default values have been set in onNew()."""
		pass


	def setParentFK(self, val=None):
		""" Accepts and sets the foreign key value linking to the
		parent table for all records.
		"""
		if self.LinkField:
			if val is None:
				val = self.getParentPK()
			self.scan(self._setParentFK, val)

	def _setParentFK(self, val):
		self.setFieldVal(self.LinkField, val)


	def setCurrentParent(self, val=None):
		""" Lets dependent child bizobjs know the current value of their parent
		record.
		"""
		if self.LinkField:
			if val is None:
				val = self.getParentPK()
			# Update the key value for the cursor
			self.__currentCursorKey = val
			# Make sure there is a cursor object for this key.
			self._CurrentCursor = val


	def addChild(self, child):
		""" Add the passed child bizobj to this bizobj.

		During the creation of the form, child bizobjs are added by the parent.
		This stores the child reference here, and sets the reference to the
		parent in the child.
		"""
		if child not in self.__children:
			self.__children.append(child)
			child.Parent = self


	def addChildByRelationDict(self, dict, bizModule):
		""" Accepts a dictionary containing relationship information
		If any of the entries pertain to this bizobj, it will check to make
		sure that the child bizobj is already added, or add it and set the
		relationship if it isn't. It then passes the dict on to the child to
		allow the child to set up its relationships.

		Returns a list containing all added child bizobjs. The list will
		be empty if none were added.
		"""
		addedChildren = []
		if self.__relationDictSet:
			# already done this...
			return addedChildren
		self.__relationDictSet = True

		myRelations = [ dict[k] for k in dict.keys()
				if dict[k]["source"].lower() == self.DataSource.lower() ]
		if not myRelations:
			return addedChildren

		for relation in myRelations:
			if relation["relationType"] == "1M":
				# Each 'relation' is a dict with the following structure:
				# 'target': child table
				# 'targetField': field in child table linked to parent
				# 'source': parent table
				# 'sourceField': field in parent table linked to child
				target = relation["target"]
				targetField = relation["targetField"]
				source = relation["source"]
				sourceField = relation["sourceField"]

				if self.getAncestorByDataSource(target):
					# The 'child' already exists as an ancestor of this bizobj. This can
					# happen in many-to-many relationships. We don't want to add it,
					# as this creates infinite loops.
					continue

				childBiz = self.getChildByDataSource(target)
				if not childBiz:
					# target is the datasource of the bizobj to find.
					childBizClass = None
					for candidate, candidateClass in bizModule.__dict__.items():
						if type(candidateClass) == type:
							candidateInstance = candidateClass(self._conn)
							if candidateInstance.DataSource.lower() == target.lower():
								childBizClass = candidateClass

					childBiz = childBizClass(self._conn)
					self.addChild(childBiz)
					addedChildren.append(childBiz)
					childBiz.LinkField = targetField
					childBiz.FillLinkFromParent = True
					if sourceField != self.KeyField:
						childBiz.ParentLinkField = sourceField
				# Now pass this on to the child
				addedGrandChildren = childBiz.addChildByRelationDict(dict, bizModule)
				for gc in addedGrandChildren:
					addedChildren.append(gc)
		return addedChildren


	def getAncestorByDataSource(self, ds):
		ret = None
		if self.Parent:
			if self.Parent.DataSource == ds:
				ret = self.Parent
			else:
				ret = self.Parent.getAncestorByDataSource(ds)
		return ret


	def requeryAllChildren(self):
		""" Requery each child bizobj's data set.

		Called to assure that all child bizobjs have had their data sets
		refreshed to match the current master row. This will normally happen
		automatically when appropriate, but user code may call this as well
		if needed.
		"""
		if len(self.__children) == 0:
			return True

		errMsg = self.beforeChildRequery()
		if errMsg:
			raise dException.dException, errMsg

		pk = self.getPK()
		for child in self.__children:
			# Let the child know the current dependent PK
			child.setCurrentParent(pk)
			if not child.isChanged() and child.RequeryWithParent:
				child.requery()

		self.afterChildRequery()


	def getPK(self):
		""" Return the value of the PK field."""
		if self.KeyField is None:
			raise dException.dException, _("No key field defined for table: ") + self.DataSource
		cc = self._CurrentCursor
		return cc.getFieldVal(cc.KeyField)


	def getParentPK(self):
		""" Return the value of the parent bizobjs' PK field.

		Alternatively, user code can just call self.Parent.getPK().
		"""
		try:
			return self.Parent.getPK()
		except dException.NoRecordsException:
			# The parent bizobj has no records
			return None


	def getFieldVal(self, fld, row=None):
		""" Return the value of the specified field in the current or specified row."""
		cursor = self._CurrentCursor
		if cursor is not None:
			return cursor.getFieldVal(fld, row)
		else:
			return None


	def setFieldVal(self, fld, val):
		""" Set the value of the specified field in the current row."""
		cursor = self._CurrentCursor
		if cursor is not None:
			if fld in [f[0] for f in self.DataStructure]:
				try:
					return cursor.setFieldVal(fld, val)
				except dException.NoRecordsException:
					return False
			else:
				## Can't do the line below like I'd like because setFieldVal() runs from
				## __setattr__() and we could be processing fld's with values like "UserSQL"...
				#raise dException.FieldNotFoundException, "Field %s not defined in the DataStructure" % fld
				pass
		# If the field doesn't exist in the datastructure, or if there isn't a
		# CurrentCursor, return False to let __setattr__ know that the attribute
		# should get set to the instance. Note: we should get rid of the 
		# __getattr__ and __setattr__ way for resolving db fields, as it is really
		# hard to debug and doesn't perform particularly well.
		return False


	def getDataSet(self, flds=(), rowStart=0, rows=None):
		""" Get the entire data set encapsulated in a list.

		If the optional	'flds' parameter is given, the result set will be filtered
		to only include the specified fields. rowStart specifies the starting row
		to include, and rows is the number of rows to return.
		"""
		ret = None
		try:
			cc = self._CurrentCursor
		except:
			cc = None
		if cc is not None:
			ret = self._CurrentCursor.getDataSet(flds, rowStart, rows)
		return ret


	def getDataStructure(self):
		""" Gets the structure of the DataSource table. Returns a list
		of 3-tuples, where the 3-tuple's elements are:
			0: the field name (string)
			1: the field type ('I', 'N', 'C', 'M', 'B', 'D', 'T')
			2: boolean specifying whether this is a pk field.
		"""
		return self._CurrentCursor.getFields(self.DataSource)


	def getDataStructureFromDescription(self):
		""" Gets the structure of the DataSource table. Returns a list
		of 3-tuples, where the 3-tuple's elements are:
			0: the field name (string)
			1: the field type ('I', 'N', 'C', 'M', 'B', 'D', 'T')
			2: boolean specifying whether this is a pk field.
		"""
		return self._CurrentCursor.getFieldInfoFromDescription()


	def getParams(self):
		""" Return the parameters to send to the cursor's execute method.

		This is the place to define the parameters to be used to modify
		the SQL statement used to produce the record set. If the cursor for
		this bizobj does not need parameters, leave this as is. Otherwise,
		override this method to return a tuple to be passed to the cursor, where
		it will be used to modify the query using standard printf syntax.
		"""
		return self.__params


	def setMemento(self):
		""" Take a snapshot of the data in the cursor.

		Tell the cursor to take a snapshot of the current state of the
		data. This snapshot will be used to determine what, if anything, has
		changed later on.

		User code should not normally call this method.
		"""
		self._CurrentCursor.setMemento()


	def getChildren(self):
		""" Return a tuple of the child bizobjs."""
		ret = []
		for child in self.__children:
			ret.append(child)
		return tuple(ret)


	def getChildByDataSource(self, dataSource):
		""" Return a reference to the child bizobj with the passed dataSource."""
		ret = None
		for child in self.getChildren():
			if child.DataSource == dataSource:
				ret = child
				break
		return ret


	def escQuote(self, val):
		""" Escape special characters in SQL strings.

		Escapes any single quotes that could cause SQL syntax errors. Also
		escapes backslashes, since they have special meaning in SQL parsing.
		Finally, wraps the value in single quotes.
		"""
		return self._CurrentCursor.escQuote(val)


	def formatForQuery(self, val):
		""" Wrap up any value(int, long, string, date, date-time, decimal, none)
		for use to be in a query.
		"""
		return self._CurrentCursor.formatForQuery(val)


	def formatDateTime(self, val):
		""" Wrap a date or date-time value in the format
		required by the backend.
		"""
		return self._CurrentCursor.formatDateTime(val)


	def moveToRowNumber(self, rowNumber):
		""" Move to the specified row number."""
		self.RowNumber = rowNumber


	def getWordMatchFormat(self):
		return self._CurrentCursor.getWordMatchFormat()



	########## SQL Builder interface section ##############
	def addField(self, exp):
		return self._CurrentCursor.addField(exp)
	def addFrom(self, exp):
		return self._CurrentCursor.addFrom(exp)
	def addGroupBy(self, exp):
		return self._CurrentCursor.addGroupBy(exp)
	def addOrderBy(self, exp):
		return self._CurrentCursor.addOrderBy(exp)
	def addWhere(self, exp, comp="and"):
		return self._CurrentCursor.addWhere(exp)
	def getSQL(self):
		return self._CurrentCursor.getSQL()
	def setFieldClause(self, clause):
		return self._CurrentCursor.setFieldClause(clause)
	def setFromClause(self, clause):
		return self._CurrentCursor.setFromClause(clause)
	def setGroupByClause(self, clause):
		return self._CurrentCursor.setGroupByClause(clause)
	def setLimitClause(self, clause):
		return self._CurrentCursor.setLimitClause(clause)
	def setOrderByClause(self, clause):
		return self._CurrentCursor.setOrderByClause(clause)
	def setWhereClause(self, clause):
		return self._CurrentCursor.setWhereClause(clause)
	def prepareWhere(self, clause):
		return self._CurrentCursor.prepareWhere(clause)





	########## Pre-hook interface section ##############
	def beforeNew(self): return ""
	def beforeDelete(self): return ""
	def beforeFirst(self): return ""
	def beforePrior(self): return ""
	def beforeNext(self): return ""
	def beforeLast(self): return ""
	def beforeSetRowNumber(self): return ""
	def beforePointerMove(self): return ""
	def beforeSave(self): return ""
	def beforeCancel(self): return ""
	def beforeRequery(self): return ""
	def beforeChildRequery(self): return ""
	def beforeCreateCursor(self): return ""
	########## Post-hook interface section ##############
	def afterNew(self): pass
	def afterDelete(self): pass
	def afterFirst(self): pass
	def afterPrior(self): pass
	def afterNext(self): pass
	def afterLast(self): pass
	def afterSetRowNumber(self): pass
	def afterPointerMove(self): pass
	def afterSave(self): pass
	def afterCancel(self): pass
	def afterRequery(self): pass
	def afterChildRequery(self): pass
	def afterChange(self): pass
	def afterCreateCursor(self, cursor): pass


	def _getAutoCommit(self):
		return self._CurrentCursor.AutoCommit

	def _setAutoCommit(self, val):
		self._CurrentCursor.AutoCommit = val


	def _getAutoPopulatePK(self):
		try:
			return self._autoPopulatePK
		except AttributeError:
			return True

	def _setAutoPopulatePK(self, val):
		self._autoPopulatePK = bool(val)
		if self._CurrentCursor:
			self._CurrentCursor.AutoPopulatePK= val


	def _getAutoSQL(self):
		try:
			return self._CurrentCursor.getSQL()
		except:
			return None


	def _getCaption(self):
		try:
			return self._caption
		except AttributeError:
			return self.DataSource

	def _setCaption(self, val):
		self._caption = str(val)


	def _getCurrentSQL(self):
		try:
			v = self._CurrentCursor.CurrentSQL
		except AttributeError:
			return None


	def _getCurrentCursor(self):
		try:
			return self.__cursors[self.__currentCursorKey]
		except (KeyError, AttributeError):
			# There is no current cursor. Try creating one.
			self.createCursor()
			try:
				return self.__cursors[self.__currentCursorKey]
			except KeyError:
				return None

	def _setCurrentCursor(self, val):
		""" Sees if there is a cursor in the cursors dict with a key that matches
		the current parent key. If not, creates one.
		"""
		self.__currentCursorKey = val
		if not self.__cursors.has_key(val):
			self.createCursor()


	def _getDataSource(self):
		try:
			return self._dataSource
		except AttributeError:
			return ""

	def _setDataSource(self, val):
		self._dataSource = str(val)
		cursor = self._CurrentCursor
		if cursor is not None:
			cursor.Table = val


	def _getDataStructure(self):
		# We need to save the explicitly-assigned DataStructure here in the bizobj,
		# so that we are able to propagate it to any future-assigned child cursors.
		_ds = self._dataStructure
		if _ds is not None:
			return _ds
		return self._CurrentCursor.DataStructure

	def _setDataStructure(self, val):
		for key, cursor in self.__cursors.items():
			cursor.DataStructure = val
		self._dataStructure = val

	def _getDefaultValues(self):
		return self._defaultValues

	def _setDefaultValues(self, val):
		self._defaultValues = val


	def _getEncoding(self):
		ret = None
		cursor = self._CurrentCursor
		if cursor is not None:
			ret = cursor.Encoding
		if ret is None:
			if self.Application:
				ret = self.Application.Encoding
			else:
				ret = dabo.defaultEncoding
		return ret

	def _setEncoding(self, val):
		cursor = self._CurrentCursor
		if cursor is not None:
			cursor.Encoding = val


	def _getFillLinkFromParent(self):
		try:
			return self._fillLinkFromParent
		except AttributeError:
			return False

	def _setFillLinkFromParent(self, val):
		self._fillLinkFromParent = bool(val)


	def _isAdding(self):
		return self._CurrentCursor.IsAdding


	def _getKeyField(self):
		try:
			return self._keyField
		except AttributeError:
			return ""

	def _setKeyField(self, val):
		self._keyField = val
		cursor = self._CurrentCursor
		if cursor is not None:
			cursor.KeyField = val


	def _getLastSQL(self):
		try:
			v = self._CurrentCursor.LastSQL
		except AttributeError:
			v = None
		return v


	def _getLinkField(self):
		try:
			return self._linkField
		except AttributeError:
			return ""

	def _setLinkField(self, val):
		self._linkField = str(val)


	def _getNewChildOnNew(self):
		try:
			return self._newChildOnNew
		except AttributeError:
			return False

	def _setNewChildOnNew(self, val):
		self._newChildOnNew = bool(val)


	def _getNewRecordOnNewParent(self):
		try:
			return self._newRecordOnNewParent
		except AttributeError:
			return False

	def _setNewRecordOnNewParent(self, val):
		self._newRecordOnNewParent = bool(val)


	def _getNonUpdateFields(self):
		return self._CurrentCursor.getNonUpdateFields()

	def _setNonUpdateFields(self, fldList=None):
		if fldList is None:
			fldList = []
		self._CurrentCursor.setNonUpdateFields(fldList)


	def _getParent(self):
		try:
			return self._parent
		except AttributeError:
			return None

	def _setParent(self, val):
		if isinstance(val, dBizobj):
			self._parent = val
		else:
			raise TypeError, _("Parent must descend from dBizobj")


	def _getParentLinkField(self):
		try:
			return self._parentLinkField
		except AttributeError:
			return ""

	def _setParentLinkField(self, val):
		self._parentLinkField = str(val)


	def _getRecord(self):
		return self._CurrentCursor.Record


	def _getRequeryChildOnSave(self):
		try:
			return self._requeryChildOnSave
		except AttributeError:
			return False

	def _setRequeryChildOnSave(self, val):
		self._requeryChildOnSave = bool(val)


	def _getRequeryOnLoad(self):
		try:
			ret = self._requeryOnLoad
		except AttributeError:
			ret = False
		return ret

	def _setRequeryOnLoad(self, val):
		self._requeryOnLoad = bool(val)


	def _getRestorePositionOnRequery(self):
		try:
			return self._restorePositionOnRequery
		except AttributeError:
			return True

	def _setRestorePositionOnRequery(self, val):
		self._restorePositionOnRequery = bool(val)


	def _getRequeryWithParent(self):
		v = getattr(self, "_requeryWithParent", None)
		if v is None:
			v = self._requeryWithParent = True
		return v

	def _setRequeryWithParent(self, val):
		self._requeryWithParent = bool(val)


	def _getRowCount(self):
		try:
			ret = self._CurrentCursor.RowCount
		except:
			ret = None
		return ret


	def _getRowNumber(self):
		try:
			ret = self._CurrentCursor.RowNumber
		except:
			ret = None
		return ret

	def _setRowNumber(self, rownum):
		errMsg = self.beforeSetRowNumber()
		if not errMsg:
			errMsg = self.beforePointerMove()
		if errMsg:
			raise dException.dException, errMsg
		self._moveToRowNum(rownum)
		self.requeryAllChildren()
		self.afterPointerMove()
		self.afterSetRowNumber()


	def _getSQL(self):
		try:
			return self._SQL
		except AttributeError:
			return ""

	def _setSQL(self, val):
		self._SQL = val
		cursor = self._CurrentCursor
		if cursor is not None:
			cursor.setSQL(val)


	def _getSqlMgr(self):
		if self._sqlMgrCursor is None:
			cursorClass = self._getCursorClass(self.dCursorMixinClass,
					self.dbapiCursorClass)
			cn = self._conn
			crs = self._sqlMgrCursor = cn.getCursor(cursorClass)
			crs.setCursorFactory(cn.getCursor, cursorClass)
			crs.KeyField = self.KeyField
			crs.Table = self.DataSource
			crs.AutoPopulatePK = self.AutoPopulatePK
			crs.BackendObject = cn.getBackendObject()
		return self._sqlMgrCursor


	def _getUserSQL(self):
		try:
			v = self._CurrentCursor.UserSQL
		except AttributeError:
			v = None
		return v

	def _setUserSQL(self, val):
		self._CurrentCursor.UserSQL = val



	### -------------- Property Definitions ------------------  ##
	AutoCommit = property(_getAutoCommit, _setAutoCommit, None,
			_("Do we need explicit begin/commit/rollback commands for transactions?  (bool)"))

	AutoPopulatePK = property(_getAutoPopulatePK, _setAutoPopulatePK, None,
			_("Determines if we are using a table that auto-generates its PKs. (bool)"))

	AutoSQL = property(_getAutoSQL, None, None,
			_("Returns the SQL statement automatically generated by the sql manager."))

	Caption = property(_getCaption, _setCaption, None,
			_("The friendly title of the cursor, used in messages to the end user. (str)"))

	CurrentSQL = property(_getCurrentSQL, None, None,
			_("Returns the current SQL that will be run, which is one of UserSQL or AutoSQL."))

	_CurrentCursor = property(_getCurrentCursor, _setCurrentCursor, None,
			_("The cursor object for the currently selected key value. (dCursorMixin child)"))

	DataSource = property(_getDataSource, _setDataSource, None,
			_("The title of the cursor. Used in resolving DataSource references. (str)"))

	DataStructure = property(_getDataStructure, _setDataStructure, None,
			_("""Returns the structure of the cursor in a tuple of 6-tuples.

				0: field alias (str)
				1: data type code (str)
				2: pk field (bool)
				3: table name (str)
				4: field name (str)
				5: field scale (int or None)

				This information will try to come from a few places, in order:
				1) The explicitly-set DataStructure property
				2) The backend table method"""))
     
	DefaultValues = property(_getDefaultValues, _setDefaultValues, None,
			_("""A dictionary specifying default values for fields when a new record is added.

			The values of the dictionary can be literal (must match the field type), or
			they can be a function object which will be called when the new record is added
			to the bizobj."""))

	Encoding = property(_getEncoding, _setEncoding, None,
			_("Name of encoding to use for unicode  (str)") )

	FillLinkFromParent = property(_getFillLinkFromParent, _setFillLinkFromParent, None,
			_("""In the onNew() method, do we fill in the linkField with the value returned
			by calling the parent bizobj\'s GetKeyValue() method? (bool)"""))

	IsAdding = property(_isAdding, None, None,
			_("Returns True if the current record is new and unsaved."))

	KeyField = property(_getKeyField, _setKeyField, None,
			_("""Name of field that is the PK. If multiple fields make up the key,
			separate the fields with commas. (str)"""))

	LastSQL = property(_getLastSQL, None, None,
			_("Returns the last executed SQL statement."))

	LinkField = property(_getLinkField, _setLinkField, None,
			_("Name of the field that is the foreign key back to the parent. (str)"))

	NewChildOnNew = property(_getNewChildOnNew, _setNewChildOnNew, None,
			_("Should new child records be added when a new parent record is added? (bool)"))

	NewRecordOnNewParent = property(_getNewRecordOnNewParent, _setNewRecordOnNewParent, None,
			_("If this bizobj\'s parent has NewChildOnNew==True, do we create a record here? (bool)"))

	NonUpdateFields = property(_getNonUpdateFields, _setNonUpdateFields, None,
			_("Fields in the cursor to be ignored during updates"))

	Parent = property(_getParent, _setParent, None,
			_("Reference to the parent bizobj to this one. (dBizobj)"))

	ParentLinkField = property(_getParentLinkField, _setParentLinkField, None,
			_("""Name of the field in the parent table that is used to determine child
			records. If empty, it is assumed that the parent's PK is used  (str)"""))

	Record = property(_getRecord, None, None,
			_("""Represents a record in the data set. You can address individual
			columns by referring to 'self.Record.fieldName' (read-only) (no type)"""))
	
	RequeryChildOnSave = property(_getRequeryChildOnSave, _setRequeryChildOnSave, None,
			_("Do we requery child bizobjs after a Save()? (bool)"))

	RequeryOnLoad = property(_getRequeryOnLoad, _setRequeryOnLoad, None,
			_("""When true, the cursor object runs its query immediately. This
			is useful for lookup tables or fixed-size (small) tables. (bool)"""))

	RequeryWithParent = property(_getRequeryWithParent, _setRequeryWithParent, None,
			_("""Specifies whether a child bizobj gets requeried automatically.

				When True (the default) moving the record pointer or requerying the
				parent bizobj will result in the child bizobj's getting requeried
				as well. When False, user code will have to manually call
				child.requery() at the appropriate time.
				"""))

	RestorePositionOnRequery = property(_getRestorePositionOnRequery, _setRestorePositionOnRequery, None,
			_("After a requery, do we try to restore the record position to the same PK?"))

	RowCount = property(_getRowCount, None, None,
			_("""The number of records in the cursor's data set. It will be -1 if the
			cursor hasn't run any successful queries yet. (int)"""))

	RowNumber = property(_getRowNumber, _setRowNumber, None,
			_("The current position of the record pointer in the result set. (int)"))

	SQL = property(_getSQL, _setSQL, None,
			_("SQL statement used to create the cursor\'s data. (str)"))

	SqlManager = property(_getSqlMgr, None, None,
			_("Reference to the cursor that handles SQL Builder information (cursor)") )

	UserSQL = property(_getUserSQL, _setUserSQL, None,
			_("SQL statement to run. If set, the automatic SQL builder will not be used."))
