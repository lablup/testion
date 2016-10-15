# A dummy self-test file.

import unittest
import sys

if __name__ == '__main__':
    if sys.argv[1] == 'test':
        sys.argv = [sys.argv[0], *sys.argv[2:]]
    if sys.argv[1] == '--noinput':
        sys.argv = [sys.argv[0], *sys.argv[2:]]
    unittest.main()
