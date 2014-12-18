#!/usr/bin/env python
import sys
import os
import boto.ec2
import argparse
import time

import boto.utils

def parse_args():
    parser = argparse.ArgumentParser(description='Attach EBS Volume')
    parser.add_argument('--tag', action='store', default='Name', help='Tag key, defaults to Name')
    parser.add_argument('--value', action='store', required=True, help='The tag value to search for')
    parser.add_argument('--attach_as', action='store', required=True, help='device path e.g. /dev/xvdb')
    return parser.parse_args()


def instance_id(): 
    return boto.utils.get_instance_metadata()['instance-id']


def region():
    return boto.utils.get_instance_metadata()['placement']['availability-zone'][:-1]


def zone(): 
    return boto.utils.get_instance_metadata()['placement']['availability-zone']


def filters(tag, val):
    return {'tag:%s' % tag : '%s' % val}


def find(tag, val):
    c = boto.ec2.connect_to_region(region())
    try:
        return [x for x in c.get_all_volumes(filters=filters(tag, val)) if x.zone == zone() and x.status == 'available'][0].id
    except Exception, e:
        print(e)
        sys.exit(2)


def attach(vol_id, attach_as):
    c = boto.ec2.connect_to_region(region())
    try:
        c.attach_volume(vol_id, instance_id(), attach_as)
    except Exception, e:
        print(e)
        sys.exit(3)


def check(attach_as):
    return os.path.exists(attach_as)


def main(args):
    attach(find(args.tag, args.value), args.attach_as)
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


