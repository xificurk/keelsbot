<?php
require_once dirname(__FILE__).'/texy.min.php';

if ($_SERVER["argc"] == 2) {
	Texy::$advertisingNotice = NULL;
	$texy = new Texy();
	$texy->imageModule->root = '';
	$texy->imageModule->linkedRoot = '';
	echo trim($texy->process($_SERVER["argv"][1]));
} else {
	echo Texy::VERSION;
}