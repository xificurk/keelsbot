#!/bin/bash

#	keelsbot.sh - Sample runner script, useful for keeping a bot up to date and running.
#	Copyright (c) 2008-2011 Petr Morávek (xificurk@gmail.com)
#	Distributed under the terms of the GNU General Public License v3


# This is location of KeelsBot source
KEELSDIR=/opt/keelsbot

if [ ! -d "$KEELSDIR" ] ; then
	echo "ERROR: Could not find KeelsBot directory!"
	exit 1
fi

if [ -z "$1" ] ; then
	echo "ERROR: You must specify the config name!"
	exit 1
fi

CONFIG=$1
# This is location of log file
LOGFILE="/var/log/keelsbot/$CONFIG.log"
# This is location of config file
CONFIGFILE="/var/lib/keelsbot/$CONFIG.config.xml"

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
	if [[ -x "$(which git)" && -d ".git" ]] ; then
		echo "Updating bot from master git repository..." >> $LOGFILE
		git pull 1>> $LOGFILE 2>> $LOGFILE
	fi
	$KEELSDIR/keelsbot.py -v -c "$CONFIGFILE" 1>> $LOGFILE 2>> $LOGFILE
	sleep 10
done
