"""
	SleekXMPP: The Sleek XMPP Library
	Copyright (C) 2007  Nathanael C. Fritz
	This file is part of SleekXMPP.

	SleekXMPP is free software; you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation; either version 2 of the License, or
	(at your option) any later version.

	SleekXMPP is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with SleekXMPP; if not, write to the Free Software
	Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""
from . import base
import logging
from xml.etree import cElementTree as ET
import copy
#TODO support item groups and results

class xep_0004(base.base_plugin):
	
	def plugin_init(self):
		self.xep = '0004'
		self.description = 'Data Forms'
		self.xmpp.add_handler("<message><x xmlns='jabber:x:data' /></message>", self.handler_message_xform)
	
	def post_init(self):
		self.xmpp['xep_0030'].add_feature('jabber:x:data')
	
	def handler_message_xform(self, xml):
		object = self.handle_form(xml)
		self.xmpp.event("message_form", object)
	
	def handler_presence_xform(self, xml):
		object = self.handle_form(xml)
		self.xmpp.event("presence_form", object)
	
	def handle_form(self, xml):
		xmlform = xml.find('{jabber:x:data}x')
		object = self.buildForm(xmlform)
		self.xmpp.event("message_xform", object)
		return object
	
	def buildForm(self, xml):
		form = Form(xml.attrib['type'])
		form.fromXML(xml)
		return form

	def makeForm(self, ftype='form', title='', instructions=''):
		return Form(self.xmpp, ftype, title, instructions)

class FieldContainer(object):
	def __init__(self, stanza = 'form'):
		self.fields = []
		self.field = {}
		self.stanza = stanza
	
	def addField(self, var, ftype='text-single', label='', desc='', required=False, value=None):
		self.field[var] = FormField(var, ftype, label, desc, required, value)
		self.fields.append(self.field[var])
		return self.field[var]
	
	def buildField(self, xml):
		self.field[xml.get('var', '__unnamed__')] = FormField(xml.get('var', '__unnamed__'), xml.get('type', 'text-single'))
		self.fields.append(self.field[xml.get('var', '__unnamed__')])
		self.field[xml.get('var', '__unnamed__')].buildField(xml)

	def buildContainer(self, xml):
		self.stanza = xml.tag
		for field in xml.findall('{jabber:x:data}field'):
			self.buildField(field)
	
	def getXML(self, ftype):
		container = ET.Element(self.stanza)
		for field in self.fields:
			container.append(field.getXML(ftype))
		return container
	
class Form(FieldContainer):
	types = ('form', 'submit', 'cancel', 'result')
	def __init__(self, xmpp=None, ftype='form', title='', instructions=''):
		if not ftype in self.types:
			raise ValueError("Invalid Form Type")
		FieldContainer.__init__(self)
		self.xmpp = xmpp
		self.type = ftype
		self.title = title
		self.instructions = instructions
		self.reported = []
		self.items = []
	
	def getValues(self):
		result = {}
		for field in self.fields:
			value = field.value
			if len(value) == 1:
				value = value[0]
			result[field.var] = value
		return result
	
	def fromXML(self, xml):
		self.buildForm(xml)
	
	def addItem(self):
		newitem = FieldContainer('item')
		self.items.append(newitem)
		return newitem

	def buildItem(self, xml):
		newitem = self.addItem()
		newitem.buildContainer(xml)

	def addReported(self):
		reported = FieldContainer('reported')
		self.reported.append(reported)
		return reported

	def buildReported(self, xml):
		reported = self.addReported()
		reported.buildContainer(xml)
	
	def setTitle(self, title):
		self.title = title
	
	def setInstructions(self, instructions):
		self.instructions = instructions
	
	def setType(self, ftype):
		self.type = ftype
	
	def getXMLMessage(self, to):
		msg = self.xmpp.makeMessage(to)
		msg.append(self.getXML())
		return msg
	
	def buildForm(self, xml):
		self.type = xml.get('type', 'form')
		if xml.find('{jabber:x:data}title') is not None:
			self.setTitle(xml.find('{jabber:x:data}title').text)
		if xml.find('{jabber:x:data}instructions') is not None:
			self.setInstructions(xml.find('{jabber:x:data}instructions').text)
		for field in xml.findall('{jabber:x:data}field'):
			self.buildField(field)
		for reported in xml.findall('{jabber:x:data}reported'):
			self.buildReported(reported)
		for item in xml.findall('{jabber:x:data}item'):
			self.buildItem(item)
	
	#def getXML(self, tostring = False):
	def getXML(self, ftype=None):
		logging.debug("creating form as %s" % ftype)
		if ftype:
			self.type = ftype
		form = ET.Element('{jabber:x:data}x')
		form.attrib['type'] = self.type
		if self.title and self.type in ('form', 'result'):
			title = ET.Element('title')
			title.text = self.title
			form.append(title)
		if self.instructions and self.type == 'form':
			instructions = ET.Element('instructions')
			instructions.text = self.instructions
			form.append(instructions)
		for field in self.fields:
			form.append(field.getXML(self.type))
		for reported in self.reported:
			form.append(reported.getXML('reported'))
		for item in self.items:
			form.append(item.getXML(self.type))
		#if tostring:
		#	form = self.xmpp.tostring(form)
		return form
	
	def makeSubmit(self):
		self.setType('submit')

class FormField(object):
	types = ('boolean', 'fixed', 'hidden', 'jid-multi', 'jid-single', 'list-multi', 'list-single', 'text-multi', 'text-private', 'text-single')
	listtypes = ('jid-multi', 'jid-single', 'list-multi', 'list-single')
	lbtypes = ('fixed', 'text-multi')
	def __init__(self, var, ftype='text-single', label='', desc='', required=False, value=None):
		if not ftype in self.types:
			raise ValueError("Invalid Field Type")
		self.type = ftype
		self.var = var
		self.label = label
		self.desc = desc
		self.options = []
		self.required = False
		self.value = []
		if self.type in self.listtypes:
			self.islist = True
		else:
			self.islist = False
		if self.type in self.lbtypes:
			self.islinebreak = True
		else:
			self.islinebreak = False
		if value:
			self.setValue(value)
	
	def addOption(self, value, label):
		if self.islist:
			self.options.append((value, label))
		else:
			raise ValueError("Cannot add options to non-list type field.")
	
	def setTrue(self):
		if self.type == 'boolean':
			self.value = [True]

	def setFalse(self):
		if self.type == 'boolean':
			self.value = [False]

	def require(self):
		self.required = True
	
	def setDescription(self, desc):
		self.desc = desc
	
	def setValue(self, value):
		if self.islinebreak and value is not None:
			self.value += value.split('\n')
		else:
			if len(self.value) and (not self.islist or self.type == 'list-single'):
				self.value = [value]
			else:
				self.value.append(value)

	def delValue(self, value):
		if type(self.value) == type([]):
			try:
				idx = self.value.index(value)
				if idx != -1:
					self.value.pop(idx)
			except ValueError:
				pass
		else:
			self.value = ''
	
	def setAnswer(self, value):
		self.setValue(value)
	
	def buildField(self, xml):
		self.type = xml.get('type', 'text-single')
		self.label = xml.get('label', '')
		for option in xml.findall('{jabber:x:data}option'):
			self.addOption(option.find('{jabber:x:data}value').text, option.get('label', ''))
		for value in xml.findall('{jabber:x:data}value'):
			self.setValue(value.text)
		if xml.find('{jabber:x:data}required') is not None:
			self.require()
		if xml.find('{jabber:x:data}desc') is not None:
			self.setDescription(xml.find('{jabber:x:data}desc').text)
	
	def getXML(self, ftype):
		field = ET.Element('field')
		if ftype != 'result':
			field.attrib['type'] = self.type
		if self.type != 'fixed':
			if self.var:
				field.attrib['var'] = self.var
			if self.label:
				field.attrib['label'] = self.label
		if ftype == 'form':
			for option in self.options:
				optionxml = ET.Element('option')
				optionxml.attrib['label'] = option[1]
				optionval = ET.Element('value')
				optionval.text = option[0]
				optionxml.append(optionval)
				field.append(optionxml)
			if self.required:
				required = ET.Element('required')
				field.append(required)
			if self.desc:
				desc = ET.Element('desc')
				desc.text = self.desc
				field.append(desc)
		for value in self.value:
			valuexml = ET.Element('value')
			if value is True or value is False:
				if value:
					valuexml.text = '1'
				else:
					valuexml.text = '0'
			else:
				valuexml.text = value
			field.append(valuexml)
		return field
