from cmd2 import Cmd
import argparse


class App(Cmd):
    """EnigmaBridge AWS command line interface"""
    prompt = '$> '
    intro = '-'*80 + '\n    Enigma Bridge AWS command line interface. ' \
                     '\n    For help, type ?\n' + \
            '-'*80

    def do_init(self, line):
        """Initializes the EB client machine, new identity is assigned."""
        print "Going to initialize the EB identity"
        print "WARNING! This is a destructive process!"
        var = raw_input("Do you really want to proceed? (Y/n): ").strip()
        if var != 'Y':
            return

        print "OK..."

    def do_EOF(self, line):
        return True


if __name__ == '__main__':
    App().cmdloop()
