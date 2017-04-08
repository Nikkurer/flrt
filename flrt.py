#!/usr/bin/env python3

# ---------------------------------------------------------
# PROJECT:  flrt - IBM FLRT URL generator
# AUTHOR:   Aleksey Trifonov <av.trifonov@jet.msk.su>
# UPDATE:   01 Apr 2017
# REVISION: v0.20
# TODO add HMC version parsing
# ---------------------------------------------------------


import os
import re
import sys
import argparse

from pprint import pprint as print
from mimetypes import guess_type
from pyunpack import Archive, PatoolError
from tempfile import TemporaryDirectory

__version__ = '0.21'

arg_parser = argparse.ArgumentParser(description='Flrt if an IBM FLRT URL generator.')
arg_parser.add_argument('--file', '-f', action='store_const', help='Parse saved flrt inventory file.')
arg_parser.add_argument('--dir', '-d', action='store_const', help='Parse snap files in directory.')


def parse_snaps(snap_dir):
    reports = {}
    par_num = 0

    if os.path.isdir(os.path.expanduser(snap_dir)):
        partition_numbers = {}
        os_file = 'general/oslevel.info'
        vios_file = 'svCollect/VIOS.level'
        general_file = 'general/general.snap'

        for file in os.scandir(os.path.expanduser(snap_dir)):
            if file.is_file() and guess_type(file.name)[1] == 'compress':
                with TemporaryDirectory() as tmpdir:
                    try:
                        print(file)
                        Archive(file).extractall(tmpdir)
                        os.chdir(tmpdir)

                    except PatoolError:
                        print("Oops, something wrong with the snap...", file.name)
                        continue

                    if os.access(general_file, os.R_OK):
                        with open(general_file, 'r', encoding="utf-8") as general:
                            general_data = general.read()

                    # Server info
                    sys_vpd = re.findall(r'(System VPD(?:.|\n)*?)(?=Physical)', general_data)
                    type_model = re.findall(r'Machine Type and Model......([\d\w\-]+)', sys_vpd[0])[0]
                    serial = re.findall(r'Cabinet Serial No...([\d\w]+)', sys_vpd[0])[0]
                    firmware = re.findall((r'sys0!system:([\w\d]+_\d+)'), general_data)[0]

                    # OS info
                    inet0_data = re.findall(r'(lsattr -El inet0(?:.|\n)*?)(?=lsattr)', general_data)
                    hostname = re.findall(r'hostname\s+([-\._\w\d]+)(?:\s|\n)', inet0_data[0])[0]

                    # TODO make partition number local for each machine, in second dict max_par{serial:mp, serial;mp}
                    # partition_numbers = {serial: partition, serial: partition}


                    if serial not in reports:
                        partition_numbers.update({serial: int('0')})
                        partition = 'p{0}'.format(str(partition_numbers[serial]))
                        reports.update({serial: {'plat': 'power', 'reportname': serial, 'reportType': 'power',
                                                 partition: {'fw': firmware, 'mtm': type_model}}})

                    partition_exists = False

                    for partition in reports[serial]:
                        if type(reports[serial][partition]) is dict:
                            if hostname in reports[serial][partition].values():
                                partition_exists = True

                    if partition_exists == False:
                        par_num += 1
                        partition = 'p{0}'.format(str(par_num))

                        if os.access(vios_file, os.R_OK):
                            # Open VIOS.level, find version and fill it in dict
                            with open(vios_file, 'r') as vios:
                                vios = re.findall(r'VIOS Level is ([\.\d]+)', vios.read().strip())[0]
                                reports[serial].update({partition: {'os': 'vios', 'parnm': hostname, 'vios': vios}})

                        elif os.access(os_file, os.R_OK):

                            # Open oslevel.info, find version and fill it in dict
                            with open(os_file, 'r') as aix:
                                aix = re.findall(r'(\d{4}-\d{2}-\d{2})', aix.read().strip())[0]
                                reports[serial].update({partition: {'os': 'aix', 'parnm': hostname, 'aix': aix}})

        par_num += 1

    return reports


def parse_file(filename):
    # Known FLRT inventory options
    inventory_options = ['reportname', 'plat', 'reportType', 'format']

    machine = {}

    with open(filename, 'r', encoding='utf-8') as inventory:
        for line in inventory:
            line = line.strip()
            tmp_line = line.split('=')

            # p0 - server
            # pn (n>0) - LPARs

            if tmp_line[0] in inventory_options:
                machine.update({tmp_line[0]: tmp_line[1]})

            elif re.match(r'p[0-9]*\.', tmp_line[0]):
                option = tmp_line[0].split('.')

                if option[0] in machine:
                    machine[option[0]].update({option[1]: tmp_line[1]})

                else:
                    machine.update({option[0]: {}})
                    machine[option[0]].update({option[1]: tmp_line[1]})

    return machine


# FIXME: нужно переименовать machine
def url_gen(machine):
    url = 'http://www14.software.ibm.com/webapp/set2/flrt/query?'
    query_type = 'format=html'
    for key, value in machine.items():

        if key == 'format':
            continue

        elif isinstance(value, str):
            url = '{}{}&{}={}'.format(url, query_type, key, value)

        elif isinstance(value, dict):
            for option_name, option_value in value.items():
                url = '{}{}&{}.{}={}'.format(url, query_type, key, option_name, option_value)
    return url


if __name__ == '__main__':

    args = arg_parser.parse_args()

    if args.file:
        # FIXME: нужно переименовать machine
        try:
            machine = parse_file(args.file)
            query_url = url_gen(machine)
            print(query_url)
            sys.exit(0)
        except Exception as e:
            print(e)
            sys.exit(1)

    if args.dir:
        # FIXME: нужно переименовать machine и reports
        try:
            reports = parse_snaps(args.dir)
            for machine in reports.keys():
                query_url = url_gen(reports[machine])
                print(query_url)
                sys.exit(0)
        except Exception as e:
            print(e)
            sys.exit(1)
