#!/bin/bash

#    keelsbot.sh - Sample runner script, useful for keeping a bot up to date and running.
#    Copyright (C) 2008-2010 Petr Morávek
#
#    This file is part of KeelsBot.
#
#    Keelsbot is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    KeelsBot is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


# This is location of KeelsBot source
KEELSDIR=/opt/keelsbot

if [ -z "$1" ] ; then
	echo "ERROR: You must specify the config name!"
	exit 1
fi

CONFIG=$1
# This is location of log file
LOGFILE="/var/log/scripts/keelsbot/$CONFIG.log"
# This is location of config file
CONFIGFILE="/var/lib/scripts/keelsbot/$CONFIG.config.xml"

if [ ! -f "$CONFIGFILE" ] ; then
	echo "ERROR: Configuration file $CONFIGFILE not found!"
	exit 1
fi

trap cleanup EXIT

cleanup()
{
	# Killing all children
	for pid in `ps -o pid= --ppid $$`; do
		if ps $pid > /dev/null; then
			echo "TERMINATING: Killing bot PID $pid" >> $LOGFILE
			kill $pid
		fi
	done
	exit 1
}

cd $KEELSDIR
while true; do
	date >> $LOGFILE
	if [ -x `which git` ] ; then
		echo "Updating bot from master git repository..." >> $LOGFILE
		git pull 1>> $LOGFILE 2>> $LOGFILE
	fi
	$KEELSDIR/keelsbot.py -v -c "$CONFIGFILE" 1>> $LOGFILE 2>> $LOGFILE
	sleep 10
done
