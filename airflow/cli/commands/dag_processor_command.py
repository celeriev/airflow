# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""DagProcessor command"""
import logging
from datetime import timedelta

import daemon
from daemon.pidfile import TimeoutPIDLockFile

from airflow.configuration import conf
from airflow.dag_processing.manager import DagFileProcessorManager
from airflow.utils import cli as cli_utils
from airflow.utils.cli import setup_locations, setup_logging

log = logging.getLogger(__name__)


def _create_dag_processor_manager(args) -> DagFileProcessorManager:
    """Creates DagFileProcessorProcess instance."""
    processor_timeout_seconds: int = conf.getint('core', 'dag_file_processor_timeout')
    processor_timeout = timedelta(seconds=processor_timeout_seconds)
    return DagFileProcessorManager(
        dag_directory=args.subdir,
        max_runs=args.num_runs,
        processor_timeout=processor_timeout,
        dag_ids=[],
        pickle_dags=args.do_pickle,
    )


@cli_utils.action_cli
def dag_processor(args):
    """Starts Airflow Dag Processor Job"""
    if not conf.getboolean("scheduler", "standalone_dag_processor"):
        raise SystemExit('The option [scheduler/standalone_dag_processor] must be True.')

    sql_conn: str = conf.get('database', 'sql_alchemy_conn').lower()
    if sql_conn.startswith('sqlite'):
        raise SystemExit('Standalone DagProcessor is not supported when using sqlite.')

    manager = _create_dag_processor_manager(args)

    if args.daemon:
        pid, stdout, stderr, log_file = setup_locations(
            "dag-processor", args.pid, args.stdout, args.stderr, args.log_file
        )
        handle = setup_logging(log_file)
        with open(stdout, 'a') as stdout_handle, open(stderr, 'a') as stderr_handle:
            stdout_handle.truncate(0)
            stderr_handle.truncate(0)

            ctx = daemon.DaemonContext(
                pidfile=TimeoutPIDLockFile(pid, -1),
                files_preserve=[handle],
                stdout=stdout_handle,
                stderr=stderr_handle,
            )
            with ctx:
                try:
                    manager.start()
                finally:
                    manager.terminate()
                    manager.end()
    else:
        manager.start()
