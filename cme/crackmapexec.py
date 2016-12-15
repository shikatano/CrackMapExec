#!/usr/bin/env python2

#This must be one of the first imports or else we get threading error on completion
from gevent import monkey
monkey.patch_all()

from gevent.pool import Pool
from gevent import joinall
from cme.logger import setup_logger, setup_debug_logger, CMEAdapter
from cme.helpers.misc import gen_random_string
from cme.targetparser import parse_targets
from cme.cli import gen_cli_args
from cme.loaders.protocol_loader import protocol_loader
from cme.loaders.module_loader import module_loader
#from cme.modulechainloader import ModuleChainLoader
from cme.servers.http import CMEServer
from cme.servers.smb import CMESMBServer
from cme.first_run import first_run_setup
from cme.context import Context
from getpass import getuser
from pprint import pformat
from ConfigParser import ConfigParser
import cme
import webbrowser
import sqlite3
import random
import os
import sys
import logging

def main():

    setup_logger()
    logger = CMEAdapter()
    first_run_setup(logger)

    args = gen_cli_args()

    if args.darrell:
        links = open(os.path.join(os.path.dirname(cme.__file__), 'data', 'videos_for_darrel.txt')).read().splitlines()
        try:
            webbrowser.open(random.choice(links))
        except:
            print "Darrel wtf I'm trying to help you, here have a gorilla..."
        sys.exit(1)

    cme_path = os.path.expanduser('~/.cme')

    config = ConfigParser()
    config.read(os.path.join(cme_path, 'cme.conf'))

    #module     = None
    #chain_list = None
    smb_share_name = gen_random_string(5).upper()
    server_port_dict = {'http': 80, 'https': 443, 'smb': 445}
    targets    = []
    current_workspace = config.get('CME', 'workspace')

    if args.verbose:
        setup_debug_logger()

    logging.debug('Passed args:\n' + pformat(vars(args)))

    if hasattr(args, 'username') and args.username:
        for user in args.username:
            if os.path.exists(user):
                args.username.remove(user)
                args.username.append(open(user, 'r'))

    if hasattr(args, 'password') and args.password:
        for passw in args.password:
            if os.path.exists(passw):
                args.password.remove(passw)
                args.password.append(open(passw, 'r'))

    elif hasattr(args, 'hash') and args.hash:
        for ntlm_hash in args.hash:
            if os.path.exists(ntlm_hash):
                args.hash.remove(ntlm_hash)
                args.hash.append(open(ntlm_hash, 'r'))

    if hasattr(args, 'cred_id') and args.cred_id:
        for cred_id in args.cred_id:
            if '-' in str(cred_id):
                start_id, end_id = cred_id.split('-')
                try:
                    for n in range(int(start_id), int(end_id) + 1):
                        args.cred_id.append(n)
                    args.cred_id.remove(cred_id)
                except Exception as e:
                    logger.error('Error parsing database credential id: {}'.format(e))
                    sys.exit(1)

    if hasattr(args, 'target') and args.target:
        for target in args.target:
            if os.path.exists(target):
                with open(target, 'r') as target_file:
                    for target_entry in target_file:
                        targets.extend(parse_targets(target_entry))
            else:
                targets.extend(parse_targets(target))

    smb_server = CMESMBServer(logger, smb_share_name, args.verbose)
    smb_server.start()

    p_loader = protocol_loader()
    protocol_path = p_loader.get_protocols()[args.protocol]['path']
    protocol_db_path = p_loader.get_protocols()[args.protocol]['dbpath']

    protocol_object = getattr(p_loader.load_protocol(protocol_path), args.protocol)
    protocol_db_object = getattr(p_loader.load_protocol(protocol_db_path), 'database')

    db_path = os.path.join(cme_path, 'workspaces', current_workspace, args.protocol + '.db')
    # set the database connection to autocommit w/ isolation level
    db_connection = sqlite3.connect(db_path, check_same_thread=False)
    db_connection.text_factory = str
    db_connection.isolation_level = None
    db = protocol_db_object(db_connection)

    setattr(protocol_object, 'smb_share_name', smb_share_name)

    if hasattr(args, 'module'): #or hasattr(args, 'module_chain'):

        loader = module_loader(args, db, logger)

        if args.list_modules:
            modules = loader.get_modules()

            for m in modules:
                logger.info('{:<25} {}'.format(m, modules[m]['description']))

        elif args.module and args.module_options:

            modules = loader.get_modules()
            for m in modules.keys():
                if args.module.lower() == m.lower():
                    logger.info('{} module options:\n{}'.format(m, modules[m]['options']))

        elif args.module:
            modules = loader.get_modules()
            for m in modules.keys():
                if args.module.lower() == m.lower():
                    module = loader.init_module(modules[m]['path'])
                    setattr(protocol_object, 'module', module)
                    break

            if hasattr(module, 'on_request') or hasattr(module, 'has_response'):

                if hasattr(module, 'required_server'):
                    args.server = getattr(module, 'required_server')

                if not args.server_port:
                    args.server_port = server_port_dict[args.server]

                context = Context(db, logger, args)
                server = CMEServer(module, context, logger, args.server_host, args.server_port, args.server)
                server.start()

                setattr(protocol_object, 'server', server.server)

    try:
        '''
            Open all the greenlet (as supposed to redlet??) threads
            Whoever came up with that name has a fetish for traffic lights
        '''
        pool = Pool(args.threads)
        jobs = [pool.spawn(protocol_object, args, db, str(target)) for target in targets]
        #Dumping the NTDS.DIT and/or spidering shares can take a long time, so we ignore the thread timeout
        #if args.ntds or args.spider:
        #    joinall(jobs)
        #else:
        for job in jobs:
            job.join(timeout=args.timeout)
    except KeyboardInterrupt:
        pass

    try:
        server.shutdown()
    except:
        pass

    smb_server.shutdown()

    print '\n'
    logger.info('KTHXBYE!')
