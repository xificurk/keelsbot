#!/bin/bash
#This sample runner script is useful for keeping a bot up to date and running.
#When running from this script, you can issue a /die to the bot and have
# it perform a clean restart from scratch with the latest version.

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
CONFIGFILE="/var/lib/scripts/keelsbot/config.$CONFIG.xml"

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
	if [ -x `which svn` ] ; then
		echo "Updating bot from SVN..." >> $LOGFILE
		svn up 1>> $LOGFILE 2>> $LOGFILE
	fi
	python $KEELSDIR/keelsbot.py -c "$CONFIGFILE" 1>> $LOGFILE 2>> $LOGFILE
	sleep 10
done
