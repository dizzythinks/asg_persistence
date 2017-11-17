#!/usr/bin/env python
"""Retrieve available EBS volume in AZ."""
import sys
import os
import boto3
import argparse
import time
import urllib2


def parse_args():
    """Argument needs to be parsed."""
    parser = argparse.ArgumentParser(description='Attach EBS Volume')
    parser.add_argument('--tag', action='store', default='Name',
                        help='Tag key, defaults to Name')
    parser.add_argument('--value', action='store', required=True,
                        help='The tag value to search for')
    parser.add_argument('--attach_as', action='store', required=True,
                        help='device path e.g. /dev/xvdb')
    parser.add_argument('--skip_check', action='store', required=False,
                        help='skip the check and just continue')
    parser.add_argument('--wait', action='store_true', required=False,
                        help='If no available volume is found, wait.')
    return parser.parse_args()


def utils(endpoint):
    """Replacing boto.utils, read from instance metadata directly."""
    return urllib2.urlopen(
        'http://169.254.169.254/latest/meta-data/%s' % endpoint
    ).read()


def instance_id():
    """Retrieve current Instance's ID."""
    return utils('instance-id')


def region():
    """Retrieve current Instance's Region."""
    return zone()[:-1]


def zone():
    """Retrieve current Instance's Zone."""
    return utils('placement/availability-zone')


def filters(tag, val):
    """Helper method for parsing filters."""
    return {
        'Name': 'tag:%s' % tag,
        'Values': ['%s' % val]
    }


def find(tag, val, client=None):
    """Locate a free volume for this instance."""
    c = client or boto3.client('ec2', region())
    try:
        for x in c.describe_volumes(Filters=[filters(tag, val)])['Volumes']:
            if x['AvailabilityZone'] == zone():
                if x['State'] == 'available':
                    return x
    except Exception, e:
        print(e)
        sys.exit(2)


def attach(vol_id, attach_as, client=None):
    """Attach EBS volume to an Instance."""
    c = client or boto3.client('ec2', region())
    if not vol_id:
        raise Exception('No volumes available')
        sys.exit(4)

    try:
        c.attach_volume(
            VolumeId=vol_id,
            InstanceId=instance_id(),
            Device=attach_as)
    except Exception, e:
        print(e)
        sys.exit(3)


def check(attach_as):
    """Resolve attach_as path."""
    return os.path.exists(attach_as)


def already_attached(args):
    """Check if the disk is actually already attached."""
    ec2 = boto3.resource('ec2', region())
    instance = ec2.Instance(instance_id())
    for v in instance.volumes.all():
        volume = ec2.Volume(v.id)
        if volume.tags:
            for tag in volume.tags:
                if tag['Key'] == args.tag and tag['Value'] == args.value:
                    print('Disk is already attached!')
                    sys.exit(0)


def main(args):
    """Initialize find+attach action."""
    already_attached(args)

    client = boto3.client('ec2', region())
    volume_id = None
    volume = find(args.tag, args.value, client)
    if volume:
        volume_id = volume['VolumeId']
        if volume['State'] != 'available' and args.wait:
            volume_waiter = client.get_waiter('volume_available')
            volume_waiter.wait(VolumeIds=[volume_id])

    attach(volume_id, args.attach_as, client)

    if not args.skip_check:
        counter = 0
        while not check(args.attach_as):
            counter = counter + 5
            time.sleep(5)
            if counter > 60:
                raise Exception('Timeout waiting for attachment')
                sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main(parse_args())
