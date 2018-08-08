#!/usr/bin/env python
# CollectD MySQL plugin, designed for MySQL 5.5+ (specifically Percona Server)
#
# Pulls most of the same metrics as the Percona Monitoring Plugins for Cacti,
# however is designed to be used on newer versions of MySQL and as such drops
# all of the legacy compatibility, and favors metrics from SHOW GLOBAL STATUS
# as opposed to SHOW ENGINE INNODB STATUS where possible.
#
# Configuration:
#  Import mysql
#  <Module mysql>
#   Host localhost
#   Port 3306 (optional)
#   User root
#   Password xxxx
#   HeartbeatTable percona.heartbeat (optional, if using pt-heartbeat)
#   Verbose true (optional, to enable debugging)
#  </Module>
#
# Requires "MySQLdb" for Python
#
# Author: Chris Boulton <chris@chrisboulton.com>
# Added metrics for Grafana Dashboards by Matej Zerovnik <matej@zunaj.si>
# License: MIT (http://www.opensource.org/licenses/mit-license.php)
#

import sys

COLLECTD_ENABLED=True
try:
	import collectd
except ImportError:
	# We're not running in CollectD, set this to False so we can make some changes
	# accordingly for testing/development.
	COLLECTD_ENABLED=False
import re
import MySQLdb

MYSQL_CONFIG = {
	'Host':           'localhost',
	'Port':           3306,
	'User':           'root',
	'Password':       '',
	'HeartbeatTable': '',
	'Verbose':        False,
}

MYSQL_STATUS_VARS = {
	'Aborted_clients': 'counter',
	'Aborted_connects': 'counter',
	'Binlog_cache_disk_use': 'counter',
	'Binlog_cache_use': 'counter',
	'Bytes_received': 'counter',
	'Bytes_sent': 'counter',
	'Connections': 'counter',
	'Created_tmp_disk_tables': 'counter',
	'Created_tmp_files': 'counter',
	'Created_tmp_tables': 'counter',
	'Innodb_buffer_pool_bytes_data': 'gauge',
	'Innodb_buffer_pool_bytes_dirty': 'gauge',
	'Innodb_buffer_pool_pages_data': 'gauge',
	'Innodb_buffer_pool_pages_dirty': 'gauge',
	'Innodb_buffer_pool_pages_free': 'gauge',
	'Innodb_buffer_pool_pages_total': 'gauge',
	'Innodb_buffer_pool_read_requests': 'counter',
	'Innodb_buffer_pool_write_requests': 'counter',
	'Innodb_buffer_pool_reads': 'counter',
	'Innodb_checkpoint_age': 'gauge',
	'Innodb_checkpoint_max_age': 'gauge',
	'Innodb_data_fsyncs': 'counter',
	'Innodb_data_pending_fsyncs': 'gauge',
	'Innodb_data_pending_reads': 'gauge',
	'Innodb_data_pending_writes': 'gauge',
	'Innodb_data_read': 'counter',
	'Innodb_data_reads': 'counter',
	'Innodb_data_writes': 'counter',
	'Innodb_data_written': 'counter',
	'Innodb_deadlocks': 'counter',
	'Innodb_history_list_length': 'gauge',
	'Innodb_ibuf_free_list': 'gauge',
	'Innodb_ibuf_merged_delete_marks': 'counter',
	'Innodb_ibuf_merged_deletes': 'counter',
	'Innodb_ibuf_merged_inserts': 'counter',
	'Innodb_ibuf_merges': 'counter',
	'Innodb_ibuf_segment_size': 'gauge',
	'Innodb_ibuf_size': 'gauge',
	'Innodb_lsn_current': 'counter',
	'Innodb_lsn_flushed': 'counter',
	'Innodb_log_writes': 'counter',
	'Innodb_max_trx_id': 'counter',
	'Innodb_mem_adaptive_hash': 'gauge',
	'Innodb_mem_dictionary': 'gauge',
	'Innodb_mem_total': 'gauge',
	'Innodb_mutex_os_waits': 'counter',
	'Innodb_mutex_spin_rounds': 'counter',
	'Innodb_mutex_spin_waits': 'counter',
	'Innodb_os_log_pending_fsyncs': 'gauge',
	'Innodb_os_log_written': 'counter',
	'Innodb_pages_created': 'counter',
	'Innodb_pages_read': 'counter',
	'Innodb_pages_written': 'counter',
	'Innodb_page_size': 'gauge',
	'Innodb_row_lock_time': 'counter',
	'Innodb_row_lock_time_avg': 'gauge',
	'Innodb_row_lock_time_max': 'gauge',
	'Innodb_row_lock_waits': 'counter',
	'Innodb_rows_deleted': 'counter',
	'Innodb_rows_inserted': 'counter',
	'Innodb_rows_read': 'counter',
	'Innodb_rows_updated': 'counter',
	'Innodb_s_lock_os_waits': 'counter',
	'Innodb_s_lock_spin_rounds': 'counter',
	'Innodb_s_lock_spin_waits': 'counter',
	'Innodb_uncheckpointed_bytes': 'gauge',
	'Innodb_unflushed_log': 'gauge',
	'Innodb_unpurged_txns': 'gauge',
	'Innodb_x_lock_os_waits': 'counter',
	'Innodb_x_lock_spin_rounds': 'counter',
	'Innodb_x_lock_spin_waits': 'counter',
	'Key_blocks_not_flushed': 'gauge',
	'Key_blocks_unused': 'gauge',
	'Key_blocks_used': 'gauge',
	'Key_read_requests': 'counter',
	'Key_reads': 'counter',
	'Key_write_requests': 'counter',
	'Key_writes': 'counter',
	'Max_used_connections': 'gauge',
	'Open_files': 'gauge',
	'Open_table_definitions': 'gauge',
	'Open_tables': 'gauge',
	'Opened_files': 'counter',
	'Opened_table_definitions': 'counter',
	'Opened_tables': 'counter',
	'Qcache_free_blocks': 'gauge',
	'Qcache_free_memory': 'gauge',
	'Qcache_hits': 'counter',
	'Qcache_inserts': 'counter',
	'Qcache_lowmem_prunes': 'counter',
	'Qcache_not_cached': 'counter',
	'Qcache_queries_in_cache': 'counter',
	'Qcache_total_blocks': 'counter',
	'Queries': 'counter',
	'Questions': 'counter',
	'Select_full_join': 'counter',
	'Select_full_range_join': 'counter',
	'Select_range': 'counter',
	'Select_range_check': 'counter',
	'Select_scan': 'counter',
	'Slave_open_temp_tables': 'gauge',
	'Slave_retried_transactions': 'counter',
	'Slow_launch_threads': 'counter',
	'Slow_queries': 'counter',
	'Sort_merge_passes': 'counter',
	'Sort_range': 'counter',
	'Sort_rows': 'counter',
	'Sort_scan': 'counter',
	'Table_locks_immediate': 'counter',
	'Table_locks_waited': 'counter',
	'Table_open_cache_hits': 'counter',
	'Table_open_cache_misses': 'counter',
	'Table_open_cache_overflows': 'counter',
	'Threadpool_idle_threads': 'gauge',
	'Threadpool_threads': 'gauge',
	'Threads_cached': 'gauge',
	'Threads_connected': 'gauge',
	'Threads_created': 'counter',
	'Threads_running': 'gauge',
	'Uptime': 'gauge',
}

MYSQL_VARS = [
	'binlog_stmt_cache_size',
	'innodb_additional_mem_pool_size',
	'innodb_buffer_pool_size',
	'innodb_concurrency_tickets',
	'innodb_io_capacity',
	'innodb_log_buffer_size',
	'innodb_log_file_size',
	'innodb_log_files_in_group',
	'innodb_max_purge_lag',
	'innodb_open_files',
	'innodb_open_files',
	'join_buffer_size',
	'key_buffer_size',
	'key_cache_block_size',
	'max_connections',
	'open_files_limit',
	'query_cache_limit',
	'query_cache_size',
	'query_cache_size',
	'read_buffer_size',
	'read_only',
	'table_cache',
	'table_definition_cache',
	'table_open_cache',
	'thread_cache_size',
	'thread_cache_size',
	'thread_concurrency',
	'tmp_table_size',
]

MYSQL_PROCESS_STATES = {
	'closing_tables': 0,
	'copying_to_tmp_table': 0,
	'end': 0,
	'freeing_items': 0,
	'init': 0,
	'locked': 0,
	'login': 0,
	'none': 0,
	'other': 0,
	'preparing': 0,
	'reading_from_net': 0,
	'sending_data': 0,
	'sorting_result': 0,
	'statistics': 0,
	'updating': 0,
	'writing_to_net': 0,
	'creating_table': 0,
	'opening_tables': 0,
}

MYSQL_INNODB_STATUS_VARS = {
	'active_transactions': 'gauge',
	'current_transactions': 'gauge',
	'file_reads': 'counter',
	'file_system_memory': 'gauge',
	'file_writes': 'counter',
	'innodb_lock_structs': 'gauge',
	'innodb_lock_wait_secs': 'gauge',
	'innodb_locked_tables': 'gauge',
	'innodb_sem_wait_time_ms': 'gauge',
	'innodb_sem_waits': 'gauge',
	'innodb_tables_in_use': 'gauge',
	'lock_system_memory': 'gauge',
	'locked_transactions': 'gauge',
	'log_writes': 'counter',
	'page_hash_memory': 'gauge',
	'pending_aio_log_ios': 'gauge',
	'pending_buf_pool_flushes': 'gauge',
	'pending_chkp_writes': 'gauge',
	'pending_ibuf_aio_reads': 'gauge',
	'pending_log_writes':'gauge',
	'queries_inside': 'gauge',
	'queries_queued': 'gauge',
	'read_views': 'gauge',
}

MYSQL_INNODB_STATUS_MATCHES = {
	# 0 read views open inside InnoDB
	'read views open inside InnoDB': {
		'read_views': 0,
	},
	# 5635328 OS file reads, 27018072 OS file writes, 20170883 OS fsyncs
	' OS file reads, ': {
		'file_reads': 0,
		'file_writes': 4,
	},
	# ibuf aio reads: 0, log i/o's: 0, sync i/o's: 0
	'ibuf aio reads': {
		'pending_ibuf_aio_reads': 3,
		'pending_aio_log_ios': 6,
		'pending_aio_sync_ios': 9,
	},
	# Pending flushes (fsync) log: 0; buffer pool: 0
	'Pending flushes (fsync)': {
		'pending_buf_pool_flushes': 7,
	},
	# 16086708 log i/o's done, 106.07 log i/o's/second
	" log i/o's done, ": {
		'log_writes': 0,
	},
	# 0 pending log writes, 0 pending chkp writes
	' pending log writes, ': {
		'pending_log_writes': 0,
		'pending_chkp_writes': 4,
	},
	# Page hash           2302856 (buffer pool 0 only)
	'Page hash    ': {
		'page_hash_memory': 2,
	},
	# File system         657820264         (812272 + 657007992)
	'File system    ': {
		'file_system_memory': 2,
	},
	# Lock system         143820296         (143819576 + 720)
	'Lock system    ': {
		'lock_system_memory': 2,
	},
	# 0 queries inside InnoDB, 0 queries in queue
	'queries inside InnoDB, ': {
		'queries_inside': 0,
		'queries_queued': 4,
	},
	# --Thread 139954487744256 has waited at dict0dict.cc line 472 for 0.0000 seconds the semaphore:
	'seconds the semaphore': {
		'innodb_sem_waits': lambda row, stats: stats['innodb_sem_waits'] + 1,
		'innodb_sem_wait_time_ms': lambda row, stats: float(row[9]) * 1000,
	},
	# mysql tables in use 1, locked 1
	'mysql tables in use': {
		'innodb_tables_in_use': lambda row, stats: stats['innodb_tables_in_use'] + int(row[4]),
		'innodb_locked_tables': lambda row, stats: stats['innodb_locked_tables'] + int(row[6]),
	},
	"------- TRX HAS BEEN": {
		"innodb_lock_wait_secs": lambda row, stats: stats['innodb_lock_wait_secs'] + int(row[5]),
	},
}

def get_mysql_conn():
	return MySQLdb.connect(
		host=MYSQL_CONFIG['Host'],
		port=MYSQL_CONFIG['Port'],
		user=MYSQL_CONFIG['User'],
		passwd=MYSQL_CONFIG['Password']
	)

def mysql_query(conn, query):
	cur = conn.cursor(MySQLdb.cursors.DictCursor)
	cur.execute(query)
	return cur

def fetch_mysql_status(conn):
	result = mysql_query(conn, 'SHOW GLOBAL STATUS')
	status = {}
	for row in result.fetchall():
		status[row['Variable_name']] = row['Value']

	# calculate the number of unpurged txns from existing variables
	if 'Innodb_max_trx_id' in status:
		status['Innodb_unpurged_txns'] = int(status['Innodb_max_trx_id']) - int(status['Innodb_purge_trx_id'])

	if 'Innodb_lsn_last_checkpoint' in status:
		status['Innodb_uncheckpointed_bytes'] = int(status['Innodb_lsn_current'])- int(status['Innodb_lsn_last_checkpoint'])

	if 'Innodb_lsn_flushed' in status:
		status['Innodb_unflushed_log'] = int(status['Innodb_lsn_current']) - int(status['Innodb_lsn_flushed'])

	return status

def fetch_mysql_master_stats(conn):
	try:
		result = mysql_query(conn, 'SHOW BINARY LOGS')
	except MySQLdb.OperationalError:
		return {}

	stats = {
		'binary_log_space': 0,
	}

	for row in result.fetchall():
		if 'File_size' in row and row['File_size'] > 0:
			stats['binary_log_space'] += int(row['File_size'])

	return stats

def fetch_mysql_slave_stats(conn):
	result    = mysql_query(conn, 'SHOW SLAVE STATUS')
	slave_row = result.fetchone()
	if slave_row is None:
		return {}

	status = {
		'relay_log_space': slave_row['Relay_Log_Space'],
		'last_errno':      slave_row['Last_Errno'],
		'slave_lag':       slave_row['Seconds_Behind_Master'] if slave_row['Seconds_Behind_Master'] != None else 0,
	}

	if MYSQL_CONFIG['HeartbeatTable']:
		query = """
			SELECT MAX(UNIX_TIMESTAMP() - UNIX_TIMESTAMP(ts)) AS delay
			FROM %s
			WHERE server_id = %s
		""" % (MYSQL_CONFIG['HeartbeatTable'], slave_row['Master_Server_Id'])
		result = mysql_query(conn, query)
		row    = result.fetchone()
		if 'delay' in row and row['delay'] != None:
			status['slave_lag'] = row['delay']

	status['slave_sql_running'] = 1 if slave_row['Slave_SQL_Running'] == 'Yes' else 0
	status['slave_io_running'] = 1 if slave_row['Slave_IO_Running'] == 'Yes' else 0
	return status

def fetch_mysql_process_states(conn):
	global MYSQL_PROCESS_STATES
	result = mysql_query(conn, 'SHOW PROCESSLIST')
	states = MYSQL_PROCESS_STATES.copy()
	for row in result.fetchall():
		state = row['State']
		if state == '' or state == None: state = 'none'
		state = re.sub(r'^(Table lock|Waiting for .*lock)$', "Locked", state)
		state = state.lower().replace(" ", "_")
		if state not in states: state = 'other'
		states[state] += 1

	return states

def fetch_mysql_variables(conn):
	global MYSQL_VARS
	result = mysql_query(conn, 'SHOW GLOBAL VARIABLES')
	variables = {}
	for row in result.fetchall():
		if row['Variable_name'] in MYSQL_VARS:
			if row['Variable_name'] == 'read_only':
				variables[row['Variable_name']] = 1 if row['Value'] == 'ON' else 0
			else:
				variables[row['Variable_name']] = row['Value']

	return variables

def fetch_mysql_response_times(conn):
	response_times = {}
	try:
		result = mysql_query(conn, """
			SELECT *
			FROM INFORMATION_SCHEMA.QUERY_RESPONSE_TIME
			WHERE `time` != 'TOO LONG'
			ORDER BY `time`
		""")
	except MySQLdb.OperationalError:
		return {}

	for i in range(1, 14):
		row = result.fetchone()

		# fill in missing rows with zeros
		if not row:
			row = { 'count': 0, 'total': 0 }

		row = {key.lower(): val for key, val in row.items()}

		response_times[i] = {
			'time':  float(row['time']),
			'count': int(row['count']),
			'total': round(float(row['total']) * 1000000, 0),
		}

	return response_times

def fetch_innodb_stats(conn):
	global MYSQL_INNODB_STATUS_MATCHES, MYSQL_INNODB_STATUS_VARS
	result = mysql_query(conn, 'SHOW ENGINE INNODB STATUS')
	row    = result.fetchone()
	status = row['Status']
	stats  = dict.fromkeys(MYSQL_INNODB_STATUS_VARS.keys(), 0)

	for line in status.split("\n"):
		line = line.strip()
		row  = re.split(r' +', re.sub(r'[,;] ', ' ', line))
		if line == '': continue

		# ---TRANSACTION 124324402462, not started
		# ---TRANSACTION 124324402468, ACTIVE 0 sec committing
		if line.find("---TRANSACTION") != -1:
			stats['current_transactions'] += 1
			if line.find("ACTIVE") != -1:
				stats['active_transactions'] += 1
		# LOCK WAIT 228 lock struct(s), heap size 46632, 65 row lock(s), undo log entries 1
		# 205 lock struct(s), heap size 30248, 37 row lock(s), undo log entries 1
		elif line.find("lock struct(s)") != -1:
			if line.find("LOCK WAIT") != -1:
				stats['innodb_lock_structs'] += int(row[2])
				stats['locked_transactions'] += 1
			else:
				stats['innodb_lock_structs'] += int(row[0])
		else:
			for match in MYSQL_INNODB_STATUS_MATCHES:
				if line.find(match) == -1: continue
				for key in MYSQL_INNODB_STATUS_MATCHES[match]:
					value = MYSQL_INNODB_STATUS_MATCHES[match][key]
					if type(value) is int:
						if value < len(row) and row[value].isdigit():
							stats[key] = int(row[value])
					else:
						stats[key] = value(row, stats)
				break

	return stats

def log_verbose(msg):
	if not MYSQL_CONFIG['Verbose']:
		return
	if COLLECTD_ENABLED:
		collectd.info('mysql plugin: %s' % msg)
	else:
		print('mysql plugin: %s' % msg)

def dispatch_value(prefix, key, value, type, type_instance=None):
	if not type_instance:
		type_instance = key

	log_verbose('Sending value: %s/%s=%s' % (prefix, type_instance, value))
	if value is None:
		return
	value = int(value) # safety check

	if COLLECTD_ENABLED:
		val               = collectd.Values(plugin='mysql', plugin_instance=prefix)
		val.type          = type
		val.type_instance = type_instance
		val.values        = [value]
		val.dispatch()

def configure_callback(conf):
	global MYSQL_CONFIG
	for node in conf.children:
		if node.key in MYSQL_CONFIG:
			MYSQL_CONFIG[node.key] = node.values[0]

	MYSQL_CONFIG['Port']    = int(MYSQL_CONFIG['Port'])
	MYSQL_CONFIG['Verbose'] = bool(MYSQL_CONFIG['Verbose'])

def read_callback():
	global MYSQL_STATUS_VARS
	conn = get_mysql_conn()

	mysql_status = fetch_mysql_status(conn)
	for key in mysql_status:
		if mysql_status[key] == '': mysql_status[key] = 0

		# collect anything beginning with Com_/Handler_ as these change
		# regularly between  mysql versions and this is easier than a fixed
		# list
		if key.split('_', 2)[0] in ['Com', 'Handler']:
			ds_type = 'counter'
		elif key in MYSQL_STATUS_VARS:
			ds_type = MYSQL_STATUS_VARS[key]
		else:
			continue

		dispatch_value('status', key, mysql_status[key], ds_type)

	mysql_variables = fetch_mysql_variables(conn)
	for key in mysql_variables:
		dispatch_value('variables', key, mysql_variables[key], 'gauge')

	mysql_master_status = fetch_mysql_master_stats(conn)
	for key in mysql_master_status:
		dispatch_value('master', key, mysql_master_status[key], 'gauge')

	mysql_states = fetch_mysql_process_states(conn)
	for key in mysql_states:
		dispatch_value('state', key, mysql_states[key], 'gauge')

	slave_status = fetch_mysql_slave_stats(conn)
	for key in slave_status:
		dispatch_value('slave', key, slave_status[key], 'gauge')

	response_times = fetch_mysql_response_times(conn)
	for key in response_times:
		dispatch_value('response_time_total', str(key), response_times[key]['total'], 'counter')
		dispatch_value('response_time_count', str(key), response_times[key]['count'], 'counter')

	innodb_status = fetch_innodb_stats(conn)
	for key in MYSQL_INNODB_STATUS_VARS:
		if key not in innodb_status: continue
		dispatch_value('innodb', key, innodb_status[key], MYSQL_INNODB_STATUS_VARS[key])

if COLLECTD_ENABLED:
	 collectd.register_read(read_callback)
	 collectd.register_config(configure_callback)

if __name__ == "__main__" and not COLLECTD_ENABLED:
	print "Running in test mode, invoke with"
	print sys.argv[0] + " Host Port User Password "
	MYSQL_CONFIG['Host'] = sys.argv[1]
	MYSQL_CONFIG['Port'] = int(sys.argv[2])
	MYSQL_CONFIG['User'] = sys.argv[3]
	MYSQL_CONFIG['Password'] = sys.argv[4]
	MYSQL_CONFIG['Verbose'] = True
	from pprint import pprint as pp
	pp(MYSQL_CONFIG)
	read_callback()


# vim:noexpandtab ts=8 sw=8 sts=8
