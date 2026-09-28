"""Network-blocked runtime tests; no source-environment deployment scripts."""
import os
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

os.environ.update(OCI_GATEWAY_KEY='a' * 64, OCI_REGION='eu-frankfurt-1',
                  OCI_COMPARTMENT_ID='offline-test', LITELLM_LOCAL_MODEL_COST_MAP='True',
                  DO_NOT_TRACK='1')
sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == '__main__':
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network prohibited')), \
         patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('Network prohibited')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS prohibited')):
        suite = unittest.defaultTestLoader.loadTestsFromNames([
            'test_gateway', 'test_litellm', 'test_native', 'test_all_models'])
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
