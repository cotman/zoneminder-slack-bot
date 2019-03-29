#
# Copyright 2016 Robert Clark (clark@exiter.com)
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

"""
Called by ZoneMinder whenever an alert is generated. It find the most important frame
 and posts it to Slack.
"""

import argparse
import logging
import sys
import os

from configparser import ConfigParser
from slackclient import SlackClient
import zonebot
from zonebot.zoneminder.zoneminder import ZoneMinder

LOGGER = logging.getLogger("zonebot")


def zonebot_alert_main():
    """
    Main method for the zonebot-alert script
    """

    # basic setup
    zonebot.init_logging()

    #  Set up the command line arguments we support
    parser = argparse.ArgumentParser(
        description='A script that receives event notifications from ZoneMinder',
        epilog="Version " + zonebot.__version__ + " (c) " +
               zonebot.__author__ +
               " (" + zonebot.__email__ + ")")

    parser.add_argument('-c', '--config',
                        metavar='file',
                        required=False,
                        help='Load the specified config file')

    parser.add_argument('event_id',
                        help='The ID of the event')

    parser.add_argument('event_dir',
                        help='The directory of the event')

    args = parser.parse_args()

    # Create the configuration from the arguments
    config = ConfigParser()
    config_file = zonebot.find_config(args.config)
    if config_file:
        config.read(config_file)
    else:
        LOGGER.error("No config file could be located")
        sys.exit(1)

    if not zonebot.validate_config(config):
        sys.exit(1)

    # Reconfigure logging with config values
    zonebot.init_logging(config)

    LOGGER.info("Sending alert about event with ID %s and directory %s", args.event_id, args.event_dir)

    zone_minder = ZoneMinder(config)
    zone_minder.login()

    data = zone_minder.load_event(args.event_id)
    data = zone_minder.parse_event(data)

    if 'image_filename' not in data:
        LOGGER.error("Could not which still frame to upload")

    image_filename = os.path.join(args.event_dir, data['image_filename'])
    if not os.path.isfile(image_filename):
        LOGGER.error("Expect image still file %s could not be read", image_filename)

    comment = 'Detected {0} on monitor {1}. {2}/index.php?view=event&eid={3}'.format(
        data['cause'],
        data['source'],
        config['ZoneMinder']['url'],
        data['id']
    )

    filename = '{0}_Event_{1}.jpeg'.format(data['source'], data['id'])

    # And off it goes ...
    slack = SlackClient(config['Slack']['api_token'])

    result = slack.api_call('files.upload',
                            initial_comment=comment,
                            filename=filename,
                            channels=config['Slack']['channels'],
                            # Note: this is broken in slackclient 1.0.1 and earlier
                            file=open(image_filename, 'rb'))

    if not result:
        LOGGER.error("Could not complete Slack API call")
        sys.exit(1)

    if not result['ok']:
        error = "Error: "
        if 'error' in result:
            error = result['error']
        elif 'warning' in result:
            error = result['warning']

        LOGGER.error("Could not upload image: %s", error)
        sys.exit(1)

    if 'permalink_public' in result['file']:
        link = result['file']['permalink_public']
    elif 'permalink' in result['file']:
        link = result['file']['permalink']
    else:
        link = 'unknown'

    LOGGER.info('Image posted to %s as %s', config['Slack']['channels'], link)
    sys.exit(0)


if __name__ == "__main__":
    """
    Run main function.
    """

    zonebot_alert_main()
