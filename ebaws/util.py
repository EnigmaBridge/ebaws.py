import argparse
import collections
import distutils.version  # pylint: disable=import-error,no-name-in-module
import errno
import logging
import os
import platform
import re
import six
import socket
import stat
import subprocess
import sys
import errors
import shutil


logger = logging.getLogger(__name__)


def run_script(params):
    """Run the script with the given params.

    :param list params: List of parameters to pass to Popen

    """
    try:
        proc = subprocess.Popen(params,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

    except (OSError, ValueError):
        msg = "Unable to run the command: %s" % " ".join(params)
        logger.error(msg)
        raise errors.SubprocessError(msg)

    stdout, stderr = proc.communicate()

    if proc.returncode != 0:
        msg = "Error while running %s.\n%s\n%s" % (
            " ".join(params), stdout, stderr)
        # Enter recovery routine...
        logger.error(msg)
        raise errors.SubprocessError(msg)

    return stdout, stderr


def exe_exists(exe):
    """Determine whether path/name refers to an executable.

    :param str exe: Executable path or name

    :returns: If exe is a valid executable
    :rtype: bool

    """
    def is_exe(path):
        """Determine if path is an exe."""
        return os.path.isfile(path) and os.access(path, os.X_OK)

    path, _ = os.path.split(exe)
    if path:
        return is_exe(exe)
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            if is_exe(os.path.join(path, exe)):
                return True

    return False


def make_or_verify_dir(directory, mode=0o755, uid=0, strict=False):
    """Make sure directory exists with proper permissions.

    :param str directory: Path to a directory.
    :param int mode: Directory mode.
    :param int uid: Directory owner.
    :param bool strict: require directory to be owned by current user

    :raises .errors.Error: if a directory already exists,
        but has wrong permissions or owner

    :raises OSError: if invalid or inaccessible file names and
        paths, or other arguments that have the correct type,
        but are not accepted by the operating system.

    """
    try:
        os.makedirs(directory, mode)
    except OSError as exception:
        if exception.errno == errno.EEXIST:
            if strict and not check_permissions(directory, mode, uid):
                raise errors.Error(
                    "%s exists, but it should be owned by user %d with"
                    "permissions %s" % (directory, uid, oct(mode)))
        else:
            raise


def check_permissions(filepath, mode, uid=0):
    """Check file or directory permissions.

    :param str filepath: Path to the tested file (or directory).
    :param int mode: Expected file mode.
    :param int uid: Expected file owner.

    :returns: True if `mode` and `uid` match, False otherwise.
    :rtype: bool

    """
    file_stat = os.stat(filepath)
    return stat.S_IMODE(file_stat.st_mode) == mode and file_stat.st_uid == uid


def safe_create_with_backup(path, mode='w', chmod=0o644):
    """
    Safely creates a new file, backs up the old one if existed
    :param path:
    :param mode:
    :param chmod:
    :return:
    """
    backup_path = None
    if os.path.exists(path):
        fhnd, fname = unique_file(path, chmod)
        fhnd.close()
        shutil.move(path, fname)
        backup_path = fname
    return safe_open(path, mode, chmod), backup_path


def safe_open(path, mode="w", chmod=None, buffering=None):
    """Safely open a file.

    :param str path: Path to a file.
    :param str mode: Same os `mode` for `open`.
    :param int chmod: Same as `mode` for `os.open`, uses Python defaults
        if ``None``.
    :param int buffering: Same as `bufsize` for `os.fdopen`, uses Python
        defaults if ``None``.

    """
    # pylint: disable=star-args
    open_args = () if chmod is None else (chmod,)
    fdopen_args = () if buffering is None else (buffering,)
    return os.fdopen(
        os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, *open_args),
        mode, *fdopen_args)


def safe_new_dir(path, mode=0o755):
    """
    Creates a new unique directory. If the given directory already exists,
    linear incrementation is used to create a new one.


    :param path:
    :param mode:
    :return:
    """
    path, tail = os.path.split(path)
    return _unique_dir(
        path, dirname_pat=(lambda count: "%s_%04d" % (tail, count)),
        count=0, mode=mode)


def _unique_dir(path, dirname_pat, count, mode):
    while True:
        current_path = os.path.join(path, dirname_pat(count))
        try:
            os.makedirs(current_path, mode)
            return os.path.abspath(current_path)

        except OSError as exception:
            # "Dir exists," is okay, try a different name.
            if exception.errno != errno.EEXIST:
                raise
        count += 1


def _unique_file(path, filename_pat, count, mode):
    while True:
        current_path = os.path.join(path, filename_pat(count))
        try:
            return safe_open(current_path, chmod=mode),\
                os.path.abspath(current_path)
        except OSError as err:
            # "File exists," is okay, try a different name.
            if err.errno != errno.EEXIST:
                raise
        count += 1


def unique_file(path, mode=0o777):
    """Safely finds a unique file.

    :param str path: path/filename.ext
    :param int mode: File mode

    :returns: tuple of file object and file name

    """
    path, tail = os.path.split(path)
    filename, extension = os.path.splitext(tail)
    return _unique_file(
        path, filename_pat=(lambda count: "%s_%04d%s" % (filename, count, extension if not None else '')),
        count=0, mode=mode)


def unique_lineage_name(path, filename, mode=0o777):
    """Safely finds a unique file using lineage convention.

    :param str path: directory path
    :param str filename: proposed filename
    :param int mode: file mode

    :returns: tuple of file object and file name (which may be modified
        from the requested one by appending digits to ensure uniqueness)

    :raises OSError: if writing files fails for an unanticipated reason,
        such as a full disk or a lack of permission to write to
        specified location.

    """
    preferred_path = os.path.join(path, "%s.conf" % (filename))
    try:
        return safe_open(preferred_path, chmod=mode), preferred_path
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise
    return _unique_file(
        path, filename_pat=(lambda count: "%s-%04d.conf" % (filename, count)),
        count=1, mode=mode)


def safely_remove(path):
    """Remove a file that may not exist."""
    try:
        os.remove(path)
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise


