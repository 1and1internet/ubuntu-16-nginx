"""
Configurability script module: Process which configures nginx.

The process method

 -==========================================================================-
    Written for python 2.7 because it is included with Ubuntu 16.04 and I
      wanted to avoid requiring that python 3 also be installed.
 -==========================================================================-
"""

import os
import os.path
import logging
import re

# noinspection PyUnresolvedReferences
from configurability import custom_files

logger = logging.getLogger(__name__)


# noinspection PyBroadException,PyUnboundLocalVariable
def process(name, config, directory, config_translator=None):
    """
    Configures Nginx based on the input configuration.

    Supports Document Root and Gzip settings.

    :param name: Name of this section of the configuration
    :param config: The configuration dictionary for this section
    :param directory: The directory in which the input files are mounted
    :param config_translator: Optional callable method for preprocessing config items
    :return:
    """
    for required_key in [
        'configuration_file_name'
    ]:
        if required_key not in config:
            raise Exception(
                'Required key %s not present in %s section of internal configuration'
                % (name, required_key)
            )
    logger.info('Configuring %s' % name)

    try:
        custom_values, file_format = custom_files.read_custom_file(
            os.path.join(directory, config['configuration_file_name'])
        )
    except Exception as file_reading_exception:
        logger.error(str(file_reading_exception))  # don't log the full stack trace
        logger.info('Not configuring %s (not a critical failure)' % name)
        return  # abort but don't fail

    assert custom_values is not None and isinstance(custom_values, dict)

    if config_translator:
        for key, value in custom_values.iteritems():
            custom_values[key] = config_translator.process(key, value)

    nginx_directory = os.path.join('etc', 'nginx')

    sites_enabled_directory = os.path.join(nginx_directory, 'sites-enabled')

    #
    # Document Root
    #

    document_root_key = 'DOCUMENT_ROOT'
    document_root_default = 'html'

    if document_root_key.lower() in custom_values:

        document_root = custom_values[document_root_key.lower()]

        if os.environ.get(document_root_key, document_root_default) not in [document_root, document_root_default]:
            raise Exception('Legacy %s variable is present with a conflicting value' % document_root_key)

        document_root_path = os.path.join('var', 'www', document_root)
        if not os.path.exists(document_root_path):
            os.makedirs(document_root_path)

        #
        #  Update the on disk well known location so that other scripts
        #  which need to know the document root can look it up.
        #
        with open(os.path.join('etc', document_root_key), 'w') as file_handle:
            file_handle.write("%s\n" % document_root)

        #
        # Update the nginx configuration
        #

        variable_regex = re.compile('\${?%s}?' % document_root_key)

        root_command_regex = re.compile('root /var/www/.*;')
        new_root_command = 'root /var/www/%s;' % document_root

        for file_path in os.listdir(sites_enabled_directory):
            full_file_path = os.path.join(sites_enabled_directory, file_path)
            if os.path.isfile(full_file_path):
                write_needed = False
                with open(full_file_path, 'r') as file_handle:
                    lines = file_handle.readlines()
                    for index, line in enumerate(lines):
                        lines[index] = variable_regex.sub(document_root, lines[index])
                        lines[index] = root_command_regex.sub(new_root_command, lines[index])
                        write_needed = write_needed or lines[index] != line
                if write_needed:
                    with open(full_file_path, 'w') as file_handle:
                        file_handle.writelines(lines)

        logger.info('%13s = %s' % (document_root_key, document_root))

    #
    # Gzip
    #

    gzip_key = 'gzip'
    if gzip_key in custom_values:

        gzip = False

        if custom_values[gzip_key].strip().upper() != 'OFF':
            gzip = True
            gzip_level = custom_values[gzip_key]
        else:
            gzip_level = '0'

        #
        #  Update the nginx configuration
        #

        gzip_command_regex = re.compile('gzip \w*;')
        new_gzip_command = 'gzip on;' if gzip else 'gzip off;'

        if gzip:
            gzip_level_command_regex = re.compile('gzip_comp_level \d*;')
            new_gzip_level_command = 'gzip_comp_level %s;' % gzip_level

        full_file_path = os.path.join(nginx_directory, 'conf.d', 'gzip.conf')
        if os.path.isfile(full_file_path):

            write_needed = False
            with open(full_file_path, 'r') as file_handle:

                # Read
                lines = file_handle.readlines()

                # Modify
                for index, line in enumerate(lines):
                    lines[index] = gzip_command_regex.sub(new_gzip_command, lines[index])
                    if gzip:
                        lines[index] = gzip_level_command_regex.sub(new_gzip_level_command, lines[index])
                    write_needed = write_needed or lines[index] != line

            # Write
            if write_needed:
                with open(full_file_path, 'w') as file_handle:
                    file_handle.writelines(lines)

        logger.info('%13s = %s' % (gzip_key.upper(), gzip_level))
