from cmd2 import Cmd
import argparse
from ebaws.core import Core


class App(Cmd):
    """EnigmaBridge AWS command line interface"""
    prompt = '$> '
    intro = '-'*80 + '\n    Enigma Bridge AWS command line interface. ' \
                     '\n    For help, type ?\n' + \
            '-'*80

    def do_dump_config(self, line):
        """Dumps the current configuration to the terminal"""
        config = Core.read_configuration()
        print(config.to_string())

    def do_init(self, line):
        """Initializes the EB client machine, new identity is assigned."""
        print "Going to initialize the EB identity"
        print "WARNING! This is a destructive process!"
        var = raw_input("Do you really want to proceed? (Y/n): ").strip()
        if var != 'Y':
            return

        config = Core.read_configuration()
        if config.has_nonempty_config():
            print "WARNING! Configuration already exists in the file %s \n" % (Core.get_config_file_path())
            print "The configuration will be overwritten by a new one (current config will be backed up)"
            var = raw_input("Do you really want to proceed? (Y/n): ").strip()
            if var != 'Y':
                return

            # Backup the old config
            fname = Core.backup_configuration(config)
            print "\nConfiguration has been backed up: %s" % fname

        # Reinit...
        # TODO:

    def do_EOF(self, line):
        return True


if __name__ == '__main__':
    App().cmdloop()
