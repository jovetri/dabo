# -*- coding: utf-8 -*-

# This serves as a catch-all script for common utilities that may be used
# in lots of places throughout Dabo. Typically, to use a function 'foo()' in
# this file, add the following import statement to your script:
#
#	import dabo.lib.utils as utils
# 
# Then, in your code, simply call:
#
#	utils.foo()

import os
import sys
import dabo
try:
	from win32com.shell import shell, shellcon
except ImportError:
	shell, shellcon = None, None


# can't compare NoneType to some types: sort None lower than anything else:
def noneSort(vv, ww):
	xx, yy = vv[0], ww[0]
	if xx is None and yy is None:
		return 0
	if xx is None and yy is not None:
		return -1
	if xx is not None and yy is None:
		return 1
	return cmp(xx, yy)

def caseInsensitiveSort(vv, ww):
	vv, ww = vv[0], ww[0]
	if vv is None:
		vv = ""
	if ww is None:
		ww = ""
	return cmp(vv.lower(), ww.lower())

def reverseText(tx):
	"""Takes a string and returns it reversed. Example:
	
	utils.reverseText("Wow, this is so cool!")
		=> returns "!looc os si siht ,woW"
	"""
	return tx[::-1]


def getUserHomeDirectory():
	"""Return the user's home directory in a platform-portable way.

	If the home directory cannot be determined, return None.
	"""
	hd = None

	# If we are on Windows and win32com is available, get the user home
	# directory using the Windows API:
	if shell and shellcon:
		return shell.SHGetFolderPath(0, shellcon.CSIDL_PROFILE, 0, 0)

	# os.path.expanduser should work on all posix systems (*nix, Mac, and some
	# Windows NT setups):
	try:
		hd = os.path.expanduser("~")
	except:
		pass

	# If for some reason the posix function above didn't work, most Linux setups
	# define the environmental variable $HOME, and perhaps this is done sometimes
	# on Mac and Win as well:
	if hd is None:
		hd = os.environ.get("HOME")

	# If we still haven't found a value, Windows tends to define a $USERPROFILE
	# directory, which usually expands to something like
	#	 c:\Documents and Settings\maryjane
	if hd is None:
		hd = os.environ.get("USERPROFILE")

	return hd


def getUserAppDataDirectory(appName="Dabo"):
	"""Return the directory where Dabo can save user preference and setting information.

	On *nix, this will be something like /home/pmcnett/.dabo
	On Windows, it will be more like c:\Documents and Settings\pmcnett\Application Data\Dabo

	This function relies on platform conventions to determine this information. If it
	cannot be determined (because platform conventions were circumvented), the return
	value will be None.

	if appName is passed, the directory will be named accordingly.

	This function will try to create the directory if it doesn't already exist, but if the
	creation of the directory fails, the return value will revert to None.
	"""
	dd = None

	if sys.platform not in ("win32",):
		# On Unix, change appname to lower, don't allow spaces, and prepend a ".":
		appName = ".%s" % appName.lower().replace(" ", "_")

	# First, on Windows, try the Windows API function:
	if shell and shellcon:
		dd = shell.SHGetFolderPath(0, shellcon.CSIDL_APPDATA, 0, 0)
	
	if dd is None and sys.platform == "win32":
		# We are on Windows, but win32com wasn't installed. Look for the APPDATA
		# environmental variable:
		dd = os.environ.get("APPDATA")

	if dd is None:
		# We are either not on Windows, or we couldn't locate the directory for 
		# whatever reason. Try going off the home directory:
		dd = getUserHomeDirectory()

	if dd is not None:
		dd = os.path.join(dd, appName)
		if not os.path.exists(dd):
			# try to create the dabo directory:
			try:
				os.makedirs(dd)
			except:
				sys.stderr.write("Couldn't create the user setting directory (%s)." % dd)
				dd = None
	return dd
	
	
def dictStringify(dct):
	"""The ability to pass a properties dict to an object relies on
	the practice of passing '**properties' to a function. Seems that 
	Python requires that the keys in any dict being expanded like
	this be strings, not unicode. This method returns a dict with all
	unicode keys changed to strings.
	"""
	ret = {}
	for kk, vv in dct.items():
		if isinstance(kk, unicode):
			try:
				ret[str(kk)] = vv
			except UnicodeEncodeError:
				kk = kk.encode(dabo.defaultEncoding)
				ret[kk] = vv
		else:
			ret[kk] = vv
	return ret
		

def relativePathList(toLoc, fromLoc=None):
	"""Given two paths, returns a list that, when joined with 
	os.path.sep, gives the relative path from 'fromLoc' to
	"toLoc'. If 'fromLoc' is not specified, the current directory
	is assumed.
	"""
	if fromLoc is None:
		fromLoc = os.getcwd()
	if toLoc.startswith(".."):
		if os.path.isdir(fromLoc):
			toLoc = os.path.join(fromLoc, toLoc)
		else:
			toLoc = os.path.join(os.path.split(fromLoc)[0], toLoc)
	toLoc = os.path.abspath(toLoc)
	if os.path.isfile(toLoc):
		toDir, toFile = os.path.split(toLoc)
	else:
		toDir = toLoc
		toFile = ""
	fromLoc = os.path.abspath(fromLoc)
	if os.path.isfile(fromLoc):
		fromLoc = os.path.split(fromLoc)[0]
	fromList = fromLoc.split(os.path.sep)
	toList = toDir.split(os.path.sep)
	# There can be empty strings from the split
	while len(fromList) > 0 and not fromList[0]:
		fromList.pop(0)
	while len(toList) > 0 and not toList[0]:
		toList.pop(0)
	lev = 0
	while (len(fromList) > lev) and (len(toList) > lev) and \
			(fromList[lev] == toList[lev]):
		lev += 1
	
	# 'lev' now contains the first level where they differ
	fromDiff = fromList[lev:]
	toDiff = toList[lev:]
	ret = [".."] * len(fromDiff) + toDiff
	if toFile:
		ret += [toFile]
	return ret


def relativePath(toLoc, fromLoc=None):
	"""Given two paths, returns a relative path from fromLoc to toLoc."""
	return os.path.sep.join(relativePathList(toLoc, fromLoc))


def getPathAttributePrefix():
	return "path://"


def resolveAttributePathing(atts, pth=None):
	"""Dabo design files store their information in XML, which means
	when they are 'read' the values come back in a dictionary of 
	attributes, which are then used to restore the designed object to its
	intended state. Path values will be stored in a relative path format,
	with the value preceeded by the string returned by 
	getPathAttributePrefix(); i.e., 'path://'.
	
	This method finds all values that begin with the 'path://' label, 
	strips off that label, converts the paths back to values that
	can be used by the object, and then updates the attribute dict with
	those new values.
	"""
	prfx = getPathAttributePrefix()
	pathsToConvert = [(kk, vv) for kk, vv in atts.items()
			if isinstance(vv, basestring) and vv.startswith(prfx)]
	for convKey, convVal in pathsToConvert:
		# Strip the path designator
		convVal = convVal.replace(prfx, "")
		# Convert to relative path
		relPath = relativePath(convVal, pth)
		# Update the atts
		atts[convKey] = relPath


def resolvePath(val, pth=None, abspath=False):
	"""Takes a single string value in the format Dabo uses to store pathing
	in XML, and returns the original path relative to the specified path (or the
	current directory, if no pth is specified). If 'abspath' is True, returns an
	absolute path instead of the default relative path.
	"""
	prfx = getPathAttributePrefix()
	# Strip the path designator
	val = val.replace(prfx, "")
	# Convert to relative path
	ret = relativePath(val, pth)
	if abspath:
		ret = os.path.abspath(ret)
	return ret


def cleanMenuCaption(cap, bad=None):
	"""Menu captions can contain several special characters that make them
	unsuitable for things such as preference settings. This method provides 
	a simple way of getting the 'clean' version of these captions. By default it
	strips ampersands, spaces and periods; you can change that by passing 
	the characters you want stripped in the 'bad' parameter.
	"""
	if bad is None:
		bad = "&. "
	ret = cap
	for ch in bad:
		ret = ret.replace(ch, "")
	return ret