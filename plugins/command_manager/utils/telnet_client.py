#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Telnet client utility for Command Manager plugin
Python 3.13+ compatible (telnetlib was removed)
"""

import time
import re
import socket
import select
from loguru import logger


class TelnetClient:
    """Client for connecting to network devices via Telnet"""
    
    def __init__(self, host, username, password, enable_password="", port=23, timeout=10):
        """Initialize the Telnet client"""
        self.host = host
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.port = port
        self.timeout = timeout
        
        self.sock = None
        self.connected = False
        self.prompt = None
        self._buffer = b""
        
    def connect(self):
        """Connect to the device"""
        try:
            # Create socket connection
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            
            # Wait for login prompt
            index, match, output = self.expect([
                b"[Uu]sername[: ]*", 
                b"[Ll]ogin[: ]*"
            ], timeout=self.timeout)
            
            if index < 0:
                raise Exception("Login prompt not found")
                
            # Send username
            self.write(f"{self.username}\n".encode())
            
            # Wait for password prompt
            index, match, output = self.expect([
                b"[Pp]assword[: ]*"
            ], timeout=self.timeout)
            
            if index < 0:
                raise Exception("Password prompt not found")
                
            # Send password
            self.write(f"{self.password}\n".encode())
            
            # Wait for command prompt
            time.sleep(2)
            output = self.read_very_eager().decode("utf-8", errors="ignore")
            
            # Try to detect prompt
            self.prompt = self._detect_prompt(output)
            
            if not self.prompt:
                raise Exception("Command prompt not found")
                
            self.connected = True
            return True
            
        except Exception as e:
            logger.error(f"Telnet connection error: {e}")
            self.disconnect()
            raise Exception(f"Failed to connect to {self.host}: {str(e)}")
            
    def disconnect(self):
        """Disconnect from the device"""
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
            
        self.connected = False
        self._buffer = b""
        
    def write(self, data):
        """Write data to the socket"""
        if not self.sock:
            raise Exception("Not connected")
        self.sock.sendall(data)
        
    def read_very_eager(self):
        """Read all available data without blocking"""
        if not self.sock:
            return b""
            
        data = b""
        try:
            # Check if data is available
            ready, _, _ = select.select([self.sock], [], [], 0)
            if ready:
                # Read available data
                chunk = self.sock.recv(4096)
                if chunk:
                    data = chunk
                    self._buffer += data
        except (socket.error, OSError):
            pass
            
        return data
        
    def expect(self, patterns, timeout=None):
        """Wait for one of the patterns to match"""
        if timeout is None:
            timeout = self.timeout
            
        start_time = time.time()
        buffer = self._buffer
        
        while time.time() - start_time < timeout:
            # Check if any pattern matches
            for i, pattern in enumerate(patterns):
                match = re.search(pattern, buffer)
                if match:
                    self._buffer = buffer[match.end():]
                    return (i, match, buffer[:match.end()])
                    
            # Read more data
            try:
                ready, _, _ = select.select([self.sock], [], [], 0.1)
                if ready:
                    chunk = self.sock.recv(4096)
                    if chunk:
                        buffer += chunk
                    else:
                        # Connection closed
                        break
            except (socket.error, OSError, socket.timeout):
                break
                
        # Timeout or connection closed
        self._buffer = buffer
        return (-1, None, buffer)
        
    def enable(self):
        """Enter enable mode"""
        if not self.connected:
            raise Exception("Not connected")
            
        if not self.enable_password:
            return
            
        # Send enable command
        self.write(b"enable\n")
        time.sleep(0.5)
        
        # Check for password prompt
        output = self.read_very_eager().decode("utf-8", errors="ignore")
        if re.search(r"[Pp]assword", output):
            # Send enable password
            self.write(f"{self.enable_password}\n".encode())
            time.sleep(1)
            
            # Read output again
            output = self.read_very_eager().decode("utf-8", errors="ignore")
            
            # Try to detect new prompt
            new_prompt = self._detect_prompt(output)
            if new_prompt:
                self.prompt = new_prompt
                
    def execute(self, command):
        """Execute a command and return the output"""
        if not self.connected:
            raise Exception("Not connected")
            
        # Clear buffer
        self.read_very_eager()
        
        # Send command
        self.write(f"{command}\n".encode())
        
        # Wait for command to complete
        time.sleep(1)
        
        # Collect output until prompt is seen or timeout
        output = ""
        start_time = time.time()
        max_pagination_iterations = 1000  # Prevent infinite loops
        pagination_count = 0
        
        while time.time() - start_time < self.timeout:
            # Read available output
            try:
                new_output = self.read_very_eager().decode("utf-8", errors="ignore")
                output += new_output
                
                # Check for pagination prompts (--More--, --more--, etc.) in the most recent output
                # Pagination typically appears at the end of output chunks
                if new_output and re.search(r"--\s*[Mm]ore\s*--", new_output, re.IGNORECASE):
                    # Remove the pagination prompt from output
                    output = re.sub(r"--\s*[Mm]ore\s*--[\r\n]*", "", output)
                    # Send space to continue
                    self.write(b" ")
                    time.sleep(0.3)
                    pagination_count += 1
                    
                    # Safety check to prevent infinite loops
                    if pagination_count > max_pagination_iterations:
                        logger.warning("Maximum pagination iterations reached, stopping")
                        break
                    
                    # Continue reading
                    continue
                
                # Check if we've reached the prompt (but not if it's part of pagination)
                if self.prompt and re.search(re.escape(self.prompt), output):
                    # Make sure the prompt is at the end, not in the middle
                    prompt_match = re.search(re.escape(self.prompt) + r"\s*$", output, re.MULTILINE)
                    if prompt_match:
                        break
                    
                # If no new output and we don't see the prompt, try reading more
                if not new_output:
                    time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error reading Telnet output: {e}")
                break
                
        # Remove command echo and prompt from output
        output = self._clean_output(output, command)
        
        # Final cleanup: remove any remaining pagination prompts (shouldn't be needed, but just in case)
        output = re.sub(r"--\s*[Mm]ore\s*--[\r\n]*", "", output)
        
        return output
        
    def _detect_prompt(self, output):
        """Try to detect the command prompt"""
        if not output:
            return None
            
        # Look for common prompt patterns
        prompt_patterns = [
            r"[\r\n]([A-Za-z0-9_\-\.\(\)\/]+[#>])\s*$",  # Common Cisco-like prompts
            r"[\r\n]([A-Za-z0-9_\-\.]+[@][A-Za-z0-9_\-\.]+[#$%])\s*$"  # Linux-like prompts
        ]
        
        for pattern in prompt_patterns:
            match = re.search(pattern, output)
            if match:
                return match.group(1)
                
        # If no pattern matches, use last non-empty line
        lines = output.splitlines()
        for line in reversed(lines):
            line = line.strip()
            if line:
                # Use up to 20 chars of the last line as prompt
                return line[-20:] if len(line) > 20 else line
                
        return None
        
    def _clean_output(self, output, command):
        """Clean up command output by removing echoed command, prompt, and control characters"""
        # First, handle backspace sequences (backspace deletes previous character)
        # This handles cases where devices use backspace for formatting
        # Process backspaces from left to right
        result = []
        for char in output:
            if char == '\b':
                # Backspace: remove last character if any
                if result:
                    result.pop()
            else:
                result.append(char)
        output = ''.join(result)
        
        # Remove ANSI escape sequences (color codes, cursor movement, etc.)
        # Pattern: ESC [ followed by parameters and a command character
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        output = ansi_escape.sub('', output)
        
        # Remove other common control characters (but keep \r, \n, \t)
        # Control characters: 0x00-0x1F except \r (0x0D), \n (0x0A), \t (0x09)
        control_chars = re.compile(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]')
        output = control_chars.sub('', output)
        
        # Remove the echoed command
        output = re.sub(re.escape(command) + r"[\r\n]+", "", output, count=1)
        
        # Remove the prompt at the end
        if self.prompt:
            output = re.sub(re.escape(self.prompt) + r"\s*$", "", output)
            
        # Clean up multiple spaces (but preserve intentional spacing)
        output = re.sub(r'[ \t]+', ' ', output)  # Multiple spaces/tabs to single space
        output = re.sub(r' *\n *', '\n', output)  # Clean up spaces around newlines
        
        # Strip extra whitespace
        output = output.strip()
        
        return output 