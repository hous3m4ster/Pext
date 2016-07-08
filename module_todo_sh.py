#!/usr/bin/env python3

# This file is part of Pext
#
# Pext is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from os.path import expanduser
from subprocess import call, check_output, Popen, PIPE
from shlex import quote

from PyQt5.QtWidgets import QMessageBox
import pexpect

from module_base import ModuleBase


class Module(ModuleBase):
    def __init__(self, binary, vm, window, q):
        self.binary = "todo.sh" if (binary is None) else binary

        self.vm = vm
        self.window = window

    def stop(self):
        self.notifier.stop()

    def getDataLocation(self):
        return expanduser("~") + "/.todo/todo.txt"

    def call(self, command, returnOutput=False):
        if returnOutput:
            return check_output([self.binary] + command).decode("utf-8")
        else:
            call([self.binary] + command)

    def getSupportedCommands(self):
        return ["add", "addto", "append", "archive", "deduplicate", "rm", "depri", "do", "mv", "prepend", "pri", "replace"]

    def getCommands(self):
        commandsText = []

        commandsStarted = False

        # We will crash here if todo.sh is not installed.
        # TODO: Find a nice way to notify the user they need to install todo.sh
        commandText = self.call(["-h"], returnOutput=True)

        for line in commandText.splitlines():
            strippedLine = line.lstrip()
            if not commandsStarted:
                if strippedLine.startswith("Actions:"):
                    commandsStarted = True

                continue
            else:
                if strippedLine == '':
                    break

                lineData = strippedLine.split(" ")
                for variation in lineData[0].split("|"):
                    if variation in self.getSupportedCommands():
                        commandsText.append(variation + " " + " ".join(lineData[1:]))

        return commandsText

    def getEntries(self):
        entryList = []

        commandOutput = self.vm.ANSIEscapeRegex.sub('', self.call(["ls"], returnOutput=True)).splitlines()

        for line in commandOutput:
            if line == '--':
                break

            entryList.append(line)

        return entryList

    def copyEntryToClipboard(self, entryName):
        proc = Popen(["xclip", "-selection", "clipboard"], stdin=PIPE)
        proc.communicate(entryName.encode("ascii"))

    def getAllEntryFields(self, entryName):
        return ['']

    def runCommand(self, command, printOnSuccess=False, hideErrors=False):
        sanitizedCommandList = []
        for commandPart in command:
            sanitizedCommandList.append(quote(commandPart))

        proc = pexpect.spawn('/bin/sh', ['-c', self.binary + " " + " ".join(sanitizedCommandList) + (" 2>/dev/null" if hideErrors else "")])
        while True:
            result = proc.expect_exact([pexpect.EOF, pexpect.TIMEOUT, "(y/n)"], timeout=3)
            if result == 0:
                exitCode = proc.sendline("echo $?")
                break
            elif result == 1 and proc.before:
                self.vm.addError("Timeout error while running '{}'. This specific way of calling the command is most likely not supported yet by Pext.".format(" ".join(command)))
                self.vm.addError("Command output: {}".format(self.vm.ANSIEscapeRegex.sub('', proc.before.decode("utf-8"))))

                return None
            else:
                proc.setecho(False)
                answer = QMessageBox.question(self.window, "Pext", proc.before.decode("utf-8"), QMessageBox.Yes | QMessageBox.No)
                proc.waitnoecho()
                proc.sendline('y' if (answer == QMessageBox.Yes) else 'n')
                proc.setecho(True)

        proc.close()
        exitCode = proc.exitstatus

        message = self.vm.ANSIEscapeRegex.sub('', proc.before.decode("utf-8")) if proc.before else ""

        if exitCode == 0:
            if printOnSuccess and message:
                self.vm.addMessage(message)

            self.vm.entryList = self.getEntries()

            return message
        else:
            self.vm.addError(message if message else "Error code {} running '{}'. More info may be logged to the console".format(str(exitCode), " ".join(command)))

            return None
