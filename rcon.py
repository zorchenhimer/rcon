#!/usr/bin/python

import yaml
import re
import socket
import sys
import os

re_number_check = re.compile('^(\d+)$')

def echo(message, prefix='(rcon)'):
	""" Print stuff to the console. """
	if message.find("\n") > -1:
		message = message.split("\n")
		for line in message:
			print("{pre} {msg}".format(pre=prefix, msg=line))
	else:
		print("{pre} {msg}".format(pre=prefix, msg=message))

def prompt(message='> '):
	""" Prompt the user for input. """
	if sys.version_info.major == 3:
		return input(message)
	else:
		return raw_input(message)

class ServerException(Exception):
	def __init__(self, code):
		self.code = code
	
	def __str__(self):
		return repr(self.code)

class Server(object):
	def __init__(self, name, address, port, password=None):
		self.__address = address
		self.__port = port
		self.__password = password
		self.__name = name
		self.__sock = None
	
	@property
	def Address(self):
		return self.__address
	
	@property
	def Port(self):
		return self.__port
	
	@property
	def Password(self):
		return self.__password
	
	@property
	def Name(self):
		return self.__name
	
	@Password.setter
	def Password(self, val):
		## TODO: validation
		self.__password = val
	
	def connect(self, quiet=False):
		self.__sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.__sock.settimeout(10)
		if self.__password == None or len(self.__password) == 0:
			go_pw = True
			while go_pw:
				p = prompt("Password: ")
				if len(p) == 0:
					echo('Password cannot be blank.  Try again')
				else:
					self.__password = p
					go_pw = False
		if not quiet:
			return self.rcon('serverinfo')
			
	
	def disconnect(self):
		if self.__sock is not None:
			self.__sock.close()
	
	def rcon(self, command):
		if self.__sock is None:
			echo('Warning: rcon before connect. Attempting connect now.')
			self.connect(True)
		try:
			self.__sock.connect((self.__address, self.__port))
			self.__sock.send("\xFF\xFF\xFF\xFFrcon {password} {command}\0".format(password=self.__password, command=command))
			resp = self.__sock.recv(4092)
			return resp[10:-1]
			
		except Exception as e:
			return "Command failed: {error}".format(error=e)
	
	def yaml(self):
		return "{name}:\n  address: \"{address}\"\n  port: {port}\n  password: \"{password}\"\n".format(
			name = self.Name,
			address = self.Address,
			port = self.Port,
			password = self.Password)
	
	def __str__(self):
		p = '*' * len(self.__password)
		return "{name} {addr}:{port} {passwd}".format(name=self.Name, addr=self.Address, port=self.Port, passwd=p)

class RconClient(object):
	def __init__(self, server_config = 'servers.yaml'):
		self.__server_list = []
		self.__server_config = server_config
		self.__current_server = None
	
	def run(self):
		if not os.path.isfile(self.__server_config):
			echo('No server configuration found.  Attepmting to make one.')
			try:
				f = open(self.__server_config, 'w')
				f.close()
				
				go_p = True
				while go_p:
					p = prompt('Configure servers now? [Y/n] ').lower()
					if p == 'y' or p == '':
						self.newConfig()
						go_p = False
					elif p == 'n':
						go_p = False
			except Exception as ex:
				echo('Failed to create server configuration: {err}'.format(err = ex))
		else:
			data = None
			with open(self.__server_config, 'r') as infile:
				try:
					data = yaml.safe_load(infile.read())
				except Exception as ex:
					echo('Error loading configuration file: {err}'.format(err = ex))
					data = None
			
			if data is not None:
				for s in data.keys():
					try:
						self.__server_list.append(Server(s, data[s]['address'], data[s]['port'], data[s]['password']))
					except Exception as ex:
						echo('Error loading server configuration: {err}'.format(err = ex))
		
		running = True
		re_empty_string = re.compile('^([\s]+)$')
		re_connect_name = re.compile('^\.connect (?P<name>[^\s]+)$')
		re_connect_full = re.compile('^\.connect (?P<address>[^\s:]+):(?P<port>\d+) (?P<password>[^\s]+)$')
		while running:
			cmd_input = ''
			if self.__current_server is not None:
				cmd_input = prompt('({name}) > '.format(name=self.__current_server.Name))
			else: 
				cmd_input = prompt()
			
			match_connect_name = re.match(re_connect_name, cmd_input)
			match_connect_full = re.match(re_connect_full, cmd_input)
			
			match_empty_string = re.match(re_empty_string, cmd_input)
			if match_empty_string or len(cmd_input) == 0:
				## Empty input.  Don't error, just continue.
				continue
			elif cmd_input == '.exit':
				running = False
				continue
			elif cmd_input == '.disconnect':
				if self.__current_server == None:
					echo('Not connected to a server!')
				else:
					self.__current_server.disconnect()
					self.__current_server = None
			## TODO: manage servers here too
			elif cmd_input == '.servers':
				echo('== Configured servers ==')
				for s in self.__server_list:
					echo(str(s))
				echo('== End of list ==')
				echo('Current server: {s}'.format(s=self.__current_server))
			elif match_connect_name is not None:
				if len(self.__server_list) == 0:
					echo('Error: server list is empty!')
				server = [s for s in self.__server_list if s.Name == match_connect_name.group('name')]
				if server is None or len(server) == 0:
					echo('Error: invalid server name')
				else:
					self.__current_server = server[0]
				
				try:
					echo(self.__current_server.connect(), '({name}) '.format(name=self.__current_server.Name))
				except ServerException as se:
					echo('Connection failed: {err}'.format(err=ex))
					self.__current_server = None
			elif match_connect_full is not None:
				sname = "{addr}:{port}".format(addr=match_connect_full.group('address'), port=match_connect_full.group('port'))
				self.__current_server = Server(sname, match_connect_full.group('address'), match_connect_full.group('port'), match_connect_full.group('password'))
				
				try:
					echo(self.__current_server.connect(), '({name}) '.format(name=self.__current_server.Name))
				except ServerException as se:
					echo('Connection failed: {err}'.format(err=ex))
					self.__current_server = None
			elif self.__current_server is not None:
				echo(self.__current_server.rcon(cmd_input), '({name}) '.format(name=self.__current_server.Name))
			else:
				echo('Error: Not connected to a server')
		
		for s in self.__server_list:
			s.disconnect()
		echo('Goodbye~')
	
	def newConfig(self):
		echo('Writing new Server Config.')
		go_main = True
		yaml_text = ''
		
		while go_main:
			## TODO: defaults
			ho = ''
			po = 0
			na = ''
			
			go_na = True
			while go_na:
				na = prompt('Short name (used to connect): ')
				if len(na) == 0:
					echo('Short name cannot be blank.')
				elif [s for s in self.__server_list if s.Name == na]:
					echo('Name already in use.  Try again.')
				elif na.find(' ') > -1 or na.find("\t") > -1:
					## TODO: make this a bit more strict
					echo('Name cannot contain spaces.  Try again.')
				else:
					go_na = False
			
			go_ho = True
			while go_ho:
				ho = prompt('Hostname: ')
				if len(ho) == 0:
					echo('Field cannot be blank.')
				else:
					go_ho = False
			
			go_po = True
			while go_po:
				po = prompt('Port: ')
				if re.match(re_number_check, po) == None:
					echo('Invalid port. Must be a number.')
				else:
					go_po = False
					
			pa = prompt('Password [Blank for ask on connect]: ')
			
			self.__server_list.append(Server(na, ho, po, pa))
			
			go_another = True
			while go_another:
				another = prompt('Add another? [Y/n] ').lower()
				if another == 'y' or another == '':
					go_another = False
				elif another == 'n':
					go_another = False
					go_main = False
		
		f = open('servers.yaml', 'w')
		f.write("# Configured Servers\n---\n")
		for s in self.__server_list:
			f.write(s.yaml())
		f.close

if __name__ == '__main__':
	client = RconClient()
	client.run()