import requests
from requests import ConnectionError
#The following disables the InsecureRequests warning and the 'Starting new HTTPS connection' log message
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

import cmd
from time import sleep
from cme.msfrpc import Msfrpc
from cme.protocols.smb.database import database

class navigator(cmd.Cmd):
    def __init__(self, main_menu):
        cmd.Cmd.__init__(self)

        self.main_menu = main_menu
        self.config = main_menu.config
        self.db = database(main_menu.conn)
        self.prompt = 'cmedb ({})({}) > '.format(main_menu.workspace, 'smb')

    def do_back(self, line):
        raise

    def display_creds(self, creds):

        print "\nCredentials:\n"
        print "  CredID  Admin On     CredType    Domain           UserName             Password"
        print "  ------  --------     --------    ------           --------             --------"

        for cred in creds:
            # (id, credtype, domain, username, password, host, notes, sid)
            credID = cred[0]
            credType = cred[1]
            domain = cred[2]
            username = cred[3]
            password = cred[4]

            links = self.db.get_links(credID=credID)

            print u"  {}{}{}{}{}{}".format('{:<8}'.format(credID),
                                           '{:<13}'.format(str(len(links)) + ' Host(s)'),
                                           '{:<12}'.format(credType),
                                           u'{:<17}'.format(domain.decode('utf-8')),
                                           u'{:<21}'.format(username.decode('utf-8')),
                                           u'{:<17}'.format(password.decode('utf-8')))

        print ""

    def display_groups(self, groups):
        print '\nGroups:\n'
        print " GroupID  Name"
        print " -------  ----"

        for group in groups:
            groupID = group[0]
            name = group[1]

            print u" {} {}".format('{:<8}'.format(groupID), '{:<15}'.format(name))

        print ""

    def display_hosts(self, hosts):

        print "\nHosts:\n"
        print "  HostID  Admins         IP               Hostname                 Domain           OS"
        print "  ------  ------         --               --------                 ------           --"

        for host in hosts:
            # (id, ip, hostname, domain, os)
            hostID = host[0]
            ip = host[1]
            hostname = host[2]
            domain = host[3]
            os = host[4]

            links = self.db.get_links(hostID=hostID)

            print u"  {}{}{}{}{}{}".format('{:<8}'.format(hostID),
                                           '{:<15}'.format(str(len(links)) + ' Cred(s)'),
                                           '{:<17}'.format(ip),
                                           u'{:<25}'.format(hostname.decode('utf-8')),
                                           u'{:<17}'.format(domain.decode('utf-8')),
                                           '{:<17}'.format(os))

        print ""

    def do_import(self, line):

        if not line:
            return

        if line == 'empire':
            headers = {'Content-Type': 'application/json'}

            #Pull the username and password from the config file
            payload = {'username': self.config.get('Empire', 'username'),
                       'password': self.config.get('Empire', 'password')}

            #Pull the host and port from the config file
            base_url = 'https://{}:{}'.format(self.config.get('Empire', 'api_host'), self.config.get('Empire', 'api_port'))

            try:
                r = requests.post(base_url + '/api/admin/login', json=payload, headers=headers, verify=False)
                if r.status_code == 200:
                    token = r.json()['token']

                    url_params = {'token': token}
                    r = requests.get(base_url + '/api/creds', headers=headers, params=url_params, verify=False)
                    creds = r.json()

                    for cred in creds['creds']:
                        if cred['credtype'] == 'token' or cred['credtype'] == 'krbtgt' or cred['username'].endswith('$'):
                            continue

                        self.db.add_credential(cred['credtype'], cred['domain'], cred['username'], cred['password'])

                    print "[+] Empire credential import successful"
                else:
                    print "[-] Error authenticating to Empire's RESTful API server!"

            except ConnectionError as e:
                print "[-] Unable to connect to Empire's RESTful API server: {}".format(e)

        elif line == 'metasploit':
            msf = Msfrpc({'host': self.config.get('Metasploit', 'rpc_host'),
                          'port': self.config.get('Metasploit', 'rpc_port')})

            try:
                msf.login('msf', self.config.get('Metasploit', 'password'))
            except MsfAuthError:
                print "[-] Error authenticating to Metasploit's MSGRPC server!"
                return

            console_id = str(msf.call('console.create')['id'])

            msf.call('console.write', [console_id, 'creds\n'])

            sleep(2)

            creds = msf.call('console.read', [console_id])

            for entry in creds['data'].split('\n'):
                cred = entry.split()
                try:
                    host = cred[0]
                    port = cred[2]
                    proto = cred[3]
                    username = cred[4]
                    password = cred[5]
                    cred_type = cred[6]

                    if proto == '(smb)' and cred_type == 'Password':
                        self.db.add_credential('plaintext', '', username, password)

                except IndexError:
                    continue

            msf.call('console.destroy', [console_id])

            print "[+] Metasploit credential import successful"

    def complete_import(self, text, line, begidx, endidx):
        "Tab-complete 'import' commands."

        commands = ["empire", "metasploit"]

        mline = line.partition(' ')[2]
        offs = len(mline) - len(text)
        return [s[offs:] for s in commands if s.startswith(mline)]


    def do_groups(self, line):

        filterTerm = line.strip()

        if filterTerm == "":
            groups = self.db.get_groups()
            self.display_groups(groups)

        else:
            groups = self.db.get_groups(filterTerm=filterTerm)

            if len(groups) > 1:
                self.display_groups(groups)
            elif len(groups) == 1:
                print '\nGroup:\n'
                print " GroupID  Name"
                print " -------  ----"

                for group in groups:
                    groupID = group[0]
                    name = group[1]

                    members = self.db_

    def do_hosts(self, line):

        filterTerm = line.strip()

        if filterTerm == "":
            hosts = self.db.get_hosts()
            self.display_hosts(hosts)

        else:
            hosts = self.db.get_hosts(filterTerm=filterTerm)

            if len(hosts) > 1:
                self.display_hosts(hosts)
            elif len(hosts) == 1:
                print "\nHost(s):\n"
                print "  HostID  IP               DC    Hostname                 Domain           OS"
                print "  ------  --               --   --------                 ------           --"

                hostIDList = []

                for host in hosts:
                    hostID = host[0]
                    hostIDList.append(hostID)

                    ip = host[1]
                    hostname = host[2]
                    domain = host[3]
                    os = host[4]
                    dc = host[5]

                    print u"  {}{}{}{}{}".format('{:<8}'.format(hostID),
                                                 '{:<17}'.format(ip),
                                                 '{:<17}'.format(dc),
                                                 u'{:<25}'.format(hostname.decode('utf-8')),
                                                 u'{:<17}'.format(domain.decode('utf-8')),
                                                 '{:<17}'.format(os))

                print ""

                print "\nCredential(s) with Admin Access:\n"
                print "  CredID  CredType    Domain           UserName             Password"
                print "  ------  --------    ------           --------             --------"

                for hostID in hostIDList:
                    links = self.db.get_links(hostID=hostID)

                    for link in links:
                        linkID, credID, hostID = link
                        creds = self.db.get_credentials(filterTerm=credID)

                        for cred in creds:
                            credID = cred[0]
                            credType = cred[1]
                            domain = cred[2]
                            username = cred[3]
                            password = cred[4]

                            print u"  {}{}{}{}{}".format('{:<8}'.format(credID),
                                                        '{:<12}'.format(credType),
                                                        u'{:<17}'.format(domain.decode('utf-8')),
                                                        u'{:<21}'.format(username.decode('utf-8')),
                                                        u'{:<17}'.format(password.decode('utf-8')))

                print ""

    def do_creds(self, line):

        filterTerm = line.strip()

        if filterTerm == "":
            creds = self.db.get_credentials()
            self.display_creds(creds)

        elif filterTerm.split()[0].lower() == "add":

            # add format: "domain username password <notes> <credType> <sid>
            args = filterTerm.split()[1:]

            if len(args) == 3:
                domain, username, password = args
                if validate_ntlm(password):
                    self.db.add_credential("hash", domain, username, password)
                else:
                    self.db.add_credential("plaintext", domain, username, password)

            else:
                print "[!] Format is 'add domain username password"
                return

        elif filterTerm.split()[0].lower() == "remove":

            args = filterTerm.split()[1:]
            if len(args) != 1 :
                print "[!] Format is 'remove <credID>'"
                return
            else:
                self.db.remove_credentials(args)
                self.db.remove_links(credIDs=args)

        elif filterTerm.split()[0].lower() == "plaintext":
            creds = self.db.get_credentials(credtype="plaintext")
            self.display_creds(creds)

        elif filterTerm.split()[0].lower() == "hash":
            creds = self.db.get_credentials(credtype="hash")
            self.display_creds(creds)

        else:
            creds = self.db.get_credentials(filterTerm=filterTerm)

            print "\nCredential(s):\n"
            print "  CredID  CredType    Pillaged From HostID  Domain           UserName             Password"
            print "  ------  --------    --------------------  ------           --------             --------"

            credIDList = []

            for cred in creds:
                credID = cred[0]
                credIDList.append(credID)

                credType = cred[1]
                domain = cred[2]
                username = cred[3]
                password = cred[4]
                pillaged_from = cred[5]

                print u"  {}{}{}{}{}{}".format('{:<8}'.format(credID),
                                              '{:<12}'.format(credType),
                                              '{:<22}'.format(pillaged_from),
                                              u'{:<17}'.format(domain.decode('utf-8')),
                                              u'{:<21}'.format(username.decode('utf-8')),
                                              u'{:<17}'.format(password.decode('utf-8'))
                                              )

            print ""

            print "\nAdmin Access to Host(s):\n"
            print "  HostID  IP               Hostname                 Domain           OS"
            print "  ------  --               --------                 ------           --"

            for credID in credIDList:
                links = self.db.get_links(credID=credID)

                for link in links:
                    linkID, credID, hostID =  link
                    hosts = self.db.get_hosts(hostID)

                    for host in hosts:
                        hostID = host[0]
                        ip = host[1]
                        hostname = host[2]
                        domain = host[3]
                        os = host[4]

                        print u"  {}{}{}{}{}".format('{:<8}'.format(hostID),
                                                     '{:<17}'.format(ip),
                                                     u'{:<25}'.format(hostname.decode('utf-8')),
                                                     u'{:<17}'.format(domain.decode('utf-8')),
                                                     '{:<17}'.format(os))

            print ""

    def complete_creds(self, text, line, begidx, endidx):
        "Tab-complete 'creds' commands."

        commands = [ "add", "remove", "hash", "plaintext"]

        mline = line.partition(' ')[2]
        offs = len(mline) - len(text)
        return [s[offs:] for s in commands if s.startswith(mline)]
