import xml.sax

class specHandler(xml.sax.ContentHandler):
	def __init__(self):
		self.appDict = {}
		self.relaDict = {}
		self.currTableDict = {}
		self.currTable = ""
		self.currFieldDict = {}
	
	def startElement(self, name, attrs):
		if name == "table":
			# New table starting
			self.currTable = attrs.getValue("name")
			self.currTableDict = {}
			self.currFieldDict = {}
			self.currRelaDict = {}

		elif name == "field":
			for att in attrs.keys():
				if att == "name":
					fldName = attrs.getValue("name")
				else:
					self.currFieldDict[att] = attrs.getValue(att)
			self.currTableDict[fldName] = self.currFieldDict.copy()
			
		elif name == "relation":
			relType = attrs.getValue("relationType")
			if relType == "1M":
				nm = attrs.getValue("name")
				self.relaDict[nm] = {}
				self.relaDict[nm]["relationType"] = "1M"
				self.relaDict[nm]["source"] = nm.split(":")[0].strip()
				self.relaDict[nm]["target"] = attrs.getValue("target")
				self.relaDict[nm]["sourceField"] = attrs.getValue("sourceField")
				self.relaDict[nm]["targetField"] = attrs.getValue("targetField")
			
	
	def endElement(self, name):
		if name == "table":
			# Save it to the app dict
			self.appDict[self.currTable] = self.currTableDict.copy()
	
	def getFieldDict(self):
		return self.appDict
	
	def getRelationDict(self):
		return self.relaDict
	

def importFieldSpecs(file=None, tbl=None):
	if file is None:
		return None
	sh = specHandler()
	xml.sax.parse(file, sh)
	ret = sh.getFieldDict()
	
	# Limit it to a specific table if requested
	if tbl is not None:
		ret = ret[tbl]
	
	return ret
	

def importRelationSpecs(file=None):
	if file is None:
		return None
	sh = specHandler()
	xml.sax.parse(file, sh)
	ret = sh.getRelationDict()
	
	return ret
