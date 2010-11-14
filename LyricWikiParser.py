# -*- Mode: python; coding: utf-8; tab-width: 8; indent-tabs-mode: t; -*-
#
# Copyright (C) 2007 Jonathan Matthew
# Copyright (C) 2010 Oleg G
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# The Rhythmbox authors hereby grant permission for non-GPL compatible
# GStreamer plugins to be used and distributed together with GStreamer
# and Rhythmbox. This permission is above and beyond the permissions granted
# by the GPL license by which Rhythmbox is covered. If you modify this code
# you may extend this exception to your version of the code, but you are not
# obligated to do so. If you do not wish to do so, delete this exception
# statement from your version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.


import urllib
import re
import rb
from xml.dom import minidom
from string import capwords

class LyricWikiParser(object):
	def __init__(self, artist, title):
		# Each word should be capitalized
		# see: http://lyrics.wikia.com/LyricWiki:Page_Names
		# in order to capitalize works properly on non ASCII letters we need to use unicode object
		# in order to other functions like urllib.quote works properly then encode back to str object
		try:
			self.artist = capwords(unicode(artist, "utf-8")).encode("utf-8")
			self.title = capwords(unicode(title, "utf-8")).encode("utf-8")
		except:
			self.artist = artist
			self.title = title
		# maximum times that we can follow by #REDIRECT [[Artist:Song]]
		self.maxredirect = 3
		self.prompted = False
	
	def search(self, callback, *data):
		artist = urllib.quote(self.artist)
		title = urllib.quote(self.title)

		htstring = 'http://lyrics.wikia.com/api.php?action=query&prop=revisions&rvprop=content&format=xml&titles=%s:%s' % (artist, title)
			
		loader = rb.Loader()
		loader.get_url (htstring, self.got_lyrics, callback, *data)

	def got_lyrics(self, result, callback, *data):
		if result is None:
			callback (None, *data)
			return
			
		try:
			xml = minidom.parseString(result);
			nodes = xml.getElementsByTagName("rev")
			if nodes.length > 0:
				result = nodes.item(0).childNodes.item(0).data.encode("utf-8")
			else:
				result = ""
		except:
			callback (None, *data)
			return
			
		# lyrycs can be between <lyrics></lyrics> or <lyric></lyric> tags
		# more than one pairs of lyrics tags can be in one response
		# see: http://lyrics.wikia.com/api.php?action=query&prop=revisions&rvprop=content&format=xml&titles=Flёur:Колыбельная_для_Солнца
		matches = re.findall("<(lyrics?)>(.+?)</\\1>", result, re.I | re.S)
		if matches:
			result = matches[0][1].strip()
			for lyric in matches[1::]:
				result += "\n\n-------------------------\n\n"
				result += lyric[1].strip();
			
			result += "\n\nLyrics provided by lyricwiki.org"
			
			callback (result, *data)
			return
			
		# after lyric request we can get #REDIRECT [[Artist:Song]] instead of lyric: we need to repeat search request with given Artist:Song
		matches = re.match("#REDIRECT\s+\[\[([^:]+):(.+?)\]\]", result, re.I)
		if matches:
			self.artist = matches.group(1)
			self.title  = matches.group(2)
			self.maxredirect -= 1
			if self.maxredirect < 0:
				# redirection limit exceed
				callback (None, *data)
				return
				
			self.search(callback, *data)
			return

		# hmm... no lyrics found, maybe we have bad tags: try to ask lyricwiki
		if self.prompted:
			# already asked, smth goes wrong
			callback (None, *data)
			return

		self.prompted = True
		artist = urllib.quote(self.artist)
		title  = urllib.quote(self.title)
		htstring = 'http://lyrics.wikia.com/api.php?action=lyrics&func=getSong&fmt=xml&artist=%s&song=%s' % (artist, title)
		loader = rb.Loader()
		loader.get_url (htstring, self.got_prompt, callback, *data)


	def got_prompt(self, result, callback, *data):
		# Lyricwiki API can correct our tags
		# example: http://lyrics.wikia.com/api.php?action=lyrics&func=getSong&fmt=xml&artist=Nightwish&song=Nightwish_-_Sleepwalker
		if result is None:
			callback (None, *data)
			return
			
		try:
			xml = minidom.parseString(result);
			result = xml.getElementsByTagName("url").item(0).childNodes.item(0).data.encode("utf-8")
		except:
			callback (None, *data)
			return
			
		matches = re.match(".+\/([^?=:]+):([^?=:]+)$", result)
		if not matches:
			# no more chance to get lyric for this Artist:Song from Lyricwiki: lyric not found
			callback (None, *data)
			return
			
		self.artist = matches.group(1)
		self.title  = matches.group(2)
		self.search(callback, *data)

