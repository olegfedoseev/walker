Walker
======

Walk the urls and generate code coverage for executed PHP code

*Work-in-progress proof-of-concept*

PHP Config
===========

PHP prepend file must include at the end:

::

	if (array_key_exists('HTTP_X_WALKER', $_SERVER) && $_SERVER['HTTP_X_WALKER'] == 'yes') {
		xdebug_start_code_coverage();
	}

PHP append file must include:

::

	if (array_key_exists('HTTP_X_WALKER', $_SERVER) && $_SERVER['HTTP_X_WALKER'] == 'yes') {
		$coverage = xdebug_get_code_coverage();
		$report = json_encode(array(
			'group' => $_SERVER['HTTP_X_WALKER_GROUP'],
			'uri' => $_SERVER['REQUEST_URI'],
			'server' => $_SERVER['SERVER_NAME'],
			'coverage' => $coverage,
			'query' => $_SERVER['SCRIPT_NAME'] . '?' . $_SERVER['QUERY_STRING']
		));

		try {
			$host = $_SERVER['HTTP_X_WALKER_HOST'];
			$port = $_SERVER['HTTP_X_WALKER_PORT'];
			$fp = fsockopen("udp://$host", $port, $errno, $errstr);
			if (!$fp) { return; }
			fwrite($fp, gzcompress($report));
			fclose($fp);
		} catch (Exception $e) {
			trigger_error($e, E_USER_NOTIE);
		}
	}