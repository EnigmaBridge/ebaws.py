from cmd2 import Cmd
import argparse


class App(Cmd):
    """EnigmaBridge AWS command line interface"""
    pass

    def do_init(self, line):
        """Initializes the EB client machine, new identity is assigned."""
        print "Going to initialize"

    def do_EOF(self, line):
        return True


if __name__ == '__main__':
    App().cmdloop()
