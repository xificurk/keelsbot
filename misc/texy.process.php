<?php
require_once dirname(__FILE__).'/texy.min.php';

if ($_SERVER["argc"] == 2) {
	Texy::$advertisingNotice = NULL;
	$texy = new Texy();
	$text = $_SERVER["argv"][1];
	$html = $texy->process($text);
	echo trim($html);
} else {
	echo Texy::VERSION;
}