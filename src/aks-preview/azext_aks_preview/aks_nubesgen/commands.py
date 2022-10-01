# pylint: disable=too-many-lines
# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import json
from posixpath import dirname
from typing import Dict, List, Optional, Tuple
import subprocess
import requests
import os
import platform
from pathlib import Path
from knack.prompting import prompt_y_n
import logging
from azext_aks_preview._consts import (
    CONST_NUBEGEN_CLI_VERSION
)


# `az aks nubesgen` function
def aks_nubesgen(destination: str,
                         app_name: str,
                         language: str,
                         create_config: str,
                         dockerfile_only: str,
                         deployment_only: str,
                         download_path: str) -> None:
    file_path, arguments = _pre_run(download_path,
                                    destination=destination,
                                    app_name=app_name,
                                    language=language,
                                    create_config=create_config,
                                    dockerfile_only=dockerfile_only,
                                    deployment_only=deployment_only)
    run_successful = _run(file_path, 'create', arguments)
    if run_successful:
        _run_finish()
    else:
        raise ValueError('`az aks nubesgen` was NOT executed successfully')


# Returns binary file path and arguments
def _pre_run(download_path: str, **kwargs) -> Tuple[str, List[str]]:
    file_path = _binary_pre_check(download_path)
    if not file_path:
        raise ValueError('Binary check was NOT executed successfully')
    arguments = _build_args(kwargs)
    return file_path, arguments


# Executes the nubesgen command
# Returns True if the process executed sucessfully, False otherwise
def _run(binary_path: str, command: str, arguments: List[str]) -> bool:
    if binary_path is None:
        raise ValueError('The given Binary path was null or empty')

    logging.info(f'Running `az aks nubesgen {command}`')
    cmd = [binary_path, command] + arguments
    process = subprocess.Popen(cmd)
    exit_code = process.wait()
    return exit_code == 0


# Function for clean up logic
def _run_finish():
    # Clean up logic can go here if needed
    logging.info('Finished running Nubesgen command')


def _build_args(args_dict: Dict[str, str] = None, **kwargs) -> List[str]:
    if not args_dict:
        args_dict = kwargs
    args_list = []
    for key, val in args_dict.items():
        arg = key.replace('_', '-')
        if val:
            args_list.append(f'--{arg}={val}')
    return args_list


# Returns the path to Nubesgen binary. None if missing the required binary
def _binary_pre_check(download_path: str) -> Optional[str]:
    # if user specifies a download path, download the Nubesgen binary to this location and use it as a path
    if download_path:
        return _download_binary(download_path)

    logging.info('The Nubesgen binary check is in progress...')
    nubesgen_binary_path = _get_existing_path()

    if nubesgen_binary_path:  # found binary
        if _is_latest_version(nubesgen_binary_path):  # no need to update
            logging.info('Your local version of Nubesgen is up to date.')
        else:  # prompt the user to update
            msg = 'We have detected a newer version of Nubesgen. Would you like to download it?'
            response = prompt_y_n(msg, default='n')
            if response:
                return _download_binary()
        return nubesgen_binary_path
    else:  # prompt the user to download binary
        # If users says no, we error out and tell them that this requires the binary
        msg = 'The required binary was not found. Would you like us to download the required binary for you?'

        if not prompt_y_n(msg, default='n'):
            raise ValueError('`az aks nubesgen` requires the missing dependency')

        return _download_binary()


# Returns True if the local binary is the latest version, False otherwise
def _is_latest_version(binary_path: str) -> bool:
    latest_version = CONST_NUBEGEN_CLI_VERSION
    process = subprocess.Popen([binary_path, 'version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if stderr.decode():
        return False
    # return string of result is "version: v0.0.x"
    current_version = stdout.decode().split('\n')[0].strip().split()[-1]
    return latest_version == current_version


# Returns the filename for the current os and architecture
# Returns None if the current system is not supported in nubesgen
def _get_filename() -> Optional[str]:
    operating_system = platform.system().lower()
    if operating_system == "darwin":
        return f'nubesgen-cli-macos'
    return f'nubesgen-cli-{operating_system}'


# Returns path to existing nubesgen binary, None otherwise
def _get_existing_path() -> Optional[str]:
    logging.info('Checking if Nubesgen binary exists locally...')

    filename = _get_filename()
    if not filename:
        return None

    paths = _get_potential_paths()
    if not paths:
        logging.error('List of potential Nubesgen paths is empty')
        return None

    for path in paths:
        binary_file_path = path + '/' + filename
        if os.path.exists(binary_file_path):
            logging.info('Existing binary found at: ' + binary_file_path)
            return binary_file_path
    return None


# Returns a list of potential nubesgen binary paths
def _get_potential_paths() -> List[str]:
    paths = os.environ['PATH'].split(':')
    # the download location of _download_binary()
    default_dir = str(Path.home()) + '/' + '.nubesgen'
    paths.append(default_dir)

    return paths


# Downloads the latest binary to ~/.nubesgen
# Returns path to the binary if sucessful, None otherwise
def _download_binary(download_path: str = '~/.nubesgen') -> Optional[str]:
    logging.info('Attempting to download dependency...')
    download_path = os.path.expanduser(download_path)
    filename = _get_filename()
    if not filename:
        return None

    url = f'https://github.com/microsoft/NubesGen/releases/download/{CONST_NUBEGEN_CLI_VERSION}/{filename}'
    headers = {'Accept': 'application/octet-stream'}

    # Downloading the file by sending the request to the URL
    response = requests.get(url, headers=headers)

    if response.ok:
        # Directory
        if os.path.exists(download_path) is False:
            Path(download_path).mkdir(parents=True, exist_ok=True)
            logging.info(f'Directory {download_path} was created inside of your HOME directory')
        full_path = f'{download_path}/{filename}'

        # Writing the file to the local file system
        with open(full_path, 'wb') as output_file:
            output_file.write(response.content)
        logging.info(f'Download of Nubesgen binary was successful with a status code: {response.status_code}')
        os.chmod(full_path, 0o755)
        return full_path

    logging.error(f'Download of Nubesgen binary was unsuccessful with a status code: {response.status_code}')
    return None
